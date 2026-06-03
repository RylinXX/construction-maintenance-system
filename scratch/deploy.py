import tarfile
import os
import paramiko
from pathlib import Path

# Config
PROJECT_ROOT = Path(r"c:\Users\scodi.KYLINX\Desktop\construction-maintenance-system")
TAR_PATH = PROJECT_ROOT / "cam.tar.gz"
ZIP_CERT_PATH = Path(r"C:\Users\RM\Downloads\pam.rlxtc.com_nginx.zip")

REMOTE_IP = "192.144.171.234"
REMOTE_PORT = 22
REMOTE_USER = "root"
REMOTE_PASS = "xll,13436576966"

def make_tarfile(output_filename, source_dir):
    print(f"Creating archive {output_filename}...")
    exclude_dirs = {'.git', '.venv', '.pytest_cache', '__pycache__', '.superpowers', 'dist', 'CAM.egg-info'}
    exclude_files = {'cam.tar.gz'}
    
    with tarfile.open(output_filename, "w:gz") as tar:
        for root, dirs, files in os.walk(source_dir):
            # Prune directories in-place
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if file in exclude_files:
                    continue
                file_path = Path(root) / file
                rel_path = file_path.relative_to(source_dir)
                tar.add(file_path, arcname=str(rel_path))
    print("Archive created successfully!")

def run_remote_command(ssh_client, cmd):
    print(f"Running: {cmd}")
    stdin, stdout, stderr = ssh_client.exec_command(cmd)
    
    # Wait for completion
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8').strip()
    err = stderr.read().decode('utf-8').strip()
    
    if out:
        print("OUT:", out)
    if err:
        print("ERR:", err)
        
    return exit_status, out, err

def deploy():
    # 1. Compress
    make_tarfile(str(TAR_PATH), str(PROJECT_ROOT))
    
    # 2. Upload via SFTP
    print("Connecting to remote server via SSH...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(REMOTE_IP, port=REMOTE_PORT, username=REMOTE_USER, password=REMOTE_PASS, timeout=30)
    print("Connected successfully!")
    
    sftp = ssh.open_sftp()
    
    print(f"Uploading deployment archive to /root/cam.tar.gz...")
    sftp.put(str(TAR_PATH), "/root/cam.tar.gz")
    
    if ZIP_CERT_PATH.exists():
        print(f"Uploading Nginx certificates to /root/pam.rlxtc.com_nginx.zip...")
        sftp.put(str(ZIP_CERT_PATH), "/root/pam.rlxtc.com_nginx.zip")
    else:
        print(f"Skipping Nginx certificate upload as certificate file does not exist: {ZIP_CERT_PATH}")
    
    sftp.close()
    print("Files uploaded successfully via SFTP!")
    
    # 3. Server-side setup
    # Clear and extract
    run_remote_command(ssh, "rm -rf /root/cam && mkdir -p /root/cam")
    run_remote_command(ssh, "tar -xzf /root/cam.tar.gz -C /root/cam")
    
    # Set up virtual environment & install requirements
    run_remote_command(ssh, "python3 -m venv /root/cam/.venv")
    run_remote_command(ssh, "/root/cam/.venv/bin/pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple")
    run_remote_command(ssh, "/root/cam/.venv/bin/pip install -e /root/cam -i https://pypi.tuna.tsinghua.edu.cn/simple")
    run_remote_command(ssh, "/root/cam/.venv/bin/pip install gunicorn -i https://pypi.tuna.tsinghua.edu.cn/simple")
    
    # Install unzip and deploy SSL
    if ZIP_CERT_PATH.exists():
        run_remote_command(ssh, "dnf install -y unzip || yum install -y unzip")
        run_remote_command(ssh, "rm -rf /tmp/nginx_cert && mkdir -p /tmp/nginx_cert")
        run_remote_command(ssh, "unzip -o /root/pam.rlxtc.com_nginx.zip -d /tmp/nginx_cert")
        
        run_remote_command(ssh, "mkdir -p /etc/nginx/ssl/pam.rlxtc.com")
        run_remote_command(ssh, "find /tmp/nginx_cert -name '*.crt' -exec cp {} /etc/nginx/ssl/pam.rlxtc.com/ \;")
        run_remote_command(ssh, "find /tmp/nginx_cert -name '*.pem' -exec cp {} /etc/nginx/ssl/pam.rlxtc.com/ \;")
        run_remote_command(ssh, "find /tmp/nginx_cert -name '*.key' -exec cp {} /etc/nginx/ssl/pam.rlxtc.com/ \;")
        run_remote_command(ssh, "ls -la /etc/nginx/ssl/pam.rlxtc.com")
    else:
        print("Skipping Nginx certificate deployment as ZIP_CERT_PATH does not exist.")
    
    # 4. Configure Nginx
    nginx_conf = """server {
    listen 80;
    server_name pam.rlxtc.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name pam.rlxtc.com;

    ssl_certificate /etc/nginx/ssl/pam.rlxtc.com/pam.rlxtc.com_bundle.crt;
    ssl_certificate_key /etc/nginx/ssl/pam.rlxtc.com/pam.rlxtc.com.key;

    ssl_session_timeout 5m;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:HIGH:!aNULL:!MD5:!RC4:!DHE;
    ssl_prefer_server_ciphers on;

    client_max_body_size 50M;

    # Direct serving of static files
    location /static/ {
        alias /root/cam/construction_maintenance/static/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    # Proxy requests to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}"""
    
    # Write Nginx configuration
    print("Writing Nginx configuration...")
    run_remote_command(ssh, "mkdir -p /etc/nginx/conf.d")
    sftp = ssh.open_sftp()
    with sftp.open("/etc/nginx/conf.d/cam.conf", "w") as f:
        f.write(nginx_conf)
    sftp.close()
    
    # 5. Configure systemd Service
    systemd_conf = """[Unit]
Description=Construction Maintenance System Flask App
After=network.target

[Service]
User=root
WorkingDirectory=/root/cam
Environment="PATH=/root/cam/.venv/bin"
ExecStart=/root/cam/.venv/bin/gunicorn --workers 4 --bind 127.0.0.1:8000 "construction_maintenance.app:create_app()"
Restart=always

[Install]
WantedBy=multi-user.target"""
    
    print("Writing systemd service file...")
    sftp = ssh.open_sftp()
    with sftp.open("/etc/systemd/system/cam.service", "w") as f:
        f.write(systemd_conf)
    sftp.close()
    
    # Reload and start services
    run_remote_command(ssh, "systemctl daemon-reload")
    run_remote_command(ssh, "systemctl enable cam.service")
    run_remote_command(ssh, "systemctl restart cam.service")
    
    # Verify Gunicorn is running
    run_remote_command(ssh, "systemctl status cam.service")
    
    # Verify Nginx config and restart Nginx
    status_code, _, _ = run_remote_command(ssh, "nginx -t")
    if status_code == 0:
        print("Nginx configuration is valid, reloading Nginx...")
        run_remote_command(ssh, "systemctl restart nginx")
        run_remote_command(ssh, "systemctl status nginx")
    else:
        print("ERROR: Nginx configuration check failed!")
        
    ssh.close()
    print("\n=== DEPLOYMENT COMPLETED! ===")

if __name__ == "__main__":
    deploy()

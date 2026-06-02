import paramiko

hostname = "192.144.171.234"
username = "root"
password = "xll,13436576966"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Connecting to {hostname}...")
    client.connect(hostname, port=22, username=username, password=password, timeout=10)
    print("Connected successfully!")
    
    commands = {
        "OS details": "uname -a; cat /etc/os-release",
        "Python version": "python3 --version || python --version",
        "Nginx status": "nginx -v",
        "Systemctl status": "systemctl --version",
        "Pip version": "pip3 --version || pip --version"
    }
    
    for name, cmd in commands.items():
        print(f"\n--- {name} ({cmd}) ---")
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode('utf-8').strip()
        err = stderr.read().decode('utf-8').strip()
        if out:
            print("OUT:", out)
        if err:
            print("ERR:", err)
            
except Exception as e:
    print("Error:", e)
finally:
    client.close()

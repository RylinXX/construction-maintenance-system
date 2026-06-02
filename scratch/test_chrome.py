import subprocess
import time
import os

def main():
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    print("Launching Chrome headlessly and capturing output...")
    p = subprocess.Popen([
        chrome_path,
        "--headless=new",
        "--disable-gpu",
        "--enable-logging",
        "--v=1",
        "http://127.0.0.1:5000/projects/1/vouchers"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        stdout, stderr = p.communicate(timeout=6)
    except subprocess.TimeoutExpired:
        p.terminate()
        stdout, stderr = p.communicate()

    print("\n--- STDOUT ---")
    print(stdout.decode("utf-8", errors="ignore"))
    print("\n--- STDERR ---")
    # Filter console or errors
    err_lines = stderr.decode("utf-8", errors="ignore").splitlines()
    for line in err_lines:
        if "CONSOLE" in line or "error" in line.lower() or "exception" in line.lower() or "fail" in line.lower():
            print(line)

if __name__ == "__main__":
    main()

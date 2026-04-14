
import os
import time
import subprocess

def run_debug():
    # Set env for sandbox
    os.environ["XBOT_SANDBOX_BUILD_FEATURES"] = "full"
    os.environ["XBOT_SKIP_INTRO"] = "1"
    
    print("Launching game for debug logs (Skipping Intro)...")
    # Launch game (assuming it's python main.py in root or src/app.py)
    cmd = ["python", "src/app.py"]
    
    process = subprocess.Popen(cmd, cwd="C:/xampp/htdocs/king-wizard/")
    
    # Wait for 30 seconds to collect logs
    time.sleep(30)
    
    print("Terminating game...")
    process.terminate()
    try:
        process.wait(timeout=5)
    except:
        process.kill()

if __name__ == "__main__":
    run_debug()

import os
import subprocess
import time

# Path to your repository
REPO_PATH = os.path.expanduser("~/ai-employee")
INTERVAL = 600 # 10 minutes

def run_git_sync():
    try:
        os.chdir(REPO_PATH)
        # 1. Pull changes
        subprocess.run(["git", "pull", "origin", "main"], check=True)
        # 2. Check for local changes
        status = subprocess.check_output(["git", "status", "--porcelain"]).decode("utf-8")
        if status:
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "Auto-sync: updates"], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)
            print("Sync Done!")
        else:
            print("Nothing to sync.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    while True:
        run_git_sync()
        time.sleep(INTERVAL)

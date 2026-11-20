import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import subprocess
import time

def main():
    print("🚀 Launching Kairos & Chrona via dedicated subprocesses...")
    p1 = subprocess.Popen([sys.executable, "kairos_bot.py"], cwd=str(Path(__file__).resolve().parent))
    p2 = subprocess.Popen([sys.executable, "chrona_bot.py"], cwd=str(Path(__file__).resolve().parent))
    
    try:
        while True:
            time.sleep(2)
            if p1.poll() is not None:
                print("Restarting Kairos...")
                p1 = subprocess.Popen([sys.executable, "kairos_bot.py"], cwd=str(Path(__file__).resolve().parent))
            if p2.poll() is not None:
                print("Restarting Chrona...")
                p2 = subprocess.Popen([sys.executable, "chrona_bot.py"], cwd=str(Path(__file__).resolve().parent))
    except KeyboardInterrupt:
        p1.terminate()
        p2.terminate()

if __name__ == "__main__":
    main()

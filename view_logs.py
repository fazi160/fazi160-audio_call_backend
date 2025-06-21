#!/usr/bin/env python3
"""
Simple script to view WebAuthn logs in real-time
Usage: python view_logs.py [log_file]
"""

import sys
import os
import time
from pathlib import Path

def tail_log(log_file, lines=50):
    """Tail a log file and show the last N lines"""
    if not os.path.exists(log_file):
        print(f"Log file not found: {log_file}")
        return
    
    with open(log_file, 'r', encoding='utf-8') as f:
        # Read all lines and get the last N
        all_lines = f.readlines()
        last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        print(f"\n=== Last {len(last_lines)} lines from {log_file} ===\n")
        for line in last_lines:
            print(line.rstrip())

def monitor_log(log_file):
    """Monitor a log file in real-time"""
    if not os.path.exists(log_file):
        print(f"Log file not found: {log_file}")
        return
    
    print(f"Monitoring {log_file}... Press Ctrl+C to stop")
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            # Go to end of file
            f.seek(0, 2)
            
            while True:
                line = f.readline()
                if line:
                    print(line.rstrip())
                else:
                    time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopped monitoring")

if __name__ == "__main__":
    # Default to webauthn.log
    log_file = sys.argv[1] if len(sys.argv) > 1 else "logs/webauthn.log"
    
    if not os.path.exists(log_file):
        print(f"Log file not found: {log_file}")
        print("Available log files:")
        logs_dir = Path("logs")
        if logs_dir.exists():
            for log in logs_dir.glob("*.log"):
                print(f"  - {log}")
        sys.exit(1)
    
    # Show last 50 lines and then monitor
    tail_log(log_file, 50)
    print("\n" + "="*80 + "\n")
    monitor_log(log_file) 
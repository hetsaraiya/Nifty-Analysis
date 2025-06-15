#!/usr/bin/env python3
"""
Log Monitor for NIFTY Options Analysis
Monitor log files in real-time and show important events
"""

import os
import time
import subprocess
from pathlib import Path

def monitor_logs():
    """Monitor log files and display important events"""
    logs_dir = Path("logs")
    
    # Create logs directory if it doesn't exist
    logs_dir.mkdir(exist_ok=True)
    
    log_files = [
        "fastapi_app.log",
        "greeks_calculator.log",
        "angel_one_api.log",
        "error.log"
    ]
    
    # Check which log files exist
    existing_logs = []
    for log_file in log_files:
        log_path = logs_dir / log_file
        if log_path.exists():
            existing_logs.append(str(log_path))
    
    if not existing_logs:
        print("No log files found. Start the application first.")
        return
    
    print("="*60)
    print("NIFTY OPTIONS ANALYSIS - LOG MONITOR")
    print("="*60)
    print(f"Monitoring {len(existing_logs)} log files:")
    for log_file in existing_logs:
        print(f"  - {log_file}")
    print("="*60)
    print("Press Ctrl+C to stop monitoring")
    print("="*60)
    
    try:
        # Use tail to follow all log files
        cmd = ["tail", "-f"] + existing_logs
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nLog monitoring stopped.")
    except FileNotFoundError:
        print("Error: 'tail' command not found. Trying alternative...")
        
        # Alternative method for systems without tail
        try:
            import threading
            
            def follow_file(filepath):
                with open(filepath, 'r') as f:
                    # Go to end of file
                    f.seek(0, 2)
                    while True:
                        line = f.readline()
                        if line:
                            print(f"[{os.path.basename(filepath)}] {line.rstrip()}")
                        else:
                            time.sleep(0.1)
            
            threads = []
            for log_file in existing_logs:
                thread = threading.Thread(target=follow_file, args=(log_file,))
                thread.daemon = True
                thread.start()
                threads.append(thread)
            
            # Keep main thread alive
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\nLog monitoring stopped.")

def show_log_summary():
    """Show a summary of recent log entries"""
    logs_dir = Path("logs")
    
    if not logs_dir.exists():
        print("No logs directory found.")
        return
    
    print("="*60)
    print("LOG SUMMARY - LAST 20 LINES FROM EACH FILE")
    print("="*60)
    
    for log_file in logs_dir.glob("*.log"):
        print(f"\n--- {log_file.name} ---")
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                # Show last 20 lines
                for line in lines[-20:]:
                    print(line.rstrip())
        except Exception as e:
            print(f"Error reading {log_file}: {e}")

def clear_logs():
    """Clear all log files"""
    logs_dir = Path("logs")
    
    if not logs_dir.exists():
        print("No logs directory found.")
        return
    
    log_files = list(logs_dir.glob("*.log"))
    
    if not log_files:
        print("No log files found.")
        return
    
    print(f"Found {len(log_files)} log files:")
    for log_file in log_files:
        print(f"  - {log_file.name}")
    
    confirm = input("\nClear all log files? (y/N): ").strip().lower()
    
    if confirm in ['y', 'yes']:
        for log_file in log_files:
            try:
                log_file.unlink()
                print(f"Cleared: {log_file.name}")
            except Exception as e:
                print(f"Error clearing {log_file.name}: {e}")
        print("Log files cleared.")
    else:
        print("Operation cancelled.")

def main():
    """Main menu for log monitoring"""
    print("NIFTY Options Analysis - Log Monitor")
    print("="*40)
    print("1. Monitor logs in real-time")
    print("2. Show log summary")
    print("3. Clear log files")
    print("4. Exit")
    print("="*40)
    
    choice = input("Choose an option (1-4): ").strip()
    
    if choice == '1':
        monitor_logs()
    elif choice == '2':
        show_log_summary()
    elif choice == '3':
        clear_logs()
    elif choice == '4':
        print("Goodbye!")
    else:
        print("Invalid choice. Please try again.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")

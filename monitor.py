import subprocess
import time
import os
import sys

def monitor_streamlit_logs():
    print("Starting Streamlit log monitor...")
    
    # Find the Streamlit log file
    find_cmd = subprocess.Popen(["find", ".", "-name", "streamlit-*.log"], 
                                stdout=subprocess.PIPE)
    log_files = find_cmd.stdout.read().decode().strip().split('\n')
    
    if not log_files or not log_files[0]:
        print("No Streamlit log files found.")
        return
    
    log_file = log_files[0]
    print(f"Monitoring log file: {log_file}")
    
    # Run tail -f to monitor the log
    tail_process = subprocess.Popen(["tail", "-f", log_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    try:
        print("Log output (press Ctrl+C to stop):")
        print("-" * 80)
        
        while True:
            line = tail_process.stdout.readline().decode()
            if not line:
                break
                
            # Check for debugging messages or errors
            if "DEBUG:" in line or "Error" in line or "Exception" in line:
                print(line.strip())
            
            # Check for worker thread messages
            if "thread" in line.lower() or "queue" in line.lower():
                print(line.strip())
                
            # Check for API related messages
            if "API:" in line:
                print(line.strip())
                
    except KeyboardInterrupt:
        print("\nStopping log monitor...")
    finally:
        tail_process.terminate()
        
if __name__ == "__main__":
    monitor_streamlit_logs() 
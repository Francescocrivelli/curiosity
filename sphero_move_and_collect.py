#!/usr/bin/env python3
"""
Sphero Data Collection Script with Video Recording

This script launches unlimited_move.py in a separate process to control the Sphero's movement
while recording video from a USB camera. The script does not interfere with the
Sphero control at all, preserving the original unlimited_move.py functionality.
"""

import os
import time
import signal
import datetime
import threading
import subprocess
import csv
import cv2
import json
import sys

# Camera settings
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

# Data collection settings
DATA_DIR = "collected_data"
VIDEO_FILENAME = "video.mp4"
METADATA_FILENAME = "metadata.json"

# Global variables
running = True
start_timestamp = None

def signal_handler(sig, frame):
    """Handle Ctrl+C to gracefully stop data collection"""
    global running
    print("\nStopping data collection...")
    running = False

def ensure_data_dir():
    """Create a timestamped data directory if it doesn't exist"""
    global DATA_DIR
    
    # Add timestamp to data directory
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    DATA_DIR = os.path.join("collected_data", f"run_{timestamp}")
    
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
    
    return DATA_DIR

def camera_recording_thread():
    """Thread to record video from camera"""
    global running, start_timestamp, DATA_DIR
    
    print("Starting camera recording thread...")
    video_path = os.path.join(DATA_DIR, VIDEO_FILENAME)
    
    # Initialize the camera
    cap = cv2.VideoCapture(CAMERA_INDEX)
    
    # Check if camera opened successfully
    if not cap.isOpened():
        print("Error: Could not open camera")
        running = False
        return
    
    # Set camera properties
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
    
    # Get actual camera properties (might be different from requested)
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"Camera initialized with resolution: {actual_width}x{actual_height} @ {actual_fps}fps")
    
    # Create VideoWriter object
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # MP4 codec
    out = cv2.VideoWriter(video_path, fourcc, actual_fps, (actual_width, actual_height))
    
    if not out.isOpened():
        print("Error: Could not create video writer")
        cap.release()
        running = False
        return
    
    # Record frames until running is set to False
    frame_count = 0
    recording_start_time = time.time()
    if start_timestamp is None:
        start_timestamp = recording_start_time
    
    try:
        while running:
            ret, frame = cap.read()
            if not ret:
                print("Error: Could not read frame")
                # Try to recover
                time.sleep(0.1)
                continue
                
            # Add timestamp to the frame
            elapsed_time = time.time() - start_timestamp
            timestamp_str = f"Time: {elapsed_time:.2f}s"
            cv2.putText(frame, timestamp_str, (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
            # Write the frame to the video file
            out.write(frame)
            frame_count += 1
            
            # Print status periodically
            if frame_count % 300 == 0:
                current_time = time.time()
                elapsed = current_time - recording_start_time
                actual_fps = frame_count / elapsed if elapsed > 0 else 0
                print(f"Recording video: {frame_count} frames, {actual_fps:.1f} fps")
    
    except Exception as e:
        print(f"Error in camera recording: {e}")
    
    finally:
        # Release everything when done
        out.release()
        cap.release()
        print(f"Video recording stopped. Saved to {video_path}")
        print(f"Recorded {frame_count} frames")

def write_metadata():
    """Write metadata about the data collection session"""
    global DATA_DIR, start_timestamp
    
    metadata_path = os.path.join(DATA_DIR, METADATA_FILENAME)
    
    end_time = datetime.datetime.now()
    duration = None
    if start_timestamp:
        duration = time.time() - start_timestamp
    
    metadata = {
        "start_time": datetime.datetime.fromtimestamp(start_timestamp).isoformat() if start_timestamp else None,
        "end_time": end_time.isoformat(),
        "duration_seconds": duration,
        "camera": {
            "index": CAMERA_INDEX,
            "width": CAMERA_WIDTH,
            "height": CAMERA_HEIGHT,
            "fps": CAMERA_FPS
        },
        "notes": "This data collection only includes video. Gyroscope and accelerometer data collection requires instrumenting the Sphero SDK."
    }
    
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
        
    print(f"Metadata written to {metadata_path}")

def run_sphero_movement():
    """Launch unlimited_move.py as a subprocess"""
    print("Starting unlimited_move.py in a separate process...")
    try:
        # Launch unlimited_move.py as a separate process
        process = subprocess.Popen([sys.executable, "unlimited_move.py"], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.STDOUT,
                                   universal_newlines=True,
                                   bufsize=1)
        
        print("Sphero movement script started (PID: {})".format(process.pid))
        
        # Monitor the subprocess output
        for line in process.stdout:
            print(f"[Sphero] {line.strip()}")
            
        # Process completed
        return_code = process.wait()
        print(f"Sphero movement script exited with code {return_code}")
        
    except Exception as e:
        print(f"Error running unlimited_move.py: {e}")
    finally:
        # If we get here and the process is still running, terminate it
        if process and process.poll() is None:
            print("Terminating Sphero movement script...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

def main():
    """Main function to run unlimited_move.py and collect data"""
    global running, DATA_DIR
    
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Ensure data directory exists
    DATA_DIR = ensure_data_dir()
    print(f"Data will be saved to {DATA_DIR}")
    
    # Create note about data collection limitations
    note_path = os.path.join(DATA_DIR, "NOTE.txt")
    with open(note_path, 'w') as f:
        f.write("IMPORTANT: This data collection only includes video.\n")
        f.write("Direct sensor data collection (gyroscope/accelerometer) would require\n")
        f.write("modifying the Sphero SDK, which interferes with unlimited_move.py.\n")
        f.write("To collect sensor data, you would need to modify unlimited_move.py directly.\n")
    
    # Start camera recording thread
    camera_thread = threading.Thread(target=camera_recording_thread)
    camera_thread.daemon = True
    camera_thread.start()
    
    # Run unlimited_move.py in the main thread
    try:
        run_sphero_movement()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Signal threads to stop
        running = False
    
    # Wait for threads to finish
    print("Waiting for data collection to complete...")
    camera_thread.join(timeout=5)
    
    # Write metadata
    write_metadata()
    
    print("Data collection complete!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted by user")
        running = False
    finally:
        # Final cleanup
        if running:
            running = False
        print("Program terminated") 
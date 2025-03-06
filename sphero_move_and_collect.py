#!/usr/bin/env python3
"""
Sphero Data Collection Script with Video Recording

This script runs the unlimited_move.py module to control Sphero's movement
while simultaneously collecting gyroscope and accelerometer data at 30Hz
and recording video from a USB camera. The data and video are synchronized
for later use in training models.
"""

import os
import time
import signal
import datetime
import threading
import csv
import cv2
import numpy as np
import yaml
import json
import unlimited_move
from pysphero.core import Sphero
from pysphero.device_api.sensor import Accelerometer, Gyroscope

# Camera settings (from config)
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

# Data collection settings
SENSOR_FREQUENCY = 30  # Hz
DATA_DIR = "collected_data"
VIDEO_FILENAME = "video.mp4"
SENSOR_FILENAME = "sensor_data.csv"
METADATA_FILENAME = "metadata.json"

# Global variables
running = True
sphero_instance = None
data_lock = threading.Lock()
sensor_data = []
start_timestamp = None

def signal_handler(sig, frame):
    """Handle Ctrl+C to gracefully stop data collection and Sphero movement"""
    global running
    print("\nStopping data collection and Sphero movement...")
    running = False
    # Allow unlimited_move to handle its own cleanup
    unlimited_move.running = False

def ensure_data_dir():
    """Create a timestamped data directory if it doesn't exist"""
    global DATA_DIR
    
    # Add timestamp to data directory
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    DATA_DIR = os.path.join("collected_data", f"run_{timestamp}")
    
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
    
    return DATA_DIR

def sensor_callback(response):
    """Process sensor data received from Sphero"""
    global sensor_data, start_timestamp
    
    # Get current timestamp relative to start
    current_time = time.time()
    if start_timestamp is None:
        start_timestamp = current_time
    
    relative_timestamp = current_time - start_timestamp
    
    # Extract individual sensor values
    try:
        # Initialize variables with default values
        accel_x = accel_y = accel_z = 0.0
        gyro_x = gyro_y = gyro_z = 0.0
        
        # Extract values from the response dict
        for sensor_key, value in response.items():
            sensor_str = str(sensor_key)
            
            if "Accelerometer.x" in sensor_str:
                accel_x = value
            elif "Accelerometer.y" in sensor_str:
                accel_y = value
            elif "Accelerometer.z" in sensor_str:
                accel_z = value
            elif "Gyroscope.x" in sensor_str:
                gyro_x = value
            elif "Gyroscope.y" in sensor_str:
                gyro_y = value
            elif "Gyroscope.z" in sensor_str:
                gyro_z = value
                
        # Create data row
        data_row = [
            relative_timestamp,
            accel_x, accel_y, accel_z,
            gyro_x, gyro_y, gyro_z
        ]
        
        # Add to data list with thread-safe lock
        with data_lock:
            sensor_data.append(data_row)
            
    except Exception as e:
        print(f"Error processing sensor data: {e}")

def data_collection_thread():
    """Thread to collect sensor data from Sphero"""
    global running, sphero_instance
    
    print("Starting sensor data collection thread...")
    
    # Create Sphero instance for sensor collection only
    # Using a separate connection from unlimited_move.py
    try:
        # Using with statement for automatic cleanup
        with Sphero(mac_address=unlimited_move.MAC_ADDRESS) as sphero:
            sphero_instance = sphero
            
            # Wake up the Sphero
            print("Waking up Sphero for sensor collection...")
            sphero.power.wake()
            time.sleep(1)  # Give it time to wake up
            
            # Set up sensor streaming
            interval = int(1000 / SENSOR_FREQUENCY)  # Convert to milliseconds
            print(f"Setting up sensor streaming at {SENSOR_FREQUENCY}Hz...")
            
            sensor = sphero.sensor
            sensor.set_notify(
                sensor_callback,
                Accelerometer,
                Gyroscope,
                interval=interval,  # e.g., 33ms for ~30Hz
                count=0,            # Continuous streaming
                timeout=1.0
            )
            
            # Keep thread alive until running is set to False
            while running:
                time.sleep(0.1)
                
            # Clean up
            print("Stopping sensor streaming...")
            try:
                sensor.cancel_notify_sensors()
            except Exception as e:
                print(f"Error canceling sensor streaming: {e}")
                
    except Exception as e:
        print(f"Error in data collection thread: {e}")
        running = False  # Signal main thread to stop

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
                break
                
            # Write the frame to the video file
            out.write(frame)
            frame_count += 1
            
            # Print status periodically
            if frame_count % 100 == 0:
                current_time = time.time()
                elapsed = current_time - recording_start_time
                actual_fps = frame_count / elapsed if elapsed > 0 else 0
                print(f"Recording: {frame_count} frames, {actual_fps:.1f} fps")
    
    except Exception as e:
        print(f"Error in camera recording: {e}")
    
    finally:
        # Release everything when done
        out.release()
        cap.release()
        print(f"Video recording stopped. Saved to {video_path}")
        print(f"Recorded {frame_count} frames")

def write_sensor_data_to_csv():
    """Write collected sensor data to CSV file"""
    global sensor_data, DATA_DIR
    
    sensor_path = os.path.join(DATA_DIR, SENSOR_FILENAME)
    print(f"Writing sensor data to {sensor_path}...")
    
    with open(sensor_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write header
        writer.writerow([
            'timestamp',
            'accel_x', 'accel_y', 'accel_z',
            'gyro_x', 'gyro_y', 'gyro_z'
        ])
        
        # Write data
        for row in sensor_data:
            writer.writerow(row)
            
    print(f"Wrote {len(sensor_data)} sensor data points to CSV")

def write_metadata():
    """Write metadata about the data collection session"""
    global DATA_DIR, start_timestamp
    
    metadata_path = os.path.join(DATA_DIR, METADATA_FILENAME)
    
    metadata = {
        "start_time": datetime.datetime.fromtimestamp(start_timestamp).isoformat() if start_timestamp else None,
        "end_time": datetime.datetime.now().isoformat(),
        "sensor_frequency": SENSOR_FREQUENCY,
        "sensor_samples": len(sensor_data),
        "camera": {
            "index": CAMERA_INDEX,
            "width": CAMERA_WIDTH,
            "height": CAMERA_HEIGHT,
            "fps": CAMERA_FPS
        }
    }
    
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
        
    print(f"Metadata written to {metadata_path}")

def main():
    """Main function to run unlimited_move.py and collect data"""
    global running, DATA_DIR
    
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Ensure data directory exists
    DATA_DIR = ensure_data_dir()
    print(f"Data will be saved to {DATA_DIR}")
    
    # Start data collection thread
    data_thread = threading.Thread(target=data_collection_thread)
    data_thread.daemon = True
    data_thread.start()
    
    # Start camera recording thread
    camera_thread = threading.Thread(target=camera_recording_thread)
    camera_thread.daemon = True
    camera_thread.start()
    
    print("Starting Sphero movement...")
    
    # Run the original unlimited_move.py functionality in the main thread
    # The run_continuous_movement function will handle connections and keep
    # the Sphero moving until running is set to False
    try:
        unlimited_move.run_continuous_movement()
    except Exception as e:
        print(f"Error in unlimited_move: {e}")
        running = False
    
    # Wait for threads to finish
    print("Waiting for data collection to complete...")
    data_thread.join(timeout=5)
    camera_thread.join(timeout=5)
    
    # Write collected data to files
    write_sensor_data_to_csv()
    write_metadata()
    
    print("Data collection complete!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        # Make sure running is set to False to stop all threads
        running = False
        if sensor_data:
            write_sensor_data_to_csv()
            write_metadata()
        print("Program terminated") 
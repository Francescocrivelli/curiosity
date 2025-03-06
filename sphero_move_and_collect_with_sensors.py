#!/usr/bin/env python3
"""
Sphero Data Collection Script with Video Recording

This script alternates between moving the Sphero using movement commands from
unlimited_move.py's approach and collecting sensor data. It also records video
from a USB camera throughout the process.
"""

import os
import time
import signal
import datetime
import threading
import csv
import cv2
import json
import sys
import random
from pysphero.core import Sphero
from pysphero.driving import Direction
from pysphero.device_api.sensor import Accelerometer, Gyroscope

# Sphero MAC address - same as in unlimited_move.py
MAC_ADDRESS = "C9:B9:61:72:CB:78"

# Camera settings
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

# Data collection settings
SENSOR_FREQUENCY = 20  # Hz (lowered as requested)
SENSOR_INTERVAL = int(1000 / SENSOR_FREQUENCY)  # Convert to milliseconds for PySphero API
DATA_DIR = "collected_data"
VIDEO_FILENAME = "video.mp4"
SENSOR_FILENAME = "sensor_data.csv"
BACKUP_SENSOR_FILENAME = "backup_sensor_data.csv"
METADATA_FILENAME = "metadata.json"

# Time sharing settings
MOVE_TIME = 10  # seconds to move before collecting data
COLLECT_TIME = 5  # seconds to collect data before moving again

# Speed settings
MAX_SPEED = 255  # Maximum speed value for Sphero

# Global variables
running = True
data_lock = threading.Lock()
sensor_data = []
start_timestamp = None
camera_thread = None
backup_thread = None

def signal_handler(sig, frame):
    """Handle Ctrl+C to gracefully stop data collection and Sphero movement"""
    global running
    
    if not running:  # If Ctrl+C is pressed twice
        print("\nForce exiting...")
        os._exit(1)
        
    print("\nStopping data collection and Sphero movement...")
    running = False

def ensure_data_dir():
    """Create a timestamped directory for this run's data"""
    global DATA_DIR
    
    # Create base directory if it doesn't exist
    if not os.path.exists("collected_data"):
        os.makedirs("collected_data")
        
    # Create a timestamped directory for this run
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = f"collected_data/run_{timestamp}"
    os.makedirs(run_dir, exist_ok=True)
    
    # Update global DATA_DIR to the run-specific directory
    DATA_DIR = run_dir
    print(f"Data will be saved to {DATA_DIR}")
    
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
        if isinstance(response, dict):
            for sensor_key, value in response.items():
                sensor_str = str(sensor_key)
                
                if "Accelerometer" in sensor_str and ".x" in sensor_str:
                    accel_x = value
                elif "Accelerometer" in sensor_str and ".y" in sensor_str:
                    accel_y = value
                elif "Accelerometer" in sensor_str and ".z" in sensor_str:
                    accel_z = value
                elif "Gyroscope" in sensor_str and ".x" in sensor_str:
                    gyro_x = value
                elif "Gyroscope" in sensor_str and ".y" in sensor_str:
                    gyro_y = value
                elif "Gyroscope" in sensor_str and ".z" in sensor_str:
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
            
            # Print status periodically (not too often to avoid console spam)
            if len(sensor_data) % 100 == 0:
                print(f"Collected {len(sensor_data)} sensor data points")
            
    except Exception as e:
        print(f"Error processing sensor data: {e}")

def camera_recording_thread():
    """Thread for video recording"""
    global running, DATA_DIR, start_timestamp
    
    try:
        # Initialize camera
        cap = cv2.VideoCapture(CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
        
        # Check if camera opened successfully
        if not cap.isOpened():
            print("Error: Could not open camera.")
            running = False
            return
        
        # Get actual camera properties
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        print(f"Camera initialized with resolution: {actual_width}x{actual_height} @ {actual_fps}fps")
        
        # Define the codec and create VideoWriter object
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video_path = os.path.join(DATA_DIR, VIDEO_FILENAME)
        out = cv2.VideoWriter(video_path, fourcc, actual_fps, (actual_width, actual_height))
        
        frame_count = 0
        last_report_time = time.time()
        
        # Loop until running is False
        while running:
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to capture image")
                time.sleep(0.1)
                continue
                
            # Add timestamp overlay
            timestamp = time.time() - start_timestamp if start_timestamp else 0
            cv2.putText(frame, f"Time: {timestamp:.3f}s", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Write the frame to video file
            out.write(frame)
            
            frame_count += 1
            
            # Periodically report recording progress
            if frame_count % 300 == 0:
                current_time = time.time()
                elapsed = current_time - last_report_time
                fps = 300 / elapsed if elapsed > 0 else 0
                print(f"Recording video: {frame_count} frames, {fps:.1f} fps")
                last_report_time = current_time
                
            # Small sleep to prevent maxing out CPU
            time.sleep(0.01)
        
        # Release everything when done
        cap.release()
        out.release()
        print(f"Video recording stopped. Saved to {video_path}")
        print(f"Recorded {frame_count} frames")
        
    except Exception as e:
        print(f"Error in video recording: {e}")
        running = False

def backup_sensor_data_thread():
    """Periodically save sensor data to prevent data loss in case of crash"""
    global running, sensor_data, DATA_DIR
    
    while running:
        try:
            # Sleep for 30 seconds, checking running flag every second
            for _ in range(30):
                if not running:
                    break
                time.sleep(1)
            
            if not running:
                break
                
            # Make a copy of current data with lock
            with data_lock:
                data_copy = sensor_data.copy()
            
            # Only write if we have data
            if len(data_copy) > 0:
                backup_path = os.path.join(DATA_DIR, BACKUP_SENSOR_FILENAME)
                
                with open(backup_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # Write header
                    writer.writerow([
                        'timestamp',
                        'accel_x', 'accel_y', 'accel_z',
                        'gyro_x', 'gyro_y', 'gyro_z'
                    ])
                    
                    # Write data
                    for row in data_copy:
                        writer.writerow(row)
                
                print(f"Backup saved: {len(data_copy)} data points")
        except Exception as e:
            print(f"Error saving backup: {e}")

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
    """Write metadata about the data collection"""
    global DATA_DIR, start_timestamp
    
    metadata = {
        "version": "1.0",
        "collection_start": datetime.datetime.fromtimestamp(start_timestamp).isoformat() if start_timestamp else None,
        "collection_end": datetime.datetime.now().isoformat(),
        "duration_seconds": time.time() - start_timestamp if start_timestamp else None,
        "camera_settings": {
            "width": CAMERA_WIDTH,
            "height": CAMERA_HEIGHT,
            "fps": CAMERA_FPS
        },
        "sensor_settings": {
            "frequency_hz": SENSOR_FREQUENCY,
            "alternating_mode": {
                "move_time": MOVE_TIME,
                "collect_time": COLLECT_TIME
            }
        },
        "sensor_samples": len(sensor_data)
    }
    
    metadata_path = os.path.join(DATA_DIR, METADATA_FILENAME)
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Metadata written to {metadata_path}")

def move_sphero(sphero, duration=MOVE_TIME):
    """Move the Sphero with random patterns for a specific duration"""
    print(f"Starting movement for {duration} seconds...")
    
    start_move_time = time.time()
    last_movement_change = start_move_time
    last_status_time = start_move_time
    commands_sent = 0
    
    # Initial movement parameters
    speed = random.randint(100, MAX_SPEED)
    heading = random.randint(0, 359)
    movement_duration = random.uniform(0.3, 1.0)
    
    # Set initial movement
    print(f"Setting initial movement: heading={heading}°, speed={speed}")
    sphero.driving.drive_with_heading(speed, heading, Direction.forward)
    commands_sent += 1
    
    # Continue movement for the specified duration
    while running and (time.time() - start_move_time < duration):
        current_time = time.time()
        
        # Change direction, speed and set new duration randomly
        if current_time - last_movement_change >= movement_duration:
            speed = random.randint(100, MAX_SPEED)
            heading = random.randint(0, 359)
            movement_duration = random.uniform(0.3, 1.0)
            print(f"New movement: heading={heading}°, speed={speed}, duration={movement_duration:.1f}s")
            sphero.driving.drive_with_heading(speed, heading, Direction.forward)
            commands_sent += 1
            last_movement_change = current_time
            
        # Print status periodically
        if current_time - last_status_time >= 5:
            elapsed = int(current_time - start_move_time)
            print(f"Movement running for {elapsed}s - Commands sent: {commands_sent}")
            last_status_time = current_time
            
        # Brief delay to prevent overwhelming the connection
        time.sleep(0.2)
        
    print(f"Movement phase complete. Sent {commands_sent} commands.")

def collect_sensor_data(sphero, duration=COLLECT_TIME):
    """Collect sensor data for a specific duration"""
    print(f"Starting sensor data collection for {duration} seconds...")
    
    # Set up sensor streaming
    print(f"Setting up sensor streaming at {SENSOR_FREQUENCY}Hz...")
    sphero.sensor.set_notify(
        sensor_callback,
        Accelerometer, 
        Gyroscope,
        interval=SENSOR_INTERVAL
    )
    
    # Collect data for the specified duration
    collection_start = time.time()
    start_count = len(sensor_data)
    
    while running and (time.time() - collection_start < duration):
        # Just wait for callbacks to collect data
        time.sleep(0.1)
    
    # Calculate collection rate
    end_count = len(sensor_data)
    collected = end_count - start_count
    total_time = time.time() - collection_start
    rate = collected / total_time if total_time > 0 else 0
    
    print(f"Data collection phase complete. Collected {collected} samples ({rate:.1f}/sec)")

def run_time_shared_collection():
    """
    Main function that alternates between movement and sensor data collection
    to avoid connection conflicts.
    """
    global running, start_timestamp
    
    # Set start timestamp if not already set
    if start_timestamp is None:
        start_timestamp = time.time()
    
    # Track and report overall progress
    cycle_count = 0
    start_time = time.time()
    last_status_time = start_time
    
    print("Starting alternating movement and data collection...")
    print(f"Pattern: {MOVE_TIME}s movement followed by {COLLECT_TIME}s data collection")
    print("Press Ctrl+C to stop")
    
    # Main loop - reconnect on failure
    while running:
        try:
            # Use context manager to properly handle connection
            print(f"Connecting to Sphero...")
            with Sphero(mac_address=MAC_ADDRESS) as sphero:
                print("Connected! Waking up Sphero...")
                sphero.power.wake()
                time.sleep(1.0)  # Give more time to wake up
                
                # Continue alternating until interrupted
                while running:
                    # First move the Sphero
                    move_sphero(sphero, MOVE_TIME)
                    if not running:
                        break
                        
                    # Then collect sensor data
                    collect_sensor_data(sphero, COLLECT_TIME)
                    
                    # Update cycle count and print status
                    cycle_count += 1
                    current_time = time.time()
                    if current_time - last_status_time >= 60:  # Status every minute
                        elapsed = int(current_time - start_time)
                        minutes, seconds = divmod(elapsed, 60)
                        print(f"Running for {minutes}m {seconds}s - Completed {cycle_count} cycles - Collected {len(sensor_data)} sensor points")
                        last_status_time = current_time
                
                print("Sphero connection closed.")
                
        except Exception as e:
            print(f"Connection error: {e}")
        
        # Only retry if still running
        if running:
            print(f"Will retry in 5 seconds...")
            time.sleep(5)

def main():
    """Main function to initiate data collection and Sphero movement"""
    global running, camera_thread, backup_thread
    
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create data directory
    ensure_data_dir()
    
    try:
        # Start camera recording thread
        camera_thread = threading.Thread(target=camera_recording_thread)
        camera_thread.daemon = True
        camera_thread.start()
        
        # Start sensor data backup thread
        backup_thread = threading.Thread(target=backup_sensor_data_thread)
        backup_thread.daemon = True
        backup_thread.start()
        
        # Run the time-shared data collection in the main thread
        run_time_shared_collection()
        
    except KeyboardInterrupt:
        running = False
    except Exception as e:
        print(f"Main error: {e}")
        running = False
    finally:
        # Make sure running is set to False
        running = False
        
        # Wait for threads to complete
        print("Waiting for data collection to complete...")
        if camera_thread and camera_thread.is_alive():
            camera_thread.join(timeout=5)
        
        # Write collected data to CSV
        write_sensor_data_to_csv()
        
        # Write metadata
        write_metadata()
        
        print("Data collection complete!")
        print("Program terminated")

if __name__ == "__main__":
    main() 
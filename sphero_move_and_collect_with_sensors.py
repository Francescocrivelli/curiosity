#!/usr/bin/env python3
"""
Sphero Data Collection Script with Video Recording

This script continuously collects sensor data from Sphero while periodically
sending movement commands. It also records video from a USB camera throughout 
the process.
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
SENSOR_FREQUENCY = 20  # Hz
SENSOR_INTERVAL = int(1000 / SENSOR_FREQUENCY)  # Convert to milliseconds for PySphero API
DATA_DIR = "collected_data"
VIDEO_FILENAME = "video.mp4"
SENSOR_FILENAME = "sensor_data.csv"
BACKUP_SENSOR_FILENAME = "backup_sensor_data.csv"
METADATA_FILENAME = "metadata.json"

# Movement settings
MOVEMENT_INTERVAL = 0.5  # Send movement commands every 0.5 seconds
MAX_SPEED = 255  # Maximum speed value for Sphero

# Global variables
running = True
data_lock = threading.Lock()
sensor_data = []
start_timestamp = None
camera_thread = None
backup_thread = None
csv_file = None
csv_writer = None
data_points_counter = 0
movement_active = True  # Flag to enable/disable movement

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
    global DATA_DIR, csv_file, csv_writer
    
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
    
    # Initialize the CSV file for real-time writing
    sensor_path = os.path.join(DATA_DIR, SENSOR_FILENAME)
    csv_file = open(sensor_path, 'w', newline='')
    csv_writer = csv.writer(csv_file)
    
    # Write header
    csv_writer.writerow([
        'timestamp',
        'accel_x', 'accel_y', 'accel_z',
        'gyro_x', 'gyro_y', 'gyro_z'
    ])
    
    # Ensure data is written to disk
    csv_file.flush()
    
    print(f"Initialized sensor data file: {sensor_path}")
    
    return DATA_DIR

def sensor_callback(response):
    """Process sensor data received from Sphero and write to file in real-time"""
    global sensor_data, start_timestamp, csv_writer, data_points_counter
    
    # Get current timestamp relative to start
    current_time = time.time()
    if start_timestamp is None:
        start_timestamp = current_time
        print("First sensor data received! Starting timing from here.")
    
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
        
        # Add to data list with thread-safe lock and write to CSV in real-time
        with data_lock:
            # Add to in-memory list (for backup purposes)
            sensor_data.append(data_row)
            
            # Write directly to CSV file
            if csv_writer:
                csv_writer.writerow(data_row)
                # Flush every 5 data points to ensure data is written to disk
                # without causing too much I/O overhead
                data_points_counter += 1
                if data_points_counter % 5 == 0:
                    csv_file.flush()
            
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

def write_metadata():
    """Write metadata about the data collection"""
    global DATA_DIR, start_timestamp, sensor_data
    
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
            "continuous_collection": True,
            "movement_interval": MOVEMENT_INTERVAL
        },
        "sensor_samples": len(sensor_data)
    }
    
    metadata_path = os.path.join(DATA_DIR, METADATA_FILENAME)
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Metadata written to {metadata_path}")

def movement_thread(sphero_instance):
    """Thread for sending movement commands periodically"""
    global running, movement_active
    
    print("Starting continuous movement thread...")
    
    # Initialize variables for movement control
    last_movement_time = time.time()
    commands_sent = 0
    last_status_time = time.time()
    
    # Continue until running is False
    while running:
        try:
            # Check if movement is active
            if not movement_active:
                time.sleep(0.1)
                continue
                
            current_time = time.time()
            
            # Send movement command at interval
            if current_time - last_movement_time >= MOVEMENT_INTERVAL:
                # Random movement parameters
                speed = random.randint(100, MAX_SPEED)
                heading = random.randint(0, 359)
                
                # Send the command
                sphero_instance.driving.drive_with_heading(speed, heading, Direction.forward)
                commands_sent += 1
                
                # Log the command
                if commands_sent <= 5 or commands_sent % 10 == 0:
                    print(f"Movement command: heading={heading}°, speed={speed}")
                
                last_movement_time = current_time
            
            # Print status periodically
            if current_time - last_status_time >= 10:
                elapsed = int(current_time - time.time() + running_time)
                minutes, seconds = divmod(elapsed, 60)
                cmd_rate = commands_sent / elapsed if elapsed > 0 else 0
                print(f"Running for {minutes}m {seconds}s - Movement commands: {commands_sent} ({cmd_rate:.1f}/sec)")
                last_status_time = current_time
            
            # Small sleep to prevent maxing out CPU
            time.sleep(0.05)
            
        except Exception as e:
            print(f"Error in movement thread: {e}")
            # Don't crash the thread, just log and continue
            time.sleep(1)
    
    print(f"Movement thread stopped. Sent {commands_sent} commands.")

def run_sensor_and_movement():
    """
    Main function that continuously collects sensor data and periodically sends
    movement commands.
    """
    global running, start_timestamp, movement_active, running_time
    
    # Running time tracker
    running_time = time.time()
    
    print("Starting continuous data collection and movement...")
    print(f"Sensor frequency: {SENSOR_FREQUENCY} Hz, Movement interval: {MOVEMENT_INTERVAL} sec")
    print("Press Ctrl+C to stop")
    
    # Main loop - reconnect on failure
    reconnect_count = 0
    max_reconnects = 10
    
    while running and reconnect_count < max_reconnects:
        try:
            # Use context manager to properly handle connection
            print(f"Connecting to Sphero...")
            with Sphero(mac_address=MAC_ADDRESS) as sphero:
                print("Connected! Waking up Sphero...")
                sphero.power.wake()
                time.sleep(1.0)  # Give more time to wake up
                
                # Set up sensor streaming IMMEDIATELY to get data from the start
                print(f"Setting up sensor streaming at {SENSOR_FREQUENCY}Hz...")
                sphero.sensor.set_notify(
                    sensor_callback,
                    Accelerometer, 
                    Gyroscope,
                    interval=SENSOR_INTERVAL
                )
                
                print("Sensor streaming active. Starting movement...")
                
                # Start movement in a separate thread
                move_thread = threading.Thread(target=movement_thread, args=(sphero,))
                move_thread.daemon = True
                move_thread.start()
                
                # Main thread just keeps the connection alive and monitors
                last_status_time = time.time()
                consecutive_errors = 0
                max_errors = 5
                
                while running:
                    try:
                        # Periodically keep connection alive with a simple command
                        current_time = time.time()
                        
                        # Check for any potential issues every 10 seconds
                        if current_time - last_status_time >= 10:
                            # Get battery level as a simple keep-alive command
                            try:
                                battery = sphero.power.get_battery_voltage()
                                consecutive_errors = 0  # Reset error counter on success
                                print(f"Sphero battery: {battery:.2f}V - Data points: {len(sensor_data)}")
                            except Exception as e:
                                consecutive_errors += 1
                                print(f"Warning: Battery check failed: {e}")
                                if consecutive_errors >= max_errors:
                                    print(f"Too many consecutive errors ({consecutive_errors}). Reconnecting...")
                                    break
                                
                            last_status_time = current_time
                            
                        time.sleep(1.0)  # Check status periodically
                        
                    except Exception as connection_e:
                        print(f"Connection monitor error: {connection_e}")
                        consecutive_errors += 1
                        if consecutive_errors >= max_errors:
                            print(f"Too many consecutive errors ({consecutive_errors}). Reconnecting...")
                            break
                        time.sleep(1.0)
                
                print("Sphero connection closed.")
                
        except Exception as e:
            print(f"Connection error: {e}")
            reconnect_count += 1
        
        # Only retry if still running
        if running:
            print(f"Will retry in 5 seconds... (attempt {reconnect_count}/{max_reconnects})")
            time.sleep(5)
    
    if reconnect_count >= max_reconnects:
        print(f"Maximum reconnect attempts ({max_reconnects}) reached. Stopping.")
        running = False

def main():
    """Main function to initiate data collection and Sphero movement"""
    global running, camera_thread, backup_thread, csv_file
    
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create data directory and initialize CSV file
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
        
        # Run the continuous data collection and movement
        run_sensor_and_movement()
        
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
        
        # Close CSV file to ensure all data is written
        if csv_file:
            csv_file.flush()
            csv_file.close()
            print(f"Sensor data file closed. Wrote {len(sensor_data)} data points.")
        
        # Write metadata
        write_metadata()
        
        print("Data collection complete!")
        print("Program terminated")

if __name__ == "__main__":
    main() 
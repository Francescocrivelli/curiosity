import time
import random
import csv
import os
import datetime
import signal
import threading
from pysphero.core import Sphero
from pysphero.driving import Direction
from pysphero.device_api.sensor import Accelerometer, Gyroscope

# Sphero MAC address
MAC_ADDRESS = "C9:B9:61:72:CB:78"

# Sample frequency settings
SAMPLE_FREQUENCY = 20  # Hz
INTERVAL = int(1000 / SAMPLE_FREQUENCY)  # Convert to milliseconds

# Data collection settings
DATA_DIR = "sphero_data"
MAX_RUNTIME = 3600  # Default runtime in seconds (1 hour)
MOVEMENT_CHANGE_INTERVAL = 5  # Seconds between movement pattern changes

# Global variables for controlling execution
running = True
data_buffer = []
buffer_lock = threading.Lock()
total_samples = 0

def signal_handler(sig, frame):
    """Handle Ctrl+C to gracefully stop data collection"""
    global running
    print("\nStopping data collection...")
    running = False

def ensure_data_dir():
    """Create data directory if it doesn't exist"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    return DATA_DIR

def get_data_filename():
    """Generate a timestamped filename for the data"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(DATA_DIR, f"sphero_data_{timestamp}.csv")

def write_buffer_to_file(filename, buffer):
    """Write the data buffer to the CSV file"""
    with open(filename, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        for row in buffer:
            writer.writerow(row)

def sensor_callback(response):
    """Process sensor data received from Sphero"""
    global data_buffer, total_samples
    
    timestamp = time.time()
    
    # Extract individual sensor values
    try:
        # Print the raw response for debugging
        print(f"Raw sensor data: {response}")
        
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
            timestamp,
            accel_x, accel_y, accel_z,
            gyro_x, gyro_y, gyro_z
        ]
        
        # Add to buffer with thread-safe lock
        with buffer_lock:
            data_buffer.append(data_row)
            total_samples += 1
            
            # Print status update periodically
            if total_samples % 100 == 0:
                print(f"Collected {total_samples} samples")
                
    except Exception as e:
        print(f"Error processing sensor data: {e}")

def data_writer_thread(filename):
    """Background thread that periodically writes data to CSV"""
    global data_buffer, running
    
    print(f"Data writer thread started, writing to {filename}")
    
    # Write CSV header
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            'timestamp',
            'accel_x', 'accel_y', 'accel_z',
            'gyro_x', 'gyro_y', 'gyro_z'
        ])
    
    while running:
        # Check if there's data to write
        if len(data_buffer) > 0:
            # Get a copy of the buffer and clear it under lock
            with buffer_lock:
                buffer_copy = data_buffer.copy()
                data_buffer.clear()
            
            # Write data to file
            write_buffer_to_file(filename, buffer_copy)
            print(f"Wrote {len(buffer_copy)} records to file")
        
        # Wait before checking again
        time.sleep(1)
    
    # Final write of any remaining data
    if len(data_buffer) > 0:
        with buffer_lock:
            buffer_copy = data_buffer.copy()
            data_buffer.clear()
        write_buffer_to_file(filename, buffer_copy)
        print(f"Final write: {len(buffer_copy)} records")

def random_movement(sphero):
    """Generate random movement patterns for the Sphero"""
    try:
        movement_type = random.randint(0, 3)
        
        if movement_type == 0:
            # Straight line
            speed = random.randint(40, 80)  # Using more moderate speeds
            heading = random.randint(0, 359)
            print(f"Moving straight: speed={speed}, heading={heading}°")
            sphero.driving.drive_with_heading(speed, heading, Direction.forward)
            
        elif movement_type == 1:
            # Arc movement - using gentler arcs
            speed = random.randint(40, 70)
            start_heading = random.randint(0, 359)
            arc_size = random.randint(30, 90)  # Smaller arc
            direction = 1 if random.random() > 0.5 else -1
            
            print(f"Arc movement: speed={speed}, start_heading={start_heading}°, arc={arc_size}°")
            for i in range(3):  # Fewer steps
                heading = (start_heading + direction * i * (arc_size//3)) % 360
                sphero.driving.drive_with_heading(speed, heading, Direction.forward)
                time.sleep(0.3)
                
        elif movement_type == 2:
            # Quick direction changes
            print("Quick direction changes")
            for _ in range(2):  # Fewer changes
                speed = random.randint(30, 60)  # Lower speed
                heading = random.randint(0, 359)
                sphero.driving.drive_with_heading(speed, heading, Direction.forward)
                time.sleep(0.4)
                
        else:
            # Spin in place - gentler spin
            print("Spinning in place")
            speed = 30  # Lower speed
            for angle in range(0, 361, 60):  # Fewer steps
                sphero.driving.drive_with_heading(speed, angle, Direction.forward)
                time.sleep(0.25)
                
    except Exception as e:
        print(f"Error in random movement: {e}")

def main(runtime=MAX_RUNTIME):
    """Main function for Sphero data collection"""
    global running
    
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create data directory and filename
    ensure_data_dir()
    filename = get_data_filename()
    print(f"Data will be saved to: {filename}")
    
    # Start data writer thread
    writer_thread = threading.Thread(target=data_writer_thread, args=(filename,))
    writer_thread.daemon = True
    writer_thread.start()
    
    with Sphero(mac_address=MAC_ADDRESS) as sphero:
        print("Waking up Sphero...", flush=True)
        sphero.power.wake()
        time.sleep(2)  # Give the ball time to wake up
        
        # Set up sensor streaming
        print("Setting up sensor streaming at 20Hz...")
        sensor = sphero.sensor
        
        try:
            # Using a less aggressive approach for longer runtime
            sensor.set_notify(
                sensor_callback,
                Accelerometer,  # Just accelerometer for now
                Gyroscope,      # And gyroscope
                interval=INTERVAL,  # 50ms for 20Hz
                count=0,            # Continuous streaming
                timeout=1.0
            )
            
            print(f"Starting data collection for {runtime} seconds (or until Ctrl+C)")
            start_time = time.time()
            last_movement_time = start_time
            
            # Wait a moment to ensure streaming is properly established
            time.sleep(1)
            
            # Main data collection loop
            try:
                while running and (time.time() - start_time < runtime):
                    current_time = time.time()
                    
                    # Change movement pattern periodically
                    if current_time - last_movement_time >= MOVEMENT_CHANGE_INTERVAL:
                        try:
                            random_movement(sphero)
                            last_movement_time = current_time
                        except Exception as e:
                            print(f"Error during movement change: {e}")
                            # If there's an error, wait a bit before trying again
                            time.sleep(2)
                    
                    # Check battery every 5 minutes
                    elapsed_time = int(current_time - start_time)
                    if elapsed_time % 300 == 0 and elapsed_time > 0:
                        try:
                            battery_voltage = sphero.power.get_battery_voltage()
                            print(f"Battery voltage: {battery_voltage}V")
                        except Exception as e:
                            print(f"Error checking battery: {e}")
                    
                    # Add a small delay to prevent overwhelming the Sphero
                    time.sleep(0.1)
                    
            except Exception as e:
                print(f"Error in main loop: {e}")
        except Exception as e:
            print(f"Error setting up sensor streaming: {e}")
        finally:
            # Clean up
            try:
                # Stop sensor streaming
                print("Stopping sensor streaming...")
                sensor.cancel_notify_sensors()
            except:
                pass
            
            try:
                # Put Sphero to sleep
                print("Putting Sphero to sleep...")
                sphero.power.enter_soft_sleep()
            except:
                pass
            
            # Wait for the writer thread to finish
            running = False
            writer_thread.join(timeout=5)
            
            # Final status
            print(f"Data collection complete. Collected {total_samples} samples.")
            print(f"Data saved to {filename}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Collect Sphero sensor data.')
    parser.add_argument('--runtime', type=int, default=MAX_RUNTIME,
                        help=f'Runtime in seconds (default: {MAX_RUNTIME})')
    args = parser.parse_args()
    
    main(runtime=args.runtime)
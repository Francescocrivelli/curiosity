import time
import random
import csv
import os
import datetime
import signal
import threading
import sys
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
MOVEMENT_UPDATE_INTERVAL = 0.1  # Seconds between random movement updates

# Global variables for controlling execution
running = True
data_buffer = []
buffer_lock = threading.Lock()
total_samples = 0
consecutive_movement_errors = 0
last_successful_movement = 0

def force_exit(message=None):
    """Force exit the script in case of unrecoverable error"""
    if message:
        print(f"CRITICAL ERROR: {message}")
    print("Forcing exit...")
    os._exit(1)  # Force exit bypassing normal cleanup

def signal_handler(sig, frame):
    """Handle Ctrl+C to gracefully stop data collection"""
    global running
    print("\nStopping data collection (Ctrl+C)...")
    running = False
    # Set a timer to force exit if cleanup takes too long
    threading.Timer(5, lambda: force_exit("Cleanup took too long")).start()

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
        # Only print occasional sensor data to avoid flooding console
        if total_samples % 100 == 0:
            print(f"Sample sensor data: {response}")
        
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
        try:
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
        except Exception as e:
            print(f"Error in data writer thread: {e}")
    
    # Final write of any remaining data
    try:
        if len(data_buffer) > 0:
            with buffer_lock:
                buffer_copy = data_buffer.copy()
                data_buffer.clear()
            write_buffer_to_file(filename, buffer_copy)
            print(f"Final write: {len(buffer_copy)} records")
    except Exception as e:
        print(f"Error during final write: {e}")

def execute_movement(sphero, speed, heading, direction=Direction.forward):
    """Execute a single movement command with error handling"""
    global consecutive_movement_errors, last_successful_movement
    
    try:
        # Execute the movement command
        sphero.driving.drive_with_heading(speed, heading, direction)
        
        # Reset error counter on success
        consecutive_movement_errors = 0
        last_successful_movement = time.time()
        return True
    except Exception as e:
        # Increment error counter
        consecutive_movement_errors += 1
        
        # Only print errors occasionally to avoid flooding console
        if consecutive_movement_errors % 5 == 0:
            print(f"Movement error ({consecutive_movement_errors}): {e}")
        
        return False

def continuous_random_movement_thread(sphero):
    """Thread that continuously updates Sphero's movement with random parameters"""
    global running, last_successful_movement
    
    print("Continuous random movement thread started")
    
    error_count = 0
    max_errors = 10
    
    while running:
        try:
            # Generate completely random movement parameters
            speed = random.randint(20, 80)  # Random speed (low enough to avoid errors)
            heading = random.randint(0, 359)  # Random heading
            
            # Small chance to change direction
            direction = Direction.forward
            if random.random() < 0.05:  # 5% chance
                direction = Direction.reverse
            
            # Execute the random movement
            success = execute_movement(sphero, speed, heading, direction)
            
            if success:
                error_count = 0
                
                # Only print movement changes occasionally
                if random.random() < 0.1:  # 10% chance to print
                    print(f"Moving: speed={speed}, heading={heading}°")
            else:
                error_count += 1
                
                # If too many consecutive errors, try a recovery
                if error_count >= max_errors:
                    print(f"Too many movement errors ({error_count}). Attempting recovery...")
                    try:
                        # Try a very conservative movement
                        sphero.driving.drive_with_heading(30, random.randint(0, 359), Direction.forward)
                        time.sleep(0.5)
                        error_count = 0
                    except:
                        pass
            
            # Sleep for a random amount of time
            # This creates more natural, unpredictable movements
            sleep_time = MOVEMENT_UPDATE_INTERVAL * (0.5 + random.random())  # Between 0.5x and 1.5x the base interval
            time.sleep(sleep_time)
            
        except Exception as e:
            print(f"Error in continuous movement thread: {e}")
            time.sleep(0.5)  # Sleep a bit longer after an error

def main(runtime=MAX_RUNTIME):
    """Main function for Sphero data collection"""
    global running, last_successful_movement
    
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
        
        # Initialize the last successful movement time
        last_successful_movement = time.time()
        
        # Start continuous random movement thread
        movement_thread = threading.Thread(target=continuous_random_movement_thread, args=(sphero,))
        movement_thread.daemon = True
        movement_thread.start()
        
        # Set up sensor streaming
        print("Setting up sensor streaming at 20Hz...")
        sensor = sphero.sensor
        
        try:
            # Set up sensor notifications
            sensor.set_notify(
                sensor_callback,
                Accelerometer, 
                Gyroscope,
                interval=INTERVAL,  # 50ms for 20Hz
                count=0,            # Continuous streaming
                timeout=1.0
            )
            
            print(f"Starting data collection for {runtime} seconds (or until Ctrl+C)")
            start_time = time.time()
            
            # Wait a moment to ensure streaming is properly established
            time.sleep(1)
            
            # Main data collection loop
            try:
                while running and (time.time() - start_time < runtime):
                    current_time = time.time()
                    
                    # Check battery every 5 minutes
                    elapsed_time = int(current_time - start_time)
                    if elapsed_time % 300 == 0 and elapsed_time > 0:
                        try:
                            battery_voltage = sphero.power.get_battery_voltage()
                            print(f"Battery voltage: {battery_voltage}V")
                        except Exception as e:
                            print(f"Error checking battery: {e}")
                    
                    # Add a small delay to prevent CPU hogging
                    time.sleep(0.5)
                    
            except Exception as e:
                print(f"Error in main loop: {e}")
        except Exception as e:
            print(f"Error setting up sensor streaming: {e}")
        finally:
            # Clean up
            running = False
            print("Cleaning up...")
            
            try:
                # Stop sensor streaming
                print("Stopping sensor streaming...")
                sensor.cancel_notify_sensors()
            except Exception as e:
                print(f"Error stopping sensor streaming: {e}")
            
            try:
                # Put Sphero to sleep
                print("Putting Sphero to sleep...")
                sphero.power.enter_soft_sleep()
            except Exception as e:
                print(f"Error putting Sphero to sleep: {e}")
            
            # Wait for the writer thread to finish
            try:
                writer_thread.join(timeout=3)
            except:
                pass
            
            # Final status
            print(f"Data collection complete. Collected {total_samples} samples.")
            print(f"Data saved to {filename}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Collect Sphero sensor data with continuous random movement.')
    parser.add_argument('--runtime', type=int, default=MAX_RUNTIME,
                        help=f'Runtime in seconds (default: {MAX_RUNTIME})')
    args = parser.parse_args()
    
    try:
        main(runtime=args.runtime)
    except Exception as e:
        print(f"Unhandled exception in main: {e}")
    finally:
        print("Script finished")
        # Force exit to ensure all threads are terminated
        os._exit(0)
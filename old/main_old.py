import time
import threading
from pysphero.core import Sphero

def main():
    # Replace with your Regular Sphero's MAC address
    mac_address = "C9:B9:61:72:CB:78"
    
    with Sphero(mac_address=mac_address) as sphero:
        print("Waking up Sphero...", flush=True)
        sphero.power.wake()
        time.sleep(2)  # Give the ball time to wake up
        
        # Get the sensor object
        sensor = sphero.sensor
        print("Sensor object available:", sensor is not None)
        
        # Based on your output, we can see sensor has a set_notify method
        # Let's try to enable notifications for various sensors
        
        # First, let's set up a notification handler
        def sensor_notification_handler(data):
            print(f"Received sensor data: {data}")
        
        # Common sensor IDs based on Sphero API documentation
        # These may vary by model and firmware version
        SENSOR_IDS = {
            'accelerometer': 0x01,
            'gyroscope': 0x02,
            'attitude': 0x03,
            'locator': 0x04,
            'velocity': 0x05,
            'ambient_light': 0x06,
            # The following are guesses based on common patterns
            'quaternion': 0x07,
            'motor_temperature': 0x10,
            'motor_current': 0x11,
            'core_time': 0x20
        }
        
        try:
            print("\nAttempting to enable sensor notifications...")
            
            # Try to enable notifications for all potential sensors
            enabled_sensors = []
            for sensor_name, sensor_id in SENSOR_IDS.items():
                try:
                    print(f"Enabling {sensor_name} (ID: {sensor_id})...")
                    sensor.set_notify(sensor_id, True)
                    enabled_sensors.append((sensor_name, sensor_id))
                    print(f"Successfully enabled {sensor_name}")
                except Exception as e:
                    print(f"Failed to enable {sensor_name}: {e}")
            
            if enabled_sensors:
                print(f"\nSuccessfully enabled {len(enabled_sensors)} sensors:")
                for name, sensor_id in enabled_sensors:
                    print(f"- {name} (ID: {sensor_id})")
                
                # Create a flag to control the sensor reading loop
                running = True
                
                # Function to continuously read sensors
                def read_sensors():
                    while running:
                        for name, sensor_id in enabled_sensors:
                            try:
                                # Try to read the sensor value directly
                                # This is a guess - the actual method may differ
                                if name == 'ambient_light':
                                    value = sensor.get_ambient_light_sensor_value()
                                    print(f"{name}: {value}")
                                # For other sensors, we might need to use a different approach
                                # or interpret the streaming data mask
                                
                                # Alternative: check if we can get streaming mask
                                streaming_mask = sensor.get_sensor_streaming_mask()
                                print(f"Streaming mask: {streaming_mask}")
                                
                            except Exception as e:
                                print(f"Error reading {name}: {e}")
                        
                        # Short delay between reads
                        time.sleep(0.2)
                
                # Start the sensor reading thread
                sensor_thread = threading.Thread(target=read_sensors)
                sensor_thread.start()
                
                # Let it run for a while
                print("\nReading sensors for 10 seconds...")
                time.sleep(10)
                
                # Stop the thread
                running = False
                sensor_thread.join()
                
                # Try to disable notifications
                print("\nDisabling sensor notifications...")
                for name, sensor_id in enabled_sensors:
                    try:
                        sensor.set_notify(sensor_id, False)
                        print(f"Disabled {name}")
                    except Exception as e:
                        print(f"Error disabling {name}: {e}")
            
            else:
                print("No sensors could be enabled. Trying alternative approaches.")
                
                # Try the raw API approach
                try:
                    print("\nTrying to enable sensor streaming using raw commands...")
                    
                    # These command values are educated guesses based on common BLE protocols
                    # and may need adjustment for your specific Sphero model
                    
                    # Common command to enable sensor streaming (values may vary)
                    ENABLE_STREAMING_CMD = 0x11  # Example command ID
                    
                    # Try to send a command to enable streaming
                    # First parameter: command ID
                    # Second parameter: payload (varies by command)
                    if hasattr(sensor, 'request'):
                        # Example payload: [mask1, mask2, rate, frames] - adjust as needed
                        result = sensor.request(ENABLE_STREAMING_CMD, [0xFF, 0xFF, 0x0A, 0x01])
                        print(f"Raw streaming command result: {result}")
                        
                        # Let it run for a few seconds and see if we get any notifications
                        print("Waiting for potential streaming data...")
                        time.sleep(5)
                        
                        # Try to disable streaming
                        result = sensor.request(ENABLE_STREAMING_CMD, [0x00, 0x00, 0x00, 0x00])
                        print(f"Disable streaming result: {result}")
                    else:
                        print("No request method available on sensor object")
                
                except Exception as e:
                    print(f"Error with raw commands: {e}")
        
        except Exception as e:
            print(f"Error setting up sensor notifications: {e}")
        
        # Clean up and put the Sphero to sleep
        print("\nEntering soft sleep...")
        sphero.power.enter_soft_sleep()
        print("Operation complete.")

if __name__ == "__main__":
    main()
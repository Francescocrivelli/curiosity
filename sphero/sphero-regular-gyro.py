import time
import struct
import random
from pysphero.core import Sphero
from pysphero.driving import Direction

# Regular Sphero MAC address
MAC_ADDRESS = "C9:B9:61:72:CB:78"

# Define potential sensor command IDs for the Sphero API
GYRO_SENSOR_ID = 0x02  # Common gyroscope sensor ID
ACCEL_SENSOR_ID = 0x01  # Common accelerometer sensor ID

def main():
    with Sphero(mac_address=MAC_ADDRESS) as sphero:
        print("Waking up Sphero...", flush=True)
        sphero.power.wake()
        time.sleep(2)  # Give the ball time to wake up
        
        print("\n--- Checking Available APIs ---")
        # Check if sensor object exists and what it can do
        sensor = getattr(sphero, 'sensor', None)
        if sensor:
            print("Sensor object exists")
            sensor_methods = [attr for attr in dir(sensor) if not attr.startswith('_')]
            print(f"Available sensor methods: {sensor_methods}")
            
            # Try to access the raw request function to send custom commands
            if hasattr(sensor, 'request'):
                print("\n--- Trying Direct Sensor Commands ---")
                
                try:
                    # Try to send raw commands to enable gyroscope streaming
                    # This is using the raw Sphero protocol format
                    # Typical command structure: [device_id, command_id, data...]
                    
                    # Common sensor streaming command (0x11)
                    streaming_command = 0x11
                    # data format: [sensor_mask1, sensor_mask2, packet_count, interval]
                    # Enable gyroscope (mask 0x02) with continuous streaming (count 0)
                    # and 10ms interval
                    streaming_data = [0x02, 0x00, 0x00, 0x0A]
                    
                    print(f"Sending sensor streaming command: 0x{streaming_command:02X} {streaming_data}")
                    result = sensor.request(streaming_command, streaming_data)
                    print(f"Command result: {result}")
                    
                    # Try a different format with different masks
                    alternative_streaming_data = [0x0F, 0x00, 0x00, 0x0A]  # Enable multiple sensors
                    print(f"Sending alternative sensor command: 0x{streaming_command:02X} {alternative_streaming_data}")
                    result = sensor.request(streaming_command, alternative_streaming_data)
                    print(f"Command result: {result}")
                    
                    # Another common command ID for older Spheros
                    alt_streaming_command = 0x18
                    print(f"Trying alternative streaming command: 0x{alt_streaming_command:02X}")
                    result = sensor.request(alt_streaming_command, streaming_data)
                    print(f"Command result: {result}")
                    
                except Exception as e:
                    print(f"Error sending raw commands: {e}")
            
            # Try the set_notify method if available
            if hasattr(sensor, 'set_notify'):
                print("\n--- Trying set_notify Method ---")
                try:
                    # Try to enable notifications for gyroscope and accelerometer
                    print(f"Enabling gyroscope notifications (ID: {GYRO_SENSOR_ID})...")
                    sensor.set_notify(GYRO_SENSOR_ID, True)
                    print("Gyroscope notifications enabled")
                    
                    print(f"Enabling accelerometer notifications (ID: {ACCEL_SENSOR_ID})...")
                    sensor.set_notify(ACCEL_SENSOR_ID, True)
                    print("Accelerometer notifications enabled")
                    
                    # Try to read sensor data
                    print("\n--- Reading Sensor Data ---")
                    for i in range(20):  # Try for 20 iterations
                        try:
                            # Check if there are streaming notifications
                            if hasattr(sensor, 'notify'):
                                result = sensor.notify()
                                if result:
                                    print(f"Notification: {result}")
                            
                            # Try to access gyroscope directly
                            gyro_data = None
                            try:
                                if hasattr(sensor, 'get_gyroscope'):
                                    gyro_data = sensor.get_gyroscope()
                                elif hasattr(sensor, 'get_value'):
                                    gyro_data = sensor.get_value(GYRO_SENSOR_ID)
                                
                                if gyro_data:
                                    print(f"Gyroscope data: {gyro_data}")
                            except Exception as e:
                                pass  # Silently ignore if this method doesn't exist
                            
                            # Try to get ambient light data (we know this works)
                            if hasattr(sensor, 'get_ambient_light_sensor_value'):
                                light = sensor.get_ambient_light_sensor_value()
                                print(f"Ambient light: {light}")
                            
                            # Small drive command to generate sensor data
                            if i % 5 == 0:  # Every 5 iterations
                                heading = random.randint(0, 359)
                                speed = random.randint(30, 80)
                                print(f"Driving with heading {heading} and speed {speed}")
                                sphero.driving.drive_with_heading(speed, heading, Direction.forward)
                                
                        except Exception as e:
                            print(f"Error reading sensor: {e}")
                        
                        time.sleep(0.5)  # Short delay between reads
                    
                    # Disable notifications
                    print("\n--- Disabling Notifications ---")
                    sensor.set_notify(GYRO_SENSOR_ID, False)
                    sensor.set_notify(ACCEL_SENSOR_ID, False)
                    
                except Exception as e:
                    print(f"Error with set_notify: {e}")
            
            # Try accessing the sensor_streaming_mask
            if hasattr(sensor, 'get_sensor_streaming_mask'):
                print("\n--- Checking Sensor Streaming Mask ---")
                try:
                    # Get current mask before enabling anything
                    mask = sensor.get_sensor_streaming_mask()
                    print(f"Initial sensor streaming mask: {mask}")
                    
                    # Try to extract information from the mask
                    if isinstance(mask, tuple) and len(mask) >= 3:
                        mask1, mask2, sensors = mask
                        print(f"Mask1: 0x{mask1:02X}, Mask2: 0x{mask2:02X}")
                        print(f"Active sensors: {sensors}")
                    
                    # Now try modifying the mask to enable gyroscope
                    if hasattr(sensor, 'set_sensor_streaming_mask'):
                        # Typical mask format: (mask1, mask2)
                        # where each bit represents a different sensor
                        # Setting bit 1 (0x02) typically enables gyroscope
                        sensor.set_sensor_streaming_mask(0x02, 0x00)
                        print("Set streaming mask to enable gyroscope")
                        
                        # Check if mask was updated
                        updated_mask = sensor.get_sensor_streaming_mask()
                        print(f"Updated sensor streaming mask: {updated_mask}")
                except Exception as e:
                    print(f"Error with sensor_streaming_mask: {e}")
        
        else:
            print("No sensor object available")
        
        # Try to find any other potential sensor-related objects
        potential_sensor_attrs = [
            'sensors',  # plural form
            'imu',      # inertial measurement unit
            'gyro',     # gyroscope specific
            'accel'     # accelerometer specific
        ]
        
        for attr in potential_sensor_attrs:
            obj = getattr(sphero, attr, None)
            if obj:
                print(f"\nFound potential sensor object: {attr}")
                methods = [m for m in dir(obj) if not m.startswith('_')]
                print(f"Available methods: {methods}")
        
        print("\nEntering soft sleep...")
        sphero.power.enter_soft_sleep()
        print("Operation complete.")

if __name__ == "__main__":
    main()
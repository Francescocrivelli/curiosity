import time
import random
from pysphero.core import Sphero
from pysphero.driving import Direction
import threading

# Regular Sphero MAC address
MAC_ADDRESS = "C9:B9:61:72:CB:78"

# Callback to handle sensor notifications
def sensor_callback(response):
    """Callback function to process sensor data"""
    print(f"Sensor data received: {response}")

def main():
    with Sphero(mac_address=MAC_ADDRESS) as sphero:
        print("Waking up Sphero...", flush=True)
        sphero.power.wake()
        time.sleep(2)  # Give the ball time to wake up
        
        # Get the sensor object
        sensor = sphero.sensor
        
        # Based on the signature we discovered:
        # set_notify(callback: Callable, *sensors: Type[pysphero.device_api.sensor._Sensor], interval: int = 250, count: int = 0, timeout: float = 1)
        
        print("\n--- Setting up sensor notifications ---")
        try:
            # We need to import the sensor types from pysphero
            from pysphero.device_api.sensor import _Sensor
            
            # Let's try to find available sensor classes
            from pysphero.device_api.sensor import Sensor as SensorModule
            
            # Look for sensor classes in the module
            sensor_classes = []
            for attr_name in dir(SensorModule):
                if attr_name.startswith('_') or attr_name == 'Sensor':
                    continue
                attr = getattr(SensorModule, attr_name)
                try:
                    # Check if it's a subclass of _Sensor
                    if isinstance(attr, type) and issubclass(attr, _Sensor):
                        sensor_classes.append((attr_name, attr))
                except TypeError:
                    # Not a class
                    pass
            
            print(f"Found sensor classes: {[name for name, _ in sensor_classes]}")
            
            # Set up notifications for all available sensors
            if sensor_classes:
                print("Setting up notifications for all sensors...")
                # Use all sensor classes as arguments
                sensor_types = [cls for _, cls in sensor_classes]
                
                # Set up notifications with a faster interval (100ms)
                sensor.set_notify(sensor_callback, *sensor_types, interval=100, count=0, timeout=2.0)
                
                print("Notifications set up. Starting driving pattern...")
                
                # Drive in different patterns to generate sensor data
                for i in range(10):
                    # Alternate between different movement patterns
                    if i % 3 == 0:
                        # Straight line
                        speed = 60
                        heading = random.randint(0, 359)
                        print(f"Driving straight with heading {heading}°")
                        sphero.driving.drive_with_heading(speed, heading, Direction.forward)
                    elif i % 3 == 1:
                        # Spin in place
                        for angle in range(0, 361, 45):
                            sphero.driving.drive_with_heading(40, angle, Direction.forward)
                            time.sleep(0.2)
                    else:
                        # Random movements
                        for j in range(3):
                            speed = random.randint(40, 80)
                            heading = random.randint(0, 359)
                            sphero.driving.drive_with_heading(speed, heading, Direction.forward)
                            time.sleep(0.5)
                    
                    # Print ambient light sensor (which we know works) for comparison
                    light = sensor.get_ambient_light_sensor_value()
                    print(f"Ambient light: {light}")
                    
                    # Wait a bit to collect sensor data
                    time.sleep(1)
                
                # Cancel notifications
                print("Cancelling notifications...")
                sensor.cancel_notify_sensors()
            else:
                print("No sensor classes found. Trying direct approach...")
                
                # If we couldn't find sensor classes, try using the notify method directly
                # Based on the error message: notify() missing 2 required positional arguments: 'command_id' and 'callback'
                
                # Check for any common sensor command IDs
                for command_id in [0x01, 0x02, 0x11, 0x18, 0x20, 0x22, 0x30]:
                    try:
                        print(f"Trying notify with command_id 0x{command_id:02X}...")
                        sensor.notify(command_id, sensor_callback)
                        
                        # Drive to generate sensor data
                        speed = 60
                        heading = random.randint(0, 359)
                        sphero.driving.drive_with_heading(speed, heading, Direction.forward)
                        
                        # Wait for potential callbacks
                        time.sleep(2)
                        
                        # Cancel notification
                        sensor.cancel_notify(command_id)
                    except Exception as e:
                        print(f"Error with command 0x{command_id:02X}: {e}")
                
        except Exception as e:
            print(f"Error setting up notifications: {e}")
        
        # One last approach - try to use the request method directly
        print("\n--- Trying direct sensor commands ---")
        try:
            # Based on our findings, request is a bound method of the sensor object
            # Common approach is to send a command ID and data to start sensor streaming
            
            # Try different command IDs for enabling sensor streaming
            streaming_command_ids = [0x11, 0x18, 0x20, 0x30]
            streaming_data = [
                # [mask1, mask2, packet_count, interval]
                [0xFF, 0xFF, 0x00, 0x0A],  # All sensors, continuous streaming, 10ms interval
                [0x03, 0x00, 0x00, 0x0A],  # Just accelerometer, continuous streaming, 10ms interval
                [0x0C, 0x00, 0x00, 0x0A]   # Just gyroscope, continuous streaming, 10ms interval
            ]
            
            for cmd_id in streaming_command_ids:
                for data in streaming_data:
                    try:
                        print(f"Sending command 0x{cmd_id:02X} with data {data}...")
                        # The correct way to call request would likely be:
                        response = sensor.request(cmd_id, data)
                        print(f"Response: {response}")
                        
                        # Drive to generate sensor data
                        sphero.driving.drive_with_heading(60, random.randint(0, 359), Direction.forward)
                        
                        # Check streaming mask to see if anything changed
                        mask = sensor.get_sensor_streaming_mask()
                        print(f"Sensor streaming mask: {mask}")
                        
                        # Wait a moment to see if we get any data
                        time.sleep(2)
                    except Exception as e:
                        print(f"Error with command 0x{cmd_id:02X} and data {data}: {e}")
        except Exception as e:
            print(f"Error with direct commands: {e}")
        
        print("\nEntering soft sleep...")
        sphero.power.enter_soft_sleep()
        print("Operation complete.")

if __name__ == "__main__":
    main()
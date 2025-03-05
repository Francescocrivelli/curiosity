import time
import random
from pysphero.core import Sphero
from pysphero.driving import Direction
from pysphero.device_api.sensor import SensorCommand, Accelerometer, Gyroscope, Attitude

# Sphero MAC address
MAC_ADDRESS = "C9:B9:61:72:CB:78"

# Callback function for sensor notifications
def sensor_callback(response):
    """Process sensor data received from Sphero"""
    print(f"Sensor data received: {response}")
    # Try to extract useful information from the response
    try:
        if hasattr(response, 'data'):
            print(f"Data: {response.data}")
    except Exception as e:
        print(f"Error processing sensor data: {e}")

def main():
    with Sphero(mac_address=MAC_ADDRESS) as sphero:
        print("Waking up Sphero...", flush=True)
        sphero.power.wake()
        time.sleep(2)  # Give the ball time to wake up
        
        # Get the sensor object
        sensor = sphero.sensor
        print(f"Sensor object ready: {sensor is not None}")
        
        # Now we'll use the proper enum objects instead of raw integers
        try:
            print("\n--- Setting up sensor streaming ---")
            
            # First, let's check the current sensor streaming mask
            mask = sensor.get_sensor_streaming_mask()
            print(f"Initial sensor streaming mask: {mask}")
            
            # Try to set up notifications for accelerometer and gyroscope
            print("Setting up notifications for accelerometer and gyroscope...")
            sensor.set_notify(
                sensor_callback,  # Our callback function
                Accelerometer,    # Accelerometer sensor class
                Gyroscope,        # Gyroscope sensor class
                interval=100,     # 100ms interval (10Hz)
                count=0,          # Continuous streaming (0 = no limit)
                timeout=1.0       # Timeout for setting up notifications
            )
            
            print("Notifications set up. Starting motion patterns to generate sensor data...")
            
            # Drive the Sphero in different patterns to generate sensor data
            for i in range(15):
                if i % 3 == 0:
                    # Drive in a straight line
                    heading = (i * 30) % 360  # Change direction each time
                    speed = 50
                    print(f"Driving straight with heading {heading}°")
                    sphero.driving.drive_with_heading(speed, heading, Direction.forward)
                
                elif i % 3 == 1:
                    # Spin in place
                    print("Spinning in place")
                    for angle in range(0, 361, 60):
                        sphero.driving.drive_with_heading(40, angle, Direction.forward)
                        time.sleep(0.3)
                
                else:
                    # Random movement
                    speed = random.randint(40, 80)
                    heading = random.randint(0, 359)
                    print(f"Random movement: speed={speed}, heading={heading}°")
                    sphero.driving.drive_with_heading(speed, heading, Direction.forward)
                
                # Check the ambient light sensor for comparison
                light = sensor.get_ambient_light_sensor_value()
                print(f"Ambient light: {light}")
                
                # Check current sensor mask to see if it changed
                mask = sensor.get_sensor_streaming_mask()
                print(f"Current sensor mask: {mask}")
                
                # Wait to collect data
                time.sleep(1)
            
            # Cancel sensor notifications
            print("\nCancelling sensor notifications...")
            sensor.cancel_notify_sensors()
            
            # Try direct requests using the proper command enums
            print("\n--- Trying direct sensor requests ---")
            
            # Try to get ambient light using the proper command enum
            try:
                print("Getting ambient light sensor value using command enum...")
                response = sensor.request(SensorCommand.get_ambient_light_sensor_value)
                print(f"Response: {response}")
                if hasattr(response, 'data'):
                    print(f"Light data: {response.data}")
            except Exception as e:
                print(f"Error with ambient light request: {e}")
            
            # Try to check sensor streaming mask using the proper command enum
            try:
                print("Getting sensor streaming mask using command enum...")
                response = sensor.request(SensorCommand.get_sensor_streaming_mask)
                print(f"Response: {response}")
                if hasattr(response, 'data'):
                    print(f"Mask data: {response.data}")
            except Exception as e:
                print(f"Error with mask request: {e}")
            
            # Try to reset locator using the proper command enum
            try:
                print("Resetting locator using command enum...")
                response = sensor.request(SensorCommand.reset_locator)
                print(f"Response: {response}")
            except Exception as e:
                print(f"Error with reset locator request: {e}")
            
            # Try to use the gyro_max_async command
            try:
                print("Trying gyro_max_async command...")
                response = sensor.request(SensorCommand.gyro_max_async)
                print(f"Response: {response}")
            except Exception as e:
                print(f"Error with gyro_max_async request: {e}")
            
        except Exception as e:
            print(f"Error with sensor operations: {e}")
        
        print("\nEntering soft sleep...")
        sphero.power.enter_soft_sleep()
        print("Operation complete.")

if __name__ == "__main__":
    main()
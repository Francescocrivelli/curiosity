import time
import signal
import random
import sys
from pysphero.core import Sphero
from pysphero.driving import Direction

# Sphero MAC address
MAC_ADDRESS = "C9:B9:61:72:CB:78"

# Speed settings
MAX_SPEED = 255  # Maximum speed value for Sphero
CONNECTION_RETRY_DELAY = 5  # Seconds between connection attempts

# Global variable to control execution
running = True

def signal_handler(sig, frame):
    """Handle Ctrl+C to gracefully stop"""
    global running
    print("\nStopping...")
    running = False

def run_continuous_movement():
    """Main function to keep Sphero moving with random direction and duration"""
    global running
    
    signal.signal(signal.SIGINT, signal_handler)
     
    commands_sent = 0
    start_time = time.time()
    last_status_time = start_time
    last_movement_change = start_time
    movement_duration = random.uniform(0.2, 1)  # Random duration between 2-8 seconds
    speed = random.randint(100, MAX_SPEED)
    current_heading = random.randint(0, 359)
    
    print(f"Starting random movement mode...")
    print(f"Press Ctrl+C to stop")
    
    # Main loop - reconnect on failure
    while running:
        try:
            # Use context manager to properly handle connection
            print(f"Connecting to Sphero...")
            with Sphero(mac_address=MAC_ADDRESS) as sphero:
                print("Connected! Waking up Sphero...")
                sphero.power.wake()
                time.sleep(0.5)  # Brief pause after waking
                
                # Initial command
                print(f"Setting initial movement: heading={current_heading}°, speed={speed}")
                sphero.driving.drive_with_heading(speed, current_heading, Direction.forward)
                commands_sent += 1
                
                # Command loop
                while running:
                    try:
                        current_time = time.time()
                        
                        # Change direction, speed and set new duration randomly
                        if current_time - last_movement_change >= movement_duration:
                            speed = random.randint(100, MAX_SPEED)
                            current_heading = random.randint(0, 359)
                            movement_duration = random.uniform(0.3, 1)  # Random duration between 2-8 seconds
                            print(f"New movement: heading={current_heading}°, speed={speed}, duration={movement_duration:.1f}s")
                            last_movement_change = current_time
                        
                        # Send command
                        sphero.driving.drive_with_heading(speed, current_heading, Direction.forward)
                        commands_sent += 1
                        
                        # Print status periodically
                        if current_time - last_status_time >= 5:
                            elapsed = int(current_time - start_time)
                            minutes, seconds = divmod(elapsed, 60)
                            cmd_rate = commands_sent / elapsed if elapsed > 0 else 0
                            print(f"Running for {minutes}m {seconds}s - Commands sent: {commands_sent} (avg {cmd_rate:.1f}/sec)")
                            last_status_time = current_time
                        
                        # Brief delay to prevent overwhelming the connection
                        time.sleep(0.2)
                        
                    except Exception as e:
                        print(f"Command error: {e}")
                        break  # Break inner loop to reconnect
                
                # Context manager will automatically clean up the connection
                print("Sphero connection closed. Attempting to reconnect...")
                
        except Exception as e:
            print(f"Connection error: {e}")
        
        # Only retry if still running
        if running:
            print(f"Will retry in {CONNECTION_RETRY_DELAY} seconds...")
            time.sleep(CONNECTION_RETRY_DELAY)

if __name__ == "__main__":
    try:
        run_continuous_movement()
    except KeyboardInterrupt:
        pass
    finally:
        print("Program terminated")

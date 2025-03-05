import asyncio
import binascii
import struct
import sys
import time
from typing import List, Optional

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("Please install bleak: pip install bleak")
    sys.exit(1)

# Sphero BOLT+ MAC address
MAC_ADDRESS = "DB:05:9F:7B:8B:B8"

# Known Sphero BLE UUIDs - these may need adjustments for BOLT+
SPHERO_SERVICE_UUID = "00010001-574f-4f20-5370-6865726f2121"
API_V2_CHARACTERISTIC_UUID = "00010002-574f-4f20-5370-6865726f2121"  # For commands
ANTI_DOS_CHARACTERISTIC_UUID = "00020005-574f-4f20-5370-6865726f2121"  # Anti-DOS
RESPONSE_CHARACTERISTIC_UUID = "00010003-574f-4f20-5370-6865726f2121"  # For responses

# Sphero API command IDs
CMD_WAKE = 0x0D
CMD_SLEEP = 0x0E
CMD_DRIVE = 0x30
CMD_ENABLE_SENSORS = 0x18  # This may vary for BOLT+
CMD_SET_HEADING = 0x05

class SpheroBLEAK:
    def __init__(self, address: str):
        self.address = address
        self.client = None
        self.is_connected = False
        self.sequence = 0
        
        # Buffer for notifications
        self.notification_buffer = []
        
    async def connect(self):
        """Connect to the Sphero device."""
        print(f"Connecting to {self.address}...")
        
        try:
            # Find the device
            device = await BleakScanner.find_device_by_address(self.address)
            if not device:
                raise Exception(f"Device {self.address} not found")
            
            # Connect to device
            self.client = BleakClient(device)
            await self.client.connect()
            self.is_connected = True
            print(f"Connected to {self.address}")
            
            # Set up notification handler
            await self.client.start_notify(
                RESPONSE_CHARACTERISTIC_UUID, 
                self.notification_handler
            )
            
            # Try Anti-DOS characteristic if available
            try:
                # The Anti-DOS sequence is typically a handshake required before commands
                await self.client.write_gatt_char(
                    ANTI_DOS_CHARACTERISTIC_UUID,
                    b"usetheforce...band"
                )
                print("Anti-DOS sequence sent")
            except Exception as e:
                print(f"Anti-DOS handshake failed: {e}")
                print("Continuing anyway - some models don't require this")
            
            return True
            
        except Exception as e:
            print(f"Connection error: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from the Sphero device."""
        if self.client and self.is_connected:
            await self.client.disconnect()
            self.is_connected = False
            print(f"Disconnected from {self.address}")
    
    def notification_handler(self, sender, data):
        """Handle notifications from the Sphero device."""
        print(f"Received notification: {binascii.hexlify(data).decode()}")
        
        # Parse the notification data
        try:
            # This parsing is a simplified example and may need adjustments
            # Sphero typically uses a packet format: [flags, id, seq, ...]
            if len(data) >= 4:
                flags = data[0]
                command_id = data[1]
                sequence = data[2]
                payload = data[3:]
                
                print(f"Flags: {flags:02X}, Command ID: {command_id:02X}, Seq: {sequence:02X}")
                print(f"Payload: {binascii.hexlify(payload).decode()}")
                
                # Store in buffer for async retrieval
                self.notification_buffer.append({
                    'flags': flags,
                    'command_id': command_id,
                    'sequence': sequence,
                    'payload': payload,
                    'raw': data
                })
        except Exception as e:
            print(f"Error parsing notification: {e}")
    
    async def send_command(self, cmd_id: int, data: List[int] = None) -> bool:
        """Send a command to the Sphero device."""
        if not self.is_connected or not self.client:
            print("Not connected")
            return False
        
        data = data or []
        
        # Sphero API V2 packet format:
        # [0] Flags (typically 0x8D for API V2 requests)
        # [1] Command ID
        # [2] Sequence number
        # [3+] Data bytes
        
        packet = bytearray([0x8D, cmd_id, self.sequence & 0xFF] + data)
        self.sequence = (self.sequence + 1) % 256
        
        try:
            print(f"Sending command: {binascii.hexlify(packet).decode()}")
            await self.client.write_gatt_char(API_V2_CHARACTERISTIC_UUID, packet)
            return True
        except Exception as e:
            print(f"Error sending command: {e}")
            return False
    
    async def wake(self):
        """Wake up the Sphero."""
        print("Waking up Sphero...")
        return await self.send_command(CMD_WAKE)
    
    async def sleep(self):
        """Put the Sphero to sleep."""
        print("Putting Sphero to sleep...")
        return await self.send_command(CMD_SLEEP)
    
    async def set_heading(self, heading: int):
        """Set the heading of the Sphero (0-359 degrees)."""
        # Convert heading to bytes (16-bit value)
        heading_bytes = list(heading.to_bytes(2, byteorder='big'))
        return await self.send_command(CMD_SET_HEADING, heading_bytes)
    
    async def drive(self, speed: int, heading: int):
        """Drive the Sphero with the given speed and heading."""
        # Speed is 8-bit (0-255), heading is 16-bit (0-359)
        if speed < 0 or speed > 255:
            speed = max(0, min(255, speed))
        
        heading = heading % 360
        data = [speed] + list(heading.to_bytes(2, byteorder='big')) + [1]  # 1 = forward
        
        print(f"Driving: speed={speed}, heading={heading}")
        return await self.send_command(CMD_DRIVE, data)
    
    async def enable_sensors(self):
        """Enable sensor streaming."""
        print("Enabling sensor streaming...")
        # This is a simplified example - the actual parameters may need adjustment
        # Typically includes a mask of sensors to enable, interval, etc.
        # Example: Enable accelerometer + gyroscope
        sensor_mask = [0xFF, 0xFF]  # Enable all possible sensors as a test
        interval = [0x0A]  # ~100ms update rate
        count = [0x00]  # Continuous streaming
        
        return await self.send_command(CMD_ENABLE_SENSORS, sensor_mask + interval + count)
    
    async def get_device_info(self):
        """Query the device for available services and characteristics."""
        if not self.is_connected or not self.client:
            print("Not connected")
            return
            
        print("\nDevice Information:")
        print("-------------------")
        
        # Get all services
        services = self.client.services
        for service in services:
            print(f"Service: {service.uuid}")
            for char in service.characteristics:
                props = []
                # In bleak, properties is a list of strings, not a bit mask
                if "read" in char.properties:
                    props.append("READ")
                if "write" in char.properties or "write-without-response" in char.properties:
                    props.append("WRITE")
                if "notify" in char.properties:
                    props.append("NOTIFY")
                
                print(f"  Characteristic: {char.uuid}")
                print(f"    Properties: {', '.join(props)}")
                print(f"    Handle: {char.handle}")
                
                # Try to read characteristics with read property
                if "read" in char.properties:
                    try:
                        value = await self.client.read_gatt_char(char.uuid)
                        print(f"    Value: {binascii.hexlify(value).decode()}")
                    except Exception as e:
                        print(f"    Could not read: {e}")
        
        print("-------------------")

async def main():
    # Create Sphero instance
    sphero = SpheroBLEAK(MAC_ADDRESS)
    
    try:
        # Connect to the Sphero
        if await sphero.connect():
            # Get device information
            await sphero.get_device_info()
            
            # Wake up the Sphero
            await sphero.wake()
            await asyncio.sleep(2)  # Wait for it to wake up
            
            # Try to enable sensors
            await sphero.enable_sensors()
            print("Listening for sensor data for 10 seconds...")
            
            # Listen for notifications for a few seconds
            for i in range(10):
                print(f"Listening... ({i+1}/10)")
                await asyncio.sleep(1)
                
                # Send some drive commands to generate sensor data
                if i % 2 == 0:
                    heading = (i * 45) % 360
                    await sphero.drive(50, heading)
            
            # Put the Sphero to sleep
            await sphero.sleep()
            
        # Disconnect
        await sphero.disconnect()
        
    except Exception as e:
        print(f"Error: {e}")
        # Ensure we disconnect
        try:
            await sphero.disconnect()
        except:
            pass

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
import asyncio
import binascii
import struct
import sys
from bleak import BleakClient, BleakScanner

# Sphero BOLT+ MAC address
MAC_ADDRESS = "DB:05:9F:7B:8B:B8"

# These are common Sphero UUIDs - they might be different for the BOLT+
# We'll scan and discover the actual UUIDs used by your device
SPHERO_API_V2_CHARACTERISTIC = "00010002-574f-4f20-5370-6865726f2121"
SPHERO_NOTIFY_CHARACTERISTIC = "00010003-574f-4f20-5370-6865726f2121"

# Common Sphero protocol command IDs (based on public documentation and reverse engineering)
CMD_WAKE = 0x13
CMD_SLEEP = 0x22
CMD_ENABLE_SENSOR_STREAMING = 0x3A  # This may vary by model

async def scan_for_device():
    """Scan for Sphero device with the given MAC address."""
    print(f"Scanning for Sphero BOLT+ ({MAC_ADDRESS})...")
    device = await BleakScanner.find_device_by_address(MAC_ADDRESS)
    if not device:
        print(f"Device {MAC_ADDRESS} not found")
        return None
    return device

async def explore_device():
    """Connect to the device and explore its services and characteristics."""
    device = await scan_for_device()
    if not device:
        return
    
    print(f"Connecting to {device.address}...")
    
    client = None
    try:
        client = BleakClient(device)
        await client.connect()
        print(f"Connected to {device.address}")
        
        # Explore all services and characteristics
        print("\n--- Services and Characteristics ---")
        services = client.services
        potential_write_chars = []
        potential_notify_chars = []
        
        for service in services:
            print(f"Service: {service.uuid}")
            for char in service.characteristics:
                print(f"  Characteristic: {char.uuid}")
                print(f"    Properties: {', '.join(char.properties)}")
                
                # Keep track of characteristics we can write to or get notifications from
                if "write" in char.properties or "write-without-response" in char.properties:
                    potential_write_chars.append(char.uuid)
                if "notify" in char.properties:
                    potential_notify_chars.append(char.uuid)
                
                # Try to read if possible
                if "read" in char.properties:
                    try:
                        value = await client.read_gatt_char(char.uuid)
                        if value:
                            print(f"    Value: {binascii.hexlify(value).decode()}")
                    except Exception as e:
                        print(f"    Could not read: {e}")
        
        print("\n--- Potential Command (Write) Characteristics ---")
        for i, char_uuid in enumerate(potential_write_chars):
            print(f"{i+1}. {char_uuid}")
        
        print("\n--- Potential Notification Characteristics ---")
        for i, char_uuid in enumerate(potential_notify_chars):
            print(f"{i+1}. {char_uuid}")
        
        # Try to find the most likely API characteristic
        api_char = None
        for char_uuid in potential_write_chars:
            if "1002" in char_uuid.lower() or "2121" in char_uuid.lower():
                print(f"\nFound likely API characteristic: {char_uuid}")
                api_char = char_uuid
                break
        
        if not api_char and potential_write_chars:
            api_char = potential_write_chars[0]
            print(f"\nUsing first available write characteristic: {api_char}")
        
        # Try to find the most likely notification characteristic
        notify_char = None
        for char_uuid in potential_notify_chars:
            if "1003" in char_uuid.lower() or "2121" in char_uuid.lower():
                print(f"Found likely notification characteristic: {char_uuid}")
                notify_char = char_uuid
                break
        
        if not notify_char and potential_notify_chars:
            notify_char = potential_notify_chars[0]
            print(f"Using first available notification characteristic: {notify_char}")
        
        # If we found both characteristics, try to wake the Sphero and enable sensors
        if api_char and notify_char:
            # Set up notification handler
            def notification_handler(sender, data):
                print(f"Notification: {binascii.hexlify(data).decode()}")
                try:
                    # Try to interpret as sensor data (format may vary)
                    print(f"Data length: {len(data)}")
                    if len(data) >= 4:  # Basic header + some data
                        print(f"Packet type: {data[0]:02X}")
                        print(f"Command ID: {data[1]:02X}")
                        print(f"Sequence: {data[2]:02X}")
                        print(f"Payload: {binascii.hexlify(data[3:]).decode()}")
                        
                        # Try to interpret as sensor data if it seems to be the right format
                        if len(data) > 10 and data[1] in [0x3A, 0x3B, 0x3C]:  # Common sensor response IDs
                            try:
                                # This is a guess at the format - adjust based on actual data
                                offset = 4  # Skip header
                                if len(data) >= offset + 12:  # Check if we have enough data for 3 sensor readings (4 bytes each)
                                    # Try to parse as accelerometer data (typically first 3 float values)
                                    accel_x = struct.unpack('!f', data[offset:offset+4])[0]
                                    accel_y = struct.unpack('!f', data[offset+4:offset+8])[0]
                                    accel_z = struct.unpack('!f', data[offset+8:offset+12])[0]
                                    print(f"Possible Accelerometer: X={accel_x:.2f}, Y={accel_y:.2f}, Z={accel_z:.2f}")
                                
                                # If there's even more data, try to parse as gyroscope
                                if len(data) >= offset + 24:  # 3 more values for gyro
                                    gyro_x = struct.unpack('!f', data[offset+12:offset+16])[0]
                                    gyro_y = struct.unpack('!f', data[offset+16:offset+20])[0]
                                    gyro_z = struct.unpack('!f', data[offset+20:offset+24])[0]
                                    print(f"Possible Gyroscope: X={gyro_x:.2f}, Y={gyro_y:.2f}, Z={gyro_z:.2f}")
                            except Exception as e:
                                print(f"Error parsing sensor data: {e}")
                except Exception as e:
                    print(f"Error processing notification: {e}")
            
            # Start notifications
            print("\nSetting up notifications...")
            await client.start_notify(notify_char, notification_handler)
            
            # Send wake command
            print("\nSending wake command...")
            sequence = 0
            # Sphero packet format: [flags, command_id, sequence, data...]
            wake_packet = bytearray([0x8D, CMD_WAKE, sequence])
            await client.write_gatt_char(api_char, wake_packet)
            sequence = (sequence + 1) % 256
            await asyncio.sleep(2)  # Give time to wake up
            
            # Try a few different sensor streaming commands
            print("\nTrying to enable sensor streaming...")
            
            # Try several different common sensor enable commands
            sensor_commands = [
                # CMD ID, data bytes (usually a mask of which sensors to enable)
                (0x3A, [0xFF, 0xFF, 0x00, 0x01]),  # Common sensor streaming command
                (0x18, [0x01, 0x01, 0x0A, 0x00]),  # Alternative format
                (0x11, [0x07, 0x00, 0x01, 0x01])   # Another alternative
            ]
            
            for cmd_id, data in sensor_commands:
                print(f"\nTrying sensor command 0x{cmd_id:02X} with data {data}...")
                try:
                    packet = bytearray([0x8D, cmd_id, sequence] + data)
                    await client.write_gatt_char(api_char, packet)
                    sequence = (sequence + 1) % 256
                    print("Command sent, listening for 5 seconds...")
                    await asyncio.sleep(5)  # Listen for notifications
                except Exception as e:
                    print(f"Error sending command: {e}")
            
            # Send a drive command to generate sensor data
            try:
                print("\nSending drive command to generate sensor data...")
                # Drive command: [flags, cmd_id, seq, speed, heading_msb, heading_lsb, flags]
                drive_cmd = 0x30  # Common drive command
                speed = 50
                heading = 90
                heading_bytes = heading.to_bytes(2, byteorder='big')
                drive_packet = bytearray([0x8D, drive_cmd, sequence, speed, heading_bytes[0], heading_bytes[1], 1])
                await client.write_gatt_char(api_char, drive_packet)
                sequence = (sequence + 1) % 256
                print("Drive command sent, listening for 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"Error sending drive command: {e}")
            
            # Stop notifications
            print("\nStopping notifications...")
            await client.stop_notify(notify_char)
            
            # Send sleep command
            print("\nSending sleep command...")
            sleep_packet = bytearray([0x8D, CMD_SLEEP, sequence])
            await client.write_gatt_char(api_char, sleep_packet)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if client and client.is_connected:
            await client.disconnect()
            print("Disconnected")

if __name__ == "__main__":
    asyncio.run(explore_device())
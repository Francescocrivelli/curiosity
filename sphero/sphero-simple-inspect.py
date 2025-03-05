import time
import inspect
import pysphero
from pysphero.core import Sphero
from pysphero.driving import Direction

# Prevent recursion by tracking visited modules
visited_modules = set()

def inspect_module(module, prefix="", max_depth=2, current_depth=0):
    """Inspect a module for enums and classes with limited recursion"""
    if current_depth > max_depth or module in visited_modules:
        return []
    
    visited_modules.add(module)
    results = []
    
    for name in dir(module):
        if name.startswith("_"):
            continue
        
        try:
            attr = getattr(module, name)
            full_name = f"{prefix}.{name}" if prefix else name
            
            # Check if it's an enum
            if hasattr(attr, "__members__"):
                members = {}
                for member_name, member_value in attr.__members__.items():
                    try:
                        value_attr = getattr(member_value, "value", "N/A")
                        members[member_name] = value_attr
                    except:
                        members[member_name] = "Error getting value"
                
                results.append((full_name, "ENUM", members))
            
            # Check if it's a class with value attributes
            elif inspect.isclass(attr):
                value_attrs = {}
                for class_attr in dir(attr):
                    if class_attr.startswith("_"):
                        continue
                    try:
                        class_attr_value = getattr(attr, class_attr)
                        if hasattr(class_attr_value, "value"):
                            value_attrs[class_attr] = getattr(class_attr_value, "value")
                    except:
                        pass
                
                if value_attrs:
                    results.append((full_name, "CLASS_WITH_VALUES", value_attrs))
            
            # Check if it's a module for recursion
            elif inspect.ismodule(attr) and current_depth < max_depth:
                # Only recurse into pysphero modules to avoid excessive scanning
                if attr.__name__.startswith('pysphero'):
                    results.extend(inspect_module(attr, full_name, max_depth, current_depth + 1))
        except:
            # Skip any attributes that cause errors
            pass
    
    return results

def main():
    print("Connecting to Sphero...")
    with Sphero(mac_address="C9:B9:61:72:CB:78") as sphero:
        print("Sphero connected")
        sphero.power.wake()
        time.sleep(2)
        
        # First, check direct sensor module
        print("\n=== CHECKING SENSOR MODULE ===")
        from pysphero.device_api import sensor as sensor_module
        
        print("Sensor module attributes:")
        for name in dir(sensor_module):
            if name.startswith("_"):
                continue
                
            try:
                attr = getattr(sensor_module, name)
                attr_type = type(attr).__name__
                
                # If it's a class, check for 'value' attributes
                if inspect.isclass(attr):
                    print(f"Class: {name} ({attr_type})")
                    value_attrs = []
                    for class_attr in dir(attr):
                        if class_attr.startswith("_"):
                            continue
                        try:
                            class_attr_value = getattr(attr, class_attr)
                            if hasattr(class_attr_value, "value"):
                                value = getattr(class_attr_value, "value")
                                value_attrs.append(f"  - {class_attr}: value={value}")
                        except:
                            pass
                    
                    if value_attrs:
                        print("\n".join(value_attrs))
                        print()
                
                # If it's an enum, show its members and values
                elif hasattr(attr, "__members__"):
                    print(f"Enum: {name}")
                    for member_name, member_value in attr.__members__.items():
                        value = getattr(member_value, "value", "N/A")
                        print(f"  - {member_name}: value={value}")
                    print()
            except Exception as e:
                print(f"Error with {name}: {e}")
        
        # Examine sensor object directly
        print("\n=== EXAMINING SPHERO.SENSOR OBJECT ===")
        sensor = sphero.sensor
        print(f"Sensor class: {sensor.__class__.__name__}")
        
        # Check direct methods
        print("\nMethods:")
        for name in dir(sensor):
            if name.startswith("_"):
                continue
            
            try:
                attr = getattr(sensor, name)
                if callable(attr):
                    sig = inspect.signature(attr)
                    print(f"  {name}{sig}")
            except Exception as e:
                print(f"  {name}: Error getting signature - {e}")
        
        # Try to find sample code or hints in docstrings
        print("\nChecking for documentation hints...")
        if sensor.__doc__:
            print(f"Sensor class docstring: {sensor.__doc__}")
        
        for name in dir(sensor.__class__):
            if name.startswith("_") or name not in ["request", "notify", "set_notify"]:
                continue
                
            method = getattr(sensor.__class__, name)
            if method.__doc__:
                print(f"\n{name} docstring:")
                print(method.__doc__)
        
        # Look for command IDs and sensor IDs
        print("\n=== SEARCHING FOR COMMAND AND SENSOR IDS ===")
        # Focus on modules that might contain command definitions
        important_modules = [
            pysphero.device_api.sensor,
            pysphero.device_api.command,
            pysphero.commands
        ]
        
        for module in important_modules:
            try:
                print(f"\nExamining module: {module.__name__}")
                
                # Look for command-related enums and classes
                for name in dir(module):
                    if name.startswith("_") or name in ["ABC", "abstractmethod"]:
                        continue
                    
                    try:
                        attr = getattr(module, name)
                        
                        # If it's an enum, show its members
                        if hasattr(attr, "__members__"):
                            print(f"Enum: {name}")
                            for member_name, member_value in attr.__members__.items():
                                value = getattr(member_value, "value", "N/A")
                                print(f"  - {member_name}: value={value}")
                            print()
                        
                        # If it's a class with command/sensor related name
                        elif inspect.isclass(attr) and any(keyword in name.lower() for keyword in ["command", "sensor", "api"]):
                            print(f"Class: {name}")
                            
                            # Check for value attributes
                            value_attrs = []
                            for class_attr in dir(attr):
                                if class_attr.startswith("_"):
                                    continue
                                try:
                                    class_attr_value = getattr(attr, class_attr)
                                    if hasattr(class_attr_value, "value"):
                                        value = getattr(class_attr_value, "value")
                                        value_attrs.append(f"  - {class_attr}: value={value}")
                                except:
                                    pass
                            
                            if value_attrs:
                                print("\n".join(value_attrs))
                                print()
                    except Exception as e:
                        print(f"Error with {name}: {e}")
            except Exception as e:
                print(f"Error examining module {module.__name__}: {e}")
        
        # Print a simple sensor test example based on what we found
        print("\n=== GENERATING TEST CODE BASED ON FINDINGS ===")
        print("Check the terminal output above for enum values to use in the following code:")
        print("""
# Example usage pattern based on findings:
from pysphero.core import Sphero
from pysphero.device_api.sensor import SensorCommandIds  # Replace with actual enum name if found

def sensor_callback(data):
    print(f"Sensor data: {data}")

with Sphero(mac_address="YOUR_MAC_ADDRESS") as sphero:
    sphero.power.wake()
    
    # Use actual command ID enum value found above
    # e.g., SensorCommandIds.ENABLE_GYROSCOPE instead of raw integer
    # sphero.sensor.set_notify(sensor_callback, SensorEnum.GYROSCOPE, interval=100)
    
    # Drive to generate sensor data
    sphero.driving.drive_with_heading(50, 90, Direction.forward)
    time.sleep(5)
""")
        
        print("\nEntering soft sleep...")
        sphero.power.enter_soft_sleep()
        print("Operation complete.")

if __name__ == "__main__":
    main()
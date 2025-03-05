import time
import inspect
import pysphero
from pysphero.core import Sphero
from pysphero.driving import Direction

# Regular Sphero MAC address
MAC_ADDRESS = "C9:B9:61:72:CB:78"

def inspect_module(module, prefix=""):
    """Recursively inspect a module for enums and classes that might be relevant"""
    results = []
    
    for name in dir(module):
        if name.startswith("_"):
            continue
        
        attr = getattr(module, name)
        full_name = f"{prefix}.{name}" if prefix else name
        
        # Check if it's an enum
        if hasattr(attr, "__members__"):
            results.append((full_name, "ENUM", attr, attr.__members__))
        
        # Check if it's a class
        elif inspect.isclass(attr):
            results.append((full_name, "CLASS", attr, None))
            
            # Look for value attributes in the class
            value_attrs = []
            for class_attr in dir(attr):
                if class_attr.startswith("_"):
                    continue
                try:
                    class_attr_value = getattr(attr, class_attr)
                    if hasattr(class_attr_value, "value"):
                        value_attrs.append((class_attr, class_attr_value, class_attr_value.value))
                except:
                    pass
            
            if value_attrs:
                results.append((full_name, "CLASS_WITH_VALUES", attr, value_attrs))
        
        # Check if it's a module
        elif inspect.ismodule(attr):
            # Recursively inspect submodules
            results.extend(inspect_module(attr, full_name))
    
    return results

def main():
    # First, let's inspect the entire pysphero library structure
    print("=== Inspecting pysphero library structure ===")
    print("Looking for command IDs, enums, and classes with value attributes...")
    
    results = inspect_module(pysphero)
    
    print("\n=== Enums and Classes with value attributes ===")
    for name, type_name, obj, details in results:
        if type_name in ["ENUM", "CLASS_WITH_VALUES"]:
            print(f"\n{type_name}: {name}")
            
            if type_name == "ENUM":
                for member_name, member_value in details.items():
                    member_value_attr = getattr(member_value, "value", "N/A")
                    print(f"  {member_name}: {member_value} (value={member_value_attr})")
            
            elif type_name == "CLASS_WITH_VALUES":
                for attr_name, attr_obj, value in details:
                    print(f"  {attr_name}: {attr_obj} (value={value})")
    
    # Now, let's connect to the Sphero and examine sensor-related objects
    print("\n\n=== Connecting to Sphero for further inspection ===")
    with Sphero(mac_address=MAC_ADDRESS) as sphero:
        print("Waking up Sphero...")
        sphero.power.wake()
        time.sleep(2)
        
        sensor = sphero.sensor
        print("\n=== Sensor object inspection ===")
        print(f"Type: {type(sensor)}")
        
        # Get all non-private attributes
        attrs = [a for a in dir(sensor) if not a.startswith("_")]
        print(f"Attributes: {attrs}")
        
        # Examine the request method in detail
        if hasattr(sensor, "request"):
            print("\n=== Request method inspection ===")
            request_method = sensor.request
            print(f"Method: {request_method}")
            try:
                signature = inspect.signature(request_method)
                print(f"Signature: {signature}")
                
                # Get source code if possible
                try:
                    source = inspect.getsource(request_method.__func__.__code__)
                    print("Source code:")
                    print(source)
                except Exception as e:
                    print(f"Could not get source: {e}")
            except Exception as e:
                print(f"Could not get signature: {e}")
        
        # Look for command ID enums within the sensor module
        print("\n=== Looking for command ID enums in sensor module ===")
        try:
            module = inspect.getmodule(sensor.__class__)
            print(f"Module: {module}")
            
            for name in dir(module):
                if name.startswith("_"):
                    continue
                
                attr = getattr(module, name)
                
                # Check if it might be a command ID enum
                if hasattr(attr, "__members__") or (inspect.isclass(attr) and "command" in name.lower()):
                    print(f"\nPotential command enum: {name}")
                    
                    # Check members for value attributes
                    for member_name in dir(attr):
                        if member_name.startswith("_"):
                            continue
                        
                        try:
                            member = getattr(attr, member_name)
                            if hasattr(member, "value"):
                                print(f"  {member_name}: {member} (value={member.value})")
                        except:
                            pass
        except Exception as e:
            print(f"Error inspecting sensor module: {e}")
        
        # Try to find the correct way to use request method by examining API_V2 constants
        print("\n=== Looking for API_V2 constants ===")
        api_v2_found = False
        for module_name in dir(pysphero):
            if module_name.startswith("_"):
                continue
            
            module_obj = getattr(pysphero, module_name)
            if not inspect.ismodule(module_obj):
                continue
            
            for name in dir(module_obj):
                if "api" in name.lower() and "v2" in name.lower():
                    api_v2_found = True
                    attr = getattr(module_obj, name)
                    print(f"Found API_V2 related: {module_name}.{name}")
                    
                    # Check if it has command IDs
                    for command_name in dir(attr):
                        if command_name.startswith("_"):
                            continue
                        
                        try:
                            command = getattr(attr, command_name)
                            if hasattr(command, "value"):
                                print(f"  {command_name}: {command} (value={command.value})")
                        except:
                            pass
        
        if not api_v2_found:
            print("No API_V2 constants found directly. Checking for any command IDs...")
            
            # Look for anything that might be a command ID
            for module_name in dir(pysphero):
                if module_name.startswith("_"):
                    continue
                
                module_obj = getattr(pysphero, module_name)
                if not inspect.ismodule(module_obj):
                    continue
                
                for name in dir(module_obj):
                    if name.startswith("_"):
                        continue
                    
                    try:
                        attr = getattr(module_obj, name)
                        if inspect.isclass(attr) and "command" in name.lower():
                            print(f"Potential command container: {module_name}.{name}")
                            
                            for cmd_name in dir(attr):
                                if cmd_name.startswith("_"):
                                    continue
                                
                                try:
                                    cmd = getattr(attr, cmd_name)
                                    if hasattr(cmd, "value"):
                                        print(f"  {cmd_name}: {cmd} (value={cmd.value})")
                                except:
                                    pass
                    except:
                        pass
        
        print("\nEntering soft sleep...")
        sphero.power.enter_soft_sleep()
        print("Operation complete.")

if __name__ == "__main__":
    main()
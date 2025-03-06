#!/usr/bin/env python3
"""
Camera Test Utility

This script tests the V4L2 camera that will be used in the data collection script.
It verifies:
1. Camera can be opened at index 0
2. Resolution and framerate settings work
3. Video can be captured and saved

Usage:
    python test_camera.py
"""

import cv2
import time
import os
import sys

# Camera settings
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30
TEST_DURATION = 5  # seconds

def test_camera():
    """Test if camera can be opened and capture video"""
    print(f"Testing camera at index {CAMERA_INDEX} with {CAMERA_WIDTH}x{CAMERA_HEIGHT} @ {CAMERA_FPS}fps")
    
    # Initialize camera
    cap = cv2.VideoCapture(CAMERA_INDEX)
    
    if not cap.isOpened():
        print("ERROR: Could not open camera")
        return False
        
    # Set camera properties
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
    
    # Check actual properties
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"Camera opened with resolution: {actual_width}x{actual_height} @ {actual_fps}fps")
    
    # Create output folder if it doesn't exist
    if not os.path.exists("test_output"):
        os.makedirs("test_output")
    
    # Create VideoWriter
    test_video_path = "test_output/camera_test.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(
        test_video_path, 
        fourcc, 
        actual_fps, 
        (actual_width, actual_height)
    )
    
    if not out.isOpened():
        print("ERROR: Could not create video writer")
        cap.release()
        return False
    
    # Capture frames for a few seconds
    start_time = time.time()
    frame_count = 0
    test_image_path = "test_output/camera_test_frame.jpg"
    
    print(f"Recording test video for {TEST_DURATION} seconds...")
    
    try:
        while (time.time() - start_time) < TEST_DURATION:
            ret, frame = cap.read()
            
            if not ret:
                print("ERROR: Could not read frame")
                break
                
            # Save first frame as an image
            if frame_count == 0:
                cv2.imwrite(test_image_path, frame)
                print(f"Saved test image to {test_image_path}")
                
                # Check image dimensions
                height, width, channels = frame.shape
                print(f"Captured image size: {width}x{height}")
            
            # Write frame to video
            out.write(frame)
            frame_count += 1
            
            # Simple progress indicator
            if frame_count % 10 == 0:
                elapsed = time.time() - start_time
                current_fps = frame_count / elapsed if elapsed > 0 else 0
                sys.stdout.write(f"\rRecorded {frame_count} frames ({current_fps:.1f} fps)")
                sys.stdout.flush()
    
    except Exception as e:
        print(f"\nERROR during recording: {e}")
        return False
        
    finally:
        # Clean up
        out.release()
        cap.release()
    
    # Final report
    elapsed = time.time() - start_time
    actual_fps = frame_count / elapsed if elapsed > 0 else 0
    
    print(f"\nTest complete! Recorded {frame_count} frames in {elapsed:.1f} seconds ({actual_fps:.1f} fps)")
    print(f"Test video saved to {test_video_path}")
    
    return frame_count > 0

def main():
    """Main function"""
    print("=== Camera Test Utility ===")
    
    if test_camera():
        print("\nSUCCESS: Camera test passed!")
        print("You can now run the sphero_move_and_collect.py script")
    else:
        print("\nFAILED: Camera test failed")
        print("Please check your camera connection and settings")

if __name__ == "__main__":
    main()
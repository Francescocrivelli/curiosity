# Sphero Data Collection

This repository contains scripts for controlling a Sphero robot and collecting data for model training.

## Scripts

### 1. unlimited_move.py
Continuous random movement control for the Sphero robot. The robot will move with random speed and direction changes.

### 2. sphero_move_and_collect.py
Runs unlimited_move.py as a separate process while recording video from a USB camera. This approach completely avoids interfering with the Sphero's movement patterns.

### 3. sphero_move_and_collect_with_sensors.py
This alternative script combines movement control AND sensor data collection. It collects:
- Accelerometer data (X, Y, Z) at 20Hz
- Gyroscope data (X, Y, Z) at 20Hz
- Video from USB camera (640x480 @ 30fps)

All data is synchronized with timestamps for later model training.

## Comparison of Approaches

| Feature | sphero_move_and_collect.py | sphero_move_and_collect_with_sensors.py |
|---------|----------------------------|----------------------------------------|
| Movement Control | Uses unlimited_move.py as-is | Reimplements movement logic |
| Video Recording | Yes | Yes |
| Sensor Data | No | Yes (20Hz) |
| Impact on Movement | None | Minimal impact |

## Key Features

### Video-Only Collection (sphero_move_and_collect.py)
- **Non-intrusive Design**: Runs unlimited_move.py in a separate process without modifying it
- **Video Recording**: Records timestamped video at configurable resolution
- **Timestamp Overlay**: Adds timestamps to video frames for easier analysis
- **Graceful Shutdown**: Properly handles termination to ensure data is saved

### Full Data Collection (sphero_move_and_collect_with_sensors.py)
- **Integrated Approach**: Combines movement control with sensor data collection
- **Low-Interference Design**: Uses carefully timed on-demand sensor requests
- **Synchronized Data**: All sensor data and video frames are timestamped
- **Automatic Backups**: Saves data periodically to prevent loss
- **Resilient Operation**: Isolates sensor errors to maintain movement quality

## Requirements

```
pysphero
opencv-python
numpy
```

## Installation

1. Install the required packages:
   ```
   pip install pysphero opencv-python numpy
   ```

2. Make sure your Sphero's MAC address is correctly set in the script you choose to run

3. Ensure your camera is properly connected and detected (index 0)

## Usage

1. Test your camera setup first:
   ```
   python test_camera.py
   ```

2. Choose which script to run:

   For video only (no sensor interference):
   ```
   python sphero_move_and_collect.py
   ```

   For video and sensor data (accelerometer/gyroscope):
   ```
   python sphero_move_and_collect_with_sensors.py
   ```

3. To stop data collection, press `Ctrl+C`. The script will gracefully stop all processes and save the collected data.

## Data Output

Data is saved to a timestamped directory under `collected_data/run_YYYYMMDD_HHMMSS/` and includes:

- `video.mp4`: Camera recording with timestamps
- `sensor_data.csv`: Accelerometer and gyroscope readings (if using the _with_sensors version)
- `metadata.json`: Information about the data collection session
- `backup_sensor_data.csv`: Automatic periodic backup (if using the _with_sensors version)

## How Sensor Collection Works

In `sphero_move_and_collect_with_sensors.py`, sensor data is collected by:

1. Using on-demand sensor requests rather than continuous streaming
2. Timing the requests to occur at approximately 20Hz
3. Carefully timed to avoid interfering with movement commands
4. Using a shorter sleep interval (0.05s vs 0.2s) compared to the original unlimited_move.py

This approach minimizes the impact on the Sphero's movement patterns while still collecting sensor data.

## Troubleshooting

- If the camera doesn't work, verify it's connected and check the camera index
- Make sure the Sphero is charged and within Bluetooth range
- If you encounter Bluetooth connection issues, try using the video-only version
- If sensor data collection seems to affect movement, try reducing SENSOR_FREQUENCY to 10Hz

## Technical Notes

- The script launches unlimited_move.py as a subprocess and captures its output
- Video recording runs independently from the Sphero movement
- This approach prioritizes preserving the original movement behavior over collecting sensor data

## Notes

- The data collection runs in separate threads so it doesn't interfere with the Sphero movement
- Video and sensor data are synchronized using timestamps
- All data collection is performed in background threads, preserving the original movement behavior 
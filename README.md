# Sphero Data Collection

This repository contains scripts for controlling a Sphero robot and collecting synchronized sensor and video data for model training.

## Scripts

### 1. unlimited_move.py
Continuous random movement control for the Sphero robot. The robot will move with random speed and direction changes.

### 2. sphero_move_and_collect.py
Runs the original movement control while simultaneously collecting:
- Accelerometer data (X, Y, Z) at 30Hz
- Gyroscope data (X, Y, Z) at 30Hz
- Video from USB camera (640x480 @ 30fps)

All data is synchronized with timestamps for later model training.

## Requirements

```
pysphero
opencv-python
numpy
pyyaml
```

## Installation

1. Install the required packages:
   ```
   pip install pysphero opencv-python numpy pyyaml
   ```

2. Make sure your Sphero's MAC address is correctly set in `unlimited_move.py`

3. Ensure your camera is properly connected and detected (index 0)

## Usage

1. Run the data collection script:
   ```
   python sphero_move_and_collect.py
   ```

2. To stop data collection, press `Ctrl+C`. The script will gracefully stop all processes and save the collected data.

## Data Output

Data is saved to a timestamped directory under `collected_data/run_YYYYMMDD_HHMMSS/` and includes:

- `video.mp4`: Camera recording
- `sensor_data.csv`: Synchronized accelerometer and gyroscope readings
- `metadata.json`: Information about the data collection session

## Troubleshooting

- If the camera doesn't work, verify it's connected and check the camera index
- Make sure the Sphero is charged and within Bluetooth range
- Check that the MAC address in `unlimited_move.py` matches your Sphero

## Notes

- The data collection runs in separate threads so it doesn't interfere with the Sphero movement
- Video and sensor data are synchronized using timestamps
- All data collection is performed in background threads, preserving the original movement behavior 
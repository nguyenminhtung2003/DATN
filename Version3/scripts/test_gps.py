#!/usr/bin/env python3
"""
Test script for GPS GY-NEO 6M UART.
Run this directly on Jetson Nano to verify hardware works.
"""
import sys
import os

# Add root project path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sensors.gps_reader import GPSReader
import config

if __name__ == "__main__":
    print(f"Testing GPS module on port: {config.GPS_PORT} at {config.GPS_BAUDRATE} baud")
    print("Initializing GPSReader...")
    # Force GPS feature true for testing
    config.HAS_GPS = True
    
    reader = GPSReader()
    print("Reading from GPS (timeout ~15 lines)...")
    result = reader.read_once()
    
    print("\n--- TEST RESULT ---")
    if result.get("status") == "OK":
        print("SUCCESS! GPS Module is working.")
        print(f"Latitude:  {result.get('lat')}")
        print(f"Longitude: {result.get('lng')}")
        print(f"Speed:     {result.get('speed')} km/h")
        print("\nYou can now set DROWSIGUARD_FEATURE_GPS=true in drowsiguard.env")
    else:
        print("FAILED!")
        print(f"Reason: {result.get('reason')}")
        print("\nTroubleshooting:")
        print("1. Ensure GPS is wired correctly to /dev/ttyTHS1 (UART).")
        print("2. Ensure the Jetson is outside or near a window (it takes time to get a fix).")
        print("3. Check module LED (blinking usually means it has a fix).")

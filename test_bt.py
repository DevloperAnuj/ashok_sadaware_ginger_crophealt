"""
Bluetooth connection test for ESP32 GingerMonitor.
Run this from the terminal to test the connection independently of Streamlit.
"""
import serial
import serial.tools.list_ports
import time
import sys

# List all Bluetooth COM ports
print("=" * 50)
print("GINGERMONITOR BLUETOOTH TEST")
print("=" * 50)

print("\nAvailable COM ports:")
for p in serial.tools.list_ports.comports():
    print(f"  {p.device} - {p.description}")

if len(sys.argv) > 1:
    port = sys.argv[1]
else:
    port = input("\nEnter COM port to test (e.g., COM5): ")

print(f"\nAttempting to connect to {port}...")
print(f"  Baud: 115200")
print(f"  Timeout: 5s")

try:
    ser = serial.Serial(
        port=port,
        baudrate=115200,
        timeout=5,
        write_timeout=3,
    )
    print(f"  ✅ Connected! Waiting for data...")
    print(f"    (ESP32 sends data every ~1.5 seconds)")
    print(f"  Press Ctrl+C to stop\n")

    # Wait for first data
    print("  Reading...", end="", flush=True)
    start_time = time.time()
    data_count = 0

    while True:
        if ser.in_waiting:
            raw = ser.read(ser.in_waiting)
            text = raw.decode("utf-8", errors="ignore")
            print(f"\n  📥 Received {len(raw)} bytes:")
            for line in text.split("\n"):
                if line.strip():
                    print(f"     {line.strip()}")
            data_count += 1
        else:
            # Try a blocking read
            try:
                ser.timeout = 1.0
                raw = ser.read(1)
                if raw:
                    # Got at least 1 byte, read the rest
                    if ser.in_waiting:
                        raw += ser.read(ser.in_waiting)
                    text = raw.decode("utf-8", errors="ignore")
                    print(f"\n  📥 Received {len(raw)} bytes:")
                    for line in text.split("\n"):
                        if line.strip():
                            print(f"     {line.strip()}")
                    data_count += 1
                ser.timeout = 5
            except Exception as e:
                ser.timeout = 5

        elapsed = time.time() - start_time
        if elapsed > 30 and data_count == 0:
            print(f"\n\n  ⚠️  No data received after 30 seconds.")
            print(f"  This means the Bluetooth connection is established")
            print(f"  but no serial data is flowing through.")
            print(f"\n  Possible causes:")
            print(f"  1. Wrong COM port (try the other one)")
            print(f"  2. ESP32 firmware not running (flash hardware_code.ccp)")
            print(f"  3. Windows Bluetooth driver issue")
            print(f"  4. ESP32 needs to be power-cycled")
            print(f"\n  Try: Unpair, restart ESP32, pair again, then test again.")
            break

        if data_count > 0:
            elapsed_str = time.time() - start_time
            print(f"\n  ✅ Data received successfully!")
            break

        print(".", end="", flush=True)
        time.sleep(0.5)

except serial.SerialException as e:
    print(f"\n  ❌ Failed to connect: {e}")
except OSError as e:
    print(f"\n  ❌ OS Error: {e}")
except KeyboardInterrupt:
    print(f"\n  Stopped by user.")
finally:
    try:
        ser.close()
    except:
        pass

print("\n" + "=" * 50)
print("Test complete.")
input("Press Enter to exit...")
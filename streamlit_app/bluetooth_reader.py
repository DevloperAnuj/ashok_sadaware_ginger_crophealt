"""
Bluetooth Serial reader for ESP32 Ginger Monitor.

Connects to the ESP32 via Bluetooth SPP (Serial Port Profile) on Windows.
Parses the structured sensor data lines sent by the hardware.

Expected hardware output format:
    Humidity: 65.00%
    N: 0 mg/kg
    P: 0 mg/kg
    K: 0 mg/kg
    Moisture: 4095
    pH: 0.00
    Temp: 27.50
"""

import os
import re
import time
import serial
import serial.tools.list_ports


# ── Sensor value translation helpers ──────────────────────────────────────────

def _translate_raw_moisture(raw: int) -> float:
    """
    Convert raw ADC moisture (0–4095) to a 0–100% scale.

    Dry soil  → high ADC value (~4095)
    Wet soil  → low ADC value (~1500)
    In water  → ~0

    Invert + scale:  moisture% = (1 - raw / 4095) * 100
    """
    raw = max(0, min(4095, raw))
    return round((1.0 - raw / 4095.0) * 100.0, 1)


def _translate_ph(raw_ph: float) -> float | None:
    """
    Return None if pH is 0.00 (invalid/uncalibrated reading from hardware).
    Otherwise return the value as-is.
    """
    if raw_ph == 0.00 or raw_ph is None:
        return None
    return round(raw_ph, 2)


# ── Regex patterns for each sensor line ───────────────────────────────────────

PATTERNS = [
    ("temperature",       re.compile(r"Temp[^\d]*([\d.]+)")),
    ("humidity",          re.compile(r"Humidity[^\d]*([\d.]+)")),
    ("soil_moisture_raw", re.compile(r"Moisture[^\d]*(\d+)")),
    ("soil_ph",           re.compile(r"pH[^\d]*([\d.]+)")),
    ("nitrogen",          re.compile(r"N[^\d]*(\d+)\s*mg/kg")),
    ("phosphorus",        re.compile(r"P[^\d]*(\d+)\s*mg/kg")),
    ("potassium",         re.compile(r"K[^\d]*(\d+)\s*mg/kg")),
]


class BluetoothReader:
    """
    Read sensor data from the ESP32 Ginger Monitor via Bluetooth SPP.

    Usage:
        reader = BluetoothReader()
        ports = BluetoothReader.list_bt_ports()   # static
        reader.connect("COM5")
        data = reader.get_latest()
        reader.disconnect()
    """

    def __init__(self):
        self.port: str | None = None
        self.device_name: str = "GingerMonitor"
        self.ser: serial.Serial | None = None
        self.connected: bool = False
        self.error: str = ""

        self._buffer: str = ""
        self._latest: dict = {}
        self._log: list[str] = []

    # ── Static: list available Bluetooth COM ports ──────────────────────────

    @staticmethod
    def list_bt_ports() -> list[tuple[str, str]]:
        """
        Enumerate all serial ports and return those that look like Bluetooth.

        Returns:
            list of (port_name, description) tuples, e.g. [("COM5", "Standard Serial over Bluetooth link")]
        """
        bt_ports: list[tuple[str, str]] = []
        try:
            for p in serial.tools.list_ports.comports():
                desc = (p.description or "").lower()
                # Bluetooth ports typically contain "bluetooth" or "bt" in the description
                if "bluetooth" in desc or "bt" in desc or "standard serial" in desc:
                    bt_ports.append((p.device, p.description))
                # Also include any port with "COM" and a number (fallback for some BT adapters)
                elif p.device and p.device.upper().startswith("COM"):
                    bt_ports.append((p.device, p.description))
        except Exception as exc:
            pass  # No serial ports available
        return bt_ports

    # ── Connection management ───────────────────────────────────────────────

    def connect(self, port: str) -> bool:
        """Open a serial connection to the given COM port."""
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=115200,
                timeout=1.0,
                write_timeout=1.0,
            )
            self.port = port
            self.connected = True
            self.error = ""
            self._buffer = ""
            self._log = []
            # Give the device a moment to start sending data
            time.sleep(0.5)
            # Flush any stale data
            if self.ser.in_waiting:
                self.ser.reset_input_buffer()
            return True
        except serial.SerialException as exc:
            self.error = str(exc)
            self.connected = False
            self.ser = None
            return False

    def disconnect(self):
        """Close the serial connection."""
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None
        self.connected = False
        self.port = None

    # ── Data reading ────────────────────────────────────────────────────────

    def get_latest(self) -> dict:
        """
        Read and parse any available data from the serial buffer.

        Returns the current sensor data dict (may be empty on first call
        before any data is received).
        """
        if not self.connected or self.ser is None:
            return dict(self._latest)

        try:
            if self.ser.in_waiting > 0:
                raw = self.ser.read(self.ser.in_waiting)
                try:
                    text = raw.decode("utf-8", errors="ignore")
                except Exception:
                    text = raw.decode("ascii", errors="ignore")

                self._buffer += text

                # Split on newlines and process complete lines
                if "\n" in self._buffer:
                    lines = self._buffer.split("\n")
                    # Keep the last incomplete line fragment in the buffer
                    self._buffer = lines.pop()
                    self._parse_lines(lines)

        except serial.SerialException:
            self.disconnect()
        except Exception:
            pass

        return dict(self._latest)

    def get_log(self) -> list[str]:
        """Return the raw serial log lines (up to 200)."""
        return list(self._log)

    # ── Internal parsing ────────────────────────────────────────────────────

    def _parse_lines(self, lines: list[str]):
        """Parse a batch of complete lines from the serial buffer."""
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            self._log.append(stripped)
            # Keep log bounded
            if len(self._log) > 200:
                self._log = self._log[-200:]

            parsed = False
            for key, pattern in PATTERNS:
                match = pattern.search(stripped)
                if match:
                    parsed = True
                    if key == "soil_moisture_raw":
                        raw = int(match.group(1))
                        self._latest["soil_moisture"] = _translate_raw_moisture(raw)
                        self._latest.pop("soil_moisture_raw", None)
                    elif key == "soil_ph":
                        raw_ph = float(match.group(1))
                        translated = _translate_ph(raw_ph)
                        if translated is not None:
                            self._latest["soil_ph"] = translated
                    else:
                        self._latest[key] = float(match.group(1))
                    break  # first match wins per line

            # Log unrecognised lines for debugging
            if not parsed and stripped:
                _ = stripped  # ignore silently — could log at debug level

        # Compute derived values after each batch of lines
        self._compute_derived()

    def _compute_derived(self):
        """
        Compute missing sensor values that the hardware doesn't provide.

        The hardware output shown by the user includes only:
          temperature, humidity, soil_moisture, soil_ph, N, P, K

        The following are NOT provided by hardware and must be simulated:
          light_intensity, soil_temperature, electrical_conductivity,
          rainfall, days_since_irrigation, days_since_last_spray, pest_risk_score
        """
        now = time.time()

        # light_intensity — not on hardware, hold last known or sensible default
        if "light_intensity" not in self._latest:
            self._latest["light_intensity"] = 420.0

        # soil_temperature — not on hardware, approximate from air temp
        if "soil_temperature" not in self._latest:
            air_temp = self._latest.get("temperature", 27.0)
            # Soil temp lags ~2–4°C below air temp
            self._latest["soil_temperature"] = round(max(12.0, air_temp - 3.0), 1)

        # electrical_conductivity — not on hardware
        if "electrical_conductivity" not in self._latest:
            self._latest["electrical_conductivity"] = 1.0

        # rainfall — not on hardware
        if "rainfall" not in self._latest:
            self._latest["rainfall"] = 0.0

        # days_since_irrigation — track internally
        if "days_since_irrigation" not in self._latest:
            self._latest["days_since_irrigation"] = 0.0
        else:
            # Increment by ~1 day per 60 reads (~2 min at 2 s auto-refresh)
            self._latest["days_since_irrigation"] += 1.0 / 60.0
            if self._latest["days_since_irrigation"] > 30:
                self._latest["days_since_irrigation"] = 30.0

        # days_since_last_spray — track internally
        if "days_since_last_spray" not in self._latest:
            self._latest["days_since_last_spray"] = 7.0
        else:
            self._latest["days_since_last_spray"] += 1.0 / 60.0
            if self._latest["days_since_last_spray"] > 60:
                self._latest["days_since_last_spray"] = 60.0

        # pest_risk_score — computed from temp/humidity/spray status
        temp = self._latest.get("temperature", 27.0)
        hum = self._latest.get("humidity", 65.0)
        dsls = self._latest.get("days_since_last_spray", 7.0)
        score = 0.0
        if 22 <= temp <= 35:
            score += 0.3
        if hum > 70:
            score += 0.3
        if dsls > 14:
            score += 0.3
        if dsls > 21:
            score += 0.1
        self._latest["pest_risk_score"] = min(1.0, score)

        # Mark "received" timestamp
        self._latest["_last_received"] = now


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    ports = BluetoothReader.list_bt_ports()
    if not ports:
        print("No Bluetooth COM ports found.")
        print("Make sure the ESP32 is paired via Windows Bluetooth settings.")
        exit(1)

    print("Available Bluetooth ports:")
    for i, (dev, desc) in enumerate(ports):
        print(f"  [{i}] {dev} — {desc}")

    try:
        idx = int(input("Select port index: "))
        port = ports[idx][0]
    except (ValueError, IndexError):
        print("Invalid selection.")
        exit(1)

    reader = BluetoothReader()
    if reader.connect(port):
        print(f"\nConnected to {port}. Reading data (Ctrl+C to stop)...\n")
        try:
            while True:
                data = reader.get_latest()
                if data:
                    # Print a compact one-line summary
                    parts = [
                        f"T:{data.get('temperature', '?'):.1f}°C",
                        f"H:{data.get('humidity', '?'):.1f}%",
                        f"M:{data.get('soil_moisture', '?'):.1f}%",
                        f"pH:{data.get('soil_ph', '?'):.2f}",
                        f"N:{data.get('nitrogen', '?'):.0f}",
                        f"P:{data.get('phosphorus', '?'):.0f}",
                        f"K:{data.get('potassium', '?'):.0f}",
                    ]
                    print(" | ".join(parts))
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping reader.")
        finally:
            reader.disconnect()
    else:
        print(f"Failed to connect: {reader.error}")
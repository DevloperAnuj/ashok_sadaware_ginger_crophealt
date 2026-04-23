"""
Reads sensor data from the ESP32 GingerMonitor over a Bluetooth COM port.

Setup steps (Windows):
  1. Pair the ESP32 via Settings → Bluetooth & devices.
     The device name is "GingerMonitor".
  2. After pairing, Windows assigns a COM port (e.g. COM5).
     Check it in Device Manager → Ports (COM & LPT).
  3. Select that COM port in the Streamlit sidebar and click Connect.

ESP32 data format (sent every ~1.5 s):
  ----- Soil Data -----
  Moisture: <raw ADC 0-4095>
  pH: <float>
  Temp: <float>
  Humidity: <float>
"""

import re
import threading
from collections import deque
from datetime import datetime

import serial
import serial.tools.list_ports


# ── Moisture calibration constants ────────────────────────────────────────────
# Measure with your sensor and update:
#   DRY_RAW — sensor in open air           (default 4095)
#   WET_RAW — sensor submerged in water    (measure and set)
DRY_RAW: int = 4095
WET_RAW: int = 1500


def _raw_moisture_to_pct(raw: float) -> float:
    span = DRY_RAW - WET_RAW
    if span == 0:
        return 0.0
    pct = (DRY_RAW - raw) / span * 100.0
    return round(max(0.0, min(100.0, pct)), 1)


def _bt_device_names() -> list[str]:
    """
    Read Bluetooth device friendly names from the Windows registry.
    Returns an empty list if registry access fails (non-Windows or no devices).
    """
    try:
        import winreg
        path = r"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices"
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
        names: list[str] = []
        i = 0
        while True:
            try:
                mac_key_name = winreg.EnumKey(root, i)
                mac_key = winreg.OpenKey(root, mac_key_name)
                try:
                    val, _ = winreg.QueryValueEx(mac_key, "FriendlyName")
                    # Windows stores this as bytes (UTF-16-LE) or str depending on version
                    if isinstance(val, bytes):
                        name = val.decode("utf-16-le", errors="ignore").rstrip("\x00")
                    else:
                        name = str(val)
                    if name.strip():
                        names.append(name.strip())
                except FileNotFoundError:
                    pass
                finally:
                    winreg.CloseKey(mac_key)
                i += 1
            except OSError:
                break
        winreg.CloseKey(root)
        return names
    except Exception:
        return []


class BluetoothReader:
    """
    Thread-safe serial reader for the ESP32 GingerMonitor.
    Call connect() to open the port and start the background reader thread.
    Call disconnect() to stop.
    """

    _PATTERNS = {
        "moisture_raw": re.compile(r"Moisture:\s*([\d.]+)"),
        "soil_ph":      re.compile(r"pH:\s*([\d.]+)"),
        "temperature":  re.compile(r"Temp:\s*([\d.]+)"),
        "humidity":     re.compile(r"Humidity:\s*([\d.]+)"),
    }

    def __init__(self):
        self._serial: serial.Serial | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._latest: dict | None = None
        self._log: deque[str] = deque(maxlen=100)
        self._running = False
        self.error: str = ""
        self.port: str = ""
        self.device_name: str = ""

    # ── Public API ────────────────────────────────────────────────────────────

    def connect(self, port: str, baud: int = 115200) -> bool:
        """Open COM port and start background reader thread. Returns True on success."""
        self.error = ""
        self.port = port
        self.device_name = ""
        try:
            self._serial = serial.Serial(port, baud, timeout=2)
            self._running = True
            # Resolve device name from Windows registry
            names = _bt_device_names()
            self.device_name = names[0] if names else "GingerMonitor"
            with self._lock:
                self._log.clear()
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()
            return True
        except Exception as exc:
            self.error = str(exc)
            self._serial = None
            return False

    def disconnect(self):
        """Stop the reader thread and close the COM port."""
        self._running = False
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None
        with self._lock:
            self._latest = None

    @property
    def connected(self) -> bool:
        return bool(self._serial and self._serial.is_open)

    def get_latest(self) -> dict | None:
        """
        Return the most recent complete sensor reading, or None if none received yet.
        Keys: temperature, humidity, soil_moisture, soil_ph
        """
        with self._lock:
            return dict(self._latest) if self._latest else None

    def get_log(self) -> list[str]:
        """Return a copy of the raw line log (newest last)."""
        with self._lock:
            return list(self._log)

    # ── Port discovery ────────────────────────────────────────────────────────

    @staticmethod
    def list_bt_ports() -> list[tuple[str, str]]:
        """
        Return (device, label) tuples for Bluetooth COM ports.
        Label includes the paired device name from the Windows registry when available.
        Falls back to all ports if no Bluetooth-tagged ports are found.
        """
        all_ports = serial.tools.list_ports.comports()
        bt_ports = [p for p in all_ports if "bluetooth" in (p.description or "").lower()]
        source = bt_ports if bt_ports else list(all_ports)

        # Pull device names from the registry once
        device_names = _bt_device_names()

        result: list[tuple[str, str]] = []
        for i, p in enumerate(sorted(source, key=lambda x: x.device)):
            # Try to attach a device name: if only one BT device is paired, assign it
            if len(device_names) == 1:
                dev_label = device_names[0]
            elif i < len(device_names):
                dev_label = device_names[i]
            else:
                dev_label = p.description or p.device
            result.append((p.device, f"{p.device}  —  {dev_label}"))

        return result

    # ── Background reader thread ───────────────────────────────────────────────

    def _read_loop(self):
        buf: dict = {}
        while self._running and self._serial and self._serial.is_open:
            try:
                raw_bytes = self._serial.readline()
                line = raw_bytes.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                # Append to log with timestamp
                ts = datetime.now().strftime("%H:%M:%S")
                with self._lock:
                    self._log.append(f"[{ts}]  {line}")

                # Parse sensor values
                for key, pattern in self._PATTERNS.items():
                    match = pattern.search(line)
                    if match:
                        buf[key] = float(match.group(1))

                if len(buf) == 4:
                    reading = {
                        "temperature":   round(buf["temperature"], 1),
                        "humidity":      round(buf["humidity"], 1),
                        "soil_moisture": _raw_moisture_to_pct(buf["moisture_raw"]),
                        "soil_ph":       round(buf["soil_ph"], 2),
                    }
                    with self._lock:
                        self._latest = reading
                    buf.clear()

            except Exception:
                break

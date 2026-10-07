"""Board-specific ADC conversion, applied once to a copy of each sensor snapshot."""
import math

# This board is absent from LHM 0.9.6's model table and uses its unscaled Vcore.
# Ri/Rf = 15/136 is also used by upstream's ASUS TUF B760M NCT6798D profile.
# On this Z790-A WIFI S it reproduces GamePP's 1.252 / 1.261 / 1.279 V steps
# from 1.128 / 1.136 / 1.152 V, including the low-voltage 0.711 V step.
# Evidence and the scope of this verified model are in docs/sensor-notes.md.
BOARD = "ASUS ROG STRIX Z790-A GAMING WIFI S"
SENSOR_ID = "/lpc/nct6798d/0/voltage/0"
PROFILE = {"board": BOARD, "riKohm": 15, "rfKohm": 136, "vfV": 0}


def motherboard_voltages(devices):
    boards = {d["id"] for d in devices if d.get("id") and d.get("type") == "Motherboard"
              and d.get("name", "").strip().upper() == BOARD}
    converted = []
    for device in devices:
        if (device.get("type") != "SuperIO" or device.get("parentId") not in boards
                or device.get("id") != "/lpc/nct6798d/0"):
            converted.append(device)
            continue
        sensors = []
        for sensor in device.get("sensors", []):
            value = sensor.get("value")
            # A future library with a calibrated model must not be scaled again.
            generic = sensor.get("voltageParameters") == {"ri": 0, "rf": 1, "vf": 0}
            if (sensor.get("id") == SENSOR_ID and sensor.get("type") == "Voltage"
                    and sensor.get("name", "").strip().casefold() == "vcore"
                    and generic and isinstance(value, (int, float)) and not isinstance(value, bool)
                    and math.isfinite(value) and value >= 0 and not sensor.get("calibration")):
                sensor = {**sensor, "rawValue": value, "value": value + value * 15 / 136,
                          "voltageParameters": {"ri": 15, "rf": 136, "vf": 0},
                          "calibration": dict(PROFILE)}
            sensors.append(sensor)
        converted.append({**device, "sensors": sensors})
    return converted

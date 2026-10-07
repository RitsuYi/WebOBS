import copy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_profiles import BOARD, SENSOR_ID, motherboard_voltages


def snapshot(value=1.144):
    return [{"id": "/motherboard", "name": BOARD, "type": "Motherboard", "sensors": []},
            {"id": "/lpc/nct6798d/0", "parentId": "/motherboard", "name": "Nuvoton NCT6798D",
             "type": "SuperIO", "sensors": [
                 {"id": SENSOR_ID, "name": "Vcore", "type": "Voltage", "value": value,
                  "voltageParameters": {"ri": 0, "rf": 1, "vf": 0}},
                 {"id": "/lpc/nct6798d/0/voltage/1", "name": "Voltage #2", "type": "Voltage", "value": 0.984}]}]


class BoardProfileTests(unittest.TestCase):
    def test_gamepp_reference_steps_and_low_voltage_follow_adc(self):
        for raw, reference in [(1.128, 1.252), (1.136, 1.261), (1.144, 1.270), (1.152, 1.279), (0.640, 0.711)]:
            with self.subTest(raw=raw):
                source = snapshot(raw)
                original = copy.deepcopy(source)
                calibrated = motherboard_voltages(source)
                vcore = calibrated[1]["sensors"][0]
                self.assertEqual(round(vcore["value"], 3), reference)
                self.assertEqual(vcore["rawValue"], raw)
                self.assertEqual(source, original)
                # Both repeated reads of a shared bridge snapshot and normalized input are safe.
                self.assertEqual(motherboard_voltages(source), calibrated)
                self.assertEqual(motherboard_voltages(calibrated), calibrated)
                self.assertEqual(calibrated[1]["sensors"][1], source[1]["sensors"][1])

    def test_only_the_verified_board_chip_channel_and_default_divider_are_changed(self):
        alterations = [(0, "name", "ASUS ROG STRIX Z790-A GAMING WIFI II"),
                       (0, "name", "ASRock Z690 Extreme"), (0, "id", "/another-board"),
                       (1, "parentId", None), (1, "id", "/lpc/nct6799d/0"),
                       ("sensor", "id", "/intelcpu/0/voltage/0"),
                       ("sensor", "voltageParameters", None),
                       ("sensor", "voltageParameters", {"ri": 15, "rf": 136, "vf": 0}),
                       ("sensor", "voltageParameters", {"ri": 0, "rf": 1, "vf": 0.1})]
        for target, key, value in alterations:
            with self.subTest(target=target, key=key, value=value):
                devices = snapshot()
                item = devices[1]["sensors"][0] if target == "sensor" else devices[target]
                item[key] = value
                self.assertEqual(motherboard_voltages(devices), devices)

    def test_missing_and_invalid_voltages_stay_missing_or_invalid(self):
        for value in [None, float("nan"), float("inf"), -1, True]:
            with self.subTest(value=value):
                sensor = motherboard_voltages(snapshot(value))[1]["sensors"][0]
                self.assertNotIn("calibration", sensor)
                if isinstance(value, float) and math.isnan(value):
                    self.assertTrue(math.isnan(sensor["value"]))
                else:
                    self.assertEqual(sensor["value"], value)


if __name__ == "__main__":
    unittest.main()

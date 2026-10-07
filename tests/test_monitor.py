import copy
import importlib.util
import json
from pathlib import Path
import uuid
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hardware import calculate_power, pick, demo_sample, HardwareCollector, SensorBridge
from monitor import DEFAULTS, Handler, State, ThreadingHTTPServer, validate_config
from cpu_usage import ProcessorUtility, SOURCE as UTILITY_SOURCE
from test_board_profiles import snapshot as board_snapshot

class PowerTests(unittest.TestCase):
    def test_estimate_and_wall_efficiency(self):
        config = copy.deepcopy(DEFAULTS)
        self.assertEqual(calculate_power(95, 117, None, config), (312, "estimated"))
        config["powerMode"] = "wall"
        self.assertAlmostEqual(calculate_power(95, 117, None, config)[0], 346.6666667)

    def test_missing_reading_is_not_zero(self):
        self.assertIsNone(calculate_power(None, 117, None, DEFAULTS)[0])
        self.assertIsNone(calculate_power(95, None, None, DEFAULTS)[0])

    def test_measured_does_not_require_component_readings(self):
        config = {**DEFAULTS, "powerMode": "measured"}
        self.assertEqual(calculate_power(None, None, 345, config), (345, "measured"))
        self.assertIsNone(calculate_power(95, 117, None, config)[0])

    def test_sensor_binding_does_not_silently_fall_back(self):
        sensors = [{"id": "/cpu/package", "name": "CPU Package", "type": "Power", "value": 52},
                   {"id": "/cpu/cores", "name": "CPU Cores", "type": "Power", "value": 36}]
        self.assertEqual(pick(sensors, "Power", ["CPU Package"]), 52)
        self.assertEqual(pick(sensors, "Power", [], "/cpu/cores"), 36)
        self.assertIsNone(pick(sensors, "Power", ["CPU Package"], "/missing"))

    def test_demo_is_explicit_and_formula_consistent(self):
        reading = demo_sample(DEFAULTS, 0)
        self.assertTrue(reading["demo"])
        self.assertEqual(reading["systemPowerW"], 312)

class ValidationTests(unittest.TestCase):
    def test_invalid_config(self):
        for key, value in [("port", 80), ("sampleIntervalMs", 0), ("psuEfficiency", 0), ("demo", "true"),
                           ("port", True), ("basePowerW", float("nan")), ("basePowerW", float("inf")),
                           ("host", "example.com"), ("host", "::1"), ("animationMs", 12.5), ("frameRate", 30),
                           ("sensors", {"cpu.powerW": 123}), ("powerMode", "anything"), ("elevatedSensors", "true")]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_config({key: value})

    def test_defaults_are_independent(self):
        config = validate_config({})
        config["sensors"]["cpu.powerW"] = "/cpu/package"
        self.assertEqual(DEFAULTS["sensors"], {})

class DeviceTests(unittest.TestCase):
    def collector(self, hardware):
        collector = HardwareCollector.__new__(HardwareCollector)
        collector.windows = SimpleNamespace(sample=lambda: ({"usage": 12, "frequencyMhz": 3400}, {"usage": 30, "usedGb": 9.6, "totalGb": 32}))
        collector.nvidia = SimpleNamespace(count=1, sample=lambda _: {"name": "NVIDIA TEST", "powerW": 75, "usage": 20, "frequencyMhz": 2600})
        collector.bridge = SimpleNamespace(snapshot=lambda **kwargs: ({"hardware": hardware}, None))
        collector.started = 0
        collector.catalog = []
        return collector

    def test_board_vcore_conversion_is_used_by_automatic_and_explicit_mapping(self):
        collector = self.collector(board_snapshot())
        for sensors in [{}, {"cpu.voltageV": "/lpc/nct6798d/0/voltage/0"}]:
            with self.subTest(sensors=sensors):
                config = {**copy.deepcopy(DEFAULTS), "sensors": sensors}
                reading = collector.sample(config)["cpu"]
                self.assertEqual(round(reading["voltageV"], 3), 1.270)
                self.assertEqual(reading["sensorSources"]["voltageV"]["rawValue"], 1.144)
                self.assertEqual(reading["sensorSources"]["voltageV"]["calibration"]["riKohm"], 15)
                vcore = collector.catalog[1]["sensors"][0]
                self.assertEqual(vcore["value"], reading["voltageV"])

    def test_requested_cpu_metrics_are_selected_instead_of_vid_core_and_cores_power(self):
        collector = self.collector([
            {"id": "/cpu/0", "name": "Intel Core i7-14700KF", "type": "Cpu", "sensors": [
                {"id": "/cpu/vid", "name": "CPU VID", "type": "Voltage", "value": 1.4},
                {"id": "/cpu/core", "name": "CPU Core #5 Thread #1", "type": "Load", "value": 90},
                {"id": "/cpu/total", "name": "CPU Total", "type": "Load", "value": 10},
                {"id": "/cpu/usages", "name": "Core Usages", "type": "Load", "value": 8.6},
                {"id": "/cpu/cores", "name": "CPU Cores", "type": "Power", "value": 25},
                {"id": "/cpu/package", "name": "CPU Package Power", "type": "Power", "value": 44.586}]},
            {"id": "/board/other", "name": "Other controller", "type": "SuperIO", "sensors": [
                {"id": "/board/other/vcore", "name": "Vcore", "type": "Voltage", "value": 1.5}]},
            {"id": "/board/nuvoton", "name": "Nuvoton NCT6798D", "type": "SuperIO", "sensors": [
                {"id": "/board/vcore", "name": "Vcore", "type": "Voltage", "value": 1.261}]}])
        reading = collector.sample(copy.deepcopy(DEFAULTS))["cpu"]
        self.assertEqual((reading["voltageV"], reading["usage"], reading["powerW"]), (1.261, 8.6, 44.586))
        self.assertEqual(reading["sensorSources"]["voltageV"]["id"], "/board/vcore")
        self.assertEqual(reading["sensorSources"]["powerW"]["name"], "CPU Package Power")

    def test_missing_requested_sensor_does_not_become_a_different_metric(self):
        collector = self.collector([{"id": "/cpu/0", "name": "CPU", "type": "Cpu", "sensors": [
            {"id": "/cpu/vid", "name": "CPU VID", "type": "Voltage", "value": 1.4},
            {"id": "/cpu/core", "name": "CPU Core #5 Thread #1", "type": "Load", "value": 90},
            {"id": "/cpu/cores", "name": "CPU Cores", "type": "Power", "value": 25},
            {"id": "/cpu/platform", "name": "CPU Platform", "type": "Power", "value": 60}]}])
        reading = collector.sample(copy.deepcopy(DEFAULTS))["cpu"]
        self.assertIsNone(reading["voltageV"])
        self.assertIsNone(reading["powerW"])
        self.assertEqual(reading["usage"], 12)
        self.assertEqual(reading["sensorSources"]["usage"]["provider"], "Windows API")

    def test_explicit_cpu_binding_remains_explicit_even_when_missing(self):
        collector = self.collector([{"id": "/board", "name": "NCT6798D", "type": "SuperIO", "sensors": [
            {"id": "/board/vcore", "name": "Vcore", "type": "Voltage", "value": 1.261}]}])
        config = {**copy.deepcopy(DEFAULTS), "sensors": {"cpu.voltageV": "/missing", "cpu.usage": "/missing"}}
        reading = collector.sample(config)["cpu"]
        self.assertIsNone(reading["voltageV"])
        self.assertIsNone(reading["usage"])
        config["sensors"] = {"cpu.voltageV": "/board/vcore"}
        reading = collector.sample(config)["cpu"]
        self.assertEqual(reading["voltageV"], 1.261)
        self.assertEqual(reading["sensorSources"]["voltageV"]["device"], "NCT6798D")

    def test_windows_utility_is_not_replaced_by_library_busy_time(self):
        collector = self.collector([{"id": "/cpu/0", "name": "CPU", "type": "Cpu", "sensors": [
            {"id": "/cpu/total", "name": "CPU Total", "type": "Load", "value": 3}]}])
        collector.windows = SimpleNamespace(sample=lambda: (
            {"usage": 13, "usageSource": dict(UTILITY_SOURCE), "frequencyMhz": 3400}, {"usage": 30}))
        reading = collector.sample(copy.deepcopy(DEFAULTS))["cpu"]
        self.assertEqual(reading["usage"], 13)
        self.assertEqual(reading["sensorSources"]["usage"]["provider"], "Windows PDH")
        config = {**copy.deepcopy(DEFAULTS), "sensors": {"cpu.usage": "/cpu/total"}}
        reading = collector.sample(config)["cpu"]
        self.assertEqual(reading["usage"], 3)
        self.assertEqual(reading["sensorSources"]["usage"]["id"], "/cpu/total")

    def test_missing_selected_gpu_is_not_another_gpu(self):
        collector = self.collector([])
        reading = collector.sample({**copy.deepcopy(DEFAULTS), "gpuDevice": "/gpu-amd/missing"})
        self.assertIsNone(reading["gpu"]["usage"])
        self.assertIsNone(reading["gpu"]["powerW"])

    def test_cpu_zero_without_driver_is_unavailable(self):
        collector = self.collector([{"id": "/cpu/0", "name": "TEST CPU", "type": "Cpu", "sensors": [
            {"id": "/cpu/power/0", "name": "CPU Package", "type": "Power", "value": 0},
            {"id": "/cpu/clock/0", "name": "CPU Core #1", "type": "Clock", "value": None}]}])
        reading = collector.sample(copy.deepcopy(DEFAULTS))
        self.assertIsNone(reading["cpu"]["powerW"])
        self.assertIsNone(reading["systemPowerW"])

    def test_selected_amd_gpu_does_not_receive_nvidia_data(self):
        collector = self.collector([{"id": "/gpu-amd/0", "name": "AMD TEST", "type": "GpuAmd", "sensors": [
            {"id": "/gpu-amd/0/load", "name": "GPU Core", "type": "Load", "value": 44},
            {"id": "/gpu-amd/0/power", "name": "GPU Package", "type": "Power", "value": 130}]}])
        reading = collector.sample({**copy.deepcopy(DEFAULTS), "gpuDevice": "/gpu-amd/0"})
        self.assertEqual(reading["gpu"]["usage"], 44)
        self.assertEqual(reading["gpu"]["powerW"], 130)
        self.assertIsNone(reading["gpu"]["frequencyMhz"])

class CpuUtilityTests(unittest.TestCase):
    def counter(self, number=13, status=0, result=0):
        counter = ProcessorUtility.__new__(ProcessorUtility)
        counter.query, counter.counter, counter.primed = 1, 2, False
        def format_value(handle, flags, kind, output):
            output._obj.value, output._obj.status = number, status
            return result
        counter.pdh = SimpleNamespace(PdhCollectQueryData=lambda _: 0, PdhGetFormattedCounterValue=format_value)
        return counter

    def test_delta_needs_two_samples_and_zero_is_a_valid_measurement(self):
        counter = self.counter(0)
        self.assertIsNone(counter.sample())
        self.assertEqual(counter.sample(), 0)

    def test_invalid_counter_readings_do_not_become_zero(self):
        for number, status, result in [(13, 0xC0000BC6, 0), (float("nan"), 0, 0), (-1, 0, 0), (13, 0, 1)]:
            with self.subTest(number=number, status=status, result=result):
                counter = self.counter(number, status, result)
                counter.sample()
                self.assertIsNone(counter.sample())

    def test_turbo_utility_is_capped_at_100_percent(self):
        counter = self.counter(156, status=1)
        counter.sample()
        self.assertEqual(counter.sample(), 100)

class FakeCollector:
    def __init__(self, config=None):
        self.bridge = type("Bridge", (), {"process": None})()
    def sample(self, config):
        return demo_sample(config, 0)
    def devices(self):
        return []
    def close(self):
        pass

class PortableTests(unittest.TestCase):
    def test_cancelled_uac_falls_back_once_without_another_consent_prompt(self):
        bridge = SensorBridge.__new__(SensorBridge)
        bridge.stopping = False
        bridge.error = bridge.session_error = bridge.stop_handle = None
        cancelled = OSError("cancelled")
        cancelled.winerror = 1223
        with patch("hardware.launch_sensor", side_effect=cancelled) as launch, \
             patch("hardware.sensor_access", return_value={"status": "driver-missing", "message": None}), \
             patch.object(bridge, "_start_normal") as fallback:
            bridge._start_elevated(Path("helper.exe"), Path("library"))
        launch.assert_called_once()
        fallback.assert_called_once()
        self.assertIsNotNone(bridge.session_error)

    def test_demo_never_requests_elevation_or_launches_a_sensor_process(self):
        with patch("hardware.launch_sensor") as launch, patch("hardware.subprocess.Popen") as process:
            bridge = SensorBridge({"demo": True})
            bridge.close()
        launch.assert_not_called()
        process.assert_not_called()

class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = Path(__file__).resolve().parents[1] / "verification" / ("test-run-" + uuid.uuid4().hex[:8])
        cls.directory.mkdir(parents=True)
        with patch("monitor.HardwareCollector", FakeCollector):
            cls.state = State(copy.deepcopy(DEFAULTS), cls.directory / "config.json")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.server.daemon_threads = True
        cls.server.state = cls.state
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.state.telemetry = demo_sample(DEFAULTS, 0)

    @classmethod
    def tearDownClass(cls):
        cls.state.stop.set()
        with cls.state.changed:
            cls.state.changed.notify_all()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        # Keep test artifacts; never recursively delete directories.

    def get(self, path):
        with urlopen(self.base + path, timeout=3) as response:
            return response.status, response.headers, response.read()

    def post(self, data, token="", origin=None):
        headers = {"Content-Type": "application/json", "X-WebOBS-Token": token}
        if origin:
            headers["Origin"] = origin
        request = Request(self.base + "/api/config", data=json.dumps(data).encode(), headers=headers, method="POST")
        return urlopen(request, timeout=3)

    def test_configuration_is_local_and_token_protected(self):
        with self.assertRaises(HTTPError) as error:
            self.post(DEFAULTS)
        self.assertEqual(error.exception.code, 403)

    def test_lan_clients_cannot_get_token_or_write(self):
        with patch.object(Handler, "is_local", return_value=False):
            _, _, raw = self.get("/api/config")
            self.assertFalse(json.loads(raw)["canEdit"])
            self.assertIsNone(json.loads(raw)["token"])
            with self.assertRaises(HTTPError) as error:
                self.post(DEFAULTS, self.state.token)
            self.assertEqual(error.exception.code, 403)
        with self.assertRaises(HTTPError) as error:
            self.post(DEFAULTS, self.state.token, "https://other.example")
        self.assertEqual(error.exception.code, 403)

    def test_round_trip_persists_and_reports_restart(self):
        new = {**copy.deepcopy(DEFAULTS), "basePowerW": 72, "port": 8181, "sensorIntervalMs": 3000}
        with self.post(new, self.state.token) as response:
            result = json.load(response)
        self.assertTrue(result["restartRequired"])
        self.assertEqual(json.loads(self.state.config_path.read_text())["basePowerW"], 72)
        self.assertEqual(self.state.current_config()["sensorIntervalMs"], 3000)

    def test_bad_config_is_rejected(self):
        with self.assertRaises(HTTPError) as error:
            self.post({"port": 0}, self.state.token)
        self.assertEqual(error.exception.code, 400)

    def test_changing_elevation_requires_restart(self):
        config = {**copy.deepcopy(DEFAULTS), "elevatedSensors": False}
        with self.post(config, self.state.token) as response:
            self.assertTrue(json.load(response)["restartRequired"])

    def test_api_and_static_files(self):
        for path in ("/", "/settings", "/dashboard.js", "/api/health", "/api/telemetry", "/api/sensors"):
            with self.subTest(path=path):
                status, headers, body = self.get(path)
                self.assertEqual(status, 200)
                self.assertTrue(body)
        _, _, body = self.get("/api/config")
        config = json.loads(body)
        self.assertTrue(config["canEdit"])
        self.assertNotIn("frameRate", config["config"])
        self.assertEqual(config["defaults"]["basePowerW"], 100)

    def test_files_outside_www_are_never_served(self):
        for path in ("/../monitor.py", "/..%2Fmonitor.py", "/config.json", "/sensor-bridge.ps1"):
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                self.get(path)
            self.assertEqual(error.exception.code, 404)

if __name__ == "__main__":
    unittest.main()

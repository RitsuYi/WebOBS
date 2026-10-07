"""WebOBS LAN monitor. Python 3.10+, no pip dependencies."""
import argparse
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import logging
import mimetypes
import os
from pathlib import Path
import secrets
import signal
import socket
import sys
import threading
import time
from urllib.parse import urlsplit, parse_qs

from hardware import HardwareCollector, demo_sample

ROOT = Path(__file__).resolve().parent
WWW = ROOT / "www"
APP_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else ROOT
CONFIG_PATH = APP_ROOT / "config.json"
DEFAULTS = {
    "host": "0.0.0.0", "port": 8080, "sampleIntervalMs": 1000,
    "animationMs": 850, "sensorIntervalMs": 1000,
    "motherboardSensors": True, "elevatedSensors": True, "basePowerW": 100, "powerMode": "estimate", "psuEfficiency": 90,
    "maxPowerW": 650, "cpuWarningPercent": 85, "memoryWarningPercent": 87.5,
    "cpuPowerMaxW": 200, "brightness": 100, "cpuDevice": "", "gpuDevice": "",
    "demo": False, "sensors": {},
}
SENSOR_TYPES = {
    "cpu.usage": "Load", "cpu.frequencyMhz": "Clock", "cpu.voltageV": "Voltage", "cpu.powerW": "Power",
    "gpu.usage": "Load", "gpu.frequencyMhz": "Clock", "gpu.voltageV": "Voltage", "gpu.powerW": "Power",
    "system.powerW": "Power",
}

def validate_config(value):
    if not isinstance(value, dict):
        raise ValueError("配置必须是 JSON 对象。")
    unknown = set(value) - set(DEFAULTS)
    if unknown:
        raise ValueError("未知配置项：" + ", ".join(sorted(unknown)))
    result = copy.deepcopy(DEFAULTS)
    result.update(value)
    ranges = {"port": (1024, 65535), "sampleIntervalMs": (250, 10000), "animationMs": (0, 3000),
              "basePowerW": (0, 1000), "psuEfficiency": (50, 100), "maxPowerW": (50, 3000),
              "cpuWarningPercent": (10, 100), "memoryWarningPercent": (10, 100),
              "cpuPowerMaxW": (10, 1000), "brightness": (20, 140),
              "sensorIntervalMs": (1000, 10000)}
    for key, (low, high) in ranges.items():
        n = result[key]
        if isinstance(n, bool) or not isinstance(n, (int, float)) or not low <= n <= high:
            raise ValueError(f"{key} 必须在 {low}–{high} 之间。")
    for key in ("port", "sampleIntervalMs", "animationMs", "brightness", "sensorIntervalMs"):
        if int(result[key]) != result[key]:
            raise ValueError(f"{key} 必须是整数。")
        result[key] = int(result[key])
    try:
        ipaddress.ip_address(result["host"])
    except (ValueError, TypeError):
        raise ValueError("监听地址必须为有效 IP，例如 0.0.0.0 或 127.0.0.1。") from None
    if ":" in result["host"]:
        raise ValueError("当前版本使用 IPv4 监听地址。")
    if result["powerMode"] not in ("estimate", "wall", "measured"):
        raise ValueError("功率模式无效。")
    if not isinstance(result["demo"], bool):
        raise ValueError("demo 必须是布尔值。")
    for key in ("motherboardSensors", "elevatedSensors"):
        if not isinstance(result[key], bool):
            raise ValueError(key + " 必须是布尔值。")
    for key in ("cpuDevice", "gpuDevice"):
        if not isinstance(result[key], str) or len(result[key]) > 250:
            raise ValueError("设备标识无效。")
    if not isinstance(result["sensors"], dict) or any(k not in SENSOR_TYPES or not isinstance(v, str) or len(v) > 250
                                                    for k, v in result["sensors"].items()):
        raise ValueError("传感器映射无效。")
    return result

def lan_addresses():
    addresses = set()
    try:
        for entry in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = entry[4][0]
            if not ip.startswith("127."):
                addresses.add(ip)
    except OSError:
        pass
    return sorted(addresses)

class State:
    def __init__(self, config, config_path=CONFIG_PATH):
        self.config = config
        self.config_path = config_path
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self.collector = HardwareCollector(config)
        self.elevated_sensors = config["elevatedSensors"]
        self.sequence = 0
        self.telemetry = None
        self.stop = threading.Event()
        self.sample_now = threading.Event()
        self.token = secrets.token_urlsafe(32)
        self.addresses = lan_addresses()
        self.bound_host, self.bound_port = config["host"], config["port"]

    def current_config(self):
        with self.lock:
            return copy.deepcopy(self.config)

    def save_config(self, config):
        with self.lock:
            temp = self.config_path.with_suffix(".json.tmp")
            temp.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temp, self.config_path)
            self.config = config
        self.sample_now.set()

    def run(self):
        while not self.stop.is_set():
            config = self.current_config()
            try:
                telemetry = demo_sample(config) if config["demo"] else self.collector.sample(config)
                telemetry["address"] = f"{self.addresses[0] if self.addresses else '127.0.0.1'}:{self.bound_port}"
                telemetry["basePowerW"] = config["basePowerW"]
                telemetry["config"] = {key: config[key] for key in ("animationMs", "maxPowerW", "cpuWarningPercent",
                                                                    "memoryWarningPercent", "cpuPowerMaxW", "brightness", "sampleIntervalMs")}
                with self.lock:
                    self.sequence += 1
                    telemetry["sequence"] = self.sequence
                    self.telemetry = telemetry
                    self.changed.notify_all()
            except Exception:
                logging.exception("Telemetry sample failed")
            self.sample_now.wait(config["sampleIntervalMs"] / 1000)
            self.sample_now.clear()

    def snapshot(self, demo=False):
        with self.lock:
            if demo:
                result = demo_sample(self.config)
                result["address"] = "PREVIEW · DEMO"
                result["basePowerW"] = self.config["basePowerW"]
                result["config"] = {key: self.config[key] for key in ("animationMs", "maxPowerW", "cpuWarningPercent",
                                                                      "memoryWarningPercent", "cpuPowerMaxW", "brightness", "sampleIntervalMs")}
                result["sequence"] = self.sequence
                return result
            return copy.deepcopy(self.telemetry)

    def wait_sample(self, sequence, demo=False):
        with self.changed:
            if self.sequence == sequence and not self.stop.is_set():
                self.changed.wait(timeout=10)
            if demo:
                return self.snapshot(True)
            return self.telemetry

class Handler(BaseHTTPRequestHandler):
    server_version = "WebOBS/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        if args and str(args[0]).startswith(('GET /api/telemetry', 'GET /api/events')):
            return
        logging.info("%s %s", self.client_address[0], fmt % args)

    @property
    def state(self):
        return self.server.state

    def json_response(self, value, status=200):
        data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def is_local(self):
        try:
            return ipaddress.ip_address(self.client_address[0]).is_loopback
        except ValueError:
            return False

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/api/telemetry":
            return self.json_response(self.state.snapshot(parse_qs(parsed.query).get("demo") == ["1"]))
        if path == "/api/events":
            return self.stream(parse_qs(parsed.query).get("demo") == ["1"])
        if path == "/api/config":
            return self.json_response({"config": self.state.current_config(), "canEdit": self.is_local(),
                                       "token": self.state.token if self.is_local() else None,
                                       "defaults": DEFAULTS,
                                       "activePort": self.state.bound_port, "activeHost": self.state.bound_host})
        if path == "/api/sensors":
            return self.json_response({"hardware": self.state.collector.devices(), "mappingTypes": SENSOR_TYPES,
                                       "issues": (self.state.snapshot() or {}).get("issues", [])})
        if path == "/api/health":
            snapshot = self.state.snapshot()
            return self.json_response({"ok": bool(snapshot), "stale": not snapshot or time.time() - snapshot["timestamp"] > 15,
                                       "addresses": self.state.addresses, "port": self.state.bound_port,
                                       "processId": os.getpid(), "bridgeProcessId": (getattr(self.state.collector.bridge, "elevated_pid", None)
                                           or (self.state.collector.bridge.process.pid if self.state.collector.bridge.process else None)),
                                       "source": "demo" if self.state.current_config()["demo"] else "hardware"})
        if path in ("/", "/index.html"):
            relative = "index.html"
        elif path in ("/settings", "/settings/", "/settings.html"):
            relative = "settings.html"
        else:
            relative = path.lstrip("/")
        file = (WWW / relative).resolve()
        if not file.is_relative_to(WWW.resolve()) or not file.is_file():
            return self.json_response({"error": "Not found"}, 404)
        data = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", (mimetypes.guess_type(file.name)[0] or "application/octet-stream") + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'self'")
        self.end_headers()
        self.wfile.write(data)

    def stream(self, demo):
        # Thread per connected display. Sampling remains shared, not per connection.
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        sequence = -1
        heartbeat = time.monotonic()
        try:
            while not self.state.stop.is_set():
                packet = self.state.wait_sample(sequence, demo)
                if packet and packet["sequence"] != sequence:
                    self.wfile.write(("data: " + json.dumps(packet, ensure_ascii=False, allow_nan=False) + "\n\n").encode("utf-8"))
                    self.wfile.flush()
                    sequence = packet["sequence"]
                    heartbeat = time.monotonic()
                elif time.monotonic() - heartbeat > 10:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                    heartbeat = time.monotonic()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass

    def do_POST(self):
        if urlsplit(self.path).path != "/api/config":
            return self.json_response({"error": "Not found"}, 404)
        if not self.is_local():
            return self.json_response({"error": "请在运行监视器的电脑上打开 localhost 配置页修改参数。"}, 403)
        if not secrets.compare_digest(self.headers.get("X-WebOBS-Token", ""), self.state.token):
            return self.json_response({"error": "配置令牌已失效，请刷新页面。"}, 403)
        origin = self.headers.get("Origin")
        if origin and urlsplit(origin).netloc != self.headers.get("Host"):
            return self.json_response({"error": "不接受跨站配置请求。"}, 403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length < 32768:
                return self.json_response({"error": "无效的请求长度。"}, 400)
            value = json.loads(self.rfile.read(length))
            config = validate_config(value)
            self.state.save_config(config)
            restart = (config["port"] != self.state.bound_port or config["host"] != self.state.bound_host
                       or config["elevatedSensors"] != self.state.elevated_sensors)
            return self.json_response({"config": config, "restartRequired": restart})
        except (ValueError, json.JSONDecodeError) as exc:
            return self.json_response({"error": str(exc)}, 400)
        except OSError:
            logging.exception("Could not persist configuration")
            return self.json_response({"error": "配置文件写入失败。"}, 500)

def main():
    parser = argparse.ArgumentParser(description="WebOBS 本地电脑仪表盘 · LAN hardware monitor")
    parser.add_argument("--port", type=int)
    parser.add_argument("--host")
    parser.add_argument("--demo", action="store_true", help="明确启用演示数据（默认采集真实硬件）")
    parser.add_argument("--no-elevation", action="store_true", help="不请求临时采集授权；缺失指标显示为 —")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        config = validate_config(json.loads(CONFIG_PATH.read_text(encoding="utf-8"))) if CONFIG_PATH.exists() else copy.deepcopy(DEFAULTS)
        if args.port is not None:
            config["port"] = args.port
        if args.host:
            config["host"] = args.host
        if args.demo:
            config["demo"] = True
        if args.no_elevation:
            config["elevatedSensors"] = False
        config = validate_config(config)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    state = State(config)
    try:
        server = ThreadingHTTPServer((config["host"], config["port"]), Handler)
    except OSError as exc:
        state.collector.close()
        parser.error(f"无法监听 {config['host']}:{config['port']}：{exc}")
    server.daemon_threads = True
    server.state = state
    worker = threading.Thread(target=state.run, daemon=True, name="telemetry")
    worker.start()
    print(f"\n  WebOBS · http://localhost:{config['port']}\n  Settings · http://localhost:{config['port']}/settings", flush=True)
    for ip in state.addresses:
        print(f"  LAN · http://{ip}:{config['port']}", flush=True)
    print("  Ctrl+C to stop. Missing sensor data is displayed as —.\n", flush=True)
    def shutdown(*_):
        state.stop.set()
        with state.changed:
            state.changed.notify_all()
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)
    try:
        server.serve_forever(poll_interval=.25)
    finally:
        state.stop.set()
        state.sample_now.set()
        worker.join(timeout=5)
        server.server_close()
        state.collector.close()

if __name__ == "__main__":
    main()

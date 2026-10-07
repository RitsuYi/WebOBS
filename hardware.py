"""Read-only Windows telemetry. Missing sensors are None, never invented readings."""
import ctypes
from ctypes import wintypes
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import uuid

from elevation import launch_sensor, verify_pipe, signal_stop, close_handle, portable_platform_error
from cpu_usage import ProcessorUtility, SOURCE as UTILITY_SOURCE
from board_profiles import motherboard_voltages

ROOT = Path(__file__).resolve().parent
APP_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else ROOT
HIDDEN = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

class MemoryStatus(ctypes.Structure):
    _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
        (name, ctypes.c_ulonglong) for name in
        ("total", "available", "total_page", "available_page", "total_virtual", "available_virtual", "extended")]

class ProcessorPower(ctypes.Structure):
    _fields_ = [(name, wintypes.ULONG) for name in
               ("number", "max_mhz", "current_mhz", "mhz_limit", "max_idle", "current_idle")]

class JobBasicLimits(ctypes.Structure):
    _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                ("flags", wintypes.DWORD), ("min_working_set", ctypes.c_size_t),
                ("max_working_set", ctypes.c_size_t), ("active_processes", wintypes.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD)]

class JobExtendedLimits(ctypes.Structure):
    _fields_ = [("basic", JobBasicLimits), ("io_counters", ctypes.c_ulonglong * 6),
                ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t)]

class SensorJob:
    """Windows closes this parent's handle on exit, including console close or a crash."""
    def __init__(self, process):
        self.handle = None
        kernel = self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateJobObjectW(None, None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            limits = JobExtendedLimits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not kernel.AssignProcessToJobObject(handle, wintypes.HANDLE(int(process._handle))):
                raise ctypes.WinError(ctypes.get_last_error())
            self.handle = handle
        except OSError:
            kernel.CloseHandle(handle)
            raise

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None

def finite(value):
    try:
        number = float(value)
        return number if math.isfinite(number) and number >= 0 else None
    except (ValueError, TypeError):
        return None

def sensor_access():
    """Probe the current backend's driver access without installing or starting anything."""
    if os.name != "nt":
        return {"status": "unsupported", "message": "当前硬件采集后端需要 Windows。"}
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                  wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    # Match LHM's requested access; opening a handle does not write to the device.
    handle = kernel.CreateFileW(r"\\?\GLOBALROOT\Device\PawnIO", 0xC0000000, 3, None, 3, 0, None)
    if handle != ctypes.c_void_p(-1).value:
        kernel.CloseHandle(handle)
        return {"status": "available", "message": None}
    error = ctypes.get_last_error()
    if error in (2, 3):
        return {"status": "driver-missing", "message": "硬件驱动尚未加载；完整采集授权成功后可读取硬件支持的电压与功耗。"}
    if error == 5:
        return {"status": "access-denied", "message": "PawnIO 驱动拒绝当前进程访问；当前权限下缺失的传感器显示为 —。"}
    return {"status": "unavailable", "message": f"当前后端无法访问 PawnIO 驱动（Windows 错误 {error}）。"}

class WindowsMetrics:
    def __init__(self):
        self.previous = None
        self.utility = ProcessorUtility()

    def sample(self):
        if os.name != "nt":
            return {"usage": None, "frequencyMhz": None}, {"usage": None, "usedGb": None, "totalGb": None}
        idle, kernel, user = (wintypes.FILETIME() for _ in range(3))
        usage = None
        if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            def ticks(t):
                return (t.dwHighDateTime << 32) | t.dwLowDateTime
            current = (ticks(idle), ticks(kernel) + ticks(user))
            if self.previous:
                total = current[1] - self.previous[1]
                if total > 0:
                    usage = max(0, min(100, 100 * (1 - (current[0] - self.previous[0]) / total)))
            self.previous = current
        memory = MemoryStatus()
        memory.length = ctypes.sizeof(memory)
        ram = {"usage": None, "usedGb": None, "totalGb": None}
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            ram = {"usage": (memory.total - memory.available) / memory.total * 100,
                   "usedGb": (memory.total - memory.available) / 2 ** 30, "totalGb": memory.total / 2 ** 30}
        frequency = None
        count = os.cpu_count() or 1
        processors = (ProcessorPower * count)()
        result = ctypes.windll.powrprof.CallNtPowerInformation(11, None, 0, ctypes.byref(processors), ctypes.sizeof(processors))
        if result == 0:
            frequencies = [p.current_mhz for p in processors if p.current_mhz > 0]
            if frequencies:
                frequency = sum(frequencies) / len(frequencies)
        utility = self.utility.sample()
        source = {"name": "GetSystemTimes", "provider": "Windows API"}
        if utility is not None:
            usage, source = utility, dict(UTILITY_SOURCE)
        return {"usage": usage, "frequencyMhz": frequency, "usageSource": source}, ram

    def close(self):
        self.utility.close()

class NvidiaMetrics:
    """NVML gives low-overhead real GPU readings without launching a process per frame."""
    class Utilization(ctypes.Structure):
        _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

    def __init__(self):
        self.library = None
        self.count = 0
        if os.name != "nt":
            return
        paths = ["nvml.dll", str(Path(os.environ.get("WINDIR", "C:/Windows")) / "System32" / "nvml.dll"),
                 "C:/Program Files/NVIDIA Corporation/NVSMI/nvml.dll"]
        for path in paths:
            try:
                library = ctypes.CDLL(path)
                if library.nvmlInit_v2() == 0:
                    count = ctypes.c_uint()
                    library.nvmlDeviceGetCount_v2(ctypes.byref(count))
                    self.library, self.count = library, count.value
                    break
            except (OSError, AttributeError):
                continue

    def sample(self, index=0):
        if not self.library or not 0 <= index < self.count:
            return {}
        handle = ctypes.c_void_p()
        lib = self.library
        if lib.nvmlDeviceGetHandleByIndex_v2(ctypes.c_uint(index), ctypes.byref(handle)):
            return {}
        result = {"id": f"nvml:{index}", "source": "NVIDIA NVML"}
        name = ctypes.create_string_buffer(128)
        if lib.nvmlDeviceGetName(handle, name, len(name)) == 0:
            result["name"] = name.value.decode("utf-8", "replace")
        utilization = self.Utilization()
        if lib.nvmlDeviceGetUtilizationRates(handle, ctypes.byref(utilization)) == 0:
            result["usage"] = float(utilization.gpu)
        for key, method, args, divisor in [
            ("frequencyMhz", "nvmlDeviceGetClockInfo", [ctypes.c_uint(0)], 1),
            ("powerW", "nvmlDeviceGetPowerUsage", [], 1000),
            ("temperatureC", "nvmlDeviceGetTemperature", [ctypes.c_uint(0)], 1)]:
            value = ctypes.c_uint()
            try:
                if getattr(lib, method)(handle, *args, ctypes.byref(value)) == 0:
                    result[key] = value.value / divisor
            except AttributeError:
                pass
        return result

    def close(self):
        if self.library:
            self.library.nvmlShutdown()

class SensorBridge:
    """One small persistent .NET Framework process; PowerShell is a source fallback."""
    def __init__(self, config=None):
        self.lock = threading.Lock()
        self.data = {}
        self.error = None
        self.updated_at = 0
        self.process = None
        self.job = None
        self.stop_handle = None
        self.elevated_pid = None
        self.session_error = None
        self.stopping = False
        self.access = sensor_access()
        config = config or {}
        if config.get("demo"):
            return
        library = ROOT / "vendor" / "LibreHardwareMonitor" / "LibreHardwareMonitorLib.dll"
        if os.name != "nt" or not library.exists():
            self.error = "尚未安装硬件库。运行 python setup-hardware.py 可启用更多传感器。"
            return
        powershell = str(Path(os.environ.get("WINDIR", "C:/Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe")
        executable = ROOT / "vendor" / "WebOBSSensor.exe"
        if executable.exists():
            command = [str(executable), str(library.parent), str(APP_ROOT / "config.json")]
        elif Path(powershell).exists():
            command = [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                       "-File", str(ROOT / "sensor-bridge.ps1"), "-ConfigPath", str(APP_ROOT / "config.json")]
        else:
            self.error = "轻量采集程序和 Windows PowerShell 5.1 均不可用。"
            return
        self.command = command
        if config.get("elevatedSensors", True) and executable.exists() and self.access["status"] != "available":
            self.session_error = portable_platform_error()
            if self.session_error:
                self._start_normal()
            else:
                self.access = {"status": "authorization-pending", "message": "正在等待临时采集授权及硬件初始化。"}
                threading.Thread(target=self._start_elevated, args=(executable, library.parent),
                                 daemon=True, name="portable-sensors").start()
        else:
            self._start_normal()

    def _start_normal(self):
        if self.stopping:
            return
        try:
            self.process = subprocess.Popen(self.command, cwd=ROOT,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", errors="replace",
                                            creationflags=HIDDEN)
            self.job = SensorJob(self.process)
            threading.Thread(target=self._read, args=(self.process.stdout,), daemon=True, name="sensor-bridge").start()
            threading.Thread(target=self._read_errors, daemon=True, name="sensor-errors").start()
        except OSError as exc:
            self.error = str(exc)
            if self.process and self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=4)

    def _start_elevated(self, executable, library):
        handle = stop = stream = None
        try:
            name = f"WebOBS.Sensors.{os.getpid()}.{uuid.uuid4().hex}"
            handle, pid, stop = launch_sensor(executable, library, APP_ROOT / "config.json", name)
            self.elevated_pid = pid
            self.stop_handle = stop
            deadline = time.monotonic() + 30
            while not self.stopping:
                try:
                    stream = open("\\\\.\\pipe\\" + name, "rb")
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("临时采集进程没有建立数据通道。")
                    time.sleep(.1)
            if stream is None:
                return
            verify_pipe(stream, pid)
            self._read(stream)
        except OSError as error:
            cancelled = getattr(error, "winerror", None) == 1223
            self.session_error = ("已取消临时采集授权；可用指标继续读取，电压与功耗缺失项显示 —。" if cancelled
                                  else "临时硬件采集未启用：" + str(error))
        finally:
            if stream:
                stream.close()
            if stop:
                signal_stop(stop)
                self.stop_handle = None
                close_handle(stop)
            if handle:
                close_handle(handle)
            self.elevated_pid = None
            if not self.stopping:
                self.session_error = self.session_error or self.error or "临时采集进程已退出。"
                self.access = sensor_access()
                self._start_normal()

    def _read(self, stream):
        for line in stream:
            try:
                if isinstance(line, bytes):
                    line = line.decode("utf-8", "replace")
                packet = json.loads(line.strip())
                with self.lock:
                    self.data = packet
                    self.updated_at = time.monotonic()
                    self.error = packet.get("error")
                    if packet.get("access") == "portable-elevated":
                        self.access = {"status": "portable-elevated", "message": None}
            except json.JSONDecodeError:
                continue
        if not self.stopping:
            with self.lock:
                self.error = self.error or "硬件采集进程已退出；请检查采集后端的运行状态。"

    def _read_errors(self):
        for line in self.process.stderr:
            if line.strip():
                with self.lock:
                    self.error = line.strip()[:500]

    def snapshot(self, max_age=8):
        with self.lock:
            if not self.updated_at or time.monotonic() - self.updated_at > max_age:
                return {}, self.error or "硬件传感器初始化中，或采集已超时。"
            return dict(self.data), self.error or self.session_error

    def close(self):
        self.stopping = True
        if self.stop_handle:
            signal_stop(self.stop_handle)
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                self.process.kill()
        if self.job:
            self.job.close()

def pick(sensors, kind, names, selected=None, average=False):
    candidates = [s for s in sensors if s.get("type") == kind and finite(s.get("value")) is not None]
    if selected:
        match = next((s for s in candidates if s.get("id") == selected), None)
        return finite(match["value"]) if match else None
    for name in names:
        matches = [s for s in candidates if name.casefold() in s.get("name", "").casefold()]
        if matches:
            values = [float(s["value"]) for s in matches]
            return sum(values) / len(values) if average else values[0]
    return None

def cpu_sensor(devices, kind, names, selected=None):
    """Resolve an exact metric name; VIDs and individual cores are different readings."""
    candidates = [(d, s) for d in devices for s in d.get("sensors", []) if s.get("type") == kind]
    if selected:
        match = next(((d, s) for d, s in candidates if s.get("id") == selected), None)
    else:
        match = next(((d, s) for name in names for d, s in candidates
                      if s.get("name", "").strip().casefold() == name.casefold()
                      and finite(s.get("value")) is not None), None)
    if not match:
        return None, None
    device, sensor = match
    source = {"id": sensor.get("id"), "name": sensor.get("name"),
              "device": device.get("name"), "provider": "LibreHardwareMonitor"}
    if sensor.get("calibration"):
        source.update({"calibration": sensor["calibration"], "rawValue": sensor.get("rawValue")})
    return finite(sensor.get("value")), source

class HardwareCollector:
    def __init__(self, config=None):
        self.windows = WindowsMetrics()
        self.nvidia = NvidiaMetrics()
        self.bridge = SensorBridge(config)
        self.started = time.monotonic()
        self.catalog = []

    def sample(self, config):
        cpu, memory = self.windows.sample()
        cpu.update({"name": "CPU", "voltageV": None, "powerW": None, "temperatureC": None, "source": "Windows API"})
        cpu["sensorSources"] = {"usage": cpu.pop("usageSource", {"name": "GetSystemTimes", "provider": "Windows API"}),
                                "voltageV": None, "powerW": None}
        packet, bridge_error = self.bridge.snapshot(max_age=config["sensorIntervalMs"] / 1000 * 3 + 5)
        devices = motherboard_voltages(packet.get("hardware", []))
        self.catalog = devices
        cpus = [d for d in devices if d.get("type") == "Cpu"]
        gpus = [d for d in devices if d.get("type", "").startswith("Gpu")]
        selected_cpu = next((d for d in cpus if d.get("id") == config["cpuDevice"]), None) if config["cpuDevice"] else (cpus[0] if cpus else None)
        selected_gpu = next((d for d in gpus if d.get("id") == config["gpuDevice"]), None)
        if not config["gpuDevice"] and not selected_gpu and gpus:
            selected_gpu = next((d for d in gpus if d.get("type") != "GpuIntel"), gpus[0])
        gpu_id = config.get("gpuDevice", "")
        nv_index = int(gpu_id.split(":")[1]) if gpu_id.startswith("nvml:") and gpu_id.split(":")[1].isdigit() else 0
        # An explicitly selected non-NVIDIA GPU must never receive NVML values from another device.
        allow_nv = (not gpu_id or gpu_id.startswith("nvml:") or (selected_gpu and selected_gpu.get("type") == "GpuNvidia"))
        nv = self.nvidia.sample(nv_index) if allow_nv and (not selected_gpu or selected_gpu.get("type") == "GpuNvidia") else {}
        if selected_gpu and selected_gpu.get("type") == "GpuNvidia" and not gpu_id.startswith("nvml:"):
            # Match the LHM adapter to its NVIDIA index by normalized product name.
            normalize = lambda name: name.casefold().replace("nvidia", "").strip()
            nv = next((reading for i in range(self.nvidia.count)
                       if normalize((reading := self.nvidia.sample(i)).get("name", "")) == normalize(selected_gpu["name"])), {})
        gpu = {"name": "GPU", "usage": None, "frequencyMhz": None, "voltageV": None,
               "powerW": None, "temperatureC": None, "source": "unavailable"}
        gpu.update(nv)
        mapping = config["sensors"]
        if selected_cpu:
            sensors = selected_cpu.get("sensors", [])
            cpu["name"] = selected_cpu["name"]
            for key, kind, names, average in [
                ("frequencyMhz", "Clock", ["CPU Core", "P-Core #", "Core #"], True),
                ("temperatureC", "Temperature", ["CPU Package", "Tctl", "Core Average", "CPU Die"], False)]:
                value = pick(sensors, kind, names, mapping.get("cpu." + key), average)
                if value is not None or mapping.get("cpu." + key):
                    cpu[key] = value
            cpu["source"] = "LibreHardwareMonitor + Windows API"
        # The requested voltage is motherboard Vcore, not a CPU-requested VID.
        boards = [d for d in devices if d.get("type") in ("Motherboard", "SuperIO")]
        boards.sort(key=lambda d: "nct6798d" not in d.get("name", "").casefold())
        for key, kind, names, scope in [
            ("usage", "Load", ["Core Usages", "Total CPU Usage", "CPU Total"], [selected_cpu] if selected_cpu else []),
            ("voltageV", "Voltage", ["Vcore", "CPU VCore"], boards),
            ("powerW", "Power", ["CPU Package Power", "CPU Package", "PPT"], [selected_cpu] if selected_cpu else [])]:
            selected = mapping.get("cpu." + key)
            if key == "usage" and not selected and cpu["sensorSources"]["usage"].get("provider") == "Windows PDH":
                continue  # A library's busy-time load must not replace aggregate Windows utility.
            value, source = cpu_sensor(devices if selected else scope, kind, names, selected)
            if key != "usage" or source is not None or selected:
                cpu[key] = value
                cpu["sensorSources"][key] = source
        if selected_gpu:
            sensors = selected_gpu.get("sensors", [])
            gpu["name"] = selected_gpu["name"]
            gpu["source"] = "LibreHardwareMonitor" + (" + NVIDIA NVML" if nv else "")
            for key, kind, names in [
                ("usage", "Load", ["GPU Core", "D3D 3D", "GPU D3D 3D"]),
                ("frequencyMhz", "Clock", ["GPU Core"]),
                ("voltageV", "Voltage", ["GPU Core", "GPU Voltage", "Core"]),
                ("powerW", "Power", ["GPU Package", "GPU Board", "GPU Power", "GPU Total"]),
                ("temperatureC", "Temperature", ["GPU Core", "GPU Temperature"])]:
                value = pick(sensors, kind, names, mapping.get("gpu." + key))
                if value is not None or mapping.get("gpu." + key):
                    gpu[key] = value
        # Explicit mappings may refer to a motherboard or power-meter sensor.
        all_sensors = [s for d in devices for s in d.get("sensors", [])]
        for unit, target in [("cpu", cpu), ("gpu", gpu)]:
            for key, kind in [("usage", "Load"), ("frequencyMhz", "Clock"), ("voltageV", "Voltage"), ("powerW", "Power")]:
                if unit == "cpu" and key in ("usage", "voltageV", "powerW"):
                    continue
                selected = mapping.get(unit + "." + key)
                if selected:
                    target[key] = pick(all_sensors, kind, [], selected)
        if cpu.get("powerW") == 0 and cpu.get("temperatureC") is None:
            cpu["powerW"] = None
        measured = pick(all_sensors, "Power", [], mapping.get("system.powerW")) if mapping.get("system.powerW") else None
        power, power_source = calculate_power(cpu.get("powerW"), gpu.get("powerW"), measured, config)
        issues = []
        if config["cpuDevice"] and not selected_cpu:
            cpu.update({"name": "选定 CPU 不可用", "usage": None, "frequencyMhz": None, "powerW": None, "voltageV": None})
            cpu["sensorSources"] = {"usage": None, "voltageV": None, "powerW": None}
            power, power_source = calculate_power(None, gpu.get("powerW"), measured, config)
            issues.append("选定的 CPU 设备未发现，请刷新设备列表。")
        if gpu_id and not selected_gpu and not nv:
            issues.append("选定的 GPU 设备未发现，请刷新设备列表。")
        if bridge_error:
            issues.append(bridge_error)
        if cpu["powerW"] is None:
            issues.append("当前采集后端未提供 CPU Package Power 读数，请检查数据来源或绑定封装功耗传感器。")
        if cpu["voltageV"] is None:
            issues.append("当前采集后端未提供主板 Vcore 读数，请检查主板传感器和数据来源。")
        access = getattr(self.bridge, "access", None)
        if access and access.get("message") and (cpu["powerW"] is None or cpu["voltageV"] is None):
            issues.append(access["message"])
        if gpu["voltageV"] is None:
            issues.append("GPU 电压传感器不可用。此读数不会以固定值代替。")
        if config["powerMode"] == "measured" and measured is None:
            issues.append("未读到绑定的整机功率传感器。请在配置页选择可用的 Power 传感器。")
        return {"timestamp": time.time(), "cpu": cpu, "gpu": gpu, "memory": memory,
                "systemPowerW": power, "powerSource": power_source, "demo": False,
                "uptimeSeconds": time.monotonic() - self.started, "issues": issues, "sensorAccess": access}

    def devices(self):
        devices = list(self.catalog)
        known_names = {d.get("name", "").casefold() for d in devices}
        for i in range(self.nvidia.count):
            gpu = self.nvidia.sample(i)
            if gpu and gpu.get("name", "").casefold() not in known_names:
                devices.append({"id": f"nvml:{i}", "name": gpu["name"], "type": "GpuNvidia", "sensors": []})
        return devices

    def close(self):
        self.bridge.close()
        self.windows.close()
        self.nvidia.close()

def calculate_power(cpu, gpu, measured, config):
    if config["powerMode"] == "measured":
        return finite(measured), "measured"
    if cpu is None or gpu is None:
        return None, "estimated"
    base = cpu + gpu + config["basePowerW"]
    if config["powerMode"] == "wall":
        return base / (config["psuEfficiency"] / 100), "wall-estimate"
    return base, "estimated"

def demo_sample(config, t=None):
    t = time.monotonic() if t is None else t
    cpu = {"name": "DEMO · CPU", "usage": 63 + 12 * math.sin(t / 5), "frequencyMhz": 4850 + 90 * math.sin(t / 7),
           "voltageV": 1.21 + .03 * math.sin(t / 5), "powerW": 95 + 18 * math.sin(t / 5), "temperatureC": 58, "source": "Demo"}
    gpu = {"name": "DEMO · GPU", "usage": 68 + 19 * math.sin(t / 6), "frequencyMhz": 2720 + 60 * math.sin(t / 6),
           "voltageV": .96 + .04 * math.sin(t / 6), "powerW": 117 + 28 * math.sin(t / 6), "temperatureC": 54, "source": "Demo"}
    memory = {"usage": 74 + 2 * math.sin(t / 12), "usedGb": (74 + 2 * math.sin(t / 12)) * 32 / 100, "totalGb": 32}
    power, source = calculate_power(cpu["powerW"], gpu["powerW"], 312, config)
    return {"timestamp": time.time(), "cpu": cpu, "gpu": gpu, "memory": memory, "systemPowerW": power,
            "powerSource": source, "demo": True, "uptimeSeconds": t, "issues": ["演示模式：当前为模拟数据，可在配置页切回真实采集。"]}

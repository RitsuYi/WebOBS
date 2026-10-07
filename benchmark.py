"""Read CPU times and working sets for the running telemetry service only."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parent

class ProcessMemory(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("page_faults", wintypes.DWORD)] + [
        (key, ctypes.c_size_t) for key in ("peak_working_set", "working_set", "peak_paged", "paged",
                                         "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile", "private")]

def process_snapshot(pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    handle = kernel.OpenProcess(0x0400 | 0x0010, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        created, exited, system, user = (wintypes.FILETIME() for _ in range(4))
        if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(system), ctypes.byref(user)):
            raise ctypes.WinError(ctypes.get_last_error())
        cpu = ((system.dwHighDateTime << 32) | system.dwLowDateTime) + ((user.dwHighDateTime << 32) | user.dwLowDateTime)
        memory = ProcessMemory()
        memory.cb = ctypes.sizeof(memory)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessMemory), wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"cpuSeconds": cpu / 1e7, "workingSetMb": memory.working_set / 2 ** 20, "privateMb": memory.private / 2 ** 20}
    finally:
        kernel.CloseHandle(handle)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    with urllib.request.urlopen(f"http://localhost:{args.port}/api/health") as response:
        health = json.load(response)
    pids = {"server": health["processId"]}
    if health["bridgeProcessId"]:
        pids["sensorBridge"] = health["bridgeProcessId"]
    first = {key: process_snapshot(pid) for key, pid in pids.items()}
    print(f"Measuring {pids} for {args.seconds:g}s. Browser rendering is excluded.", flush=True)
    start = time.monotonic()
    time.sleep(args.seconds)
    elapsed = time.monotonic() - start
    report = {"durationSeconds": elapsed, "logicalProcessors": os.cpu_count(), "port": args.port,
              "dataSource": health["source"], "processes": {}, "notes": "Steady-state CPU sampling with connected SSE displays; browser rendering and service startup excluded."}
    total_cpu = total_memory = 0
    for key, pid in pids.items():
        last = process_snapshot(pid)
        cpu = (last["cpuSeconds"] - first[key]["cpuSeconds"]) / elapsed * 100
        total_cpu += cpu
        total_memory += last["workingSetMb"]
        report["processes"][key] = {"pid": pid, "cpuPercentOfOneCore": round(cpu, 4),
                                   "cpuPercentWholeMachine": round(cpu / os.cpu_count(), 4),
                                   "workingSetMb": round(last["workingSetMb"], 2), "privateMb": round(last["privateMb"], 2)}
    report["totalCpuPercentWholeMachine"] = round(total_cpu / os.cpu_count(), 4)
    report["totalWorkingSetMb"] = round(total_memory, 2)
    destination = ROOT / "verification" / "performance.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

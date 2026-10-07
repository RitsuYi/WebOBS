"""Launch only the temporary sensor helper through the Windows UAC consent UI."""
import ctypes
from ctypes import wintypes
import os
import subprocess
import sys


def portable_platform_error():
    """The bundled legacy AMD64 driver is supported on modern Windows only."""
    if os.name != "nt" or sys.getwindowsversion().build < 19041:
        return "便携硬件采集需要 Windows 10 2004 或更新版本。"
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.IsWow64Process2.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.USHORT), ctypes.POINTER(wintypes.USHORT)]
    process_machine, native_machine = wintypes.USHORT(), wintypes.USHORT()
    if not kernel.IsWow64Process2(kernel.GetCurrentProcess(), ctypes.byref(process_machine), ctypes.byref(native_machine)):
        return "无法确认硬件驱动兼容性，已跳过临时驱动加载。"
    if native_machine.value != 0x8664:
        return "当前便携硬件驱动支持 Intel / AMD x64 电脑。"
    return None


class ShellExecuteInfo(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("mask", wintypes.ULONG), ("window", wintypes.HWND),
                ("verb", wintypes.LPCWSTR), ("file", wintypes.LPCWSTR), ("parameters", wintypes.LPCWSTR),
                ("directory", wintypes.LPCWSTR), ("show", ctypes.c_int), ("instance", wintypes.HINSTANCE),
                ("id_list", ctypes.c_void_p), ("class_name", wintypes.LPCWSTR), ("class_key", wintypes.HKEY),
                ("hot_key", wintypes.DWORD), ("icon", wintypes.HANDLE), ("process", wintypes.HANDLE)]


def parent_creation_time():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    values = [wintypes.FILETIME() for _ in range(4)]
    if not kernel.GetProcessTimes(kernel.GetCurrentProcess(), *(ctypes.byref(v) for v in values)):
        raise ctypes.WinError(ctypes.get_last_error())
    return (values[0].dwHighDateTime << 32) | values[0].dwLowDateTime


def launch_sensor(executable, library, config, pipe_name):
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    shell.ShellExecuteExW.argtypes = [ctypes.POINTER(ShellExecuteInfo)]
    shell.ShellExecuteExW.restype = wintypes.BOOL
    kernel.GetProcessId.argtypes = [wintypes.HANDLE]
    kernel.GetProcessId.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateEventW.restype = wintypes.HANDLE
    stop = kernel.CreateEventW(None, True, False, None)
    if not stop:
        raise ctypes.WinError(ctypes.get_last_error())
    info = ShellExecuteInfo()
    info.size = ctypes.sizeof(info)
    info.mask = 0x40 | 0x8000  # Keep the process handle; don't create a visible console.
    info.verb, info.file, info.directory, info.show = "runas", str(executable), str(executable.parent), 0
    info.parameters = subprocess.list2cmdline([str(library), str(config), "--portable", str(os.getpid()),
                                              str(parent_creation_time()), pipe_name, str(stop)])
    if not shell.ShellExecuteExW(ctypes.byref(info)):
        error = ctypes.get_last_error()
        kernel.CloseHandle(stop)
        raise ctypes.WinError(error)
    pid = kernel.GetProcessId(info.process)
    if not pid:
        kernel.CloseHandle(info.process)
        kernel.CloseHandle(stop)
        raise OSError("无法识别临时采集进程。")
    return info.process, pid, stop


def verify_pipe(stream, expected_pid):
    import msvcrt
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetNamedPipeServerProcessId.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG)]
    actual = wintypes.ULONG()
    if not kernel.GetNamedPipeServerProcessId(wintypes.HANDLE(msvcrt.get_osfhandle(stream.fileno())), ctypes.byref(actual)):
        raise ctypes.WinError(ctypes.get_last_error())
    if actual.value != expected_pid:
        raise OSError("临时采集数据通道的进程身份不匹配。")


def signal_stop(handle):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.SetEvent.argtypes = [wintypes.HANDLE]
    kernel.SetEvent(handle)


def close_handle(handle):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle(handle)

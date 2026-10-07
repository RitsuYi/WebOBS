"""Windows aggregate CPU utility, including the OS's current performance accounting."""
import ctypes
from ctypes import wintypes
import math
import os

COUNTER_PATH = r"\Processor Information(_Total)\% Processor Utility"
SOURCE = {"id": "windows:processor-utility", "name": "Total CPU Usage (% Processor Utility)", "provider": "Windows PDH"}


class CounterValue(ctypes.Structure):
    # PDH_FMT_COUNTERVALUE contains a DWORD and an aligned union; read its double member.
    _fields_ = [("status", wintypes.DWORD), ("value", ctypes.c_double)]


class ProcessorUtility:
    def __init__(self):
        self.pdh = self.query = self.counter = None
        self.primed = False
        if os.name != "nt":
            return
        try:
            pdh = self.pdh = ctypes.WinDLL("pdh", use_last_error=True)
            pdh.PdhOpenQueryW.argtypes = [wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(wintypes.HANDLE)]
            pdh.PdhAddEnglishCounterW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, ctypes.c_size_t,
                                                 ctypes.POINTER(wintypes.HANDLE)]
            pdh.PdhCollectQueryData.argtypes = [wintypes.HANDLE]
            pdh.PdhGetFormattedCounterValue.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
                                                       ctypes.POINTER(CounterValue)]
            pdh.PdhCloseQuery.argtypes = [wintypes.HANDLE]
            query = wintypes.HANDLE()
            if pdh.PdhOpenQueryW(None, 0, ctypes.byref(query)):
                return
            self.query = query
            counter = wintypes.HANDLE()
            # English paths work independently of the Windows display language.
            if pdh.PdhAddEnglishCounterW(query, COUNTER_PATH, 0, ctypes.byref(counter)):
                self.close()
                return
            self.counter = counter
        except (OSError, AttributeError):
            self.close()

    def sample(self):
        if not self.query or not self.counter:
            return None
        if self.pdh.PdhCollectQueryData(self.query):
            self.primed = False
            return None
        if not self.primed:
            self.primed = True
            return None  # This delta counter needs two samples.
        value = CounterValue()
        # Preserve turbo values during formatting, then cap the displayed percentage at 100.
        if self.pdh.PdhGetFormattedCounterValue(self.counter, 0x200 | 0x8000, None, ctypes.byref(value)):
            return None
        if value.status not in (0, 1) or not math.isfinite(value.value) or value.value < 0:
            return None
        return min(100.0, value.value)

    def close(self):
        if self.query:
            self.pdh.PdhCloseQuery(self.query)
            self.query = self.counter = None

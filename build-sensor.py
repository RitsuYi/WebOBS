"""Use Windows' bundled .NET Framework compiler; no SDK installation required."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent

def main():
    framework = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET" / "Framework64" / "v4.0.30319"
    compiler = framework / "csc.exe"
    if not compiler.exists():
        raise RuntimeError("The bundled .NET Framework compiler is unavailable. PowerShell fallback remains available.")
    destination = ROOT / "vendor" / "WebOBSSensor.exe"
    library = ROOT / "vendor" / "LibreHardwareMonitor" / "LibreHardwareMonitorLib.dll"
    if not library.exists():
        raise RuntimeError("Run python setup-hardware.py first.")
    subprocess.run([str(compiler), "/nologo", "/optimize+", "/target:exe", "/platform:x64",
                    "/reference:" + str(library), "/reference:" + str(framework / "System.Web.Extensions.dll"),
                    "/reference:" + str(framework / "System.Core.dll"),
                    "/out:" + str(destination), str(ROOT / "SensorBridge.cs"), str(ROOT / "PortableSensors.cs")], cwd=ROOT, check=True)
    print(f"Lightweight sensor bridge ready: {destination}")

if __name__ == "__main__":
    main()

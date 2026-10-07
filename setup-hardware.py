"""Download the pinned official sensor library; no driver installation or deletion."""
import hashlib
import io
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
URL = "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/download/v0.9.6/LibreHardwareMonitor.zip"
SHA256 = "086d9f1b5a99e643edc2cfaaac16051685b551e4c5ac0b32a57c58c0e529c001"

def main():
    print("Downloading official LibreHardwareMonitor 0.9.6 (6.6 MB)...", flush=True)
    request = urllib.request.Request(URL, headers={"User-Agent": "WebOBS/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        archive = response.read()
    if hashlib.sha256(archive).hexdigest() != SHA256:
        raise RuntimeError("Checksum mismatch. Nothing has been extracted.")
    destination = ROOT / "vendor" / "LibreHardwareMonitor"
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        for member in bundle.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise RuntimeError("Unsafe archive entry")
        bundle.extractall(destination)
    print(f"Sensor library ready: {destination}")
    print("CPU power/voltage require the official PawnIO driver and administrator access.")
    print("This script does not install drivers. See README.md.")

if __name__ == "__main__":
    main()

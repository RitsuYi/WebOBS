"""Unpack official PyPI wheels into the workspace without invoking pip cleanup."""
import hashlib
import io
import json
import time
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
PACKAGES = {"pyinstaller": "6.22.3", "altgraph": None, "packaging": None, "pefile": None,
            "pyinstaller-hooks-contrib": None, "pywin32-ctypes": None, "setuptools": None}

def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "WebOBS-build/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except OSError:
            if attempt == 3:
                raise
            print(f"Retrying download ({attempt + 1}/3)...", flush=True)
            time.sleep(attempt + 1)

def main():
    target = ROOT / ".build-tools"
    target.mkdir(exist_ok=True)
    manifest = []
    for name, version in PACKAGES.items():
        package_path = name.replace("-", "_")
        path = f"{package_path}/{version}" if version else package_path
        data = json.loads(fetch(f"https://pypi.org/pypi/{path}/json"))
        wheels = [entry for entry in data["urls"] if entry["filename"].endswith(".whl") and
                  (entry["filename"].endswith("win_amd64.whl") if name == "pyinstaller" else entry["filename"].endswith("none-any.whl"))]
        if not wheels:
            raise RuntimeError(f"No compatible official wheel for {name}")
        wheel = wheels[0]
        print(f"Downloading {name} {data['info']['version']}...", flush=True)
        raw = fetch(wheel["url"])
        if hashlib.sha256(raw).hexdigest() != wheel["digests"]["sha256"]:
            raise RuntimeError("Wheel checksum mismatch")
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            for member in archive.infolist():
                if not (target / member.filename).resolve().is_relative_to(target.resolve()):
                    raise RuntimeError("Unsafe wheel entry")
            archive.extractall(target)
        manifest.append({"name": name, "version": data["info"]["version"], "sha256": wheel["digests"]["sha256"]})
    (target / "download-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Build tools ready. Run python build.py. No existing files or directories were deleted.")

if __name__ == "__main__":
    main()

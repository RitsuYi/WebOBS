"""Build into a new directory. Never cleans or deletes an existing directory."""
import argparse
import os
from pathlib import Path
import subprocess
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description="Build a portable Windows executable")
    parser.add_argument("--output", default="dist", help="New output directory (must not contain WebOBS)")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT):
        parser.error("Output must stay inside the project.")
    if (output / "WebOBS").exists():
        parser.error("WebOBS already exists. Choose a different --output. No files will be deleted.")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / ".build-tools")
    env["PYINSTALLER_CONFIG_DIR"] = str(ROOT / ".build-tools" / "cache")
    env["PYTHONUTF8"] = "1"
    work = ROOT / ".build" / ("build-" + uuid.uuid4().hex[:12])
    command = [sys.executable, "-m", "PyInstaller", "--onedir", "--console", "--noupx", "--name", "WebOBS",
               "--distpath", str(output), "--workpath", str(work), "--specpath", str(work),
               "--add-data", f"{ROOT / 'www'}:www", "--add-data", f"{ROOT / 'sensor-bridge.ps1'}:.",
               "--add-data", f"{ROOT / 'vendor' / 'LibreHardwareMonitor'}:vendor/LibreHardwareMonitor",
               "--add-data", f"{ROOT / 'vendor' / 'WebOBSSensor.exe'}:vendor",
               "--add-data", f"{ROOT / 'THIRD_PARTY.md'}:.", "--add-data", f"{ROOT / 'README.md'}:."]
    for name in ("PawnIO.sys", "manifest.json", "LICENSE-and-source.md", "COPYING", "PawnIO-2.1.0-source.zip", "PawnPP-source.zip"):
        command.extend(["--add-data", f"{ROOT / 'vendor' / 'PawnIO' / name}:vendor/PawnIO"])
    command.append(str(ROOT / "monitor.py"))
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    for name in ("README.md", "THIRD_PARTY.md"):
        shutil.copyfile(ROOT / name, output / "WebOBS" / name)
    shutil.copytree(ROOT / "docs", output / "WebOBS" / "docs")
    shutil.copyfile(ROOT / "docs" / "sensor-notes.md", output / "WebOBS" / "SENSOR-NOTES.md")
    # A fresh portable build uses this project's explicit settings, not a stale old build.
    if (ROOT / "config.json").exists():
        shutil.copyfile(ROOT / "config.json", output / "WebOBS" / "config.json")
    print(f"Ready: {output / 'WebOBS' / 'WebOBS.exe'}")

if __name__ == "__main__":
    main()

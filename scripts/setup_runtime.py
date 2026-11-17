import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if not python.is_file():
    subprocess.run([sys.executable, "-m", "venv", str(root / ".venv")], check=True)
subprocess.run([str(python), "-m", "pip", "install", str(root) + "[modbus]"], check=True)
print(str(python))

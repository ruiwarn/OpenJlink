import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if not python.is_file():
    raise SystemExit("Run python scripts/setup_runtime.py in this Skill directory first")
if Path(sys.prefix).resolve() == (root / ".venv").resolve():
    from openjlink.cli import main
    raise SystemExit(main())
os.execv(str(python), [str(python), str(root / "scripts/openjlink.py"), *sys.argv[1:]])

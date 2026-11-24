import os
from pathlib import Path
import sys

_LIBRARIES = {}


def discover_device_databases(tools=None):
    candidates = []
    for key in ("JLink.exe", "JLinkExe"):
        tool = (tools or {}).get(key)
        if tool:
            root = Path(tool).expanduser().resolve().parent
            candidates.extend((root / "JLinkDevices.xml", root / "Devices" / "JLinkDevices.xml"))
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            segger = Path(appdata) / "SEGGER"
            candidates.extend((segger / "JLinkDevices" / "JLinkDevices.xml", segger / "JLinkDevices.xml"))
    else:
        segger = Path.home() / ".config" / "SEGGER"
        candidates.extend((segger / "JLinkDevices" / "JLinkDevices.xml", segger / "JLinkDevices.xml"))
    found = set()
    for candidate in candidates:
        if candidate.is_file():
            found.add(str(candidate.resolve()))
    return sorted(found)


def new_probe(dll_path=None):
    import pylink
    key = str(Path(dll_path).expanduser().resolve()) if dll_path else ""
    library = _LIBRARIES.get(key)
    if library is None:
        library = pylink.library.Library(dllpath=dll_path, use_tmpcpy=False)
        _LIBRARIES[key] = library
    return pylink.JLink(lib=library, log=lambda text: print(text, file=sys.stderr),
                       error=lambda text: print(text, file=sys.stderr),
                       warn=lambda text: print(text, file=sys.stderr),
                       unsecure_hook=lambda title, message, flags: pylink.enums.JLinkFlags.DLG_BUTTON_NO)


def inventory(dll_path=None):
    probe = new_probe(dll_path)
    try:
        return [{"serial": int(p.SerialNumber), "product": p.acProduct.decode(errors="replace"),
                 "connection": int(p.Connection)} for p in probe.connected_emulators()]
    finally:
        probe.close()


def identity(probe):
    return {"product": probe.product_name, "hardware": probe.hardware_version,
            "firmware": probe.firmware_version, "core": probe.core_name(),
            "voltage_mv": int(probe.hardware_status.VTarget), "halted": bool(probe.halted()),
            "capabilities": int(probe.capabilities)}

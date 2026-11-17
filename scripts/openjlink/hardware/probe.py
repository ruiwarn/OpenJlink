import sys


def new_probe(dll_path=None):
    import pylink
    library = pylink.library.Library(dllpath=dll_path) if dll_path else None
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

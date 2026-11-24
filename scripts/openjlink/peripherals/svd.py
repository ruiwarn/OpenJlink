from pathlib import Path
from cmsis_svd.model import SVDPeripheral, SVDPeripheralArray
from cmsis_svd.parser import SVDParser
from lxml import etree
from openjlink.common import InputError, file_info, integer, memory_range


class Peripherals:
    def __init__(self, path, byte_order):
        if byte_order not in ("little", "big"):
            raise InputError("Explicit little/big byte_order required")
        self.source = file_info(path)
        if self.source["size"] > 8 * 1024 * 1024:
            raise InputError("SVD exceeds 8 MiB")
        parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
        tree = etree.fromstring(Path(self.source["path"]).read_bytes(), parser).getroottree()
        if tree.docinfo.doctype:
            raise InputError("SVD document types/entities are unsupported")
        expansion = 0
        for element in tree.iter():
            multiplier = 1
            for ancestor in (element, *element.iterancestors()):
                dim = ancestor.findtext("dim")
                if dim is not None:
                    multiplier *= integer(int(dim, 0), 1, 1024)
            expansion += multiplier
            if expansion > 200000:
                raise InputError("SVD expansion exceeds limit")
        device = SVDParser(tree).get_device()
        self.device = device.name
        self.byte_order = byte_order
        self.registers = {}
        for entry in device.peripherals:
            peripherals = entry.peripherals if isinstance(entry, SVDPeripheralArray) else [entry]
            for peripheral in peripherals:
                for register in peripheral.get_registers():
                    if not isinstance(register.parent, SVDPeripheral):
                        continue
                    name = peripheral.name + "." + register.name
                    if name in self.registers:
                        raise InputError("Ambiguous SVD register name")
                    fields = register.get_fields()
                    readable = register.access is not None and register.access.value in ("read-only", "read-write", "read-writeOnce")
                    safe = readable and register.read_action is None and all(f.read_action is None for f in fields)
                    address = peripheral.base_address + register.address_offset
                    size = register.size
                    if size not in (8, 16, 32) or address % (size // 8):
                        safe = False
                    self.registers[name] = {"name": name, "address": address, "bits": size,
                                            "access": register.access.value if register.access else None,
                                            "safe_read_declared": safe,
                                            "fields": [{"name": f.name, "offset": f.bit_offset, "width": f.bit_width,
                                                        "readable": f.access is None or f.access.value in ("read-only", "read-write", "read-writeOnce")}
                                                       for f in fields]}

    def current(self):
        if file_info(self.source["path"])["sha256"] != self.source["sha256"]:
            raise InputError("SVD source changed; reload before using register addresses")

    def catalog(self, query, limit):
        self.current()
        integer(limit, 1, 1000)
        matches = [v for k, v in sorted(self.registers.items()) if query.casefold() in k.casefold()]
        return {"source": self.source, "device": self.device, "registers": matches[:limit], "total": len(matches),
                "truncated": len(matches) > limit,
                "target_match": "caller must verify exact device/revision", "clusters": "unsupported"}

    def select(self, names):
        self.current()
        if not isinstance(names, list) or not 1 <= len(names) <= 16 or len(set(names)) != len(names):
            raise InputError("Supply 1..16 unique register names")
        result = []
        for name in names:
            register = self.registers.get(name)
            if not register or not register["safe_read_declared"]:
                raise InputError("Unknown, side-effecting, write-only, unaligned or unsupported register")
            memory_range(register["address"], register["bits"] // 8)
            for field in register["fields"]:
                integer(field["offset"], 0, register["bits"] - 1)
                integer(field["width"], 1, register["bits"] - field["offset"])
            result.append(register)
        return result

    def decode(self, register, data_hex):
        value = int.from_bytes(bytes.fromhex(data_hex), self.byte_order)
        return {"name": register["name"], "value": value,
                "fields": {f["name"]: (value >> f["offset"]) & ((1 << f["width"]) - 1)
                           for f in register["fields"] if f["readable"]}}

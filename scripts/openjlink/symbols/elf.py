import io
import posixpath
import re
import struct
from pathlib import Path
from elftools.elf.elffile import ELFFile
from elftools.dwarf.dwarf_expr import DWARFExprParser
from openjlink.common import InputError, file_info, memory_range


def images(path, base_address=None):
    info = file_info(path)
    if info["size"] > 64 * 1024 * 1024:
        raise InputError("Image exceeds 64 MiB")
    raw = Path(info["path"]).read_bytes()
    result = []
    if raw.startswith(b"\x7fELF"):
        elf = ELFFile(io.BytesIO(raw))
        result = [(int(s["p_paddr"]), s.data()) for s in elf.iter_segments()
                  if s["p_type"] == "PT_LOAD" and s["p_filesz"]]
    elif Path(path).suffix.lower() in (".hex", ".ihex"):
        upper, end, cells = 0, False, {}
        for line in raw.decode("ascii").splitlines():
            if not line.strip():
                continue
            if end or not line.startswith(":"):
                raise InputError("Invalid Intel HEX record/order")
            record = bytes.fromhex(line[1:])
            if len(record) < 5 or len(record) != record[0] + 5 or sum(record) % 256:
                raise InputError("Intel HEX length/checksum mismatch")
            size, address, kind = record[0], int.from_bytes(record[1:3], "big"), record[3]
            data = record[4:-1]
            if kind == 0:
                for offset, value in enumerate(data):
                    target = upper + address + offset
                    if target in cells and cells[target] != value:
                        raise InputError("Conflicting HEX records")
                    cells[target] = value
            elif kind in (2, 4) and size == 2 and address == 0:
                upper = int.from_bytes(data, "big") << (4 if kind == 2 else 16)
            elif kind == 1 and size == 0 and address == 0:
                end = True
            elif kind not in (3, 5) or size != 4:
                raise InputError("Unsupported HEX record")
        if not end:
            raise InputError("Intel HEX is missing EOF")
        for address in sorted(cells):
            if result and address == result[-1][0] + len(result[-1][1]):
                result[-1][1].append(cells[address])
            else:
                result.append((address, bytearray([cells[address]])))
        result = [(a, bytes(d)) for a, d in result]
    else:
        if Path(path).suffix.lower() != ".bin" or base_address is None:
            raise InputError("Use ELF/AXF/OUT, Intel HEX, or BIN with explicit base_address")
        result = [(base_address, raw)]
    if not result:
        raise InputError("Image has no programmed bytes")
    previous = -1
    for address, data in sorted(result):
        memory_range(address, len(data), 64 * 1024 * 1024)
        if address < previous:
            raise InputError("Overlapping load segments require an explicit image layout")
        previous = address + len(data)
    return info, result


def clip_segments(segments, ranges):
    if not isinstance(ranges, list) or not ranges:
        raise InputError("Supply 1..N target memory ranges")
    spans = []
    for item in sorted(ranges, key=lambda entry: entry.get("address", -1) if isinstance(entry, dict) else -1):
        if not isinstance(item, dict) or set(item) != {"address", "size"}:
            raise InputError("Each range requires exactly address and size")
        memory_range(item["address"], item["size"], 64 * 1024 * 1024)
        start, end = item["address"], item["address"] + item["size"]
        if spans and start <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], end)
        else:
            spans.append([start, end])
    clipped = []
    for req_start, req_end in spans:
        for seg_start, seg_data in segments:
            seg_end = seg_start + len(seg_data)
            lo, hi = max(req_start, seg_start), min(req_end, seg_end)
            if lo < hi:
                chunk = seg_data[lo - seg_start:hi - seg_start]
                if clipped and lo == clipped[-1][0] + len(clipped[-1][1]):
                    clipped[-1][1].extend(chunk)
                else:
                    clipped.append((lo, bytearray(chunk)))
    if not clipped:
        raise InputError("Image has no bytes within requested ranges")
    return [(addr, bytes(data)) for addr, data in clipped]


def _merge_segments(pairs):
    merged = []
    for address, data in sorted(pairs, key=lambda item: item[0]):
        if not data:
            continue
        if merged and address <= merged[-1][0] + len(merged[-1][1]):
            prev_addr, prev_data = merged[-1]
            overlap = prev_addr + len(prev_data) - address
            if overlap >= len(data):
                continue
            prev_data.extend(data[overlap:])
        else:
            merged.append((address, bytearray(data)))
    return [(addr, bytes(data)) for addr, data in merged]


def elf_section_segments(elf):
    load_segs = [s for s in elf.iter_segments() if s["p_type"] == "PT_LOAD" and s["p_filesz"]]
    pairs = []
    for sec in elf.iter_sections():
        if not (sec["sh_flags"] & 2) or sec["sh_type"] == "SHT_NOBITS" or sec["sh_size"] == 0:
            continue
        sec_off, sec_size, sec_addr = int(sec["sh_offset"]), int(sec["sh_size"]), int(sec["sh_addr"])
        in_file = [s for s in load_segs if int(s["p_offset"]) <= sec_off and sec_off + sec_size <= int(s["p_offset"]) + int(s["p_filesz"])]
        seg = next((s for s in in_file if int(s["p_vaddr"]) <= sec_addr <= int(s["p_vaddr"]) + int(s["p_memsz"])), in_file[0] if in_file else None)
        if seg is not None:
            lma = int(seg["p_paddr"]) + (sec_off - int(seg["p_offset"]))
            pairs.append((lma, sec.data()))
    return _merge_segments(pairs)


def _segments_cover(verified_segments, req_addr, req_data):
    pos = req_addr
    end = req_addr + len(req_data)
    for v_addr, v_data in verified_segments:
        v_end = v_addr + len(v_data)
        if v_end <= pos:
            continue
        if v_addr > pos:
            return False
        take_end = min(end, v_end)
        req_off = pos - req_addr
        v_off = pos - v_addr
        chunk_len = take_end - pos
        if req_data[req_off:req_off + chunk_len] != v_data[v_off:v_off + chunk_len]:
            return False
        pos = take_end
        if pos >= end:
            return True
    return pos >= end


def inspect_image(path: str, base_address: int | None = None):
    info, segments = images(path, base_address)
    return {"source": info, "ranges": [{"address": a, "size": len(d)} for a, d in segments],
            "programmed_bytes": sum(len(d) for a, d in segments), "hardware_accessed": False}


def _attribute_owner(die, name):
    visited = set()
    while name not in die.attributes:
        if die.offset in visited or "DW_AT_specification" not in die.attributes:
            return None
        visited.add(die.offset)
        die = die.get_DIE_from_attribute("DW_AT_specification")
    return die


def _cu_path(cu):
    top = cu.get_top_DIE()
    name_attr = top.attributes.get("DW_AT_name")
    if not name_attr:
        return ""
    cu_file = name_attr.value.decode(errors="replace").replace("\\", "/")
    comp_attr = top.attributes.get("DW_AT_comp_dir")
    if comp_attr and not posixpath.isabs(cu_file) and not re.match(r"^[A-Za-z]:/", cu_file):
        comp_dir = comp_attr.value.decode(errors="replace").replace("\\", "/")
        cu_file = posixpath.normpath(posixpath.join(comp_dir, cu_file))
    return cu_file


def _die_address(die):
    ops = DWARFExprParser(die.cu.structs).parse_expr(die.attributes["DW_AT_location"].value)
    if len(ops) == 1 and ops[0].op_name == "DW_OP_addr":
        return f"0x{ops[0].args[0]:08x}"
    return "non-fixed"


class Symbols:
    def __init__(self, path):
        self.info = file_info(path)
        self.elf = ELFFile(io.BytesIO(Path(self.info["path"]).read_bytes()))
        self.dwarf = self.elf.get_dwarf_info() if self.elf.has_dwarf_info() else None
        self.variables = {}
        if self.dwarf:
            for cu in self.dwarf.iter_CUs():
                cu_file = _cu_path(cu)
                for die in cu.iter_DIEs():
                    if die.tag != "DW_TAG_variable" or "DW_AT_location" not in die.attributes:
                        continue
                    owner = _attribute_owner(die, "DW_AT_name")
                    if owner is not None:
                        name = owner.attributes["DW_AT_name"].value.decode(errors="replace")
                        self.variables.setdefault(name, []).append((cu_file, die))

    def current(self):
        if file_info(self.info["path"])["sha256"] != self.info["sha256"]:
            raise InputError("Symbol source changed; reload symbols and verify the image")

    def matches_verified_segments(self, verified_segments):
        required = elf_section_segments(self.elf)
        if not required:
            return False
        ordered = _merge_segments(verified_segments)
        return all(_segments_cover(ordered, addr, data) for addr, data in required)

    def type_die(self, die):
        owner = _attribute_owner(die, "DW_AT_type")
        if owner is None:
            raise InputError("Variable or member type unavailable")
        die = owner.get_DIE_from_attribute("DW_AT_type")
        while die.tag in ("DW_TAG_typedef", "DW_TAG_const_type", "DW_TAG_volatile_type", "DW_TAG_restrict_type"):
            die = die.get_DIE_from_attribute("DW_AT_type")
        return die

    def size(self, die):
        if "DW_AT_byte_size" in die.attributes:
            return int(die.attributes["DW_AT_byte_size"].value)
        if die.tag == "DW_TAG_array_type":
            total = self.size(self.type_die(die))
            for sub in die.iter_children():
                if sub.tag == "DW_TAG_subrange_type":
                    count = sub.attributes.get("DW_AT_count")
                    upper = sub.attributes.get("DW_AT_upper_bound")
                    if count is None and upper is None:
                        raise InputError("Array size unavailable")
                    total *= count.value if count else upper.value + 1
            return total
        raise InputError("Type size unavailable")

    def resolve(self, name):
        self.current()
        if "::" in name:
            qualifier, expr = name.split("::", 1)
            if not qualifier or "::" in expr:
                raise InputError("Use optional file.c::variable, struct.member or array[index]")
            qualifier = qualifier.replace("\\", "/")
        else:
            qualifier, expr = None, name
        tokens = re.findall(r"[A-Za-z_]\w*|\[\d+\]", expr)
        if not tokens or ".".join(tokens).replace(".[", "[") != expr:
            raise InputError("Use a global variable, struct.member or array[index]")
        matches = self.variables.get(tokens[0], [])
        if qualifier is not None:
            matches = [(cu, d) for cu, d in matches if cu and (cu == qualifier or cu.endswith("/" + qualifier) or posixpath.basename(cu) == qualifier)]
        if not matches:
            raise InputError("Variable missing or ambiguous; optimized/local variables are not guessed")
        if len(matches) > 1:
            hints = [f"{posixpath.basename(cu) or '<unknown>'}::{tokens[0]}@{_die_address(d)}" for cu, d in matches[:8]]
            raise InputError(f"Ambiguous variable '{tokens[0]}'; qualify with file::name ({', '.join(hints)})")
        _, die = matches[0]
        ops = DWARFExprParser(die.cu.structs).parse_expr(die.attributes["DW_AT_location"].value)
        if len(ops) != 1 or ops[0].op_name != "DW_OP_addr":
            raise InputError("Variable has no fixed memory address")
        address = ops[0].args[0]
        typ = self.type_die(die)
        for token in tokens[1:]:
            if token.startswith("["):
                if typ.tag != "DW_TAG_array_type":
                    raise InputError("Indexing requires an array")
                if sum(d.tag == "DW_TAG_subrange_type" for d in typ.iter_children()) != 1:
                    raise InputError("Multidimensional/dynamic arrays require an explicit debugger context")
                item = self.type_die(typ)
                size = self.size(item)
                index = int(token[1:-1])
                if index >= self.size(typ) // size:
                    raise InputError("Array index out of range")
                address += index * size
                typ = item
            else:
                members = [m for m in typ.iter_children() if m.tag == "DW_TAG_member" and m.attributes.get("DW_AT_name") and m.attributes["DW_AT_name"].value.decode(errors="replace") == token]
                if len(members) != 1 or "DW_AT_bit_size" in members[0].attributes:
                    raise InputError("Member missing or unsupported bitfield")
                member = members[0]
                offset = member.attributes.get("DW_AT_data_member_location")
                if offset is not None and type(offset.value) is not int:
                    raise InputError("Dynamic member offset unsupported")
                address += offset.value if offset else 0
                typ = self.type_die(member)
        size = self.size(typ)
        memory_range(address, size)
        encoding = typ.attributes.get("DW_AT_encoding")
        code = encoding.value if encoding else None
        if typ.tag == "DW_TAG_enumeration_type" and code is None:
            code = 5 if any(e.attributes.get("DW_AT_const_value") and e.attributes["DW_AT_const_value"].value < 0 for e in typ.iter_children()) else 7
        return address, size, code, typ

    def decode(self, name, data):
        address, size, encoding, typ = self.resolve(name)
        endian = "little" if self.elf.little_endian else "big"
        if typ.tag == "DW_TAG_pointer_type":
            return {"pointer": int.from_bytes(data, endian)}
        if encoding == 4 and size in (4, 8):
            return struct.unpack(("<" if self.elf.little_endian else ">") + ("f" if size == 4 else "d"), data)[0]
        if encoding in (2, 5, 6, 7, 8) or typ.tag == "DW_TAG_enumeration_type":
            return int.from_bytes(data, endian, signed=encoding in (5, 6))
        return {"hex": data.hex(), "type": typ.tag}

    def encode(self, name, value):
        address, size, encoding, typ = self.resolve(name)
        if encoding == 4 and size in (4, 8):
            return struct.pack(("<" if self.elf.little_endian else ">") + ("f" if size == 4 else "d"), value)
        if type(value) is int and (encoding in (2, 5, 6, 7, 8) or typ.tag == "DW_TAG_enumeration_type"):
            return value.to_bytes(size, "little" if self.elf.little_endian else "big", signed=encoding in (5, 6))
        raise InputError("Writing supports scalar integer/enum/float, not pointers or aggregates")

    def search(self, query="", limit=100):
        self.current()
        if "::" in query:
            q = query.lower()
            names = [f"{posixpath.basename(cu) or '<unknown>'}::{n}" for n in sorted(self.variables) for cu, _ in self.variables[n] if q in f"{cu}::{n}".lower()]
            return {"generation": self.info["sha256"], "names": names[:limit]}
        return {"generation": self.info["sha256"], "names": [n for n in sorted(self.variables) if query.lower() in n.lower()][:limit]}

    def memory_map(self):
        return [{"name": s.name, "address": int(s["sh_addr"]), "size": int(s["sh_size"]), "type": s["sh_type"]} for s in self.elf.iter_sections() if s["sh_flags"] & 2]

    def location(self, address):
        self.current()
        if self.dwarf:
            for cu in self.dwarf.iter_CUs():
                program = self.dwarf.line_program_for_CU(cu)
                if not program:
                    continue
                previous = None
                for entry in program.get_entries():
                    state = entry.state
                    if state is None:
                        continue
                    if previous and previous.address <= address < state.address:
                        files = program["file_entry"]
                        version5 = program["version"] >= 5
                        entry = files[previous.file if version5 else previous.file - 1]
                        filename = entry.name.decode(errors="replace").replace("\\", "/")
                        comp = cu.get_top_DIE().attributes.get("DW_AT_comp_dir")
                        directory = comp.value.decode(errors="replace").replace("\\", "/") if comp else ""
                        index = entry.dir_index if version5 else entry.dir_index - 1
                        if index >= 0 and index < len(program["include_directory"]):
                            included = program["include_directory"][index].decode(errors="replace").replace("\\", "/")
                            directory = included if posixpath.isabs(included) or re.match(r"^[A-Za-z]:/", included) else posixpath.join(directory, included)
                        if not posixpath.isabs(filename) and not re.match(r"^[A-Za-z]:/", filename):
                            filename = posixpath.normpath(posixpath.join(directory, filename))
                        return {"address": address, "file": filename, "line": previous.line}
                    previous = None if state.end_sequence else state
        return {"address": address, "resolved": False}

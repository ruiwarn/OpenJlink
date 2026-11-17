import json
import struct
from pathlib import Path
from openjlink.common import InputError, file_info, hex_bytes, integer, number, write_json


def decode_packets(path: str, output: str, format: str, fields: list[str], timestamp_field: str,
                   tick_hz: float, sequence_field: str, sync_hex: str = "",
                   sequence_modulus: int = 4294967296, timestamp_modulus: int = 4294967296):
    number(tick_hz, 1, 1e12)
    integer(sequence_modulus, 2, 0x10000000000000000)
    integer(timestamp_modulus, 2, 0x10000000000000000)
    if not format or format[0] not in ("<", ">"):
        raise InputError("Packet format must explicitly select < or > byte order")
    codec = struct.Struct(format)
    if not 1 <= codec.size <= 4096 or not isinstance(fields, list) or any(not isinstance(x, str) or not x for x in fields) or len(set(fields)) != len(fields) or not 1 <= len(fields) <= 64:
        raise InputError("Invalid fixed packet size/fields")
    if timestamp_field not in fields or sequence_field not in fields:
        raise InputError("Timestamp and sequence fields must exist")
    if len(codec.unpack(bytes(codec.size))) != len(fields):
        raise InputError("Field count does not match packet format")
    sync = hex_bytes(sync_hex, 32) if sync_hex else b""
    info = file_info(path)
    if info["size"] > 64 * 1024 * 1024:
        raise InputError("Telemetry input exceeds 64 MiB")
    raw = Path(info["path"]).read_bytes()
    out = Path(output)
    if out.exists() or Path(str(out) + ".meta.json").exists():
        raise InputError("Output must not already exist")
    position = count = dropped = skipped = duplicates = elapsed_ticks = 0
    previous_sequence = previous_time = None
    meta = {"format": "openjlink-jsonl-v1", "kind": "variables", "clock": "target_ticks",
            "tick_hz": tick_hz, "source": info, "atomic": "packet grouping declared by caller; not independently verified"}
    with out.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps({"metadata": meta}) + "\n")
        while position < len(raw):
            if sync:
                found = raw.find(sync, position)
                if found == -1:
                    break
                skipped += found - position
                position = found + len(sync)
            if len(raw) - position < codec.size:
                if sync:
                    position -= len(sync)
                break
            values = dict(zip(fields, codec.unpack_from(raw, position)))
            position += codec.size
            timestamp, sequence = values[timestamp_field], values[sequence_field]
            integer(timestamp, 0, timestamp_modulus - 1)
            integer(sequence, 0, sequence_modulus - 1)
            if previous_sequence is not None:
                delta = (sequence - previous_sequence) % sequence_modulus
                if delta == 0:
                    duplicates += 1
                elif delta > sequence_modulus // 2:
                    raise InputError("Sequence reset/reorder detected; split recordings")
                else:
                    dropped += delta - 1
                time_delta = (timestamp - previous_time) % timestamp_modulus
                if time_delta > timestamp_modulus // 2:
                    raise InputError("Timestamp reset/reorder detected")
                elapsed_ticks += time_delta
            previous_sequence, previous_time = sequence, timestamp
            stream.write(json.dumps({"seq": count, "t_ns": round(elapsed_ticks / tick_hz * 1e9),
                                     "target_sequence": sequence, "target_timestamp": timestamp,
                                     "data": {k: {"value": v} for k, v in values.items() if k not in (timestamp_field, sequence_field)}}, allow_nan=False) + "\n")
            count += 1
            if count > 1000000:
                raise InputError("Telemetry record limit exceeded")
    result = {"recording": file_info(out), "samples": count, "detected_sequence_gaps": dropped,
              "duplicates": duplicates, "resync_bytes": skipped, "trailing_bytes": len(raw) - position,
              "complete": bool(count) and not (dropped or duplicates or skipped or len(raw) - position),
              "integrity": "sequence/timing only; packet checksum not checked by generic fixed-layout decoder"}
    write_json(str(out) + ".meta.json", result)
    return result

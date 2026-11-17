import json
import time
from pathlib import Path
from openjlink.common import InputError, file_info, integer, number, write_json


def capture(workbench, kind, duration, path, period, names, regions, channel):
    number(duration, 0.01, 3600)
    number(period, 0.0001, 60)
    if duration / period > 1000000:
        raise InputError("Capture exceeds one million requested samples; split recordings")
    if kind not in ("variables", "peripherals", "memory", "rtt", "systemview"):
        raise InputError("Use variables/peripherals/memory/rtt/systemview")
    if kind == "variables":
        if not isinstance(names, list) or not 1 <= len(names) <= 64 or len(set(names)) != len(names):
            raise InputError("Supply 1..64 unique symbol paths")
        for name in names:
            workbench.require_symbols().resolve(name)
    if kind == "memory":
        workbench.read_regions(regions)
    if kind == "peripherals":
        if workbench.peripherals is None:
            raise InputError("Load an explicit SVD first")
        workbench.peripherals.select(names)
    if kind in ("rtt", "systemview"):
        integer(channel, 0, 255)
        if not workbench.rtt:
            raise InputError("Start RTT explicitly before capturing")
    p = Path(path).expanduser().resolve()
    if not p.parent.is_dir() or p.exists() or Path(str(p) + ".meta.json").exists():
        raise InputError("Capture requires an existing parent and a new output filename")
    meta = {"format": "openjlink-jsonl-v1", "kind": "variables" if kind == "peripherals" else kind, "source_kind": kind, "target": dict(workbench.selection),
            "symbols": workbench.symbols.info if workbench.symbols else None,
            "peripherals": workbench.peripherals.source if kind == "peripherals" else None,
            "clock": "host_monotonic_ns", "atomic": False, "period_requested": period,
            "duration_requested": duration, "target_drop_count": None, "complete": False}
    count, payload, intervals, previous, error = 0, 0, [], None, None
    start = time.monotonic_ns()
    try:
        with p.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps({"metadata": meta}, allow_nan=False) + "\n")
            due = time.monotonic()
            while (time.monotonic_ns() - start) / 1e9 < duration and not workbench.cancel.is_set():
                begin = time.monotonic_ns()
                if kind == "variables":
                    values = {name: workbench.read_variable(name) for name in names}
                elif kind == "peripherals":
                    values = {r["name"]: {"value": r["value"], "fields": r["fields"]}
                              for r in workbench.read_peripherals(names)["registers"]}
                elif kind == "memory":
                    values = workbench.read_regions(regions)
                else:
                    values = workbench.rtt_read(channel, 65536)
                    payload += values["bytes"]
                stream.write(json.dumps({"seq": count, "t_ns": begin, "end_ns": time.monotonic_ns(), "data": values}, allow_nan=False) + "\n")
                if previous is not None:
                    intervals.append(begin - previous)
                previous = begin
                count += 1
                due += period
                time.sleep(max(0, min(due - time.monotonic(), period)))
            stream.flush()
        meta["complete"] = not workbench.cancel.is_set()
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        elapsed = (time.monotonic_ns() - start) / 1e9
        ordered = sorted(intervals)
        meta.update({"samples": count, "elapsed_s": elapsed, "poll_hz": count / elapsed if elapsed else 0,
                     "payload_bytes": payload, "cancelled": workbench.cancel.is_set(), "error": error,
                     "p99_poll_interval_ns": ordered[min(len(ordered) - 1, int(len(ordered) * .99))] if ordered else None,
                     "maximum_poll_interval_ns": max(ordered) if ordered else None,
                     "sampling_frequency_note": "RTT poll frequency is not target sample frequency",
                     "recording": file_info(p) if p.is_file() else None})
        write_json(str(p) + ".meta.json", meta)
    return meta


def read_recording(path, maximum_rows=1000000):
    info = file_info(path)
    if info["size"] > 256 * 1024 * 1024:
        raise InputError("Recording exceeds 256 MiB")
    rows, metadata, previous = [], None, None
    with Path(info["path"]).open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if "metadata" in row:
                if metadata is not None or rows:
                    raise InputError("Unexpected metadata/reset in recording")
                metadata = row["metadata"]
                continue
            if len(rows) >= maximum_rows or row.get("seq") != len(rows):
                raise InputError("Recording sequence gap or size limit")
            timestamp = row.get("t_ns")
            if type(timestamp) is not int or previous is not None and timestamp < previous:
                raise InputError("Invalid or reversed timestamp")
            previous = timestamp
            rows.append(row)
    if metadata is None:
        raise InputError("Missing recording metadata")
    return info, metadata, rows

import html
import json
import math
import statistics
from pathlib import Path
from openjlink.capture.recording import read_recording
from openjlink.common import InputError, file_info, number


def summarize_recording(path: str):
    info, metadata, rows = read_recording(path)
    channels = {}
    if metadata["kind"] == "variables":
        for row in rows:
            for name, reading in row["data"].items():
                value = reading["value"]
                if type(value) in (int, float) and math.isfinite(value):
                    channels.setdefault(name, []).append(value)
    values = {name: {"count": len(v), "min": min(v), "max": max(v), "mean": statistics.fmean(v),
                     "first": v[0], "last": v[-1]} for name, v in channels.items()}
    intervals = [b["t_ns"] - a["t_ns"] for a, b in zip(rows, rows[1:])]
    meta_path = Path(str(path) + ".meta.json")
    result = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else None
    if result and result.get("recording", {}).get("sha256") != info["sha256"]:
        raise InputError("Recording does not match completion manifest")
    return {"source": info, "metadata": metadata, "completion": result, "samples": len(rows),
            "duration_s": (rows[-1]["t_ns"] - rows[0]["t_ns"]) / 1e9 if len(rows) > 1 else 0,
            "max_interval_ns": max(intervals) if intervals else None, "channels": values,
            "target_loss": "unknown unless target records provide counters"}


def compare_recordings(before: str, after: str):
    a, b = summarize_recording(before), summarize_recording(after)
    return {"before": a, "after": b, "mean_changes": {n: b["channels"][n]["mean"] - a["channels"][n]["mean"] for n in a["channels"].keys() & b["channels"].keys()},
            "causation_established": False}


def analyze_events(events: list[dict], tick_hz: float | None = None):
    if not isinstance(events, list) or not 1 <= len(events) <= 1000000:
        raise InputError("Supply 1..1000000 events")
    if tick_hz is not None:
        number(tick_hz, 1, 1e12)
    current, stack, previous, first = None, [], None, None
    totals, slices, overflows, unknown = {}, {}, 0, 0.0
    unmatched_exits = 0
    names = {}
    for event in events:
        if type(event.get("t_us")) in (int, float):
            t = number(event["t_us"], 0, 1e18) / 1e6
        elif tick_hz is not None:
            t = number(event.get("t_ticks"), 0, 1e24) / tick_hz
        else:
            raise InputError("Every event needs t_us or an explicit tick_hz for t_ticks")
        if previous is not None:
            if t < previous:
                raise InputError("Reversed/reset event time; split captures")
            elapsed = t - previous
            if current is None:
                unknown += elapsed
            else:
                totals[current] = totals.get(current, 0) + elapsed
                slices.setdefault(current, []).append(elapsed)
        if first is None:
            first = t
        kind = event.get("kind")
        if kind == "task_start_exec":
            current = "task:" + str(event["task_id"])
            stack.clear()
        elif kind in ("task_stop_exec", "scheduler", "isr_to_scheduler", "idle"):
            current = "idle" if kind == "idle" else None
            stack.clear()
        elif kind == "isr_enter":
            stack.append(current)
            current = "isr:" + str(event.get("isr_id", event.get("id", "unknown")))
        elif kind == "isr_exit":
            unmatched_exits += int(not stack)
            current = stack.pop() if stack else None
        elif kind == "overflow":
            overflows += 1
            current, stack = None, []
        if "task_id" in event and event.get("task_name"):
            names["task:" + str(event["task_id"])] = event["task_name"]
        previous = t
    duration = previous - first
    return {"duration_s": duration, "actors": {k: {"name": names.get(k, k), "seconds": v,
            "percent": 100 * v / duration if duration else None, "max_observed_interval_s": max(slices[k])} for k, v in totals.items()},
            "unknown_seconds": unknown, "overflow_events": overflows, "open_isr_depth": len(stack),
            "unmatched_isr_exits": unmatched_exits, "complete": overflows == 0 and not stack and not unmatched_exits,
            "deadlock_or_priority_inversion": "not_inferred",
            "window": "first through last event; no extrapolation; ISR time excluded from task time"}


def decode_systemview(path: str, tick_hz: float | None = None):
    from openjlink.analysis.systemview import SystemViewParser
    info = file_info(path)
    if info["size"] > 64 * 1024 * 1024:
        raise InputError("Trace exceeds 64 MiB")
    parser = SystemViewParser()
    events = []
    with Path(info["path"]).open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            events.extend(parser.feed(block))
            if len(events) > 1000000:
                raise InputError("Decoded event limit exceeded")
    summary = analyze_events(events, tick_hz) if events else None
    return {"source": info, "events": events, "synced": parser.synced,
            "dropped_bytes": parser.dropped_bytes, "dropped_packets": parser.dropped_packets,
            "pending_bytes": parser.pending_bytes,
            "decoder_complete": bool(summary and summary["complete"] and parser.synced and not (parser.pending_bytes or parser.dropped_bytes or parser.dropped_packets)),
            "target_loss": "unknown beyond observed decoder/overflow indicators",
            "summary": summary,
            "decoder_scope": "MKLink public SystemView decoder adaptation; validate against target SystemView version"}


def export_rtt(recording: str, output: str):
    info, metadata, rows = read_recording(recording)
    if metadata["kind"] not in ("rtt", "systemview"):
        raise InputError("Expected RTT/SystemView recording")
    with Path(output).open("xb") as stream:
        for row in rows:
            stream.write(bytes.fromhex(row["data"]["hex"]))
    return {"source": info, "output": file_info(output), "target_loss": "unknown"}


def render_recording(path: str, output: str):
    info, metadata, rows = read_recording(path)
    if metadata["kind"] != "variables":
        raise InputError("Plotting requires variable recording")
    if len(rows) > 100000:
        raise InputError("Select at most 100000 samples for this lightweight viewer")
    data = [{"t": (r["t_ns"] - rows[0]["t_ns"]) / 1e9,
             "v": {n: v["value"] for n, v in r["data"].items() if type(v["value"]) in (int, float)}} for r in rows]
    encoded = json.dumps(data, allow_nan=False).replace("<", "\\u003c")
    title = html.escape(Path(path).name)
    template = Path(__file__).with_name("viewer.html").read_text(encoding="utf-8")
    page = template.replace("__TITLE__", title).replace("__DATA__", encoded)
    with Path(output).open("x", encoding="utf-8") as stream:
        stream.write(page)
    return {"source": info, "output": file_info(output), "hardware_accessed": False}

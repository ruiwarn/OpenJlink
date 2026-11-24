_DROP_KEYS = {
    "application_health",
    "safety_basis",
    "frame_assumption",
    "engineering_policy",
    "sampling_frequency_note",
    "hardware_validation",
    "target_drop_count_known",
}


def _op_schema(info):
    if "job_operations" not in info:
        return info["signature"]
    return {
        "signature": info["signature"],
        "job_operations": {k: v["signature"] for k, v in info["job_operations"].items()},
        "terminal_states": info["terminal_states"],
    }


def compact_schema(data, operation=None):
    if operation is not None:
        item = _op_schema(data)
        return {"signature": item} if isinstance(item, str) else item
    return {name: _op_schema(info) for name, info in data.items()}


def _strip_boilerplate(value):
    if not isinstance(value, dict):
        return value
    cleaned = {k: v for k, v in value.items() if k not in _DROP_KEYS}
    if cleaned.get("runtime_health") == "not_checked":
        cleaned.pop("runtime_health", None)
    return cleaned


def compact_result(operation, result):
    if not isinstance(result, dict):
        return result
    if operation == "ping":
        return {"version": result["version"], "state_dir": result["state_dir"],
                "operation_count": len(result.get("operations", []))}
    if operation == "probe_info":
        return {k: result[k] for k in ("serial", "device", "interface", "speed_khz", "core", "voltage_mv", "halted", "devices_xml_path") if k in result}
    if operation == "read_variable":
        return {"name": result["name"], "value": result["value"], "firmware_verified": result["firmware_verified"]}
    if operation == "read_variables":
        return {"values": result["values"], "firmware_verified": result["firmware_verified"],
                "generation": result["generation"][:12], "atomic": result["atomic"]}
    if operation == "check_heartbeat":
        readings = result.get("readings", [])
        elapsed_ms = round((readings[-1]["end_ns"] - readings[0]["start_ns"]) / 1e6, 2) if readings else 0.0
        return {"value_changed": result["value_changed"], "values": [r["hex"] for r in readings], "elapsed_ms": elapsed_ms}
    if operation == "read_memory":
        return {"address": result["address"], "size": result["size"], "hex": result["hex"],
                "elapsed_ms": round((result["end_ns"] - result["start_ns"]) / 1e6, 2)}
    if operation == "read_regions":
        return {"regions": [{"address": r["address"], "size": r["size"], "hex": r["hex"]} for r in result["regions"]],
                "transactions": result["transactions"], "atomic": result["atomic"]}
    if operation == "type_info":
        return {k: result[k] for k in ("name", "address", "size", "encoding", "tag", "fields", "fields_truncated") if k in result}
    if operation == "search_symbols":
        return {"names": result["names"], "total": result["total"], "truncated": result["truncated"]}
    if operation == "load_symbols":
        return {"generation": result["generation"][:12], "sha256": result["generation"],
                "variables": result["variables"], "firmware_match": result["firmware_match"]}
    if operation == "read_peripherals":
        return {"device": result["device"],
                "registers": [{"name": r["name"], "value": r["value"], "fields": r["fields"]} for r in result["registers"]]}
    if operation == "list_peripherals":
        regs = [{"name": r["name"], "address": r["address"], "bits": r["bits"], "safe": r["safe_read_declared"]} for r in result["registers"]]
        return {"device": result["device"], "registers": regs, "total": result["total"],
                "truncated": result.get("truncated", result["total"] > len(regs))}
    if operation in ("job_status", "wait_job"):
        out = {k: v for k, v in result.items() if not (k == "retry_safe" and v is False)}
        if isinstance(out.get("result"), dict):
            out["result"] = _strip_boilerplate(out["result"])
        return out
    return _strip_boilerplate(result)

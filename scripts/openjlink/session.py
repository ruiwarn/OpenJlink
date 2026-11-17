import hashlib
import inspect
import json
import os
import shutil
import sqlite3
import struct
import threading
import time
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from openjlink import __version__
from openjlink.common import InputError, FileLock, approval, file_info, hex_bytes, integer, memory_range, number, timed_read, write_json
from openjlink.hardware.probe import identity, inventory, new_probe
from openjlink.symbols.elf import Symbols, images


class Workbench:
    def __init__(self, state_dir, factory=new_probe):
        self.directory = Path(state_dir).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.owner = FileLock(self.directory / "owner.lock").acquire()
        self.gate = threading.RLock()
        self.db_lock = threading.Lock()
        self.db = sqlite3.connect(self.directory / "jobs.sqlite3", check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, digest TEXT, state TEXT, result TEXT)")
        self.db.execute("UPDATE jobs SET state='unknown' WHERE state IN ('accepted','running')")
        self.db.commit()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.factory = factory
        self.probe = None
        self.selection = None
        self.probe_lock = None
        self.symbols = None
        self.peripherals = None
        self.verified = None
        self.rtt = False
        self.quarantine = False
        self.breakpoints = set()
        self.job_active = None
        self.cancel = threading.Event()

    def close(self):
        self.executor.shutdown(wait=True)
        try:
            self.disconnect()
        finally:
            self.db.close()
            self.owner.close()

    def ping(self):
        return {"version": __version__, "state_dir": str(self.directory), "operations": sorted(OPERATIONS),
                "limits": {"direct_read_bytes": 4096, "regions": 16, "rtt_write_bytes": 256},
                "hardware_validation": "not_run", "engineering_policy": "explicit inputs; no project configuration discovery"}

    def inspect_environment(self):
        import importlib.metadata
        names = ("pylink-square", "pyelftools", "pyserial", "cmsis-svd", "pymodbus")
        versions = {}
        for name in names:
            try:
                versions[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                versions[name] = None
        return {"python": os.sys.executable, "packages": versions,
                "tools": {n: shutil.which(n) for n in ("JLink.exe", "JLinkGDBServerCL.exe", "JLinkExe", "JLinkGDBServer", "arm-none-eabi-gdb", "arm-none-eabi-gdb.exe")},
                "hardware_accessed": False}

    def discover_probes(self, dll_path: str | None = None):
        return inventory(dll_path)

    def connect(self, serial: int, device: str, interface: str = "SWD", speed_khz: int = 1000,
                dll_path: str | None = None):
        integer(serial, 1)
        integer(speed_khz, 5, 50000)
        if not isinstance(device, str) or not device.strip() or any(c in device for c in "\r\n\0"):
            raise InputError("Explicit target device name required")
        if interface not in ("SWD", "JTAG"):
            raise InputError("interface must be SWD or JTAG")
        requested = {"serial": serial, "device": device, "interface": interface, "speed_khz": speed_khz}
        if self.probe:
            if requested != self.selection or self.quarantine:
                raise InputError("Disconnect the current/uncertain session explicitly first")
            return self.device_status()
        import pylink
        self.probe_lock = FileLock(Path(tempfile.gettempdir()) / "openjlink-locks" / f"{serial}.lock").acquire()
        probe = None
        try:
            probe = self.factory(dll_path)
            probe.open(serial_no=serial)
            probe.set_tif(getattr(pylink.enums.JLinkInterfaces, interface))
            probe.connect(device, speed=speed_khz)
            self.probe = probe
            self.selection = requested
            self.verified = None
            self.quarantine = False
            return self.device_status()
        except BaseException:
            if probe:
                probe.close()
            self.probe = None
            self.probe_lock.close()
            self.probe_lock = None
            raise

    def device_status(self):
        return {"connected": self.probe is not None, "selection": self.selection,
                "rtt": self.rtt, "quarantined": self.quarantine, "job": self.job_active,
                "symbols": self.symbols.info if self.symbols else None,
                "symbols_verified": bool(self.symbols and self.verified == self.symbols.info["sha256"])}

    def probe_info(self):
        return {**self.selection, **identity(self.require_probe())}

    def require_probe(self):
        if not self.probe or self.quarantine:
            raise InputError("Connect first, or explicitly disconnect an uncertain session before reconnecting")
        return self.probe

    def disconnect(self):
        try:
            if self.probe:
                if self.rtt:
                    self.probe.rtt_stop()
                for handle in self.breakpoints:
                    self.probe.breakpoint_clear(handle)
        finally:
            try:
                if self.probe:
                    self.probe.close()
            finally:
                self.probe = None
                self.selection = None
                self.rtt = False
                self.verified = None
                self.breakpoints.clear()
                if self.probe_lock:
                    self.probe_lock.close()
                    self.probe_lock = None
        return {"disconnected": True, "reset_requested": False, "resume_requested": False}

    def load_symbols(self, path: str):
        self.symbols = Symbols(path)
        self.verified = None
        return {"source": self.symbols.info, "generation": self.symbols.info["sha256"],
                "variables": len(self.symbols.variables), "firmware_match": "unverified"}

    def search_symbols(self, query: str = "", limit: int = 100):
        integer(limit, 1, 1000)
        return self.require_symbols().search(query, limit)

    def require_symbols(self):
        if not self.symbols:
            raise InputError("Load an explicit ELF/AXF/OUT first")
        self.symbols.current()
        return self.symbols

    def memory_map(self):
        return self.require_symbols().memory_map()

    def type_info(self, name: str):
        address, size, encoding, typ = self.require_symbols().resolve(name)
        return {"name": name, "address": address, "size": size, "encoding": encoding,
                "tag": typ.tag, "generation": self.symbols.info["sha256"]}

    def symbolize(self, addresses: list[int]):
        if not isinstance(addresses, list) or not 1 <= len(addresses) <= 128:
            raise InputError("Supply 1..128 addresses")
        return [self.require_symbols().location(integer(a) & ~1) for a in addresses]

    def read_memory(self, address: int, size: int):
        memory_range(address, size)
        return timed_read(self.require_probe(), address, size)

    def load_peripherals(self, path: str, byte_order: str):
        from openjlink.peripherals.svd import Peripherals
        self.peripherals = Peripherals(path, byte_order)
        return self.peripherals.catalog("", 100)

    def list_peripherals(self, query: str = "", limit: int = 100):
        if self.peripherals is None:
            raise InputError("Load an explicit SVD first")
        return self.peripherals.catalog(query, limit)

    def read_peripherals(self, names: list[str]):
        if self.peripherals is None:
            raise InputError("Load an explicit SVD first")
        registers = self.peripherals.select(names)
        snapshot = self.read_regions([{"address": r["address"], "size": r["bits"] // 8} for r in registers])
        return {"source": self.peripherals.source, "device": self.peripherals.device,
                "registers": [{**self.peripherals.decode(r, v["hex"]), **v} for r, v in zip(registers, snapshot["regions"])],
                "atomic": False, "safety_basis": "SVD declarations only; caller must verify vendor manual and revision"}

    def read_regions(self, regions: list[dict]):
        if not isinstance(regions, list) or not 1 <= len(regions) <= 16:
            raise InputError("Supply 1..16 regions")
        for r in regions:
            if set(r) != {"address", "size"}:
                raise InputError("Each region requires exactly address and size")
            memory_range(r["address"], r["size"])
        if sum(r["size"] for r in regions) > 4096:
            raise InputError("Snapshot total exceeds 4096 bytes")
        spans = []
        for r in sorted(regions, key=lambda x: x["address"]):
            a, end = r["address"], r["address"] + r["size"]
            if spans and a <= spans[-1][1]:
                spans[-1][1] = max(spans[-1][1], end)
            else:
                spans.append([a, end])
        reads = [self.read_memory(a, b - a) for a, b in spans]
        result = []
        for r in regions:
            read = next(x for x in reads if x["address"] <= r["address"] and r["address"] + r["size"] <= x["address"] + x["size"])
            start = r["address"] - read["address"]
            result.append({**r, "hex": bytes.fromhex(read["hex"])[start:start + r["size"]].hex(),
                           "start_ns": read["start_ns"], "end_ns": read["end_ns"]})
        return {"regions": result, "transactions": len(reads), "atomic": False, "clock": "host_monotonic"}

    def dump_memory(self, address: int, size: int, path: str):
        memory_range(address, size, 16 * 1024 * 1024)
        p = Path(path).expanduser().resolve()
        if p.exists() or Path(str(p) + ".meta.json").exists() or not p.parent.is_dir():
            raise InputError("Use a new file in an existing output directory")
        result = {"address": address, "size": size, "bytes_read": 0, "complete": False,
                  "clock": "host_monotonic_ns", "start_ns": time.monotonic_ns()}
        try:
            with p.open("xb") as stream:
                for offset in range(0, size, 4096):
                    raw = bytes.fromhex(self.read_memory(address + offset, min(4096, size - offset))["hex"])
                    stream.write(raw)
                    result["bytes_read"] += len(raw)
            result["complete"] = True
        finally:
            result.update(end_ns=time.monotonic_ns(), output=file_info(p) if p.is_file() else None)
            write_json(str(p) + ".meta.json", result)
        return result

    def write_regions(self, writes: list[dict], confirm: bool = False):
        approval(confirm)
        if not isinstance(writes, list) or not 1 <= len(writes) <= 8:
            raise InputError("Supply 1..8 write regions")
        total = 0
        for item in writes:
            if set(item) != {"address", "data_hex"}:
                raise InputError("Write regions require exactly address and data_hex")
            data = hex_bytes(item["data_hex"])
            memory_range(item["address"], len(data))
            total += len(data)
        if total > 12 * 1024:
            raise InputError("Total writes exceed 12 KiB")
        result = [self.write_memory(item["address"], item["data_hex"], True) for item in writes]
        return {"results": result, "verified": True, "atomic": False}

    def set_speed(self, speed_khz: int, confirm: bool = False):
        approval(confirm)
        integer(speed_khz, 5, 50000)
        if self.rtt:
            raise InputError("Stop RTT explicitly before changing speed")
        self.require_probe().set_speed(speed_khz)
        self.selection["speed_khz"] = speed_khz
        return {"speed_khz_requested": speed_khz, "target_stability_verified": False}

    def write_memory(self, address: int, data_hex: str, confirm: bool = False, expected_hex: str | None = None):
        approval(confirm)
        data = hex_bytes(data_hex)
        memory_range(address, len(data))
        if expected_hex is not None and self.read_memory(address, len(data))["hex"] != hex_bytes(expected_hex).hex():
            raise InputError("Expected old value mismatch; no write performed")
        probe = self.require_probe()
        try:
            written = probe.memory_write8(address, list(data))
            if written != len(data):
                raise RuntimeError("Partial memory write")
            actual = self.read_memory(address, len(data))["hex"]
            if actual != data.hex():
                raise RuntimeError("Write readback mismatch")
        except Exception:
            self.quarantine = True
            raise
        return {"address": address, "bytes_written": written, "verified": True}

    def read_variable(self, name: str):
        symbols = self.require_symbols()
        address, size, encoding, typ = symbols.resolve(name)
        result = self.read_memory(address, size)
        value = symbols.decode(name, bytes.fromhex(result["hex"]))
        if isinstance(value, float) and not __import__("math").isfinite(value):
            value = str(value)
        return {**result, "name": name, "value": value, "generation": symbols.info["sha256"],
                "firmware_verified": self.verified == symbols.info["sha256"]}

    def write_variable(self, name: str, value: int | float, generation: str,
                       confirm: bool = False, expected_hex: str | None = None):
        symbols = self.require_symbols()
        if generation != symbols.info["sha256"] or self.verified != generation:
            raise InputError("Verify the current ELF image against target Flash before symbolic writes")
        data = symbols.encode(name, value)
        address, size, encoding, typ = symbols.resolve(name)
        return self.write_memory(address, data.hex(), confirm, expected_hex)

    def verify_image(self, path: str, base_address: int | None = None):
        info, segments = images(path, base_address)
        self.require_probe()
        for address, data in segments:
            for offset in range(0, len(data), 4096):
                expected = data[offset:offset + 4096]
                if self.read_memory(address + offset, len(expected))["hex"] != expected.hex():
                    self.verified = None
                    raise InputError(f"Image verification mismatch at 0x{address + offset:08X}")
        if self.symbols and info["sha256"] == self.symbols.info["sha256"]:
            self.verified = info["sha256"]
        return {"verified": True, "source": info, "ranges": [{"address": a, "size": len(d)} for a, d in segments]}

    def check_heartbeat(self, address: int, size: int = 4, interval: float = .1, samples: int = 3):
        integer(size, 1, 8)
        integer(samples, 2, 32)
        number(interval, .01, 10)
        readings = []
        for index in range(samples):
            if index:
                time.sleep(interval)
            readings.append(self.read_memory(address, size))
        return {"readings": readings, "value_changed": len({r["hex"] for r in readings}) > 1,
                "application_health": "caller must identify a meaningful counter; value changes alone do not prove full health"}

    def core_registers(self):
        probe = self.require_probe()
        if not probe.halted():
            raise InputError("Halt explicitly before a core-register snapshot")
        return {probe.register_name(i).lower(): int(probe.register_read(i)) for i in probe.register_list()}

    def debug_control(self, action: str, confirm: bool = False):
        approval(confirm)
        probe = self.require_probe()
        if self.rtt:
            raise InputError("Stop RTT explicitly before changing CPU execution")
        if action not in ("halt", "resume", "step"):
            raise InputError("Use halt, resume or step")
        if action == "step" and not probe.halted():
            raise InputError("Halt before stepping")
        getattr(probe, {"halt": "halt", "resume": "restart", "step": "step"}[action])()
        return {"action": action, "halted": bool(probe.halted())}

    def breakpoint(self, action: str, address: int | None = None, handle: int | None = None, confirm: bool = False):
        if action == "list":
            return {"owned_handles": sorted(self.breakpoints)}
        approval(confirm)
        probe = self.require_probe()
        if not probe.halted():
            raise InputError("Halt explicitly before changing breakpoints")
        if action == "set":
            integer(address)
            if address % 2:
                raise InputError("Use an even instruction address")
            used = int(probe.breakpoint_set(address, thumb=True))
            self.breakpoints.add(used)
            return {"handle": used, "address": address}
        if action not in ("clear", "clear_owned"):
            raise InputError("Use list/set/clear/clear_owned")
        handles = list(self.breakpoints) if action == "clear_owned" else [handle]
        for item in handles:
            if item not in self.breakpoints:
                raise InputError("Only breakpoints created by this session may be cleared")
            probe.breakpoint_clear(item)
            self.breakpoints.remove(item)
        return {"cleared": handles}

    def rtt_start(self, address: int | None = None):
        probe = self.require_probe()
        if address is not None:
            integer(address)
            if address % 4:
                raise InputError("RTT control block must be four-byte aligned")
        if not self.rtt:
            probe.rtt_start(address)
            self.rtt = True
        return {"started": True, "target_drop_count": None, "target_drop_count_known": False}

    def rtt_channels(self):
        probe = self.require_probe()
        if not self.rtt:
            raise InputError("Start RTT first; control-block discovery may still be pending")
        result = {}
        for up, key, count in ((True, "up", probe.rtt_get_num_up_buffers()), (False, "down", probe.rtt_get_num_down_buffers())):
            result[key] = []
            for index in range(count):
                descriptor = probe.rtt_get_buf_descriptor(index, up)
                result[key].append({"index": index, "size": int(descriptor.SizeOfBuffer), "flags": int(descriptor.Flags)})
        return result

    def rtt_read(self, channel: int = 0, maximum: int = 4096):
        integer(channel, 0, 255)
        integer(maximum, 1, 65536)
        if not self.rtt:
            raise InputError("Start RTT first")
        data = bytes(self.require_probe().rtt_read(channel, maximum))
        return {"channel": channel, "hex": data.hex(), "bytes": len(data), "host_ns": time.monotonic_ns(),
                "target_loss": "unknown", "destructive_read": True}

    def rtt_write(self, data_hex: str, channel: int = 0, confirm: bool = False):
        approval(confirm)
        integer(channel, 0, 255)
        data = hex_bytes(data_hex, 256)
        if not self.rtt:
            raise InputError("Start RTT first")
        try:
            sent = self.require_probe().rtt_write(channel, list(data))
        except Exception:
            self.quarantine = True
            raise
        return {"submitted": sent, "requested": len(data), "complete": sent == len(data),
                "application_acknowledged": False, "retry_safe": False}

    def rtt_stop(self):
        if self.rtt:
            self.require_probe().rtt_stop()
            self.rtt = False
        return {"stopped": True}

    def fault_snapshot(self, architecture: str, stack_address: int | None = None):
        if architecture not in ("cortex-m0", "cortex-m0+", "cortex-m3", "cortex-m4", "cortex-m7", "cortex-m23", "cortex-m33"):
            raise InputError("Explicit supported Cortex-M architecture required")
        regs = self.core_registers()
        result = {"architecture": architecture, "core_registers": regs, "halt_requested": False,
                  "stack_frame": None, "fault_status": {}, "full_backtrace": "not_inferred"}
        if architecture in ("cortex-m3", "cortex-m4", "cortex-m7", "cortex-m33"):
            result["fault_status"] = {name: int.from_bytes(bytes.fromhex(self.read_memory(address, 4)["hex"]), "little") for name, address in (("cfsr", 0xE000ED28), ("hfsr", 0xE000ED2C), ("mmfar", 0xE000ED34), ("bfar", 0xE000ED38))}
        if stack_address is not None:
            memory_range(stack_address, 32)
            if stack_address % 4:
                raise InputError("Stack frame must be aligned")
            frame = struct.unpack("<8I", bytes.fromhex(self.read_memory(stack_address, 32)["hex"]))
            result["stack_frame"] = dict(zip(("r0", "r1", "r2", "r3", "r12", "lr", "pc", "xpsr"), frame))
            result["frame_assumption"] = "caller supplied address of basic exception frame; extended/security frames must be adjusted by caller"
            if self.symbols:
                result["locations"] = self.symbolize([frame[5], frame[6]])
        return result

    def start_job(self, operation: str, arguments: dict, request_id: str, confirm: bool = False):
        approval(confirm)
        if operation not in ("program", "erase", "reset", "capture"):
            raise InputError("Job operation must be program/erase/reset/capture")
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128:
            raise InputError("request_id must contain 1..128 characters")
        if not isinstance(arguments, dict):
            raise InputError("arguments must be an object")
        if not self.selection:
            raise InputError("Connect to an explicit probe and device first")
        arguments = json.loads(json.dumps(arguments, allow_nan=False))
        if operation == "program":
            actual = file_info(arguments["path"])["sha256"]
            if arguments.get("expected_sha256", actual) != actual:
                raise InputError("Requested image hash does not match the file")
            arguments["expected_sha256"] = actual
        payload = {"operation": operation, "arguments": arguments, "target": self.selection}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
        with self.db_lock:
            existing = self.db.execute("SELECT digest,state,result FROM jobs WHERE id=?", (request_id,)).fetchone()
            if existing:
                if existing[0] != digest:
                    raise InputError("request_id already used for different arguments/target")
                return {"job_id": request_id, "state": existing[1], "reused": True}
            if self.job_active:
                raise InputError("A job is already active")
            self.db.execute("INSERT INTO jobs VALUES (?,?,'accepted',NULL)", (request_id, digest))
            self.db.commit()
            self.job_active = request_id
            self.cancel.clear()
        self.executor.submit(self._run_job, request_id, operation, arguments)
        return {"job_id": request_id, "state": "accepted", "retry_safe": False}

    def _run_job(self, job_id, operation, arguments):
        with self.gate:
            self._save_job(job_id, "running", None)
            try:
                result = getattr(self, "_" + operation)(**arguments)
                state = "completed"
            except (InputError, TypeError) as exc:
                result, state = {"error": str(exc)}, "failed"
            except Exception as exc:
                self.quarantine = operation != "capture"
                result, state = {"error": str(exc), "retry_safe": False}, "unknown"
            self._save_job(job_id, state, result)
            self.job_active = None

    def _save_job(self, job_id, state, result):
        with self.db_lock:
            self.db.execute("UPDATE jobs SET state=?, result=? WHERE id=?", (state, json.dumps(result, allow_nan=False), job_id))
            self.db.commit()

    def job_status(self, job_id: str):
        with self.db_lock:
            row = self.db.execute("SELECT state,result FROM jobs WHERE id=?", (job_id,)).fetchone()
        return {"job_id": job_id, "state": row[0] if row else "unknown", "result": json.loads(row[1]) if row and row[1] else None, "retry_safe": False}

    def cancel_capture(self):
        self.cancel.set()
        return {"stop_requested": True, "hardware_writes_cancelled": False}

    def _program(self, path: str, base_address: int | None = None, allowed_ranges: list[dict] | None = None,
                 reset_after: bool = False, expected_sha256: str | None = None,
                 preserve_ranges: list[dict] | None = None):
        probe = self.require_probe()
        if self.rtt:
            raise InputError("Stop RTT explicitly before programming")
        if type(reset_after) is not bool:
            raise InputError("reset_after must be boolean")
        snapshot = self.directory / (uuid.uuid4().hex + Path(path).suffix)
        raw = Path(path).read_bytes()
        if len(raw) > 64 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise InputError("Image changed since job submission or exceeds size limit")
        with snapshot.open("xb") as stream:
            stream.write(raw)
        info, segments = images(snapshot, base_address)
        if not isinstance(allowed_ranges, list) or not allowed_ranges:
            raise InputError("Explicit allowed_ranges required for programming")
        for r in allowed_ranges:
            memory_range(r["address"], r["size"], 64 * 1024 * 1024)
        for address, data in segments:
            if not any(r["address"] <= address and address + len(data) <= r["address"] + r["size"] for r in allowed_ranges):
                raise InputError("Image exceeds authorized ranges")
        if preserve_ranges:
            for region in preserve_ranges:
                if any(region["address"] < a + len(d) and a < region["address"] + region["size"] for a, d in segments):
                    raise InputError("Program bytes overlap a preserved range")
        preserved = self.read_regions(preserve_ranges)["regions"] if preserve_ranges else []
        self.verified = None
        try:
            probe.flash_file(info["path"], base_address or 0)
            result = self.verify_image(info["path"], base_address)
            for region in preserved:
                if self.read_memory(region["address"], region["size"])["hex"] != region["hex"]:
                    raise RuntimeError("Preserved range changed; inspect the Flash loader/erase geometry")
            if reset_after:
                probe.reset(halt=False)
        except Exception as exc:
            raise RuntimeError(f"Programming effect may be partial: {exc}") from exc
        return {**result, "preserved_ranges_verified": len(preserved), "reset_requested": bool(reset_after), "runtime_health": "not_checked", "target": self.selection}

    def _erase(self, device: str):
        if device != self.selection["device"] or self.rtt:
            raise InputError("Exact connected device required; stop RTT first")
        self.verified = None
        self.require_probe().erase()
        return {"erase_command_completed": True, "blank_check": "not_performed", "device": device}

    def _reset(self, halt: bool = True):
        if type(halt) is not bool or self.rtt:
            raise InputError("halt must be boolean; stop RTT first")
        self.require_probe().reset(halt=halt)
        return {"reset": True, "halted": bool(self.probe.halted()), "runtime_health": "not_checked"}

    def _capture(self, kind: str, duration: float, path: str, period: float = 0.01,
                 names: list[str] | None = None, regions: list[dict] | None = None, channel: int = 0):
        from openjlink.capture.recording import capture
        return capture(self, kind, duration, path, period, names, regions, channel)


OPERATIONS = {
    "ping": "Health and available operation names; no target I/O",
    "inspect_environment": "Find host tools and dependencies without connecting",
    "discover_probes": "Enumerate USB probes without target connection",
    "connect": "Connect an explicit serial/device; connection behavior depends on target scripts",
    "device_status": "Cached ownership, job and symbol status",
    "probe_info": "Read connected probe/target identity and VREF",
    "disconnect": "Stop this session RTT, clear only owned breakpoints, close probe",
    "load_symbols": "Load explicit ELF/AXF/OUT; does not assert firmware match",
    "search_symbols": "Find fixed-address globals in DWARF",
    "memory_map": "Allocated ELF sections",
    "type_info": "Resolve a global/member/array element",
    "symbolize": "Resolve instruction addresses to source lines",
    "read_memory": "Read up to 4096 bytes without claiming atomicity",
    "load_peripherals": "Load an explicit SVD and byte order without target I/O",
    "list_peripherals": "List named registers, bit fields and declared read safety",
    "read_peripherals": "Read named SVD registers after rejecting declared side effects; all selections validated before I/O",
    "read_regions": "Read up to 16 regions, 4096 bytes total, merging only overlapping/adjacent ranges",
    "dump_memory": "Save a bounded large RAM/Flash range to a new file with a completion manifest",
    "write_regions": "Authorized ordered non-atomic batch writes with mandatory readback",
    "set_speed": "Set an explicit SDK debug clock after stopping RTT; no performance guarantee",
    "write_memory": "Authorized RAM/MMIO write with old-value guard and mandatory readback; side effects remain caller responsibility",
    "read_variable": "Typed symbol read, reporting image verification status",
    "write_variable": "Authorized scalar write requiring current verified symbol generation",
    "verify_image": "Compare programmed ELF/HEX/BIN bytes to target without programming",
    "check_heartbeat": "Compare a caller-identified counter over time without resetting the target",
    "core_registers": "Read registers of explicitly halted core",
    "debug_control": "Authorized halt/resume/step; affects target timing",
    "breakpoint": "List/create/clear only session-owned instruction breakpoints",
    "rtt_start": "Start RTT using explicit CB address or SDK discovery",
    "rtt_channels": "Discover RTT buffer descriptors; may report not-yet-found",
    "rtt_read": "Destructive bounded channel read; target drops unknown",
    "rtt_write": "Authorized bounded binary RTT input; partial writes are not retried",
    "rtt_stop": "Stop this session RTT",
    "fault_snapshot": "Architecture-aware halted Cortex-M snapshot; basic frame address must be supplied",
    "start_job": "Journaled program/erase/reset/capture; acceptance is not completion",
    "job_status": "Read persisted task result; unknown never permits replay",
    "cancel_capture": "Request cooperative capture stop; does not cancel programming"
}


def dispatch(workbench, operation, arguments=None):
    if operation not in OPERATIONS:
        raise InputError("Unknown operation")
    method = getattr(workbench, operation)
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise InputError("arguments must be an object")
    inspect.signature(method).bind(**arguments)
    if operation in ("job_status", "device_status", "cancel_capture", "ping"):
        return method(**arguments)
    if workbench.job_active and operation != "start_job":
        raise InputError("Hardware job active; query job_status or cancel_capture")
    if not workbench.gate.acquire(blocking=False):
        raise InputError("Another operation is active")
    try:
        return method(**arguments)
    finally:
        workbench.gate.release()

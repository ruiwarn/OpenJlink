import ast
import io
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
import tokenize
import pytest
from openjlink.common import FileLock, InputError, memory_range
from openjlink.session import Workbench
from openjlink.symbols.elf import images
from openjlink.analysis.report import analyze_events, summarize_recording
from openjlink.analysis.systemview import SystemViewParser
from openjlink.host.process import run_build


class Probe:
    def __init__(self):
        self.mem = {}
        self.reads = []
        self.writes = []
        self.running = True
        self.flashes = 0
        self.partial = False
        self.serial = None
        self.rx = b"abc"

    def open(self, serial_no):
        self.serial = serial_no

    def set_tif(self, value):
        self.interface = value

    def connect(self, device, speed):
        self.device = device

    def close(self):
        pass

    def memory_read8(self, address, size):
        self.reads.append((address, size))
        return [self.mem.get(address + i, 0) for i in range(size)]

    def memory_read32(self, address, count):
        self.reads.append((address, count * 4))
        return [int.from_bytes(bytes(self.mem.get(address + i * 4 + j, 0) for j in range(4)), "little") for i in range(count)]

    def memory_write8(self, address, data):
        self.writes.append((address, data))
        self.mem.update({address + i: value for i, value in enumerate(data)})
        return len(data) - 1 if self.partial else len(data)

    def halted(self):
        return not self.running

    def halt(self):
        self.running = False

    def restart(self):
        self.running = True

    def step(self):
        pass

    def breakpoint_set(self, address, thumb):
        return 7

    def breakpoint_clear(self, handle):
        pass

    def register_list(self):
        return [0]

    def register_name(self, index):
        return "PC"

    def register_read(self, index):
        return 0x100

    def rtt_start(self, address):
        pass

    def rtt_stop(self):
        pass

    def rtt_read(self, channel, maximum):
        data, self.rx = self.rx[:maximum], self.rx[maximum:]
        return list(data)

    def rtt_write(self, channel, data):
        return min(2, len(data))

    def flash_file(self, path, address):
        self.flashes += 1
        info, segments = images(path, address)
        for a, data in segments:
            self.memory_write8(a, data)

    def reset(self, halt=True):
        self.running = not halt


@pytest.fixture
def bench(tmp_path):
    probe = Probe()
    w = Workbench(tmp_path / "state", factory=lambda dll: probe)
    w.connect(123456, "TestDevice")
    try:
        yield w, probe
    finally:
        w.close()


def wait_job(w, job_id):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        job = w.job_status(job_id)
        if job["state"] not in ("accepted", "running"):
            return job
        time.sleep(.005)
    raise AssertionError("Job did not finish")


@pytest.mark.parametrize("address,size", [(True, 4), (-1, 1), (0xFFFFFFFF, 2), (0, 0), (0, 4097)])
def test_memory_boundaries(address, size):
    with pytest.raises(InputError):
        memory_range(address, size)


def test_merge_only_adjacent_and_preserve_order(bench):
    w, p = bench
    p.mem = {100 + i: i for i in range(8)}
    result = w.read_regions([{"address": 104, "size": 4}, {"address": 100, "size": 4}, {"address": 200, "size": 1}])
    assert p.reads == [(100, 8), (200, 1)]
    assert [r["address"] for r in result["regions"]] == [104, 100, 200]
    assert result["regions"][0]["hex"] == "04050607"
    assert result["atomic"] is False


def test_write_authorization_old_value_and_partial_quarantine(bench):
    w, p = bench
    with pytest.raises(InputError):
        w.write_memory(100, "abcd")
    with pytest.raises(InputError):
        w.write_memory(100, "abcd", True, "ff00")
    assert not p.writes
    assert w.write_memory(100, "abcd", True, "0000")["verified"]
    p.partial = True
    with pytest.raises(RuntimeError):
        w.write_memory(100, "1234", True)
    assert w.quarantine
    with pytest.raises(InputError):
        w.read_memory(100, 1)


def test_batch_validates_all_items_before_any_write(bench):
    w, p = bench
    with pytest.raises(InputError):
        w.write_regions([{"address": 100, "data_hex": "aa"}, {"address": 101, "data_hex": "zz"}], True)
    assert not p.writes
    result = w.write_regions([{"address": 100, "data_hex": "aabb"}, {"address": 104, "data_hex": "cc"}], True)
    assert result["verified"] and not result["atomic"]


def test_dump_memory_saves_full_range_and_manifest(bench, tmp_path):
    w, p = bench
    path = tmp_path / "memory.bin"
    result = w.dump_memory(0, 5000, str(path))
    assert result["complete"] and result["bytes_read"] == 5000
    assert path.stat().st_size == 5000
    assert p.reads == [(0, 4096), (4096, 904)]
    with pytest.raises(InputError):
        w.dump_memory(0, 1, str(path))


def test_explicit_selection_and_cpu_control(bench):
    w, p = bench
    with pytest.raises(InputError):
        w.connect(999, "Other")
    with pytest.raises(InputError):
        w.core_registers()
    with pytest.raises(InputError):
        w.debug_control("step", True)
    w.debug_control("halt", True)
    assert w.core_registers() == {"pc": 0x100}
    assert w.breakpoint("set", 0x100, confirm=True)["handle"] == 7
    with pytest.raises(InputError):
        w.breakpoint("clear", handle=4, confirm=True)
    w.breakpoint("clear_owned", confirm=True)
    assert not w.breakpoints


def test_rtt_partial_write_not_success(bench):
    w, p = bench
    w.rtt_start()
    assert w.rtt_read()["hex"] == "616263"
    assert w.rtt_read()["hex"] == ""
    result = w.rtt_write("01020304", confirm=True)
    assert result["complete"] is False and result["retry_safe"] is False
    with pytest.raises(InputError):
        w.rtt_write("ff" * 257, confirm=True)


def test_fault_architecture_does_not_read_nonexistent_status(bench):
    w, p = bench
    w.debug_control("halt", True)
    result = w.fault_snapshot("cortex-m0", 0x1000)
    assert not result["fault_status"]
    assert p.reads == [(0x1000, 32)]
    w.fault_snapshot("cortex-m4")
    assert (0xE000ED28, 4) in p.reads


def test_job_idempotency_includes_image_bytes(bench, tmp_path):
    w, p = bench
    image = tmp_path / "app.bin"
    image.write_bytes(b"abcd")
    args = {"path": str(image), "base_address": 0x1000, "allowed_ranges": [{"address": 0x1000, "size": 4}]}
    w.start_job("program", args, "program-1", True)
    assert wait_job(w, "program-1")["state"] == "completed"
    assert p.flashes == 1
    assert w.start_job("program", args, "program-1", True)["reused"]
    assert p.flashes == 1
    image.write_bytes(b"efgh")
    with pytest.raises(InputError):
        w.start_job("program", args, "program-1", True)


def test_invalid_program_range_does_not_flash(bench, tmp_path):
    w, p = bench
    image = tmp_path / "image.bin"
    image.write_bytes(b"abcd")
    w.start_job("program", {"path": str(image), "base_address": 0x1000, "allowed_ranges": [{"address": 0x2000, "size": 4}]}, "range", True)
    assert wait_job(w, "range")["state"] == "failed"
    assert p.flashes == 0


def test_program_retains_requested_preserved_bytes(bench, tmp_path):
    w, p = bench
    image = tmp_path / "image.bin"
    image.write_bytes(b"abcd")
    p.mem[0x2000] = 88
    w.start_job("program", {"path": str(image), "base_address": 0x1000,
                "allowed_ranges": [{"address": 0x1000, "size": 4096}],
                "preserve_ranges": [{"address": 0x2000, "size": 1}]}, "preserved", True)
    result = wait_job(w, "preserved")
    assert result["state"] == "completed" and result["result"]["preserved_ranges_verified"] == 1
    assert p.mem[0x2000] == 88


def test_unknown_job_never_replays_and_survives_restart(tmp_path):
    p = Probe()
    p.erase = lambda: (_ for _ in ()).throw(TimeoutError("lost reply"))
    w = Workbench(tmp_path / "state", factory=lambda dll: p)
    w.connect(456789, "Device")
    w.start_job("erase", {"device": "Device"}, "uncertain", True)
    assert wait_job(w, "uncertain")["state"] == "unknown"
    w.close()
    reopened = Workbench(tmp_path / "state")
    try:
        assert reopened.job_status("uncertain")["state"] == "unknown"
    finally:
        reopened.close()


@pytest.mark.parametrize("failure_state", ["running", "completed"])
def test_journal_failure_reports_unknown_and_blocks_replay(tmp_path, monkeypatch, failure_state):
    probe = Probe()
    erased = []
    probe.erase = lambda: erased.append(True)
    state_dir = tmp_path / "journal"
    w = Workbench(state_dir, factory=lambda dll: probe)
    w.connect(765432, "Device")
    save = w._save_job
    failed = False
    def failing_save(job_id, state, result):
        nonlocal failed
        if failed or state == failure_state:
            failed = True
            raise sqlite3.OperationalError("database or disk is full")
        save(job_id, state, result)
    monkeypatch.setattr(w, "_save_job", failing_save)
    try:
        w.start_job("erase", {"device": "Device"}, "disk-full", True)
        w.executor.submit(lambda: None).result(timeout=3)
        result = w.job_status("disk-full")
        assert result["state"] == "unknown" and result["persisted"] is False
        assert "disk is full" in result["result"]["persistence_error"]
        assert w.job_active is None and w.quarantine
        assert len(erased) == int(failure_state == "completed")
        w.disconnect()
        w.connect(765432, "Device")
        for job_id in ("disk-full", "new-id"):
            with pytest.raises(InputError):
                w.start_job("erase", {"device": "Device"}, job_id, True)
    finally:
        w.close()
    reopened = Workbench(state_dir, factory=lambda dll: probe)
    try:
        reopened.connect(765432, "Device")
        result = reopened.start_job("erase", {"device": "Device"}, "disk-full", True)
        assert result["state"] == "unknown" and result["reused"]
        assert len(erased) == int(failure_state == "completed")
    finally:
        reopened.close()


def test_capture_recording_manifest_and_plot(bench, tmp_path):
    w, p = bench
    output = tmp_path / "capture.jsonl"
    w.start_job("capture", {"kind": "memory", "regions": [{"address": 100, "size": 4}], "duration": .03,
                "period": .01, "path": str(output)}, "capture", True)
    assert wait_job(w, "capture")["state"] == "completed"
    result = summarize_recording(str(output))
    assert result["completion"]["complete"] and result["samples"] >= 1
    with output.open("a") as stream:
        stream.write('{}\n')
    with pytest.raises((InputError, KeyError)):
        summarize_recording(str(output))


def test_nested_isr_accounting_and_scheduler_handoff():
    events = [{"kind": "task_start_exec", "task_id": 1, "t_us": 0},
              {"kind": "isr_enter", "isr_id": 10, "t_us": 10},
              {"kind": "isr_enter", "isr_id": 11, "t_us": 20},
              {"kind": "isr_exit", "t_us": 30}, {"kind": "isr_exit", "t_us": 40},
              {"kind": "task_stop_exec", "t_us": 50}]
    result = analyze_events(events)
    assert result["actors"]["task:1"]["seconds"] == pytest.approx(20e-6)
    assert result["actors"]["isr:10"]["seconds"] == pytest.approx(20e-6)
    assert result["actors"]["isr:11"]["seconds"] == pytest.approx(10e-6)
    assert sum(a["percent"] for a in result["actors"].values()) == pytest.approx(100)
    events[4]["kind"] = "isr_to_scheduler"
    result = analyze_events(events)
    assert result["unknown_seconds"] == pytest.approx(10e-6)


def test_event_time_validation_and_overflow():
    with pytest.raises(InputError):
        analyze_events([{"kind": "idle", "t_ticks": 100}])
    with pytest.raises(InputError):
        analyze_events([{"kind": "idle", "t_us": 2}, {"kind": "idle", "t_us": 1}])
    result = analyze_events([{"kind": "idle", "t_ticks": 0}, {"kind": "overflow", "t_ticks": 10}], 1000)
    assert result["complete"] is False


@pytest.mark.parametrize("matched", [False, True])
def test_event_analysis_detects_unmatched_isr_exit(matched):
    first = {"kind": "isr_enter", "isr_id": 3, "t_us": 0} if matched else {"kind": "idle", "t_us": 0}
    result = analyze_events([first, {"kind": "isr_exit", "t_us": 10}, {"kind": "idle", "t_us": 20}])
    assert result["unmatched_isr_exits"] == int(not matched)
    assert result["complete"] is matched


def test_systemview_decoder_handles_fragmented_stream():
    p = SystemViewParser()
    assert p.feed(b"\0" * 5) == []
    events = p.feed(b"\0" * 5 + bytes([4, 1, 10, 2, 3, 5, 3, 5]))
    assert [e["kind"] for e in events] == ["task_start_exec", "isr_enter", "isr_exit"]
    assert events[-1]["t_ticks"] == 20


@pytest.fixture(params=[4, 5])
def elf_fixture(tmp_path, request):
    compiler = shutil.which("arm-none-eabi-gcc")
    if not compiler:
        pytest.skip("Optional ELF fixture requires an Arm GCC compiler")
    source = tmp_path / "fixture.c"
    source.write_text('struct Config { int value; float scale; }; volatile struct Config config={7,1.5f}; volatile unsigned short values[3]={1,2,3}; void _start(void) { for (;;) {} }', encoding="utf-8")
    output = tmp_path / "fixture.elf"
    subprocess.run([compiler, "-g", f"-gdwarf-{request.param}", "-O0", "-nostdlib", "-mcpu=cortex-m3", "-mthumb", "-Wl,-Ttext=0x1000", "-Wl,-Tdata=0x20000000", str(source), "-o", str(output)], check=True, capture_output=True)
    return output


def test_real_elf_members_arrays_and_stale_symbols(elf_fixture, bench):
    w, p = bench
    w.load_symbols(str(elf_fixture))
    location = w.symbolize([0x1000])[0]
    assert Path(location["file"]).name == "fixture.c" and location["line"] > 0
    assert w.type_info("config.value")["size"] == 4
    assert w.type_info("values[2]")["address"] == w.type_info("values[0]")["address"] + 4
    with pytest.raises(InputError):
        w.type_info("values[3]")
    with pytest.raises(InputError):
        w.write_variable("config.value", 10, w.symbols.info["sha256"], True)
    info, segments = images(elf_fixture)
    for address, data in segments:
        p.memory_write8(address, data)
    w.verify_image(str(elf_fixture))
    assert w.write_variable("config.value", 10, info["sha256"], True)["verified"]
    assert w.read_variable("config.value")["value"] == 10
    elf_fixture.write_bytes(elf_fixture.read_bytes() + b"x")
    with pytest.raises(InputError):
        w.read_variable("config.value")


def test_hex_preserves_holes_and_rejects_checksum(tmp_path):
    path = tmp_path / "app.hex"
    path.write_text(':020000040800F2\n:020000000102FB\n:020010000304E7\n:00000001FF\n')
    info, segments = images(path)
    assert segments == [(0x08000000, b"\1\2"), (0x08000010, b"\3\4")]
    path.write_text(':02000000010200\n:00000001FF\n')
    with pytest.raises(InputError):
        images(path)


def test_build_failure_does_not_collect_stale_artifacts(tmp_path):
    stale = tmp_path / "old.bin"
    stale.write_bytes(b"old")
    result = run_build([sys.executable, "-c", "raise SystemExit(3)"], str(tmp_path), [str(stale)], str(tmp_path), confirm=True)
    assert result["success"] is False and result["artifacts"] == []


def test_cross_process_owner_lock(tmp_path):
    with FileLock(tmp_path / "shared.lock"):
        child = subprocess.run([sys.executable, "-c", "from openjlink.common import FileLock; FileLock(__import__('sys').argv[1]).acquire()", str(tmp_path / "shared.lock")], capture_output=True)
        assert child.returncode != 0




def test_general_scope_and_no_comments_or_docstrings():
    scripts = Path(__file__).parents[1] / "scripts"
    for path in scripts.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not any(t.type == tokenize.COMMENT for t in tokenize.generate_tokens(io.StringIO(text).readline))
        tree = ast.parse(text)
        assert ast.get_docstring(tree) is None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                assert ast.get_docstring(node) is None


@pytest.fixture
def svd_fixture(tmp_path):
    path = tmp_path / "device.svd"
    path.write_text('<device schemaVersion="1.3"><name>TestMCU</name><version>1</version><description>Fixture</description><addressUnitBits>8</addressUnitBits><width>32</width><size>32</size><access>read-write</access><peripherals><peripheral><name>TEST</name><description>Fixture</description><baseAddress>0x40000000</baseAddress><registers><register><name>CTRL</name><addressOffset>0</addressOffset><fields><field><name>MODE</name><bitOffset>4</bitOffset><bitWidth>3</bitWidth></field></fields></register><register><name>CLEAR</name><addressOffset>4</addressOffset><readAction>clear</readAction></register><register><name>WRITE</name><addressOffset>8</addressOffset><access>write-only</access></register><register><name>FIELD_CLEAR</name><addressOffset>12</addressOffset><fields><field><name>FLAG</name><bitOffset>0</bitOffset><bitWidth>1</bitWidth><readAction>clear</readAction></field></fields></register></registers></peripheral></peripherals></device>', encoding="utf-8")
    return path


def test_svd_fields_read_safety_and_stale_source(bench, svd_fixture):
    w, probe = bench
    result = w.load_peripherals(str(svd_fixture), "little")
    assert result["total"] == 4 and result["device"] == "TestMCU"
    probe.memory_write8(0x40000000, [0x50, 0, 0, 0])
    result = w.read_peripherals(["TEST.CTRL"])
    assert result["registers"][0]["fields"]["MODE"] == 5
    probe.reads.clear()
    for name in ("TEST.CLEAR", "TEST.WRITE", "TEST.FIELD_CLEAR", "TEST.MISSING"):
        with pytest.raises(InputError):
            w.read_peripherals(["TEST.CTRL", name])
        assert not probe.reads
    svd_fixture.write_text(svd_fixture.read_text() + " ", encoding="utf-8")
    with pytest.raises(InputError):
        w.read_peripherals(["TEST.CTRL"])


def test_svd_rejects_entities_and_large_expansion(bench, svd_fixture):
    w, probe = bench
    original = svd_fixture.read_text()
    svd_fixture.write_text('<!DOCTYPE device [<!ENTITY test "x">]>' + original, encoding="utf-8")
    with pytest.raises(InputError):
        w.load_peripherals(str(svd_fixture), "little")
    svd_fixture.write_text(original.replace('<name>CTRL</name>', '<dim>999999999</dim><name>CTRL%s</name>'), encoding="utf-8")
    with pytest.raises(InputError):
        w.load_peripherals(str(svd_fixture), "little")
    assert not probe.reads


@pytest.mark.parametrize("bits", [8, 16, 32])
@pytest.mark.parametrize("byte_order", ["little", "big"])
def test_svd_preserves_bus_access_width(bench, svd_fixture, monkeypatch, bits, byte_order):
    w, probe = bench
    svd_fixture.write_text(svd_fixture.read_text().replace("<name>CTRL</name>", f"<name>CTRL</name><size>{bits}</size>"))
    w.load_peripherals(str(svd_fixture), byte_order)
    reads = []
    value = {8: 0x50, 16: 0x1250, 32: 0x12345650}[bits]
    def read(address, count):
        reads.append((address, count))
        return [value]
    def wrong_width(*args):
        raise AssertionError("Wrong bus access width")
    for width in (8, 16, 32):
        monkeypatch.setattr(probe, f"memory_read{width}", read if width == bits else wrong_width, raising=False)
    result = w.read_peripherals(["TEST.CTRL"])["registers"][0]
    assert reads == [(0x40000000, 1)]
    assert result["value"] == value and result["fields"]["MODE"] == 5
    assert result["hex"] == value.to_bytes(bits // 8, byte_order).hex()


def test_svd_rejects_short_word_read(bench, svd_fixture, monkeypatch):
    w, probe = bench
    w.load_peripherals(str(svd_fixture), "little")
    monkeypatch.setattr(probe, "memory_read32", lambda address, count: [], raising=False)
    with pytest.raises(RuntimeError, match="Short read"):
        w.read_peripherals(["TEST.CTRL"])


def test_peripheral_capture_is_replayable(bench, svd_fixture, tmp_path):
    w, probe = bench
    w.load_peripherals(str(svd_fixture), "little")
    output = tmp_path / "peripherals.jsonl"
    w.start_job("capture", {"kind": "peripherals", "names": ["TEST.CTRL"], "duration": .02,
                           "period": .01, "path": str(output)}, "svd-capture", True)
    assert wait_job(w, "svd-capture")["state"] == "completed"
    result = summarize_recording(str(output))
    assert result["channels"]["TEST.CTRL"]["first"] == 0
    assert result["metadata"]["source_kind"] == "peripherals"

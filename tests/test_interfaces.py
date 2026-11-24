import json
import os
import queue
import struct
import subprocess
import sys
import threading
import textwrap
from pathlib import Path
from types import SimpleNamespace
import pytest
from openjlink import __version__
from openjlink.capture.telemetry import decode_packets
from openjlink.analysis.report import decode_systemview, render_recording, summarize_recording
from openjlink.protocol.serial import serial_exchange, modbus
from openjlink.common import InputError
from openjlink.debug.gdb import gdb_inspect, gdb_server_arguments
from openjlink.session import Workbench


def test_environment_reports_dependencies_without_hardware(tmp_path):
    from importlib.metadata import version
    def forbidden_factory(dll):
        raise AssertionError("Environment inspection must not open a probe")
    workbench = Workbench(tmp_path / "state", factory=forbidden_factory)
    try:
        result = workbench.inspect_environment()
        assert result["packages"]["cmsis-svd"] == version("cmsis-svd")
        assert "mcp" not in result["packages"]
        assert result["hardware_accessed"] is False
    finally:
        workbench.close()


def test_actual_serial_loopback_binary_exchange():
    result = serial_exchange("loop://", "00ff4142", timeout=.01, maximum=4, confirm=True)
    assert result["rx_hex"] == "00ff4142"
    assert result["complete_write"]
    assert not result["response_correlated"]
    with pytest.raises(InputError):
        serial_exchange("loop://", "aa", timeout=.01)


def test_modbus_protocol_ack_and_zero_retries(monkeypatch):
    calls = []
    class Client:
        def __init__(self, port, **kwargs):
            assert kwargs["retries"] == 0
            self.trace = kwargs["trace_packet"]
        def connect(self):
            return True
        def close(self):
            pass
        def write_register(self, address, value, device_id):
            calls.append((address, value, device_id))
            self.trace(True, b"\1\6")
            self.trace(False, b"\1\6")
            return SimpleNamespace(isError=lambda: False)
    monkeypatch.setattr("pymodbus.client.ModbusSerialClient", Client)
    with pytest.raises(InputError):
        modbus("mock-port", 6, 10, values=[22])
    result = modbus("mock-port", 6, 10, slave=7, values=[22], confirm=True)
    assert calls == [(10, 22, 7)]
    assert result["protocol_acknowledged"] and not result["application_acknowledged"]
    assert [f["direction"] for f in result["frames"]] == ["tx", "rx"]
    with pytest.raises(InputError):
        modbus("mock-port", 6, 65535, values=[1, 2], confirm=True)


@pytest.mark.parametrize("mode", ["direct", "call", "session"])
@pytest.mark.parametrize("failure", [False, True])
def test_modbus_cli_reports_protocol_failure_and_keeps_session(tmp_path, mode, failure):
    child = textwrap.dedent('''
        import sys
        from types import SimpleNamespace
        import pymodbus.client
        failure = bool(int(sys.argv.pop(1)))
        class Client:
            def __init__(self, port, **kwargs):
                assert kwargs["retries"] == 0
                self.trace = kwargs["trace_packet"]
            def connect(self):
                return True
            def close(self):
                pass
            def read_holding_registers(self, address, count, device_id):
                self.trace(True, b"request")
                self.trace(False, b"error" if failure else b"reply")
                return SimpleNamespace(isError=lambda: failure, registers=[123])
        pymodbus.client.ModbusSerialClient = Client
        from openjlink.cli import main
        raise SystemExit(main())
    ''')
    values = {"port": "mock-port", "function": 3, "address": 0}
    arguments = ["modbus", "--port", "mock-port", "--function", "3", "--address", "0"]
    request = None
    if mode == "call":
        arguments = ["call", "modbus", "--args", json.dumps(values)]
    elif mode == "session":
        arguments = ["session"]
        request = json.dumps({"id": 1, "operation": "modbus", "arguments": values}) + '\n{"id":2,"operation":"ping"}\n'
    result = subprocess.run([sys.executable, "-c", child, str(int(failure)), "--state-dir", str(tmp_path / "state"), *arguments],
                            input=request, capture_output=True, text=True, encoding="utf-8", timeout=10)
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert result.returncode == (int(failure) if mode != "session" else 0), result.stderr
    response = responses[0]
    assert response["ok"] is not failure
    if mode == "session":
        assert response["id"] == 1 and responses[1]["id"] == 2 and responses[1]["ok"]
        response = response["result"]
    assert [frame["direction"] for frame in response["frames"]] == ["tx", "rx"]
    assert bytes.fromhex(response["frames"][1]["hex"]) == (b"error" if failure else b"reply")


def test_telemetry_sequence_wrap_plot_and_manifest(tmp_path):
    raw = tmp_path / "telemetry.bin"
    raw.write_bytes(b"".join(struct.pack("<IIf", sequence, tick, value) for sequence, tick, value in
                             [(0xFFFFFFFF, 0xFFFFFFF0, 1.0), (0, 4, 2.0), (2, 24, 3.0)]))
    output = tmp_path / "samples.jsonl"
    result = decode_packets(str(raw), str(output), "<IIf", ["sequence", "ticks", "value"], "ticks", 1000, "sequence")
    assert result["detected_sequence_gaps"] == 1 and not result["complete"]
    summary = summarize_recording(str(output))
    assert summary["channels"]["value"]["mean"] == 2
    plot = tmp_path / "plot.html"
    render_recording(str(output), str(plot))
    page = plot.read_text(encoding="utf-8")
    assert "__DATA__" not in page and "hardware" in page and "Find rising edge" in page
    assert "</script><script>" not in page
    output.write_text(output.read_text() + '\n', encoding="utf-8")
    with pytest.raises((InputError, ValueError)):
        summarize_recording(str(output))


def test_telemetry_truncated_sync_is_not_complete(tmp_path):
    raw, output = tmp_path / "raw.bin", tmp_path / "data.jsonl"
    raw.write_bytes(b"AA" + struct.pack("<II", 1, 10) + b"AA")
    result = decode_packets(str(raw), str(output), "<II", ["seq", "time"], "time", 1000, "seq", "4141")
    assert result["trailing_bytes"] == 2 and not result["complete"]


def test_independent_sequence_and_time_counter_widths(tmp_path):
    raw, output = tmp_path / "raw.bin", tmp_path / "data.jsonl"
    raw.write_bytes(struct.pack("<HIHI", 65535, 100000, 0, 100020))
    result = decode_packets(str(raw), str(output), "<HI", ["seq", "ticks"], "ticks", 1000,
                            "seq", sequence_modulus=65536)
    assert result["complete"] and not result["detected_sequence_gaps"]


@pytest.mark.parametrize("truncated", [False, True])
def test_systemview_file_decoding_reports_integrity(tmp_path, truncated):
    raw = tmp_path / "trace.bin"
    raw.write_bytes(b"\0" * 10 + bytes([4, 1, 10, 2, 3, 5, 3, 5]) + (b"\4" if truncated else b""))
    result = decode_systemview(str(raw), tick_hz=1000)
    assert result["synced"]
    assert result["dropped_packets"] == 0
    assert result["summary"]["duration_s"] == pytest.approx(.01)
    assert result["pending_bytes"] == int(truncated)
    assert result["decoder_complete"] is not truncated


def test_systemview_requires_sync_before_decoding(tmp_path):
    raw = tmp_path / "unsynced.bin"
    raw.write_bytes(bytes([4, 1, 10]))
    result = decode_systemview(str(raw), tick_hz=1000)
    assert not result["events"] and not result["synced"]
    assert result["pending_bytes"] == 3 and not result["decoder_complete"]


def test_gdb_arguments_do_not_launch_and_disable_autoload(tmp_path, monkeypatch):
    elf = tmp_path / "a file.elf"
    elf.write_bytes(b"x")
    plugin = tmp_path / "RTOS.dll"
    plugin.write_bytes(b"x")
    result = gdb_server_arguments(123456, "A_Device", rtos_plugin=str(plugin))
    assert result["no_target_access_performed"]
    assert "-rtos" in result["argv"]
    def run(argv, **kwargs):
        assert "--nx" in argv and "--nh" in argv and "set auto-load off" in argv
        assert kwargs["shell"] is False
        assert "thread apply all bt" in argv
        return SimpleNamespace(returncode=0, stdout="thread data", stderr="")
    monkeypatch.setattr(subprocess, "run", run)
    result = gdb_inspect(str(elf), action="backtrace", confirm=True)
    assert result["target_execution_may_change"]


def test_cli_persistent_session_and_error_exit(tmp_path):
    args = [sys.executable, "-m", "openjlink", "--state-dir", str(tmp_path / "state"), "session"]
    result = subprocess.run(args, input='{"id":1,"operation":"ping"}\n{"id":2,"operation":"device_status"}\n', capture_output=True, text=True)
    assert result.returncode == 0
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(lines) == 2 and lines[0]["result"]["operations"] and lines[1]["result"]["connected"] is False
    result = subprocess.run([sys.executable, "-m", "openjlink", "call", "read_memory", "--args", "{}"], capture_output=True, text=True)
    assert result.returncode == 1 and json.loads(result.stdout)["ok"] is False


def test_cli_session_responds_without_waiting_for_eof(tmp_path):
    environment = dict(os.environ)
    environment.pop("PYTHONUNBUFFERED", None)
    args = [sys.executable, "-m", "openjlink", "--state-dir", str(tmp_path / "live-state"), "session"]
    process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", env=environment)
    responses = queue.Queue()
    try:
        for request_id, operation in enumerate(("ping", "device_status")):
            reader = threading.Thread(target=lambda: responses.put(process.stdout.readline()), daemon=True)
            reader.start()
            process.stdin.write(json.dumps({"id": request_id, "operation": operation}) + "\n")
            process.stdin.flush()
            response = json.loads(responses.get(timeout=5))
            assert response["id"] == request_id and response["ok"]
            assert process.poll() is None
            reader.join(timeout=1)
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdout.close()
        process.stderr.close()


def test_direct_cli_and_distribution_identity(tmp_path):
    from importlib.metadata import distribution
    root = Path(__file__).parents[1]
    metadata = distribution("openjlink")
    assert metadata.metadata["Name"] == "openjlink"
    assert metadata.version == __version__
    assert {e.name: e.value for e in metadata.entry_points if e.group == "console_scripts"} == {"openjlink": "openjlink.cli:main"}
    assert "name: openjlink\n" in (root / "SKILL.md").read_text(encoding="utf-8")
    assert not any("mcp" in dependency.lower() for dependency in metadata.requires)
    command = [sys.executable, "-m", "openjlink"]
    version = subprocess.run(command + ["--version"], capture_output=True, text=True)
    assert version.returncode == 0 and version.stdout.startswith("OpenJlink ")
    raw = tmp_path / "test.bin"
    raw.write_bytes(b"test")
    inspected = subprocess.run(command + ["inspect-image", "--path", str(raw), "--base-address", "0x08000000"], capture_output=True, text=True)
    assert inspected.returncode == 0 and json.loads(inspected.stdout)["ranges"] == [{"address": 0x08000000, "size": 4}]
    disconnected = subprocess.run(command + ["--state-dir", str(tmp_path / "state"), "read-memory", "--address", "0x20000000", "--size", "4"], capture_output=True, text=True)
    assert disconnected.returncode == 1 and json.loads(disconnected.stdout)["error"] == "InputError"


def test_session_wire_encoding_is_utf8_under_ascii_host(tmp_path):
    environment = {**os.environ, "PYTHONIOENCODING": "ascii"}
    request = json.dumps({"id": "测试😀", "operation": "ping"}, ensure_ascii=False) + "\n"
    args = [sys.executable, "-m", "openjlink", "--state-dir", str(tmp_path / "utf8-state"), "session"]
    result = subprocess.run(args, input=request.encode("utf-8"), capture_output=True, env=environment)
    assert result.returncode == 0
    assert json.loads(result.stdout.decode("utf-8"))["id"] == "测试😀"


def test_state_dir_after_subcommand_schema_jobs_and_session_help(tmp_path):
    command = [sys.executable, "-m", "openjlink"]
    for args in (
        ["ping", "--state-dir", str(tmp_path / "after-direct")],
        ["call", "ping", "--state-dir", str(tmp_path / "after-call")],
        ["session", "--state-dir", str(tmp_path / "after-session")],
    ):
        res = subprocess.run(command + args, input='{"id":1,"operation":"ping"}\n', capture_output=True, text=True)
        assert res.returncode == 0, res.stderr
        row = json.loads(res.stdout.splitlines()[0])
        assert (row["ok"] and row["result"]["operations"]) if "session" in args else row["operations"]

    schema = json.loads(subprocess.check_output(command + ["schema"], text=True))
    assert len(schema) == 54
    job_schema = json.loads(subprocess.check_output(command + ["schema", "start_job"], text=True))
    assert set(job_schema["job_operations"]) == {"program", "erase", "reset", "capture"}
    assert job_schema["terminal_states"] == ["completed", "failed", "unknown"]

    session_help = subprocess.check_output(command + ["session", "--help"], text=True)
    assert '"operation"' in session_help and '"arguments"' in session_help


def test_compact_cli_and_session_batch(tmp_path):
    command = [sys.executable, "-m", "openjlink"]
    full_raw = subprocess.check_output(command + ["schema"], text=True)
    compact_raw = subprocess.check_output(command + ["schema", "--compact"], text=True)
    compact_data = json.loads(compact_raw)
    assert len(compact_data) == 54 and isinstance(compact_data["ping"], str)
    assert len(compact_raw) < len(full_raw) * 0.6
    start_compact = json.loads(subprocess.check_output(command + ["schema", "--compact", "start_job"], text=True))
    assert set(start_compact) == {"signature", "job_operations", "terminal_states"}

    batch_json = tmp_path / "batch.json"
    batch_json.write_text(json.dumps([
        {"operation": "ping"},
        {"operation": "device_status"},
    ]), encoding="utf-8")
    res = subprocess.run(
        command + ["session", "--state-dir", str(tmp_path / "batch-arr"), "--compact", "--batch", str(batch_json)],
        capture_output=True, text=True, check=True,
    )
    rows = [json.loads(line) for line in res.stdout.splitlines()]
    assert [r["id"] for r in rows] == [1, 2]
    assert rows[0]["result"]["operation_count"] == 40
    assert "engineering_policy" not in rows[0]["result"]

    jsonl_in = '{"id":10,"operation":"ping"}\n{"id":11,"operation":"read_memory","arguments":{"address":0,"size":4}}\n{"id":12,"operation":"device_status"}\n'
    err_res = subprocess.run(
        command + ["session", "--state-dir", str(tmp_path / "batch-err"), "--compact", "--batch", "-", "--stop-on-error"],
        input=jsonl_in, capture_output=True, text=True,
    )
    assert err_res.returncode == 1
    err_rows = [json.loads(line) for line in err_res.stdout.splitlines()]
    assert [r["id"] for r in err_rows] == [10, 11] and err_rows[0]["ok"] is True and err_rows[1]["ok"] is False

    ping_compact = json.loads(subprocess.check_output(
        command + ["--compact", "ping", "--state-dir", str(tmp_path / "direct-compact")], text=True,
    ))
    assert set(ping_compact) == {"version", "state_dir", "operation_count"}


def test_skill_launcher_uses_its_own_environment(tmp_path):
    root = tmp_path / "skill"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "run.py").write_bytes((Path(__file__).parents[1] / "scripts/run.py").read_bytes())
    (scripts / "openjlink.py").write_text("import sys\nprint(sys.prefix)\n", encoding="utf-8")
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(root / ".venv")], check=True, capture_output=True)
    result = subprocess.run([sys.executable, str(scripts / "run.py")], capture_output=True, text=True)
    assert result.returncode == 0 and Path(result.stdout.strip()).resolve() == (root / ".venv").resolve()

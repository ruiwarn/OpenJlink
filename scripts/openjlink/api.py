import inspect
from openjlink.analysis.report import summarize_recording, compare_recordings, analyze_events, decode_systemview, export_rtt, render_recording
from openjlink.debug.gdb import gdb_inspect, gdb_server_arguments
from openjlink.host.process import run_build
from openjlink.capture.telemetry import decode_packets
from openjlink.symbols.elf import inspect_image
from openjlink.protocol.serial import serial_ports, serial_exchange, modbus
from openjlink.session import OPERATIONS, Workbench, dispatch


EXTRAS = {
    "inspect_image": (inspect_image, "Preview ELF/HEX/BIN load ranges and file hash without hardware access"),
    "decode_packets": (decode_packets, "Decode an explicit fixed telemetry packet layout with target time, sequence gaps and wrap detection"),
    "run_build": (run_build, "Run the exact authorized build/test argument list and hash explicit artifacts"),
    "summarize_recording": (summarize_recording, "Summarize a saved recording and verify its completion manifest"),
    "compare_recordings": (compare_recordings, "Compare two explicit captures without asserting causation"),
    "analyze_events": (analyze_events, "Analyze task/ISR events with exclusive-time accounting"),
    "decode_systemview": (decode_systemview, "Offline SystemView byte decoding, with integrity counters"),
    "export_rtt": (export_rtt, "Extract raw RTT/SystemView bytes from a capture"),
    "render_recording": (render_recording, "Create an offline zoomable variable plot and replay"),
    "serial_ports": (serial_ports, "List ordinary serial ports"),
    "serial_exchange": (serial_exchange, "One bounded serial exchange; writes require authorization; never replays"),
    "modbus": (modbus, "Modbus RTU FC1/2/3/4/5/6/15/16, explicit slave, zero retries"),
    "gdb_server_arguments": (gdb_server_arguments, "Generate official server argv with explicit target/plugin; does not launch"),
    "gdb_inspect": (gdb_inspect, "Inspect an explicitly configured GDB server; may affect target execution")
}
OFFLINE = {"inspect_image", "decode_packets", "summarize_recording", "compare_recordings", "analyze_events", "decode_systemview", "export_rtt", "render_recording", "serial_ports", "gdb_server_arguments"}


JOB_OPERATIONS = {
    "program": ("_program", "Program ELF/HEX/BIN within explicit allowed_ranges and optional preserve_ranges"),
    "erase": ("_erase", "Erase connected device matching explicit device name"),
    "reset": ("_reset", "Reset target with explicit halt flag"),
    "capture": ("_capture", "Timed memory, peripheral, or RTT capture to a recording file"),
}


def method_signature(callable_object):
    value = inspect.signature(callable_object)
    return value.replace(parameters=[p for p in value.parameters.values() if p.name != "self"])


def signature(name):
    return method_signature(EXTRAS[name][0] if name in EXTRAS else getattr(Workbench, name))


def catalog():
    result = {}
    for name in OPERATIONS.keys() | EXTRAS.keys():
        result[name] = {"description": EXTRAS[name][1] if name in EXTRAS else OPERATIONS[name],
                        "signature": str(signature(name))}
    result["start_job"]["job_operations"] = {
        op: {"description": desc, "signature": str(method_signature(getattr(Workbench, method)))}
        for op, (method, desc) in JOB_OPERATIONS.items()
    }
    result["start_job"]["terminal_states"] = ["completed", "failed", "unknown"]
    return dict(sorted(result.items()))


def call(workbench, operation, arguments):
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    if operation not in EXTRAS:
        return dispatch(workbench, operation, arguments)
    if operation == "gdb_inspect" and workbench.probe:
        raise ValueError("Disconnect SDK ownership before attaching GDB")
    function = EXTRAS[operation][0]
    inspect.signature(function).bind(**arguments)
    return function(**arguments)

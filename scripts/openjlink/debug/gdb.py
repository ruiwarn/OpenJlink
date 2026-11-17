import re
import subprocess
from openjlink.common import InputError, approval, file_info, integer, number


def gdb_inspect(elf: str, action: str = "threads", host: str = "127.0.0.1", port: int = 2331,
                gdb: str = "arm-none-eabi-gdb", timeout: float = 15, confirm: bool = False):
    approval(confirm)
    info = file_info(elf)
    if any(c in info["path"] for c in "\r\n\0"):
        raise InputError("Control characters in debugger paths are unsupported")
    integer(port, 1, 65535)
    number(timeout, .1, 120)
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise InputError("Use an explicitly configured loopback GDB Server")
    commands = {"threads": "info threads", "backtrace": "thread apply all bt", "registers": "info registers"}
    if action not in commands:
        raise InputError("Use threads/backtrace/registers")
    argv = [gdb, "--nx", "--nh", "--batch", "-iex", "set auto-load off", "-ex", "set pagination off",
            "-ex", "set confirm off", "-ex", "file " + '"' + info["path"].replace("\\", "/").replace('"', '\\"') + '"',
            "-ex", f"target remote {host}:{port}", "-ex", commands[action], "-ex", "detach"]
    result = subprocess.run(argv, capture_output=True, text=True, errors="replace", timeout=timeout, shell=False)
    return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
            "action": action, "thread_awareness": "depends on server RTOS plugin; one thread does not prove no RTOS",
            "target_execution_may_change": True, "detached_requested": True, "automatic_retry": False}


def gdb_server_arguments(serial: int, device: str, server: str = "JLinkGDBServerCL.exe", port: int = 2331,
                          speed_khz: int = 1000, interface: str = "SWD", rtos_plugin: str | None = None):
    integer(serial, 1)
    integer(port, 1024, 65532)
    integer(speed_khz, 5, 50000)
    if not isinstance(device, str) or not re.fullmatch(r"[\w .:+()/-]+", device) or interface not in ("SWD", "JTAG"):
        raise InputError("Explicit device/interface required")
    argv = [server, "-select", f"USB={serial}", "-device", device, "-if", interface, "-speed", str(speed_khz),
            "-port", str(port), "-swoport", str(port + 1), "-telnetport", str(port + 2),
            "-RTTTelnetPort", str(port + 3), "-localhostonly", "1", "-noreset", "-noir", "-nogui"]
    if rtos_plugin:
        argv.extend(["-rtos", file_info(rtos_plugin)["path"]])
    return {"argv": argv, "start_required": "Disconnect toolkit SDK session first; launch exactly this argument list using host process tools",
            "no_target_access_performed": True}

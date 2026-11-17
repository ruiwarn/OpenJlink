import subprocess
import time
import uuid
from pathlib import Path
from openjlink.common import InputError, approval, file_info, number, write_json


def run_build(argv: list[str], cwd: str, artifacts: list[str], output_dir: str,
              timeout: float = 300, confirm: bool = False):
    approval(confirm)
    number(timeout, 0.1, 7200)
    if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or "\0" in x for x in argv):
        raise InputError("argv must be an explicit nonempty argument list")
    if not isinstance(artifacts, list) or any(not isinstance(x, str) for x in artifacts):
        raise InputError("artifacts must be explicit paths, including an empty list when none expected")
    directory = Path(cwd).expanduser().resolve(strict=True)
    output = Path(output_dir).expanduser().resolve(strict=True)
    if not directory.is_dir() or not output.is_dir():
        raise InputError("cwd and output_dir must exist")
    build_id = uuid.uuid4().hex
    log = output / (build_id + ".log")
    started = time.time_ns()
    timed_out, code = False, None
    with log.open("xb") as stream:
        process = subprocess.Popen(argv, cwd=directory, shell=False, stdin=subprocess.DEVNULL,
                                   stdout=stream, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            process.wait()
    result = {"build_id": build_id, "argv": argv, "cwd": str(directory), "exit_code": code,
              "timed_out": timed_out, "started_unix_ns": started, "finished_unix_ns": time.time_ns(),
              "log": file_info(log), "artifacts": [], "success": code == 0 and not timed_out,
              "child_processes_after_timeout": "not_guaranteed_stopped" if timed_out else None}
    if result["success"]:
        try:
            result["artifacts"] = [file_info(directory / p) for p in artifacts]
        except (OSError, InputError) as exc:
            result.update(success=False, error=str(exc))
    write_json(output / (build_id + ".json"), result)
    return result

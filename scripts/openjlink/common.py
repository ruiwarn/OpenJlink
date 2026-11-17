import hashlib
import json
import math
import os
import time
from pathlib import Path


class InputError(ValueError):
    pass


def integer(value, minimum=0, maximum=0xFFFFFFFF):
    if type(value) is not int or not minimum <= value <= maximum:
        raise InputError(f"Expected integer in {minimum}..{maximum}")
    return value


def number(value, minimum, maximum):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise InputError(f"Expected finite number in {minimum}..{maximum}")
    return value


def memory_range(address, size, maximum=4096):
    integer(address)
    integer(size, 1, maximum)
    if address + size > 0x100000000:
        raise InputError("Memory range exceeds 32-bit address space")


def hex_bytes(text, maximum=4096):
    if not isinstance(text, str) or len(text) > maximum * 3:
        raise InputError("Expected bounded hexadecimal text")
    try:
        data = bytes.fromhex(text)
    except ValueError as exc:
        raise InputError("Invalid hexadecimal bytes") from exc
    integer(len(data), 1, maximum)
    return data


def approval(confirm):
    if confirm is not True:
        raise InputError("Explicit authorization required: confirm=true")


def file_info(path):
    p = Path(path).expanduser().resolve(strict=True)
    if not p.is_file():
        raise InputError("Expected a regular file")
    h = hashlib.sha256()
    with p.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return {"path": str(p), "size": p.stat().st_size, "sha256": h.hexdigest()}


def write_json(path, value):
    p = Path(path)
    with p.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return file_info(p)


class FileLock:
    def __init__(self, path):
        self.path = Path(path)
        self.file = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b")
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            stream.close()
            raise RuntimeError(f"Resource busy: {self.path.name}") from exc
        self.file = stream
        return self

    def close(self):
        if self.file:
            self.file.close()
            self.file = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *args):
        self.close()


def timed_read(probe, address, size):
    memory_range(address, size, 16 * 1024 * 1024)
    start = time.monotonic_ns()
    data = bytes(probe.memory_read8(address, size))
    if len(data) != size:
        raise RuntimeError(f"Short read: requested {size}, received {len(data)}")
    return {"address": address, "size": size, "hex": data.hex(), "start_ns": start,
            "end_ns": time.monotonic_ns(), "clock": "host_monotonic"}

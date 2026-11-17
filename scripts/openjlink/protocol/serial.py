import hashlib
import time
from pathlib import Path
import tempfile
from openjlink.common import FileLock, InputError, approval, hex_bytes, integer, number


def port_lock(port):
    key = hashlib.sha256(port.casefold().encode()).hexdigest()
    return FileLock(Path(tempfile.gettempdir()) / "openjlink-locks" / ("uart-" + key + ".lock"))


def serial_ports():
    from serial.tools.list_ports import comports
    return [{"port": p.device, "description": p.description, "serial_number": p.serial_number} for p in comports()]


def serial_exchange(port: str, data_hex: str = "", baudrate: int = 115200, parity: str = "N",
                    databits: int = 8, stopbits: float = 1, timeout: float = 1,
                    maximum: int = 4096, confirm: bool = False):
    import serial
    integer(baudrate, 50, 10000000)
    integer(databits, 5, 8)
    number(timeout, 0.001, 30)
    integer(maximum, 1, 65536)
    if parity not in ("N", "E", "O", "M", "S") or stopbits not in (1, 1.5, 2):
        raise InputError("Invalid serial framing")
    data = hex_bytes(data_hex) if data_hex else b""
    if data:
        approval(confirm)
    start = time.monotonic_ns()
    with port_lock(port), serial.serial_for_url(port, baudrate, bytesize=databits, parity=parity,
                                        stopbits=stopbits, timeout=timeout, write_timeout=timeout) as connection:
        sent = connection.write(data) if data else 0
        received = connection.read(maximum)
    return {"port": port, "tx_hex": data.hex(), "rx_hex": received.hex(), "sent": sent,
            "complete_write": sent == len(data), "start_ns": start, "end_ns": time.monotonic_ns(),
            "response_correlated": False, "application_acknowledged": False, "retry_safe": False}


def modbus(port: str, function: int, address: int, slave: int = 1, count: int = 1,
           values: list[int] | None = None, baudrate: int = 9600, parity: str = "N",
           stopbits: int = 1, timeout: float = 1, confirm: bool = False):
    from pymodbus.client import ModbusSerialClient
    integer(function, 1, 16)
    integer(address, 0, 65535)
    integer(slave, 1, 247)
    integer(count, 1, 125 if function in (3, 4) else 2000)
    integer(baudrate, 50, 10000000)
    number(timeout, 0.01, 30)
    if parity not in ("N", "E", "O") or stopbits not in (1, 2):
        raise InputError("Invalid Modbus framing")
    reads = {1: "read_coils", 2: "read_discrete_inputs", 3: "read_holding_registers", 4: "read_input_registers"}
    writes = {5: "write_coil", 6: "write_register", 15: "write_coils", 16: "write_registers"}
    if function not in reads.keys() | writes.keys():
        raise InputError("Supported FC: 1/2/3/4/5/6/15/16")
    if function in writes:
        approval(confirm)
        maximum = 1 if function in (5, 6) else (1968 if function == 15 else 123)
        if not isinstance(values, list) or not 1 <= len(values) <= maximum:
            raise InputError("Invalid write value count")
        for value in values:
            integer(value, 0, 1 if function in (5, 15) else 65535)
    size = count if function in reads else len(values)
    if address + size > 65536:
        raise InputError("Modbus address range overflow")
    frames = []
    def packet(sending, packet):
        frames.append({"direction": "tx" if sending else "rx", "hex": bytes(packet).hex(), "host_ns": time.monotonic_ns()})
        return packet
    client = ModbusSerialClient(port, baudrate=baudrate, parity=parity, stopbits=stopbits,
                               timeout=timeout, retries=0, trace_packet=packet)
    with port_lock(port):
        try:
            if not client.connect():
                raise RuntimeError("Modbus port unavailable")
            if function in reads:
                response = getattr(client, reads[function])(address, count=count, device_id=slave)
            else:
                value = values[0] if function in (5, 6) else values
                if function in (5, 15):
                    value = bool(value) if function == 5 else [bool(x) for x in value]
                response = getattr(client, writes[function])(address, value, device_id=slave)
            if response.isError():
                return {"ok": False, "response": str(response), "frames": frames, "retry_safe": False}
            data = list(response.registers) if function in (3, 4) else list(response.bits[:count]) if function in (1, 2) else None
            return {"ok": True, "values": data, "frames": frames, "application_acknowledged": False,
                    "protocol_acknowledged": True, "retries": 0}
        finally:
            client.close()

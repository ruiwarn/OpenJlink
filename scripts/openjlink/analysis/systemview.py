from __future__ import annotations
import re
import struct
from typing import Any
EVTID_NOP = 0
EVTID_OVERFLOW = 1
EVTID_ISR_ENTER = 2
EVTID_ISR_EXIT = 3
EVTID_TASK_START_EXEC = 4
EVTID_TASK_STOP_EXEC = 5
EVTID_TASK_START_READY = 6
EVTID_TASK_STOP_READY = 7
EVTID_TASK_CREATE = 8
EVTID_TASK_INFO = 9
EVTID_TRACE_START = 10
EVTID_TRACE_STOP = 11
EVTID_SYSTIME_CYCLES = 12
EVTID_SYSTIME_US = 13
EVTID_SYSDESC = 14
EVTID_USER_START = 15
EVTID_USER_STOP = 16
EVTID_IDLE = 17
EVTID_ISR_TO_SCHEDULER = 18
EVTID_TIMER_ENTER = 19
EVTID_TIMER_EXIT = 20
EVTID_STACK_INFO = 21
EVTID_MODULEDESC = 22
EVTID_INIT = 24
EVTID_NAME_RESOURCE = 25
EVTID_PRINT_FORMATTED = 26
EVTID_NUMMODULES = 27
EVTID_END_CALL = 28
EVTID_TASK_TERMINATE = 29
EVTID_EX = 31
_LENGTH_PREFIX_THRESHOLD = 24
_MAX_PACKET_PAYLOAD = 4096
_MAX_BUF = 1048576
_EVENT_SPECS: dict[int, tuple[str, list[tuple[str, str]]]] = {EVTID_NOP: ('nop', []), EVTID_OVERFLOW: ('overflow', [('u32', 'drop_count')]), EVTID_ISR_ENTER: ('isr_enter', [('u32', 'isr_id')]), EVTID_ISR_EXIT: ('isr_exit', []), EVTID_TASK_START_EXEC: ('task_start_exec', [('id', 'task_id')]), EVTID_TASK_STOP_EXEC: ('task_stop_exec', []), EVTID_TASK_START_READY: ('task_start_ready', [('id', 'task_id')]), EVTID_TASK_STOP_READY: ('task_stop_ready', [('id', 'task_id'), ('u32', 'cause')]), EVTID_TASK_CREATE: ('task_create', [('id', 'task_id')]), EVTID_TASK_INFO: ('task_info', [('id', 'task_id'), ('u32', 'prio'), ('str', 'name')]), EVTID_TRACE_START: ('trace_start', []), EVTID_TRACE_STOP: ('trace_stop', []), EVTID_SYSTIME_CYCLES: ('systime_cycles', [('u32', 'systime')]), EVTID_SYSTIME_US: ('systime_us', [('u32', 'systime_low'), ('u32', 'systime_high')]), EVTID_SYSDESC: ('sysdesc', [('str', 'desc')]), EVTID_USER_START: ('user_start', [('u32', 'user_id')]), EVTID_USER_STOP: ('user_stop', [('u32', 'user_id')]), EVTID_IDLE: ('idle', []), EVTID_ISR_TO_SCHEDULER: ('isr_to_scheduler', []), EVTID_TIMER_ENTER: ('timer_enter', [('u32', 'timer_id')]), EVTID_TIMER_EXIT: ('timer_exit', []), EVTID_STACK_INFO: ('stack_info', [('id', 'task_id'), ('u32', 'stack_base'), ('u32', 'stack_size'), ('u32', 'stack_end')]), EVTID_MODULEDESC: ('moduledesc', [('u32', 'module_id'), ('str', 'desc')]), EVTID_INIT: ('init', [('u32', 'sys_freq'), ('u32', 'cpu_freq'), ('u32', 'ram_base'), ('u32', 'id_shift')]), EVTID_NAME_RESOURCE: ('name_resource', [('id', 'resource_id'), ('str', 'name')]), EVTID_PRINT_FORMATTED: ('print_formatted', [('str', 'msg'), ('u32', 'options'), ('u32', 'num_args')]), EVTID_NUMMODULES: ('nummodules', [('u32', 'num_modules')]), EVTID_END_CALL: ('end_call', [('u32', 'event_id')]), EVTID_TASK_TERMINATE: ('task_terminate', [('id', 'task_id')])}
_ISR_DESC_RE = re.compile('I#(\\d+)=([^,\\s]+)')

class _NeedMore(Exception):
    pass

class _FramingError(Exception):

    def __init__(self, message: str, *, discard: int=1) -> None:
        super().__init__(message)
        self.discard = max(1, discard)

class SystemViewParser:
    MIN_SYNC_ZEROS = 5

    def __init__(self, *, timestamp_bits: int=32) -> None:
        self._buf = bytearray()
        self._dropped_bytes = 0
        self._dropped_packets = 0
        self._synced = False
        self._abs_time = 0
        self._ts_mask = (1 << timestamp_bits) - 1 if timestamp_bits < 32 else 4294967295
        self._ram_base = 0
        self._id_shift = 2
        self._cpu_freq = 0
        self._timestamp_freq = 0
        self._cpu_freq_override: int | None = None
        self._task_names: dict[int, str] = {}
        self._isr_names: dict[int, str] = {}
        self._current_task: int | None = None
        self._num_modules = 0

    @property
    def dropped_bytes(self) -> int:
        return self._dropped_bytes

    @property
    def dropped_packets(self) -> int:
        return self._dropped_packets

    @property
    def pending_bytes(self) -> int:
        return len(self._buf)

    @property
    def synced(self) -> bool:
        return self._synced

    @property
    def abs_time(self) -> int:
        return self._abs_time

    @property
    def cpu_freq(self) -> int:
        return self._cpu_freq

    @property
    def timestamp_freq(self) -> int:
        return self._timestamp_freq or self._cpu_freq

    def set_cpu_freq(self, freq: int, *, lock: bool=False) -> None:
        value = int(freq)
        if value <= 0:
            return
        self._cpu_freq = value
        if lock:
            self._cpu_freq_override = value

    def task_name(self, task_id: int) -> str | None:
        return self._task_names.get(task_id)

    def isr_name(self, isr_id: int) -> str | None:
        return self._isr_names.get(isr_id)

    def reset(self) -> None:
        self._buf.clear()
        self._synced = False
        self._abs_time = 0
        self._dropped_bytes = 0
        self._dropped_packets = 0

    def feed(self, data: bytes) -> list[dict]:
        if data:
            self._buf.extend(data)
        events: list[dict] = []
        while self._buf:
            if len(self._buf) > _MAX_BUF:
                self._dropped_bytes += len(self._buf) - self.MIN_SYNC_ZEROS
                del self._buf[:len(self._buf) - self.MIN_SYNC_ZEROS]
                self._synced = False
            if not self._synced and not self._try_sync():
                break
            try:
                ev = self._parse_packet()
            except _NeedMore:
                break
            except _FramingError as exc:
                discard = min(exc.discard, len(self._buf))
                self._dropped_bytes += discard
                del self._buf[:discard]
                self._synced = False
                continue
            self._synced = True
            if ev is not None:
                events.append(ev)
        return events

    def _try_sync(self) -> bool:
        n = len(self._buf)
        i = 0
        while i < n:
            if self._buf[i] != 0:
                i += 1
                continue
            j = i
            while j < n and self._buf[j] == 0:
                j += 1
            run_len = j - i
            if run_len >= self.MIN_SYNC_ZEROS and j < n:
                self._dropped_bytes += i
                del self._buf[:j]
                self._synced = True
                return True
            if run_len >= self.MIN_SYNC_ZEROS:
                keep_from = n - self.MIN_SYNC_ZEROS
                if keep_from > 0:
                    self._dropped_bytes += i
                    del self._buf[:keep_from]
                return False
            i = j
        if n > 1024:
            self._dropped_bytes += n - self.MIN_SYNC_ZEROS
            del self._buf[:n - self.MIN_SYNC_ZEROS]
        return False

    def _parse_packet(self) -> dict | None:
        pos = 0
        first = self._peek(pos)
        if first & 128:
            event_id, pos = self._read_varint(pos)
            event_id_end = pos
            length, pos = self._read_varint(pos)
        elif first >= _LENGTH_PREFIX_THRESHOLD:
            event_id = first
            pos += 1
            event_id_end = pos
            length, pos = self._read_varint(pos)
        else:
            event_id = first
            pos += 1
            event_id_end = pos
            length = None
        if event_id > 4096:
            raise _FramingError(f'implausible event id {event_id}')
        if event_id >= 512 and self._num_modules <= 0:
            raise _FramingError(f'module event {event_id} before module declaration', discard=event_id_end)
        if length is not None and length > _MAX_PACKET_PAYLOAD:
            raise _FramingError(f'implausible payload length {length}')
        spec = _EVENT_SPECS.get(event_id)
        if spec is None:
            if length is None:
                raise _FramingError(f'unknown event id {event_id} without length')
            payload_bytes, pos = self._read_exact(pos, length)
            ev: dict[str, Any] = {'kind': f'raw_{event_id}', 'event_id': event_id, 'payload_hex': bytes(payload_bytes).hex()}
        else:
            kind, fields = spec
            if length is not None:
                payload_end = pos + length
                if payload_end > len(self._buf):
                    raise _NeedMore
                ev = {'kind': kind}
                ev.update(self._decode_fields(fields, pos, payload_end))
                pos = payload_end
            else:
                ev = {'kind': kind}
                field_vals, pos = self._decode_fields_need(fields, pos)
                ev.update(field_vals)
        invalid_task_info = False
        if ev.get('kind') == 'task_info':
            name = ev.get('name')
            invalid_task_info = not isinstance(name, str) or not name.strip() or len(name) > 32 or ('�' in name) or (not name.isprintable())
        delta, pos = self._read_varint(pos)
        delta &= self._ts_mask
        if invalid_task_info:
            self._dropped_packets += 1
            del self._buf[:pos]
            return None
        self._abs_time = self._abs_time + delta
        ev['delta_ticks'] = delta
        ev['t_ticks'] = self._abs_time
        self._post_process(ev)
        del self._buf[:pos]
        return None if event_id == EVTID_NOP else ev

    def _post_process(self, ev: dict) -> None:
        kind = ev['kind']
        if kind == 'systime_us':
            ev['systime'] = ev['systime_low'] | ev['systime_high'] << 32
        elif kind == 'init':
            sys_freq = ev.get('sys_freq', 0)
            self._timestamp_freq = sys_freq if sys_freq and sys_freq != ev.get('cpu_freq', 0) else 0
            if self._cpu_freq_override is None:
                self._cpu_freq = ev.get('cpu_freq', 0) or self._cpu_freq
            else:
                self._cpu_freq = self._cpu_freq_override
            self._ram_base = ev.get('ram_base', 0)
            id_shift = ev.get('id_shift')
            self._id_shift = 2 if id_shift is None else int(id_shift)
        elif kind == 'task_info':
            tid = ev.get('task_id')
            name = ev.get('name')
            if tid is not None and name:
                self._task_names[tid] = name
        elif kind == 'name_resource':
            rid = ev.get('resource_id')
            name = ev.get('name')
            if rid is not None and name:
                self._task_names.setdefault(rid, name)
        elif kind == 'sysdesc':
            desc = ev.get('desc', '') or ''
            for m in _ISR_DESC_RE.finditer(desc):
                self._isr_names[int(m.group(1))] = m.group(2)
        elif kind == 'nummodules':
            self._num_modules = max(0, int(ev.get('num_modules', 0) or 0))
        elif kind == 'task_start_exec':
            self._current_task = ev.get('task_id')
        elif kind == 'task_stop_exec':
            if self._current_task is not None:
                ev['task_id'] = self._current_task
        elif kind == 'overflow':
            self._current_task = None
        if 'task_id' in ev:
            ev['task_name'] = self._task_names.get(ev['task_id'])
        if 'isr_id' in ev:
            ev['isr_name'] = self._isr_names.get(ev['isr_id'])
        frequency = self.timestamp_freq
        if frequency:
            ev['cpu_delta_us'] = ev['delta_ticks'] * 1000000.0 / frequency
            ev['t_us'] = ev['t_ticks'] * 1000000.0 / frequency

    def _peek(self, pos: int) -> int:
        if pos >= len(self._buf):
            raise _NeedMore
        return self._buf[pos]

    def _read_varint(self, pos: int) -> tuple[int, int]:
        result = 0
        shift = 0
        while True:
            if pos >= len(self._buf):
                raise _NeedMore
            b = self._buf[pos]
            pos += 1
            result |= (b & 127) << shift
            if not b & 128:
                return (result, pos)
            shift += 7
            if shift > 35:
                raise _FramingError('varint too long')

    def _read_exact(self, pos: int, n: int) -> tuple[bytearray, int]:
        if pos + n > len(self._buf):
            raise _NeedMore
        return (self._buf[pos:pos + n], pos + n)

    def _decode_fields(self, fields, pos: int, end: int) -> dict:
        out: dict[str, Any] = {}
        for ftype, fname in fields:
            if ftype == 'str':
                val, pos = self._read_str_bounded(pos, end)
            elif ftype == 'id':
                raw, pos = self._read_varint(pos)
                val = (raw << self._id_shift) + self._ram_base
                out[fname + '_raw'] = raw
            else:
                val, pos = self._read_varint(pos)
            out[fname] = val
        return out

    def _decode_fields_need(self, fields, pos: int) -> tuple[dict, int]:
        out: dict[str, Any] = {}
        for ftype, fname in fields:
            if ftype == 'str':
                val, pos = self._read_str(pos)
            elif ftype == 'id':
                raw, pos = self._read_varint(pos)
                val = (raw << self._id_shift) + self._ram_base
                out[fname + '_raw'] = raw
            else:
                val, pos = self._read_varint(pos)
            out[fname] = val
        return (out, pos)

    def _read_str(self, pos: int) -> tuple[str, int]:
        if pos >= len(self._buf):
            raise _NeedMore
        count = self._buf[pos]
        pos += 1
        if count == 255:
            if pos + 2 > len(self._buf):
                raise _NeedMore
            length = struct.unpack_from('<H', self._buf, pos)[0]
            pos += 2
        else:
            length = count
        if pos + length > len(self._buf):
            raise _NeedMore
        s = bytes(self._buf[pos:pos + length]).decode('utf-8', errors='replace')
        return (s, pos + length)

    def _read_str_bounded(self, pos: int, end: int) -> tuple[str, int]:
        if pos >= end:
            raise _FramingError('string count out of payload bounds')
        count = self._buf[pos]
        pos += 1
        if count == 255:
            if pos + 2 > end:
                raise _FramingError('string length out of payload bounds')
            length = struct.unpack_from('<H', self._buf, pos)[0]
            pos += 2
        else:
            length = count
        if pos + length > end:
            raise _FramingError('string body out of payload bounds')
        s = bytes(self._buf[pos:pos + length]).decode('utf-8', errors='replace')
        return (s, pos + length)

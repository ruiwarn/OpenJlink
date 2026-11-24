---
name: openjlink
description: Use the OpenJlink CLI for project-independent J-Link embedded development, including connection failures, firmware that does not start, variable and peripheral inspection, RTT logs, unexpected resets, HardFaults, RTOS stalls, and protocol testing. Adapt to the current project's rules without replacing physical acceptance tests.
---

# OpenJlink

Reusable J-Link CLI for embedded targets. Supply chip, RTOS, build/test commands, image layout, ELF/SVD paths, and acceptance criteria from the current project.

## Project use

Prefer global `openjlink` (fallback: Skill `.venv` / `scripts/run.py`; see [setup](references/setup.md)). Read project rules first, establish a baseline before stimuli, and read back modified state to verify writes and cleanup.

Token-efficient usage:
- Use `--compact` on `schema`, `session`, `call`, or direct commands to omit repeated hashes, nanosecond timestamps, and boilerplate strings.
- For multi-step hardware flows, prefer one `openjlink session --state-dir <dir> --compact --batch <file|-> --stop-on-error` process over separate connect/read calls or custom Python wrappers.
- Use `read_variables` / `write_variables` for batched symbolic access, `check_heartbeat(name=...)` to track counters by symbol, `type_info` to list struct fields, `wait_job` instead of polling `job_status`, and `file.c::symbol` when statics collide across CUs.
- `write_variable` / `write_variables` accept the 12-char short `generation` prefix returned in `--compact` mode after `verify_image` unlocks `symbols_verified`.
- J-Link SDK banner logs go to `<state_dir>/jlink.log`.

## Route from problem

| Problem | Capabilities |
|---|---|
| Connect failure / missing probe / VREF | inspect_environment, discover_probes, connect, probe_info |
| Image mismatch or firmware not running | run_build, inspect_image, verify_image, check_heartbeat |
| Variables, structs, configs, buffers | load_symbols, search_symbols, type_info, read_variables, write_variables |
| Peripheral registers / bit fields | load_peripherals, list_peripherals, read_peripherals |
| Unexpected reset / HardFault | halt -> core_registers, fault_snapshot, symbolize (before reset) |
| Timed traces / before-after diff | start_job(capture), summarize_recording, compare_recordings, render_recording |
| RTT logs / RTOS / Serial / Modbus | rtt_*, gdb_inspect, decode_systemview, analyze_events, serial_exchange, modbus |

Read [scenarios](references/scenarios.md), [debugging](references/debugging.md), [capture](references/capture.md), [rtos](references/rtos.md), [protocol](references/protocol.md), or [coverage](references/coverage.md) as needed.

## Boundaries

- Always select probes by explicit `serial`. One process owns one probe; disconnect before handing off to IDE/GDB.
- `confirm=true` is required for writes, halts, resets, and programming (only within existing authorization).
- Store `state_dir`, captures, and logs in task scratch directories, never in the Skill directory.
- `start_job` acceptance is not completion: wait with `wait_job` or poll `job_status`; never replay an `unknown` job with a new `request_id`. Stop captures before exiting.
- Verify SVD read safety against vendor manuals; addresses are 32-bit and breakpoints are Thumb.

## Reporting

State target/tool versions, artifact hashes, checked scope, raw paths, and time sources. Distinguish builds, completed writes, matching readback, execution, and physical acceptance.

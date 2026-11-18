# OpenJlink

[English](README.md) | [简体中文](README.zh-CN.md)

A general-purpose J-Link CLI for embedded developers and AI assistants. OpenJlink provides memory and variable access, programming verification, RTT, fault snapshots, RTOS event analysis, peripheral register inspection, and evidence capture. Each development task supplies the project's existing build system, RTOS, test entry points, and application rules.

Use direct commands, JSON calls, or a persistent CLI session.

## Installation

Requires Python 3.10+ and a separately installed SEGGER J-Link Software Pack. This repository does not distribute official DLLs, probe firmware, chip Flash algorithms, or vendor SVD files.

With uv installed, install a user-wide command in an isolated tool environment:

```text
uv tool install "openjlink[modbus] @ git+https://github.com/ruiwarn/OpenJlink.git"
openjlink --version
openjlink --help
openjlink schema
```

If uv reports that its executable directory is missing from PATH, run `uv tool update-shell` and open a new shell. Verify `openjlink --version` from an unrelated directory without activating an environment.

For local source development, download the source and run these commands from its root directory:

```text
python scripts/setup_runtime.py
python scripts/run.py --help
```

This fallback creates an isolated `.venv` in that directory; it does not install a global command. To use OpenJlink as an AI Skill, install the repository in your skills directory and prefer the global CLI installation above. The skill entry point is [SKILL.md](SKILL.md).

## Using OpenJlink in a project

Install OpenJlink once and call the CLI from your project directory, or use the absolute path to the Skill's `scripts/run.py`. Build commands, image/ELF/SVD paths, target devices, probe serial numbers, and address ranges are supplied explicitly. Project firmware does not need to depend on OpenJlink or include a copy of its code.

```text
openjlink --state-dir .openjlink-state inspect-environment
openjlink inspect-image --path build/app.bin --base-address 0x08000000
openjlink schema start_job
openjlink call inspect_image --args @image-arguments.json
```

Replace the example image path and address with the values for your project. Place `--state-dir` before the subcommand. It holds the current task's state and job records; you choose its location. OpenJlink does not modify your project's `.gitignore` automatically.

For connected reads, RTT, or a sequence of debugging operations, keep one persistent process open:

```text
openjlink --state-dir .openjlink-state session
```

Send one JSON request per line and receive one immediate JSON response per line:

```json
{"id":1,"operation":"ping","arguments":{}}
{"id":2,"operation":"device_status","arguments":{}}
```

These two requests do not connect to a target. To connect, call `connect` with the actual `serial`, `device`, `interface`, and `speed_khz`, then continue sending operations to the same process's standard input. JSON operation names use underscores; direct commands use hyphens and named arguments. Pass complex lists and objects through JSON or `--args @file.json`.

A single command closes its own session when it finishes. Separate connect/read processes do not share a connection. Ending a session waits for submitted jobs. Request `cancel_capture` and check the terminal job state before exiting a capture session; closing the input does not cancel a Flash operation.

## Capabilities

| Development task | Operations |
|---|---|
| Diagnose connection failures, select a probe, check host dependencies | inspect-environment, discover-probes, connect, probe-info |
| Build, program, and verify firmware | run-build, inspect-image, start-job, job-status, verify-image, check-heartbeat |
| Inspect RAM, Flash, buffers, and configuration | read-memory, read-regions, dump-memory, write-memory, write-regions |
| Locate globals, structure members, and array elements | load-symbols, search-symbols, type-info, read-variable, write-variable, symbolize |
| Inspect peripheral registers and bit fields | load-peripherals, list-peripherals, read-peripherals |
| Halt, step, manage breakpoints, and capture faults | debug-control, breakpoint, core-registers, fault-snapshot |
| Capture logs, exchange binary data, and record streams | rtt-start, rtt-channels, rtt-read, rtt-write, start-job, export-rtt |
| Plot, replay, detect telemetry gaps, and compare recordings | decode-packets, summarize-recording, compare-recordings, render-recording |
| Inspect RTOS threads and execution events | gdb-server-arguments, gdb-inspect, decode-systemview, analyze-events |
| Run serial, RS485, and protocol regressions | serial-ports, serial-exchange, modbus, run-build |

Run `openjlink schema` for the complete operation list and current signatures. Additional guides cover [project setup](references/setup.md), [development scenarios](references/scenarios.md), [debugging](references/debugging.md), [capture](references/capture.md), [RTOS](references/rtos.md), and [protocols](references/protocol.md).

## Results and limitations

Writes, halts, resets, programming, and command transmission require existing caller authorization and explicit confirmation. An `accepted` job is not yet `completed`. If a result is `unknown`, query the original job instead of replaying it automatically. Check the Flash loader's actual erase geometry for the target before programming.

Memory addresses are currently 32-bit, instruction breakpoints use Thumb, and fault snapshots support the listed Cortex-M architectures. This does not establish support for every processor supported by J-Link. DWARF support covers fixed-address globals, one-dimensional arrays, and scalar values. SVD support currently covers non-cluster registers and bit fields; read safety depends on the description file and vendor documentation. SVD writes are not provided.

Capture uses one owner and bounded jobs. RTT reads consume the target buffer. Cross-process history subscriptions, a shared live backend, pre/post-trigger ring capture, a complete graphical RTOS timeline, and SWO/ETM capture are not implemented. Finding a rising edge in an offline plot is not a hardware trigger. See [coverage and remaining work](references/coverage.md) for details and priorities.

J-Link V9/V11 identify hardware generations, not complete product models. Probe models, drivers, chip loaders, RTOS instrumentation, workload, and actual throughput require separate validation. Host timestamps do not replace target sampling timestamps, VREF does not measure power, and matching readback does not establish application or physical behavior.

## Development checks

```text
python -m pip install -e ".[test,modbus]"
python -m pytest -q
ruff check scripts tests --select F,E9
```

Some ELF regressions use `arm-none-eabi-gcc` and are explicitly skipped when it is unavailable. Installation and unit tests do not automatically run hardware tests. Software regression results and real probe/target acceptance are recorded separately.

## License

OpenJlink's original code is released under MIT. See [NOTICE](NOTICE) for third-party sources, dependencies, and modification details, and [LICENSES](LICENSES) for retained third-party licenses. OpenJlink is not affiliated with or endorsed by SEGGER.

# OpenJlink

[English](README.md) | [简体中文](README.zh-CN.md)

A general-purpose J-Link CLI for embedded developers and AI assistants. OpenJlink provides memory and variable access, programming verification, RTT, fault snapshots, RTOS event analysis, peripheral register inspection, and evidence capture. Each development task supplies the project's existing build system, RTOS, test entry points, and application rules.

Use direct commands, JSON calls, or a persistent CLI session.

## Install with your AI assistant

You can share this repository as an early preview. A local coding agent with terminal, filesystem, and network access can follow the request below. A repository link alone does not execute an installation, and a chat-only assistant cannot install software on your computer.

Copy this request to your coding agent:

> Install OpenJlink v0.1.3 from https://github.com/ruiwarn/OpenJlink for my user account, including its reusable AI Skill and globally available CLI. Read this README and respect the host's installation policies.
>
> 1. Detect the operating system, CPU architecture, actual home directory, and AI host. Use that host's documented user-level Skill directory, honoring configured locations and existing installations. Common locations are listed below; do not assume every AI product uses the same directory. If the host does not support Skills, install the CLI and report that limitation. Keep project files and unrelated skills unchanged.
> 2. Reuse compatible installed tools. If uv is missing, download and inspect the official uv 0.12.16 installer linked below, then install it for this user. Reuse a suitable Python 3.10+ interpreter; otherwise install uv-managed Python 3.13.5. Keep these dependencies outside project and system Python packages, and refresh command discovery after installation.
> 3. Download the v0.1.3 wheel and source ZIP into a user download/cache directory from the release links below and verify their SHA-256 values. Stage the ZIP, then install the contents of its OpenJlink directory as the host's openjlink Skill directory, with SKILL.md directly inside it. Include agents, references, scripts, and license files. Inspect existing installations and preserve local edits before updating; avoid duplicate Skill entries.
> 4. Install the verified local wheel with the modbus extra using uv tool install, as shown below. This route does not require Git. Make the tool's executable directory available through persistent user PATH; use uv tool update-shell when needed and refresh the current process or open a fresh shell. A private virtual environment alone does not complete global installation.
> 5. Detect the separately installed official SEGGER J-Link Software Pack and record its version and architecture. Reuse a suitable installation. If hardware support needs it and it is missing, use the official SEGGER download page; stop at required license consent, administrator interaction, or policy restrictions and report that step. Do not substitute a guessed universal SDK version, change USB drivers, or access a target to demonstrate installation. CLI/Skill installation can finish with hardware setup reported pending.
> 6. From an unrelated directory and fresh shell, without environment activation, verify openjlink --version, --help, and schema. Version must be 0.1.3 and the catalog must contain 54 operations. Run inspect-environment with a writable task state directory and test ping/device_status in one session without connecting. Verify host Skill discovery; refresh or restart the host if needed, otherwise report discovery pending. Report installed paths, actual versions, checks, and any blocked step. Stop on download or installation failure instead of reporting success.

Common user-level destinations; `~` means the actual user's home directory on Windows, Linux, or macOS:

| AI host | Skill destination |
|---|---|
| Codex | `~/.agents/skills/openjlink/` |
| Claude Code | `~/.claude/skills/openjlink/` |
| Gemini CLI | `~/.agents/skills/openjlink/` or its native `~/.gemini/skills/openjlink/`; use one recognized location |
| Other hosts | Resolve their documented user-level Skill directory before installing |

Pinned release assets:

| Asset | SHA-256 |
|---|---|
| [CLI wheel](https://github.com/ruiwarn/OpenJlink/releases/download/v0.1.3/openjlink-0.1.3-py3-none-any.whl) | `0472ad96e624ae4a6c9901a0366cbb51bb2f2775f015449e7c0f26933c610aa8` |
| [Skill/source ZIP](https://github.com/ruiwarn/OpenJlink/releases/download/v0.1.3/OpenJlink_0.1.3.zip) | `cded53809ec06b34f89807d6e7a4912b5bb68e692864cbb51848535f7f4cc2f9` |

Run this baseline from the download/cache directory containing the verified wheel. Install Python only when needed; if reusing an existing interpreter, supply its actual path to `--python` instead:

```text
uv python install 3.13.5
uv tool install --upgrade --python 3.13.5 "./openjlink-0.1.3-py3-none-any.whl[modbus]"
uv tool update-shell
openjlink --version
openjlink --help
openjlink schema
```

Official references: [uv installation](https://docs.astral.sh/uv/getting-started/installation/), pinned uv 0.12.16 installers for [Windows](https://astral.sh/uv/0.12.16/install.ps1) and [Linux/macOS](https://astral.sh/uv/0.12.16/install.sh), [managed Python](https://docs.astral.sh/uv/guides/install-python/), [SEGGER downloads](https://www.segger.com/downloads/jlink/), and Skill discovery for [Codex](https://developers.openai.com/codex/skills/), [Claude Code](https://code.claude.com/docs/en/skills), and [Gemini CLI](https://geminicli.com/docs/cli/skills/). These paths describe local hosts; remote agents install into their own execution environment unless explicitly connected to your machine.

## Installation

Requires Python 3.10+ and a separately installed SEGGER J-Link Software Pack. This repository does not distribute official DLLs, probe firmware, chip Flash algorithms, or vendor SVD files.

With uv installed, install a user-wide command in an isolated tool environment:

```text
uv tool install --upgrade "openjlink[modbus] @ git+https://github.com/ruiwarn/OpenJlink.git@v0.1.3"
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

These two requests do not connect to a target. To connect, call `connect` with the actual `serial`, `device`, `interface`, and `speed_khz`, then continue sending operations to the same process's standard input. Pass `--compact` to omit repeated boilerplate/hashes, or `--batch <file|-> --stop-on-error` to run a JSON array or JSONL batch and exit. JSON operation names use underscores; direct commands use hyphens and named arguments. Pass complex lists and objects through JSON or `--args @file.json`.

A single command closes its own session when it finishes. Separate connect/read processes do not share a connection. Ending a session waits for submitted jobs. Request `cancel_capture` and check the terminal job state before exiting a capture session; closing the input does not cancel a Flash operation.

## Capabilities

| Development task | Operations |
|---|---|
| Diagnose connection failures, select a probe, check host dependencies | inspect-environment, discover-probes, connect, probe-info |
| Build, program, and verify firmware | run-build, inspect-image, start-job, job-status, wait-job, verify-image, check-heartbeat |
| Inspect RAM, Flash, buffers, and configuration | read-memory, read-regions, dump-memory, write-memory, write-regions |
| Locate globals, structure members, and array elements | load-symbols, search-symbols, type-info, read-variable, read-variables, write-variable, write-variables, symbolize |
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

# CLI installation and project use

Requires Python 3.10+ and a separately installed SEGGER J-Link Software Pack. Project firmware does not need a build dependency on OpenJlink.

## Install once, use across projects

Install a persistent user-wide command with uv. Its tool environment keeps dependencies separate from project and system Python packages:

```text
uv tool install "openjlink[modbus] @ git+https://github.com/ruiwarn/OpenJlink.git"
openjlink --version
openjlink --help
```

If uv reports that its executable directory is missing from PATH, run `uv tool update-shell` and open a new shell. Verify command discovery and execution from a directory unrelated to the source or Skill, without environment activation. Do not report global installation complete when only an absolute Skill path or a private `.venv` works. Do not replace an unrelated command with the same name without checking its owner.

For a source-development fallback, `python scripts/setup_runtime.py` creates the Skill's private `.venv`, and `python <absolute-OpenJlink-directory>/scripts/run.py ...` uses it. This fallback does not install a global command. Skill locations can differ across Windows, Linux, and macOS; resolve this fallback from the actual installation directory rather than hardcoding one machine's path. Stop on installation failure instead of modifying system Python packages.

An AI task can read the current project's rules, use OpenJlink through its CLI, verify the actual build and target information, then perform the requested observation and save data in the task directory. No per-project Skill installation is required.

## Three command forms

```text
openjlink --version
openjlink schema
openjlink read-memory --help
openjlink inspect-image --path build/app.bin --base-address 0x08000000
openjlink call inspect_image --args @arguments.json
openjlink --state-dir .openjlink-state session
```

Direct commands use hyphens; JSON operation names use underscores. Integers accept the `0x` prefix. Lists and objects use JSON. Quote paths containing spaces for the current shell; prefer UTF-8 JSON files for complex arguments. Place the state directory option before the subcommand.

## Persistent hardware sessions

One process accepts one request per line and immediately returns one JSON response per line. The caller writes stdin and reads stdout incrementally. ping and device_status do not connect to a target:

```json
{"id":1,"operation":"ping","arguments":{}}
{"id":2,"operation":"device_status","arguments":{}}
```

For development, continue sending connect, load_symbols, read_variable, and other operations to that same process. connect requires the real serial/device/interface/speed_khz; do not copy a fictional device. A standalone call closes its own session, so a later process cannot use the previous connection.

A finite batch can supply newline JSON through a file or pipe. Interactive AI use keeps both input and output pipes open. Output is flushed immediately and does not require closing stdin. Protocol and hardware errors return ok=false. A failed single call exits nonzero; a session continues accepting requests, so callers must inspect ok for every response.

Closing input ends the session and waits for submitted jobs. Query their terminal state first. Capture can request cancel_capture; closing a process cannot undo hardware writes. Long-job status persists in state_dir. Only one tool process may own that directory at a time; changing directories does not bypass the probe lock.

## Local information and adaptation

Read build/test entry points, chip details, image layout, preserved regions, SVD, and RTOS information for the task. Reuse existing programmers and test scripts when they meet the need. Use OpenJlink for consistent results, symbols, capture, or evidence. Keep concrete variables and protocol acceptance criteria in the project.

schema, inspect_image, and loading symbols or peripheral descriptions do not connect to a target. Initial installation does not automatically enumerate or connect to hardware, program, halt, reset, or replace a USB driver merely to demonstrate success.

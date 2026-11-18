---
name: openjlink
description: Use the OpenJlink CLI for project-independent J-Link embedded development, including connection failures, firmware that does not start, variable and peripheral inspection, RTT logs, unexpected resets, HardFaults, RTOS stalls, and protocol testing. Adapt to the current project's rules without replacing physical acceptance tests.
---

# OpenJlink

Provide reusable CLI tools and debugging methods. Obtain the chip, RTOS, build entry points, image layout, variables, units, and acceptance criteria from the current project and task; do not store them as defaults in this Skill.

## Project use

Use the globally installed `openjlink` command. If it is missing, follow the user-wide installation in [setup.md](references/setup.md), then verify it from an unrelated directory and a fresh shell without activating an environment. A Skill-local `.venv` or `scripts/run.py` alone does not complete global installation. Keep runtime dependencies isolated from project and system Python packages. Projects do not need to copy the tool, change their build system, or connect to another service.

Read the project's rules first and reuse its existing build, programming, and test entry points. Identify the exact target, probe serial number, image/ELF/SVD sources, and actions permitted to affect the target. Ask only for information needed by the current task that is still missing.

Establish the required baseline before applying test stimuli. If it fails, preserve the observations and mark dependent scenarios blocked until the cause is resolved. Define what each observed variable proves; an internal counter does not independently establish a physical output. Verify changed settings and cleanup by reading back the required state.

Use `schema` and each subcommand's `--help` as the parameter authority. Direct commands use hyphens; JSON operation names use underscores. Offline checks can run independently. Connected multi-step operations require one persistent `session` process; separate connect/read processes do not share a connection.

## Route from the problem

| User problem | Initial capabilities |
|---|---|
| Connection failure, missing probe, or unexpected target voltage | inspect_environment, discover_probes, connect, probe_info; verify wiring and the exact target without automatically unlocking or switching power |
| Programming succeeded but firmware does not run, or the wrong image may be loaded | run_build, inspect_image, verify_image, check_heartbeat; distinguish building, readback, and execution |
| Incorrect variables, configuration, or buffers | load_symbols, type_info, read_variable/read_regions; verify ELF matching and access side effects first |
| Incorrect peripheral register or status bit | load_peripherals, list_peripherals, read_peripherals; check the SVD device/revision against its manual |
| Unexpected reset, HardFault, or invalid execution | Preserve fault state first, then use core_registers, fault_snapshot, and symbolize; avoid resetting before capture |
| Out-of-range values or differences before and after a change | Bounded capture, summarize_recording, compare_recordings, render_recording |
| Lost RTT logs or unresponsive commands | rtt_channels, rtt_read/write, raw-byte capture; submitted bytes do not establish application acknowledgement |
| RTOS stalls, tasks not running, or long ISRs | gdb_inspect or SystemView events; collect thread snapshots and execution timelines separately |
| Partial serial frames, timeouts, or unresponsive devices | serial_exchange, modbus, existing protocol testers; preserve TX/RX and do not blindly replay writes |
| Fast or synchronized multi-variable observation | Evaluate target timestamps, sequence numbers, and packets formed at one sampling point; host polling is not synchronized sampling |

Read [scenario workflows](references/scenarios.md), [debugging](references/debugging.md), [capture](references/capture.md), [RTOS](references/rtos.md), or [protocols](references/protocol.md) as needed. For advanced operations that are not provided, consult [coverage](references/coverage.md) before choosing a path; do not invent commands.

## Execution boundaries

- Select a probe by its explicit serial number. V9/V11 identify hardware generations. A target name selects a configuration and does not independently prove chip markings, revision, or wiring. Connection scripts may affect execution.
- Pass confirm for memory writes, commands, halts, resets, and programming only within existing user authorization and scope. Do not ask again for authorization already given. The tool does not provide read-protection unlocking, OTP, or programmable power.
- One process owns one probe. Hand ownership over explicitly between this tool and IDE/GDB. During capture, query status or request capture cancellation instead of issuing concurrent hardware operations. Locks do not establish that third-party tools have released the probe.
- Store state_dir, raw data, and build logs in task-selected directories, not the installation directory. Ending a session closes its connection and waits for existing jobs; it does not cancel or roll back their effects. Stop capture before exiting.
- An accepted start_job is not completion. Query the original job_id. An unknown result may already have affected hardware; do not replay it with another ID. Native Flash calls cannot be safely force-cancelled.
- Memory/MMIO reads may have side effects. Verify SVD safety declarations against the exact manual. This version does not write SVD fields. Addresses are 32-bit and instruction breakpoints use Thumb; confirm support before using other architectures.

## Reporting

Record target/tool versions, artifact hashes, operation scope, actual checks, raw files, and time sources. Distinguish successful builds, completed writes, matching readback, firmware execution, application tests, and physical results. RTT loss is unknown without target counters. Do not diagnose deadlock or priority inversion without ready/blocked states and lock-relationship evidence.

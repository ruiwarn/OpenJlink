# Development coverage and remaining work

2026-11-17. OpenJlink provides a generic CLI and Skill. Command counts do not measure competitor coverage. Basic debugging, recording, analysis, and SVD inspection are implemented; the original hardware and scenario acceptance requirements remain incomplete.

## Comparison with public competitor sources

The baseline is MKLink AI Probe v0.3.6, commit d000370b901a72e4f8ec8fe09cf8b837f2579f0c. Its default registration contains 46 tools, and generic calls can route to 105 shared sub-capabilities. These counts are not directly comparable with OpenJlink's flat operation list.

| Capability | Competitor source evidence | Current OpenJlink coverage | Follow-up value |
|---|---|---|---|
| Single owner and asynchronous jobs | runtime_capabilities.py, runtime_mcp.py | Probe/state locks, job deduplication, and unknown results; no shared service | P0: retain reliable jobs; add a shared backend for demonstrated long-capture needs |
| RTT channel history/cursors | remote/dashboards.py read_channel, remote/api.py rtt_history | Raw I/O and finite recording; reads consume bytes; no multi-consumer cursor | P0/P1: useful for continuous diagnosis; CLI use does not prevent adding a backend |
| Peripheral/bit-field semantics | peripheral_watch.py, remote/api.py peripheral_select | Explicit SVD loading, catalog, bit-field reads, and capture; declared side effects rejected; no clusters or field writes | P1: validate read safety, inheritance, arrays, and clusters against target examples |
| Fault capture and interpretation | remote/api.py fault_snapshot, hardfault-detail | Architecture selection, fault status, explicit basic frames, and source lines; automatic EXC_RETURN/extended-frame reasoning and semantic reporting remain limited | P0: improve evidence and architecture adaptation, then validate known fault firmware |
| Variable plots and triggering | static/rtt_viewer.js preTriggerBuffer, postTriggerRemaining | Offline plots, replay, and edge search; no acquisition trigger, pre/post-trigger ring, or formula channels | P1: capture windows for intermittent failures offer more value than extra menus |
| Throughput measurement and fast sampling | dump_memory.py, runtime_mcp.py measure_dump_memory | Actual poll intervals and counts; no dedicated throughput matrix or target baseline | P1: measure Hz, byte count, P99, loss, and disturbance before claiming speed |
| RTOS timelines and statistics | systemview_analyzer.py task_intervals/analyze_events | Event decoding and exclusive nested-ISR accounting; no task timeline, switch/ready/blocked latency statistics, or complete report | P1: accept event sources and clocks before extending offline analysis |
| Long-running serial logs and scripted sequences | remote/api.py serial_sequence_start, serial_recording_start, modbus_loop_start | Single serial/Modbus exchanges and existing test entry points; no generic continuous serial recorder/sequence executor | P1: reuse project testers first and avoid duplicate protocol criteria |
| Multiple images and startup validation | v0.3.6 release notes and programming implementation | Single-image ranges, snapshots, readback, and preserved-region checks; AI still coordinates complete partition preflight and runtime assertions | P0/P1: make Boot/APP/parameter ranges and artifact relationships reviewable first |
| GUI, remote access, power, OTP, and standalone production | Published routes and release notes | Outside the current CLI development core; no empty implementation claims | P2: expand only for actual development needs with suitable hardware |

Evidence: [release](https://github.com/Aladdin-Wang/Mklink-AI-Probe/releases/tag/v0.3.6), [capability routing](https://github.com/Aladdin-Wang/Mklink-AI-Probe/blob/d000370b901a72e4f8ec8fe09cf8b837f2579f0c/Mklink-AI-Probe/mklink/runtime_capabilities.py), [RTT cursors](https://github.com/Aladdin-Wang/Mklink-AI-Probe/blob/d000370b901a72e4f8ec8fe09cf8b837f2579f0c/Mklink-AI-Probe/mklink/remote/dashboards.py#L720), [peripheral descriptions](https://github.com/Aladdin-Wang/Mklink-AI-Probe/blob/d000370b901a72e4f8ec8fe09cf8b837f2579f0c/Mklink-AI-Probe/mklink/peripheral_watch.py), [trigger buffers](https://github.com/Aladdin-Wang/Mklink-AI-Probe/blob/d000370b901a72e4f8ec8fe09cf8b837f2579f0c/Mklink-AI-Probe/mklink/static/rtt_viewer.js#L3210), [RTOS analysis](https://github.com/Aladdin-Wang/Mklink-AI-Probe/blob/d000370b901a72e4f8ec8fe09cf8b837f2579f0c/Mklink-AI-Probe/mklink/systemview_analyzer.py). These are static source findings, not evidence that we operated competitor hardware.

## Other useful operations

Further generic development needs include data watchpoints/conditional breakpoints, individual core-register writes, source-level stepping/locals, SWO/ITM/DWT, range erase, target-capability preflight, capture triggers, recording crop/export, and a common experiment manifest. Not all are confirmed competitor features. Reuse mature debuggers or libraries; OpenJlink supplies scenario coordination, validation, and evidence rather than another transport implementation. State explicitly when no dedicated CLI command exists.

## Review of the original requirements

"Software foundation" means an implementation path and local regressions exist; it does not mean the complete requirement or a reference board has passed acceptance.

| Requirement | Status and remaining work |
|---|---|
| R01 Target identity | Partial: explicit selection and identity queries; full SDK/target capabilities, wrong-target blocking, and unplug/replug matrices remain limited |
| R02 Shared sessions | Partial: exclusive ownership and busy responses; no client-exit/acquisition separation or shared subscriptions |
| R03 Build artifacts | Software foundation: explicit entry points, logs, and hashes; actual project workflow acceptance remains |
| R04 Symbol matching | Software foundation: fixed-address DWARF, generation, and ELF readback guards; other toolchains/optimized forms need adaptation |
| R05 Programming and execution | Partial: single-image readback, preserved regions, and heartbeat are separate; no automatic application acceptance or multi-image plan |
| R06 RTT | Partial: bounded byte I/O/recording; no history cursors or board-level restart/slow-consumer matrix |
| R07 Snapshots/writes | Partial: range/type/short-read/old-value/readback checks; ordinary memory writes have no session-level region allowlist; SVD access is controlled read only |
| R08 Evidence | Partial: file manifests, hashes, and timing; no common experiment linkage or complete failure matrix such as disk-full cases |
| R09 Faults | Partial: basic frames, status, and source lines; extended/secure frames and reference fault-firmware acceptance remain |
| R10 Execution control | Partial: Thumb instruction breakpoints and core control; resource limits, advanced breakpoints/GDB workflows, and uncertain-state handling need work |
| R11 Job states | Software foundation: deduplication and persisted terminal/unknown states; hardware disconnection and process-interruption acceptance remain |
| R12 Plot replay | Partial: offline plots exist; reference-board sampling performance and long runs are untested |
| R13 Synchronized sampling | Partial: packet decoding, sequence, and timestamp wraps; guide and validate target-side sampling within each project |
| R14 Protocols | Partial: serial and Modbus basics; custom protocols, partial frames, and actual device matrices remain |
| R15 Control/protection | Method guidance: application criteria and physical evidence belong to concrete development tasks, not generic tool defaults |
| R16 Bare-metal scheduling | Partial: generic event statistics; period, execution-slice, and jitter analysis need work |
| R17 Display | Partial: offline zoom/cursor/replay; no shared live view or capture trigger |
| R18 RTOS | Partial: GDB inspection and event foundations; reference RTOS projects, timelines, and wait-relationship analysis remain incomplete |
| R19 Physical instruments | Expand on demand; physical measurement acceptance has not been performed |
| R20 Environment expansion | CI targets Windows/Linux; use actual workflow results; remote and production workflows are outside this version |

Next P0 work should establish build -> program -> readback -> execution -> logging with one identified probe and known target, then address continuous logs, capability preflight, and common evidence for real failures. P1 candidates are SVD extensions, triggering, and RTOS timelines. P2 platform and specialized-hardware features do not block the generic development CLI.

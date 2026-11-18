# From development problems to observations

Use this table to discover suitable capabilities, not as a list of mandatory actions. Choose the smallest observation that addresses the problem and preserve the project's existing entry points and constraints.

For controlled experiments, check baseline state, competing causes, stimulus acknowledgement, and recovery before interpreting changes. Record the observed symbol/address and its relationship to the intended application or physical result. If a baseline or required setting cannot be verified, mark dependent assertions blocked. Periodic sparse polling can miss transitions or repeatedly sample the same phase; choose an observation window and sampling method from the project's timing requirements. Read back restored settings and final state even when the test fails.

| Scenario | Suggested workflow | Required inputs and inference limits |
|---|---|---|
| Bring up a new project | Project rules -> inspect_environment -> confirm target/artifacts -> connect only when needed | Do not require a common build system or default to the first probe |
| Intermittent connection failure | Save tool/firmware/serial details, interface speed, VREF, and raw errors; check wiring and ownership | Do not automatically blame the probe, replace drivers, or reset |
| Avoid programming stale output after a failed build | run_build saves exit code/log -> only successful artifacts proceed to inspect_image/programming | Modification time alone does not establish artifact identity; do not program after failure |
| Firmware does not start after programming | Check image/ELF/ranges -> program and read back -> use the project's start procedure -> known heartbeat/startup logs/protocol | Assess readback and execution separately; reset is not the default |
| Preserve parameters or a filesystem | Analyze image and preserved ranges against erase geometry -> compare before/after reads | Comparison detects changes already made; it cannot prevent an incorrect loader from erasing data |
| Unexpected variable or structure state | Matching ELF -> search_symbols/type_info -> read members/arrays -> bounded capture if needed | Do not guess optimized or dynamic locations; verify_image before symbolic writes |
| Unexpected UART/ADC/DMA/timer state | Load the exact SVD -> list registers/fields -> verify the manual -> read_peripherals | Reject declared readAction and write-only access; an SVD does not prove revision matching or authorize polling unfamiliar MMIO |
| Intermittent out-of-range value or state transition | Define signals/units/timing needs -> bounded capture -> plots/differences -> narrow the window | Offline edge search is not a capture trigger; trigger ring capture is not implemented |
| Reset, HardFault, or invalid execution | Preserve fault state/reset cause -> confirm halting is allowed -> fault_snapshot -> PC/LR/source lines | Derive the basic frame address from EXC_RETURN/architecture; do not reset before capturing evidence |
| RTOS stalls or high load | Use thread snapshots for current state and event tracing for execution; account for tasks and ISRs separately | Configure missing RTOS plugins/hooks before claiming a timeline |
| Suspected deadlock or priority inversion | Collect stacks, wait objects, lock owners, priorities, ready/blocked states, and switches | A long absence of execution is insufficient; current automatic analysis does not cover complete wait relationships |
| Long ISR or period jitter | Use target-clock events; check nesting and loss; compare against observation-disabled behavior | Host RTT arrival time is not ISR execution time; do not assume every core has DWT |
| No application response to RTT input | Check actual channels -> bounded transmission -> application ACK/status read | Do not replay partial writes; current reads consume the buffer and have no history-cursor backend |
| Partial serial frame, bad checksum, or reboot | Preserve raw TX/RX -> use existing frame parser/protocol tests -> align with reset/log evidence | Received bytes do not prove a correlated response; inspect state before retrying a timed-out write |
| Compare a change against its baseline | Fix load/stimulus/capture conditions -> save two raw recordings -> compare_recordings and project tests | Mean differences do not establish causation; physical/electrical results need independent instruments |
| Fast synchronized multi-signal capture | Evaluate signal bandwidth -> form packets at one sampling point with target sequence/time -> RTT -> decode_packets | Develop target sampling in the concrete project; do not promise competitor throughput from host polling |

For watchpoints, conditional breakpoints, source-level step/next, locals, or complex stack contexts, use correctly configured GDB/IDE with explicit ownership handoff. The current gdb_inspect CLI provides only thread, backtrace, and register actions; do not invent more action values.

# RTOS and SystemView

Configure and validate thread-aware debugging and execution-event tracing separately. Bare-metal firmware can also record interrupts and user events; adopting an RTOS is not required by this tool.

## Threads and backtraces

Confirm the J-Link Software Pack version, exact target, and RTOS. FreeRTOS/embOS have official GDB Server plugin paths. Verify an actual plugin for RT-Thread and other systems; SystemView support does not establish thread-plugin support.

`gdb_server_arguments(serial,device,...,rtos_plugin)` generates official server arguments without accessing hardware. After explicitly handing ownership over from SDK/IDE, launch that exact argument list through host process tools and record the process/log. Supply a real plugin path. Without the required plugin, do not claim to enumerate all RTOS threads.

`gdb_inspect(elf,action,host,port,gdb,confirm)` connects to a configured loopback GDB Server. action is threads/backtrace/registers. User initialization and ELF auto-load scripts are disabled; raw stdout/stderr/exit code are returned. Connecting, halting, and detaching may alter execution. Use it within authorization and do not attach concurrently with this tool's SDK connection.

Thread lists, current states, and stack depth do not constitute an execution timeline. Preserve backtrace errors: optimization, missing CFI, stack corruption, and incorrect context can all affect unwinding.

## SystemView events

If the project already has SystemView, verify the target/RTOS/version, time source, RTT channel, buffer mode, and symbols. Otherwise, guide integration of the official target module and matching OS hooks within the specific development task's authorization; do not modify arbitrary projects automatically.

For FreeRTOS, check trace macros for its version, SEGGER_SYSVIEW_Config_FreeRTOS.c, timestamp implementation, and interrupt-locking method. Preserve existing trace macros and do not assume Cortex-M0 has DWT. For RT-Thread, verify scheduler/thread/ISR hooks and the OS version while preserving existing hook chains. Follow official or existing ports for Zephyr, ThreadX, embOS, and others; one hook set is not interchangeable across all systems.

The target must generate events before the corresponding RTT channel can be captured, exported with export_rtt, and decoded with decode_systemview. A supplied tick_hz must describe the project's actual event clock, not an assumed CPU nominal frequency. Decoder provenance and scope are in [sources.md](sources.md); validation does not cover all recent SystemView/board combinations.

`analyze_events` accepts decoded kind/t_us events, or t_ticks with an explicit frequency. It accounts for exclusive task and nested-ISR time, reports unknown intervals separately, and marks overflow as incomplete. Its window spans only the first through last event, without extrapolating unfinished trailing activity. A maximum observed interval is not a complete task response latency.

Validate using known periodic tasks, a long ISR, nested ISRs, blocking/wakeup, idle periods, event overflow, timestamp wrap, and target restart. Without ready/blocked, wait-object, or lock-owner evidence, a long absence of execution does not establish deadlock or priority inversion.

Official references:

- https://kb.segger.com/J-Link_GDB_Server
- https://www.segger.com/products/development-tools/systemview/technology/supported-rtos/
- https://www.segger.com/products/development-tools/systemview/license/conditions-activation/

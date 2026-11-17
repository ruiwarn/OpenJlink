# RTOS 与 SystemView

线程感知调试和运行事件跟踪分别配置、分别验收。裸机也能记录中断/用户事件，不需要为了本工具换成 RTOS。

## 线程与调用栈

先确认 J-Link Software Pack 版本、精确目标和 RTOS。FreeRTOS/embOS 有官方 GDB Server 插件路径；RT-Thread 等必须检查真实插件，不能由“支持 SystemView”推断“有线程插件”。

`gdb_server_arguments(serial,device,...,rtos_plugin)` 生成官方服务器参数，不启动硬件。由 AI 在明确交接 SDK/IDE 所有权后，使用终端工具启动该参数列表，记录进程和日志。插件传真实文件路径；未提供插件时不得声称能列出所有 RTOS 线程。

`gdb_inspect(elf,action,host,port,gdb,confirm)` 连接已配置的回环 GDB Server，action 为 threads/backtrace/registers。它禁用用户 GDB 初始化和 ELF 自动加载脚本，返回原始 stdout/stderr/退出码。连接、暂停和 detach 可能改变执行状态；确认允许后使用，不与本工具 SDK 连接并用。

线程列表、当前状态和栈深不是运行时间线；栈回溯失败时保留原始原因，优化、缺 CFI、栈破坏或错误上下文都可能影响结果。

## SystemView 事件

工程已有 SystemView 时先核对目标/RTOS/版本、时间源、RTT 通道、缓冲模式和 symbols。没有时，AI 在具体开发授权中指导集成官方 target module 和对应 OS hooks，不默认修改任何工程。

FreeRTOS 核对对应版本的 trace 宏、SEGGER_SYSVIEW_Config_FreeRTOS.c、时间戳实现和中断锁定方式；不要覆盖已有 trace 宏或假定 Cortex-M0 有 DWT。RT-Thread 核对调度/线程/ISR hooks，保留工程已有 hook 链，并检查 OS 版本。Zephyr、ThreadX、embOS 等按其官方/已有移植说明适配，不能把一套钩子直接用于所有系统。

目标先产生事件，然后通过 RTT 采集对应通道、export_rtt，再 decode_systemview。传入 tick_hz 时须来自工程真实事件时钟，不能拿 CPU 标称频率代替定时器频率。解码器来源及适用边界在 sources.md，尚未与所有新版本 SystemView 实板组合验收。

`analyze_events` 接受已解码的 kind/t_us 或 t_ticks 事件，统计任务和嵌套 ISR 的独占时间；未知区间单列，溢出会将完整性标为不通过。窗口仅覆盖首末事件，不推算末尾未完成片段。最大观察区间不是完整任务响应时延。

先用已知周期任务、长 ISR、嵌套 ISR、阻塞/唤醒、空闲、事件溢出、时间戳回绕和目标重启验证。缺少 ready/blocked、等待对象或锁持有者证据时，不能把“很久没运行”直接诊断为死锁或优先级反转。

官方依据：

- https://kb.segger.com/J-Link_GDB_Server
- https://www.segger.com/products/development-tools/systemview/technology/supported-rtos/
- https://www.segger.com/products/development-tools/systemview/license/conditions-activation/

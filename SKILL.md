---
name: openjlink
description: 使用 OpenJlink CLI 进行通用 J-Link 嵌入式开发。适用于连接失败、烧录后不运行、变量/外设观测、RTT 日志、偶发复位、HardFault、RTOS 卡顿和协议联动；根据当前工程规则适配，不绑定工程或替代物理验收。
---

# OpenJlink

提供通用 CLI 和调试方法。芯片、RTOS、构建入口、镜像布局、变量、单位与通过条件从当前工程和任务获取，不固化到本 Skill。

## 工程使用

在本 Skill 根目录执行一次 `python scripts/setup_runtime.py`，以后通过本目录 `scripts/run.py` 的绝对路径调用；已有安装也可用 `openjlink` 命令。不要求工程安装 Python 依赖、复制工具、修改构建系统或接入额外服务。具体命令、JSON 与持久会话见 [setup.md](references/setup.md)。

先读工程规则，复用其已有构建、下载和测试入口。明确目标型号、探针序列号、镜像/ELF/SVD 来源，以及本次允许影响目标的动作；只询问当前任务还缺的必要信息，不一次要求所有配置。

`schema` 和各子命令 `--help` 是实际参数依据。直接命令使用连字符，JSON 操作名使用下划线。离线检查可单独执行；连接后多步操作使用同一个 `session` 进程，不能连续启动独立 connect/read 命令冒充共享连接。

## 从问题选择场景

| 用户的问题 | 先使用的能力 |
|---|---|
| 连不上、找不到探针、目标电压异常 | inspect_environment、discover_probes、connect、probe_info；核对接线/精确目标，不自动解锁或切电 |
| 烧录成功却没运行、可能下载错程序 | run_build、inspect_image、verify_image、check_heartbeat；区分构建、回读和运行 |
| 变量不对、想看配置和缓冲 | load_symbols、type_info、read_variable/read_regions；先确认 ELF 匹配和访问副作用 |
| 某个寄存器/状态位不对 | load_peripherals、list_peripherals、read_peripherals；核对 SVD 型号/修订与手册 |
| 偶发复位、HardFault、跑飞 | 先保留现场，再用 core_registers、fault_snapshot、symbolize；不要先复位 |
| 变量何时越界、改动前后有何差异 | 有界采集、summarize_recording、compare_recordings、render_recording |
| RTT 丢日志、命令没反应 | rtt_channels、rtt_read/write、采集原始字节；发送完成不代表应用确认 |
| RTOS 卡顿、任务不运行、ISR 太长 | gdb_inspect 或 SystemView 事件；线程快照与运行时间线分别取证 |
| 串口半帧、超时、设备不响应 | serial_exchange、modbus、已有协议测试器；保留 TX/RX，不盲重发写命令 |
| 高速或同步多变量观测 | 优先评估目标时间戳、序号和同点成包；不把主机轮询称为同步采样 |

按需读 [场景流程](references/scenarios.md)、[调试](references/debugging.md)、[采集](references/capture.md)、[RTOS](references/rtos.md)、[协议](references/protocol.md)。涉及未提供的高级操作时，先查 [能力差距](references/coverage.md)，不要编造命令。

## 执行边界

- 用明确序列号选择探针；V9/V11 仅是硬件代际。目标名称是选择配置，不能独立证明芯片丝印、修订或真实接线。连接脚本可能影响运行。
- 写内存、发送命令、暂停、复位和烧录在用户已有授权与范围内才传 confirm；已有授权不重复询问。工具不提供读保护解锁、OTP 或可编程供电。
- 一个进程拥有一只探针；与 IDE/GDB 明确交接。采集任务期间只能查状态或请求停止采集，不并行发硬件操作；锁不替代第三方工具的占用判断。
- state_dir、原始数据和构建日志放在任务指定目录，不放安装目录。退出会话会关闭自身连接并等待已有任务，不等于取消或回滚；先停止采集再退出。
- start_job 的 accepted 不是完成。查询原 job_id；unknown 表示动作可能已生效，不换 ID 重放。原生 Flash 调用不能安全强制中止。
- 内存/MMIO 读取可能有副作用。SVD 的安全声明还需对照准确手册；本版本不写 SVD 字段。地址为 32 位，指令断点按 Thumb；其他架构先确认支持范围。

## 报告

记录目标/工具版本、产物摘要、操作范围、实际检查、原始文件和时间来源。分开构建通过、写入完成、回读一致、程序运行、业务测试与物理结果。没有目标计数器时，RTT 丢失为未知；没有 ready/blocked/锁关系证据时，不确诊死锁或优先级反转。

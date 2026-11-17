# OpenJlink

面向嵌入式开发者和 AI 的通用 J-Link CLI。提供内存与变量、烧录校验、RTT、故障现场、RTOS 事件、外设寄存器和证据分析能力。工程已有的构建系统、RTOS、测试入口和业务规则由开发任务决定。

只需要 CLI。提供直接命令、JSON 调用和持久会话，不需要额外的工具协议服务。

## 安装

要求 Python 3.10+，以及用户自行安装的 SEGGER J-Link Software Pack。本仓库不包含官方 DLL、探针固件、芯片 Flash 算法或厂商 SVD 文件。

```text
python -m pip install "openjlink[modbus] @ git+https://github.com/ruiwarn/OpenJlink.git"
openjlink --version
openjlink --help
openjlink schema
```

也可下载源码后，在根目录执行：

```text
python scripts/setup_runtime.py
python scripts/run.py --help
```

后者使用本目录自己的 `.venv`。作为 AI Skill 使用时，将本仓库安装到技能目录并执行相同初始化；入口是 [SKILL.md](SKILL.md)。

## 工程中使用

不需要把工具代码复制进每个工程。在工程目录调用全局 CLI，或使用 Skill 中 `scripts/run.py` 的绝对路径。构建命令、镜像/ELF/SVD、目标型号、序列号和地址范围均显式传入。

```text
openjlink --state-dir .openjlink-state inspect-environment
openjlink inspect-image --path build/app.bin --base-address 0x08000000
openjlink schema start_job
openjlink call inspect_image --args @image-arguments.json
```

示例镜像路径和地址须换成当前工程实际值。`--state-dir` 位于子命令前，用于本次任务的状态与任务记录；是否放入工程目录由调用者决定，不默认修改 `.gitignore`。

需要连接后读取、RTT 或连续调试时，使用同一个持久进程：

```text
openjlink --state-dir .openjlink-state session
```

输入每行一个 JSON 请求，输出每行一个即时响应：

```json
{"id":1,"operation":"ping","arguments":{}}
{"id":2,"operation":"device_status","arguments":{}}
```

这两条不连接目标。实际连接使用 `connect`，提供真实 `serial`、`device`、`interface`、`speed_khz`；后续操作继续写入该进程的标准输入。JSON 模式使用下划线操作名，直接命令使用连字符和命名参数。复杂列表/对象通过 JSON 或 `--args @file.json` 传入。

单次命令执行完会关闭自身会话。不能将独立的 connect/read 命令当作同一连接。会话结束会等待已提交任务；采集应先请求 `cancel_capture` 并查询任务终态，不能靠关闭输入取消 Flash 操作。

## 能做什么

| 开发场景 | 操作 |
|---|---|
| 连不上、选错探针、缺主机依赖 | inspect-environment、discover-probes、connect、probe-info |
| 编译后下载并核对程序 | run-build、inspect-image、start-job、job-status、verify-image、check-heartbeat |
| 查看 RAM、Flash、缓冲和配置 | read-memory、read-regions、dump-memory、write-memory、write-regions |
| 按全局变量、结构体成员或数组定位 | load-symbols、search-symbols、type-info、read-variable、write-variable、symbolize |
| 查看外设寄存器和位域 | load-peripherals、list-peripherals、read-peripherals |
| 暂停、单步、断点、故障取证 | debug-control、breakpoint、core-registers、fault-snapshot |
| 日志、二进制交互和连续记录 | rtt-start、rtt-channels、rtt-read、rtt-write、start-job、export-rtt |
| 曲线、回放、遥测缺口、前后对比 | decode-packets、summarize-recording、compare-recordings、render-recording |
| RTOS 线程与运行事件 | gdb-server-arguments、gdb-inspect、decode-systemview、analyze-events |
| 串口、RS485 与协议回归 | serial-ports、serial-exchange、modbus、run-build |

全部操作及真实签名以 `openjlink schema` 为准。更多流程见 [工程使用](references/setup.md)、[应用场景](references/scenarios.md)、[调试](references/debugging.md)、[采集](references/capture.md)、[RTOS](references/rtos.md) 和 [协议](references/protocol.md)。

## 结果与限制

写入、暂停、复位、下载和发送命令要求调用者已有授权并显式确认。任务 accepted 不等于 completed；结果 unknown 时查询原任务，不自动重放。Flash loader 的真实擦除范围还需按目标核对。

当前内存地址为 32 位；指令断点按 Thumb 使用；故障快照面向列出的 Cortex-M 架构。不能据此宣称覆盖所有 J-Link 支持的处理器。固定地址全局符号、单维数组和标量是当前 DWARF 范围。SVD 当前支持非 cluster 的寄存器/位域，读安全性依赖描述文件和厂商资料；不提供 SVD 写入。

采集为单拥有者、有界任务；RTT 读取会消耗目标缓冲。没有跨进程历史订阅、实时共享后台、触发前后环形采集、完整 RTOS 图形时间线或 SWO/ETM 采集。离线图中的上升沿查找不是硬件触发。细项和优先级见 [能力差距](references/coverage.md)。

J-Link V9/V11 不是完整产品型号。探针型号、驱动、芯片 loader、RTOS 插桩、负载与实际吞吐需要分别验收。主机时间不能代替目标采样时间，VREF 不能代替功率测量，回读相同不能代替运行或物理结果。

## 开发检查

```text
python -m pip install -e ".[test,modbus]"
python -m pytest -q
ruff check scripts tests --select F,E9
```

部分 ELF 回归使用 `arm-none-eabi-gcc`；缺少时会明确跳过。硬件测试不随安装或单元测试自动执行。软件回归与真实探针/目标板验收分开记录。

## 许可

OpenJlink 自有代码按 MIT 发布。第三方来源、依赖和修改说明见 [NOTICE](NOTICE)；保留的第三方许可在 [LICENSES](LICENSES)。本项目与 SEGGER 无隶属或背书关系。

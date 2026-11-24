# OpenJlink

[English](README.md) | [简体中文](README.zh-CN.md)

面向嵌入式开发者和 AI 的通用 J-Link CLI。提供内存与变量、烧录校验、RTT、故障现场、RTOS 事件、外设寄存器和证据分析能力。工程已有的构建系统、RTOS、测试入口和业务规则由开发任务决定。

只需要 CLI。提供直接命令、JSON 调用和持久会话，不需要额外的工具协议服务。

## 交给 AI 安装

可以把仓库作为早期预览版公开分享。拥有终端、文件和网络权限的本地编程 AI 可以按下面的要求安装。单独发一个链接不会执行安装；纯聊天界面的 AI 无法在你的电脑上安装软件。

把下面这段话复制给你的编程 AI：

> 请从 https://github.com/ruiwarn/OpenJlink 为当前用户安装 OpenJlink v0.1.1，包括可复用的 AI Skill 和全局 CLI。先阅读本 README，并遵守当前环境的安装规则。
>
> 1. 检测操作系统、CPU 架构、真实用户主目录和当前 AI 宿主。使用该宿主文档规定的用户级 Skill 目录，尊重已配置的位置和已有安装。常见位置见下表；不要假定所有 AI 产品的目录相同。宿主不支持 Skill 时，仍可安装 CLI，并明确说明这一限制。保持工程文件和其他 Skill 不变。
> 2. 复用已经安装且兼容的工具。如果缺少 uv，下载并检查下方官方 uv 0.12.16 安装器，再安装到当前用户环境。复用合适的 Python 3.10+；没有时安装由 uv 管理的 Python 3.13.5。依赖与工程、系统 Python 包隔离，安装后刷新命令查找路径。
> 3. 从下方发布链接将 v0.1.1 wheel 和源码 ZIP 下载到用户下载/缓存目录，核对 SHA-256。先解压到临时位置，再将 ZIP 中 OpenJlink 目录的内容安装到宿主的 openjlink Skill 目录，确保 SKILL.md 就在该目录下。包括 agents、references、scripts 和许可文件。更新已有安装前检查来源并保留本地修改，避免出现重复 Skill 入口。
> 4. 按下方命令使用 uv tool install 安装已校验的本地 wheel 和 modbus 扩展；这条路径不需要 Git。让命令目录进入持久用户 PATH；需要时运行 uv tool update-shell，并刷新当前进程或打开新终端。只建立私有虚拟环境不算完成全局安装。
> 5. 检查用户单独安装的官方 SEGGER J-Link Software Pack，记录实际版本和架构，复用合适的已有安装。如果硬件使用需要它且尚未安装，使用 SEGGER 官方下载页；遇到必须由用户确认的许可、管理员交互或环境限制时，停在该步骤并说明情况。不要猜一个适用于所有探针的 SDK 版本，不要更换 USB 驱动，也不要操作目标板来证明安装成功。可以完成 CLI/Skill 安装，并单列硬件环境尚待处理。
> 6. 在无关目录、新终端、不激活虚拟环境的情况下，验证 openjlink --version、--help 和 schema。版本应为 0.1.1，清单应有 51 项操作。选择可写的任务状态目录执行 inspect-environment，并在同一 session 中测试 ping/device_status，全程不连接目标。确认宿主能够发现 Skill；需要时刷新或重启宿主，否则明确报告发现状态待确认。报告安装路径、实际版本、验证结果和未完成步骤。下载或安装失败时停止，不要报告成功。

常见用户级目录如下；`~` 表示 Windows、Linux 或 macOS 中当前用户的真实主目录：

| AI 宿主 | Skill 安装位置 |
|---|---|
| Codex | `~/.agents/skills/openjlink/` |
| Claude Code | `~/.claude/skills/openjlink/` |
| Gemini CLI | `~/.agents/skills/openjlink/` 或原生 `~/.gemini/skills/openjlink/`，选用一个能被识别的位置 |
| 其他宿主 | 安装前查询其文档规定的用户级 Skill 目录 |

固定版本发布文件：

| 文件 | SHA-256 |
|---|---|
| [CLI wheel](https://github.com/ruiwarn/OpenJlink/releases/download/v0.1.1/openjlink-0.1.1-py3-none-any.whl) | `456a8fe59836b4009b6bd54b17e4c57e476c611ff83ea1d7c5ee8ddb72853a9f` |
| [Skill/源码 ZIP](https://github.com/ruiwarn/OpenJlink/releases/download/v0.1.1/OpenJlink_0.1.1.zip) | `d220ab57b2f6ed39d01d690ebe203561eb8448a3c14f11da29c25e440abac5d0` |

在存放已校验 wheel 的下载/缓存目录中运行以下基准命令。仅在需要时补装 Python；复用已有解释器时，将 `--python` 参数换成它的实际路径：

```text
uv python install 3.13.5
uv tool install --upgrade --python 3.13.5 "./openjlink-0.1.1-py3-none-any.whl[modbus]"
uv tool update-shell
openjlink --version
openjlink --help
openjlink schema
```

官方依据：[uv 安装说明](https://docs.astral.sh/uv/getting-started/installation/)、固定 uv 0.12.16 的 [Windows 安装器](https://astral.sh/uv/0.12.16/install.ps1)与 [Linux/macOS 安装器](https://astral.sh/uv/0.12.16/install.sh)、[Python 管理](https://docs.astral.sh/uv/guides/install-python/)、[SEGGER 下载](https://www.segger.com/downloads/jlink/)，以及 [Codex](https://developers.openai.com/codex/skills/)、[Claude Code](https://code.claude.com/docs/en/skills)、[Gemini CLI](https://geminicli.com/docs/cli/skills/) 的 Skill 发现说明。上述目录面向本地宿主；远程 AI 默认安装到它自己的执行环境，除非已经明确连接到你的电脑。

## 安装

要求 Python 3.10+，以及用户自行安装的 SEGGER J-Link Software Pack。本仓库不包含官方 DLL、探针固件、芯片 Flash 算法或厂商 SVD 文件。

已安装 uv 时，通过独立工具环境安装用户级全局命令：

```text
uv tool install --upgrade "openjlink[modbus] @ git+https://github.com/ruiwarn/OpenJlink.git@v0.1.1"
openjlink --version
openjlink --help
openjlink schema
```

如果 uv 提示命令目录不在 PATH 中，运行 `uv tool update-shell` 后重新打开终端。在无关目录、不激活虚拟环境的情况下验证 `openjlink --version`。

本地源码开发时，也可在下载的源码根目录执行：

```text
python scripts/setup_runtime.py
python scripts/run.py --help
```

这种备用方式使用本目录自己的 `.venv`，不会安装全局命令。作为 AI Skill 使用时，将本仓库安装到技能目录，优先使用上述全局 CLI 安装方式；入口是 [SKILL.md](SKILL.md)。

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

这两条不连接目标。实际连接使用 `connect`，提供真实 `serial`、`device`、`interface`、`speed_khz`；后续操作继续写入该进程的标准输入。传入 `--compact` 可省略重复模板字段与长哈希，传入 `--batch <file|-> --stop-on-error` 可一次性执行 JSON 数组或 JSONL 批处理后退出。JSON 模式使用下划线操作名，直接命令使用连字符和命名参数。复杂列表/对象通过 JSON 或 `--args @file.json` 传入。

单次命令执行完会关闭自身会话。不能将独立的 connect/read 命令当作同一连接。会话结束会等待已提交任务；采集应先请求 `cancel_capture` 并查询任务终态，不能靠关闭输入取消 Flash 操作。

## 能做什么

| 开发场景 | 操作 |
|---|---|
| 连不上、选错探针、缺主机依赖 | inspect-environment、discover-probes、connect、probe-info |
| 编译后下载并核对程序 | run-build、inspect-image、start-job、job-status、wait-job、verify-image、check-heartbeat |
| 查看 RAM、Flash、缓冲和配置 | read-memory、read-regions、dump-memory、write-memory、write-regions |
| 按全局变量、结构体成员或数组定位 | load-symbols、search-symbols、type-info、read-variable、read-variables、write-variable、write-variables、symbolize |
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

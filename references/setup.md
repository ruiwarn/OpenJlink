# CLI 安装与工程使用

要求 Python 3.10+ 和用户安装的 SEGGER J-Link Software Pack。工程不需要增加对 OpenJlink 的构建依赖。

## 一次安装，多工程使用

源码根目录执行 `python scripts/setup_runtime.py`，在本目录的 `.venv` 安装运行依赖。以后从任意工程通过 `python <OpenJlink绝对目录>/scripts/run.py ...` 使用。下载失败时停止，不改系统 Python。

也可在自己选定的 Python 环境安装仓库，使用 `openjlink`。Windows、Linux/macOS 的技能目录可能不同，应从当前 Skill 的实际安装路径取得入口，不把一台电脑的绝对路径写进工程共享规则。

AI 在工程中可按这样的任务使用：读取该工程规则，使用 OpenJlink 的 CLI，先检查真实构建/目标信息，再完成指定观测；数据保存到本次任务目录。无需每个工程重新安装 Skill。

## 三种命令形式

```text
openjlink --version
openjlink schema
openjlink read-memory --help
openjlink inspect-image --path build/app.bin --base-address 0x08000000
openjlink call inspect_image --args @arguments.json
openjlink --state-dir .openjlink-state session
```

直接命令用连字符，JSON 操作名用下划线。整数支持 `0x` 前缀；列表/对象参数为 JSON。路径有空格时按当前终端正确引用，复杂参数推荐 UTF-8 JSON 文件。状态目录参数在子命令前。

## 持久硬件会话

同一个进程接收每行一个请求并即时返回一行 JSON；调用方逐次写 stdin 并读取 stdout。ping 与 device_status 不连接目标：

```json
{"id":1,"operation":"ping","arguments":{}}
{"id":2,"operation":"device_status","arguments":{}}
```

实际开发时，继续在该进程发送 connect、load_symbols、read_variable 等。connect 必须提供真实 serial/device/interface/speed_khz；不能照抄虚构设备。单独 call 结束即关闭自己的会话，不能把后续新进程当作原连接。

有限批次可用文件/管道传入多行 JSON；交互式 AI 使用保持打开的输入输出管道。输出即时刷新，不需要关闭 stdin 才看到结果。协议错误与硬件错误都返回 ok=false；单次失败返回非零退出码，会话则保留后续处理能力，调用方必须逐条检查 ok。

关闭输入会结束会话并等待已提交任务。先查询终态，采集可请求 cancel_capture；关闭进程不能撤销已写硬件。长任务状态持久化在 state_dir，同一目录一次只允许一个工具进程，不能换目录绕过同一探针锁。

## 本地资料和适配

构建/测试入口、芯片、镜像布局、保留区、SVD 与 RTOS 信息按任务读取。已有下载器或测试脚本满足需求时直接复用；需要统一结果、符号、采集或证据时使用 OpenJlink。具体变量和协议判据留在工程中。

schema、inspect_image、load_symbols/外设描述解析不执行目标连接。首次安装不自动枚举/连接目标，更不会为证明成功而烧录、暂停、复位或换 USB 驱动。

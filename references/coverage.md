# 通用开发覆盖与差距

2026-11-17。OpenJlink 是通用 CLI 与 Skill，不以命令数量表示竞品覆盖率。当前软件有基础调试、记录、分析和 SVD 观测；原始需求的硬件与场景验收尚未完成。

## 对照公开竞品

对照 MKLink AI Probe v0.3.6、提交 d000370b901a72e4f8ec8fe09cf8b837f2579f0c。其默认注册为 46 个工具，其中通用调用还能路由 105 项共享子能力；这些数字不可与 OpenJlink 的平铺操作数直接比较。

| 能力 | 竞品源码证据 | OpenJlink 当前情况 | 后续价值 |
|---|---|---|---|
| 单拥有者和异步任务 | runtime_capabilities.py、runtime_mcp.py | 已有探针/状态锁、任务去重与 unknown；无共享服务 | P0 保留可靠任务；共享后台按实际长采集场景立项 |
| RTT 通道历史/游标 | remote/dashboards.py read_channel、remote/api.py rtt_history | 有原始收发与有限记录，读取会消耗缓冲；没有多消费者游标 | P0/P1：持续诊断时价值高，CLI 本身不妨碍增加后台 |
| 外设/位域语义 | peripheral_watch.py、remote/api.py peripheral_select | 新增显式 SVD、目录、位域读取和采集，拒绝声明副作用；cluster 和字段写未支持 | P1：先完善读安全、继承/数组/cluster 的目标样例 |
| 故障现场与解释 | remote/api.py fault_snapshot、hardfault-detail | 有架构选择、故障状态、指定基本帧和源码行；自动 EXC_RETURN/扩展帧推导及语义报告不足 | P0：优先完善证据与架构适配，实际异常固件验收 |
| 变量曲线和触发 | static/rtt_viewer.js 包含 preTriggerBuffer、postTriggerRemaining | 有离线曲线、回放与上升沿查找；没有采集时触发、前后环形缓冲、公式通道 | P1：偶发问题的触发窗口比增加界面菜单更有价值 |
| 吞吐测量与高速采样 | dump_memory.py、runtime_mcp.py measure_dump_memory | 有实际轮询间隔与计数；无专门吞吐矩阵和目标性能基线 | P1：先测实际 Hz/字节数/P99/丢样/扰动，不照搬速度宣传 |
| RTOS 时间线与统计 | systemview_analyzer.py task_intervals/analyze_events | 有事件解码与嵌套 ISR 独占统计；无任务时间线、切换/ready/blocked 延迟统计和完整报告 | P1：事件来源与时钟先验收，再增加离线分析 |
| 串口长期记录/脚本序列 | remote/api.py serial_sequence_start、serial_recording_start、modbus_loop_start | 有单次串口/Modbus和运行已有测试入口；无通用持续串口记录/序列执行器 | P1：优先复用工程已有测试器，避免两套协议判据 |
| 多镜像与启动闭环 | v0.3.6 发布说明、下载实现 | 单镜像范围/快照/回读/保留区核对已提供；多分区全计划预检、运行断言仍由 AI 编排 | P0/P1：先让 Boot/APP/参数区的范围和产物关联可审阅 |
| GUI、远程、供电、OTP、脱机 | 对应公开路由及发布说明 | 不在当前 CLI 研发核心范围；没有用空实现宣称支持 | P2：只有实际研发需求与硬件条件具备才扩展 |

证据链接：[发布](https://github.com/Aladdin-Wang/Mklink-AI-Probe/releases/tag/v0.3.6)、[能力路由](https://github.com/Aladdin-Wang/Mklink-AI-Probe/blob/d000370b901a72e4f8ec8fe09cf8b837f2579f0c/Mklink-AI-Probe/mklink/runtime_capabilities.py)、[RTT 游标实现](https://github.com/Aladdin-Wang/Mklink-AI-Probe/blob/d000370b901a72e4f8ec8fe09cf8b837f2579f0c/Mklink-AI-Probe/mklink/remote/dashboards.py#L720)、[外设描述](https://github.com/Aladdin-Wang/Mklink-AI-Probe/blob/d000370b901a72e4f8ec8fe09cf8b837f2579f0c/Mklink-AI-Probe/mklink/peripheral_watch.py)、[触发缓冲](https://github.com/Aladdin-Wang/Mklink-AI-Probe/blob/d000370b901a72e4f8ec8fe09cf8b837f2579f0c/Mklink-AI-Probe/mklink/static/rtt_viewer.js#L3210)、[RTOS 分析](https://github.com/Aladdin-Wang/Mklink-AI-Probe/blob/d000370b901a72e4f8ec8fe09cf8b837f2579f0c/Mklink-AI-Probe/mklink/systemview_analyzer.py)。以上为静态源码确认，不代表我们运行过竞品硬件。

## 更多有用操作

下列是通用研发增量需求，并非都已在竞品确认：数据观察点/条件断点、单独核寄存器写入、源码级单步/局部变量、SWO/ITM/DWT、按范围擦除、目标能力预检、采集触发、记录裁剪/导出和统一实验清单。优先复用成熟调试器或库；OpenJlink 补场景编排、输入校验和证据，不重新实现传输协议。当前没有这些专用 CLI 命令时须明确说明。

## 原始需求逐项复核

“软件基础”只表示当前实现路径与本地回归存在，不表示整项需求或参考板验收通过。

| 原需求 | 状态与剩余工作 |
|---|---|
| R01 目标身份 | 部分：显式选择与身份查询；完整 SDK/目标能力说明、错目标阻断与拔插矩阵不足 |
| R02 会话共享 | 部分：独占与 busy；缺客户端退出/后台采集分离及共享订阅 |
| R03 构建产物 | 软件基础：显式入口/日志/摘要，实际工程闭环待验 |
| R04 符号匹配 | 软件基础：固定地址 DWARF、generation 与 ELF 回读守卫；其他工具链/优化形态待适配 |
| R05 下载与运行 | 部分：单镜像回读/保留区/心跳分别提供；无自动业务运行验收与多镜像计划 |
| R06 RTT | 部分：有界字节收发/记录；缺历史游标和重启/慢消费者板级矩阵 |
| R07 快照/写入 | 部分：范围/类型/短读/预期旧值/回读；常规内存写没有会话级区域白名单，SVD 仅受控读 |
| R08 证据 | 部分：文件清单/哈希/时间；缺统一实验关联清单及磁盘满等完整失败矩阵 |
| R09 故障 | 部分：基础帧/状态/源码行；缺扩展/安全帧和参考异常固件验收 |
| R10 运行控制 | 部分：Thumb 指令断点与核心控制；资源上限、复杂断点/GDB 工作流和未知状态处理需加强 |
| R11 任务状态 | 软件基础：去重、持久终态/unknown；硬件断线与进程中断仍待验 |
| R12 曲线回放 | 部分：离线图已做；参考板采样性能和长测未做 |
| R13 同步采样 | 部分：包解码/序号/时间回绕；目标端同点采样按工程指导实现和验证 |
| R14 协议 | 部分：串口与Modbus基础；自定义协议、半帧与真实设备矩阵待验 |
| R15 控制/保护 | 方法指导：业务判据和物理证据属于具体开发任务，不内置到通用工具 |
| R16 裸机调度 | 部分：通用事件统计；周期、执行片与抖动分析还需补充 |
| R17 展示 | 部分：离线缩放/光标/回放；缺实时共享与采集触发 |
| R18 RTOS | 部分：GDB 检查和事件基础；参考 RTOS 工程、时间线/等待关系分析未完成 |
| R19 物理仪器 | 按需扩展，当前没有物理测量验收 |
| R20 环境扩展 | CI 拟覆盖 Windows/Linux；结果以实际工作流为准，远程/量产不在本版 |

下一轮 P0 应先做一只明确探针和已知目标的构建→下载→回读→运行→日志完整闭环，再按真实问题补会话持续日志、能力预检和统一证据。P1 选择 SVD 扩展、触发和 RTOS 时间线；P2 的平台与专有硬件功能不阻挡通用研发 CLI。

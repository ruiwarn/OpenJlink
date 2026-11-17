# 构建、下载与调试

## 构建与镜像

使用工程允许的命令。`run_build(argv,cwd,artifacts,output_dir,confirm)` 只按给定参数列表执行，不调用 shell，不猜产物，不安装工具链。成功时记录退出码、日志和显式产物的 SHA-256；失败不收集旧产物。它不证明镜像已下载。

增量构建允许产物字节不变，不能仅凭修改时间判新旧。AI 应将成功构建的清单与后续烧录输入关联。构建超时会停止直接子进程，但不保证其所有后代都已退出；此时结果不通过，不继续下载。

`inspect_image(path,base_address)` 离线检查 ELF/AXF/OUT、Intel HEX 或 BIN。BIN 必须提供基址；HEX 保留地址空洞并检查校验与 EOF。ELF 使用有文件内容的 PT_LOAD 物理加载地址，不把 BSS 当烧录数据。工具不保证外置 Flash 初始化或每种厂商特殊镜像可直接处理；这些条件从工程获得。

烧录走 `start_job(operation="program",arguments=...,request_id=...,confirm=true)`。arguments 包括 `path`、BIN 的 `base_address`、必须给出的 `allowed_ranges=[{address,size}]`、可选 `reset_after` 和 `preserve_ranges`。allowed_ranges 必须结合实际擦除单元及授权范围确定，不能只看几个待写字节。镜像存为任务私有快照，任务去重包含镜像摘要，避免排队期间文件重建导致下载内容变化。

工具调用 SDK loader 后逐段回读比较；不是仅相信返回码。`preserve_ranges` 可在下载前后核对参数/文件系统区域，最多 16 项/总计4096B；核对失败表示可能已经改写，不能恢复或自动重烧。更大的保留区可先后用 dump_memory 单独留证。任何会擦到保留区的 loader/几何错误仍必须在执行前由工程分析避免。

默认不复位；`reset_after` 是显式选择。完成后由 AI 按该工程确认启动方式，用已知心跳、任务计数、RTT 或协议测试检查运行。不要把 verified=true 写成整机功能通过。整片擦除使用单独的 erase 任务，必须传当前精确 device；不默认解锁受保护器件。

## 符号、变量和内存

`load_symbols` 不连接目标，generation 是文件内容摘要。`verify_image` 实际比较符号 ELF 中的加载字节与板上内容后，才允许 `write_variable`。这验证存储镜像匹配，不证明 CPU 当前正在运行该镜像。

支持固定地址全局变量、结构体成员、单维数组元素和标量 int/enum/float。优化掉、同名多定义、动态位置、多维数组、位域、指针写入和聚合写入明确拒绝。需要这些能力时使用工程的 GDB 和准确的上下文，不猜地址或静默降级。

`read_memory` 最大4096B；`read_regions` 最多16项/总计4096B，只合并连续/重叠范围。不同硬件读取不是原子快照。`dump_memory` 可将最大16MiB的指定范围分块保存，并记录完整/部分结果。

`write_memory` 必须回读一致，可通过 expected_hex 核对预期旧值；`write_regions` 最多8项/总计12KiB，按序执行并非原子事务。MMIO 是否适合回读由工程决定。硬件写异常后会隔离当前 SDK 会话，先检查证据，再显式断开/重连。

## CPU、断点和故障

`debug_control` 提供 halt/resume/step，暂停会影响控制环、看门狗与协议。先停止 RTT，再改变执行状态；不能声称实时性不受影响。断点只清理由本会话创建的句柄，不清其他工具的断点。

`fault_snapshot` 要求目标已明确暂停，architecture 必须准确。M0/M0+/M23 不读 M3/M4 风格的 CFSR/HFSR；M3/M4/M7/M33 读取相应故障状态。异常栈基本帧地址由调用者提供，工具不假定 handler 中当前 MSP 就是入异常时栈顶。FPU 扩展栈、TrustZone、安全栈、异常嵌套和损坏栈必须按目标分析后确定地址。

`symbolize` 用当前 ELF 将 PC/LR 映射到可找到的源码行，不编造完整回溯。自动复位后现场可能丢失，先取证；持久故障记录的布局与实现由具体工程开发任务决定。

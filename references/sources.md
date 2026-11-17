# 依赖与来源

- pylink-square 2.1.0：https://github.com/square/pylink ，Apache-2.0；调用用户安装的 SEGGER 动态库。本包不复制该库源码或官方 DLL。
- pyelftools 0.32：https://github.com/eliben/pyelftools ，用于 ELF/DWARF。
- pyserial：https://github.com/pyserial/pyserial ，用于通用串口。
- cmsis-svd 0.6：https://github.com/cmsis-svd/cmsis-svd ，Apache-2.0；复用 XML 继承、寄存器和字段解析，不重新编写 SVD 解析器。
- pymodbus：https://github.com/pymodbus-dev/pymodbus ，可选 Modbus RTU。
- SystemView 解码器改编自 MKLink AI Probe v0.3.6 对应提交 d000370b901a72e4f8ec8fe09cf8b837f2579f0c 的 mklink/systemview_parser.py：https://github.com/Aladdin-Wang/Mklink-AI-Probe/blob/d000370b901a72e4f8ec8fe09cf8b837f2579f0c/Mklink-AI-Probe/mklink/systemview_parser.py 。保留 MIT 许可于 LICENSES/MKLink-MIT.txt；改动为移除文档/注释、接入原有同步扫描、修正同步填充字节计数，并增加 pending_bytes 公开属性以报告文件末尾残包。未复制整个 MKLink 设备层。此来源不代表已验证任意 SystemView 版本。

目标端 SEGGER RTT/SystemView、RTOS 适配、芯片 loader 与 J-Link SDK 各有自己的适用条件与授权，不能从本包或 MKLink 根目录许可推出所有组件均可任意分发。

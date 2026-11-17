# Dependencies and provenance

- pylink-square 2.1.0: https://github.com/square/pylink, Apache-2.0. Calls the user's installed SEGGER library. OpenJlink does not vendor that library's source or official DLLs.
- pyelftools 0.32: https://github.com/eliben/pyelftools, used for ELF/DWARF.
- pyserial: https://github.com/pyserial/pyserial, used for generic serial communication.
- cmsis-svd 0.6: https://github.com/cmsis-svd/cmsis-svd, Apache-2.0. Reuses XML inheritance, register, and field parsing.
- pymodbus: https://github.com/pymodbus-dev/pymodbus, optional Modbus RTU support.
- The SystemView decoder adapts mklink/systemview_parser.py from MKLink AI Probe v0.3.6, commit d000370b901a72e4f8ec8fe09cf8b837f2579f0c: https://github.com/Aladdin-Wang/Mklink-AI-Probe/blob/d000370b901a72e4f8ec8fe09cf8b837f2579f0c/Mklink-AI-Probe/mklink/systemview_parser.py. Its MIT license is retained in LICENSES/MKLink-MIT.txt. Changes remove comments/docstrings, activate the existing sync scanner, correct sync-padding accounting, and expose pending_bytes to report trailing partial packets. The complete device layer was not copied. This provenance does not establish validation against every SystemView version.

Target-side SEGGER RTT/SystemView modules, RTOS adaptations, chip loaders, and the J-Link SDK each have their own applicability and license conditions. The package or the competitor's root license does not grant redistribution rights for every component.

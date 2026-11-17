# Building, programming, and debugging

## Builds and images

Use commands allowed by the project. `run_build(argv,cwd,artifacts,output_dir,confirm)` executes the supplied argument list without a shell, artifact guessing, or toolchain installation. On success it records the exit code, log, and SHA-256 of explicit artifacts. On failure it does not collect stale output. It does not establish that firmware was programmed.

An incremental build can legitimately leave artifact bytes unchanged, so modification time alone does not determine freshness. Associate the successful build manifest with subsequent programming input. A build timeout stops the direct child but does not guarantee all descendants exited. Treat that result as failed and do not proceed to programming.

`inspect_image(path,base_address)` checks ELF/AXF/OUT, Intel HEX, or BIN offline. BIN requires an explicit base address. HEX preserves address holes and checks checksums and EOF. ELF uses the physical load addresses of PT_LOAD segments with file contents; BSS is not programming data. Determine external-Flash initialization and support for vendor-specific images from the project.

Program through `start_job(operation="program",arguments=...,request_id=...,confirm=true)`. Arguments include `path`, `base_address` for BIN, required `allowed_ranges=[{address,size}]`, and optional `reset_after` and `preserve_ranges`. Determine allowed_ranges from actual erase units and authorization, not just the bytes to be written. The image is stored as a private job snapshot, and deduplication includes its hash so rebuilding a file while queued cannot silently change the programmed bytes.

After invoking the SDK loader, the tool reads back and compares each segment. `preserve_ranges` checks parameter/filesystem regions before and after programming, up to 16 regions and 4096 bytes total. Failure means data may already have changed; it does not restore data or permit automatic reprogramming. Use dump_memory separately for larger preservation evidence. Analyze loader behavior and erase geometry before execution to avoid erasing preserved regions.

Reset is disabled by default; `reset_after` is explicit. After completion, follow the project's startup procedure and inspect execution using a known heartbeat, task counter, RTT, or protocol test. Do not report verified=true as whole-device acceptance. Chip erase is a separate erase job requiring the exact connected device. Protected devices are not automatically unlocked.

## Symbols, variables, and memory

`load_symbols` does not connect to the target; generation is the file-content hash. `write_variable` is allowed only after `verify_image` compares the ELF's load bytes against target contents. This verifies stored image matching, not that the CPU is currently executing that image.

Supported symbol forms are fixed-address globals, structure members, one-dimensional array elements, and scalar int/enum/float values. Optimized-out variables, ambiguous names, dynamic locations, multidimensional arrays, bit fields, pointer writes, and aggregate writes are rejected. Use the project's GDB and accurate context for these cases instead of guessing addresses or silently falling back.

`read_memory` allows up to 4096 bytes. `read_regions` allows at most 16 regions and 4096 bytes total, merging only adjacent or overlapping ranges. Separate hardware reads are not atomic. `dump_memory` saves an explicit range of up to 16 MiB in chunks, with complete/partial-result metadata.

`write_memory` requires matching readback and can check an expected old value through expected_hex. `write_regions` allows up to eight regions and 12 KiB total, executed in order without atomic transaction semantics. The project determines whether readback is appropriate for a given MMIO location. A hardware write exception quarantines the SDK session; inspect evidence before explicitly disconnecting and reconnecting.

## CPU control, breakpoints, and faults

`debug_control` provides halt/resume/step. Halting affects control loops, watchdogs, and communication. Stop RTT before changing CPU execution, and do not claim unchanged real-time behavior. Only breakpoint handles created by this session are cleared.

`fault_snapshot` requires an explicitly halted target and an accurate architecture. M0/M0+/M23 do not read M3/M4-style CFSR/HFSR. M3/M4/M7/M33 read their corresponding fault status. The caller supplies the basic exception-frame address; the current handler MSP is not assumed to be the exception-entry stack top. Determine addresses for FPU extended frames, TrustZone, secure stacks, nested exceptions, and damaged stacks from the actual target context.

`symbolize` maps PC/LR through the current ELF to available source lines; it does not fabricate a full backtrace. Capture evidence before a reset destroys fault state. Persistent fault-record layout and implementation belong to the concrete project's development task.

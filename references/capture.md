# Capture, synchronized data, and offline analysis

## RTT and continuous recording

The target must already integrate and enable RTT. `rtt_start(address)` uses a known control-block address or SDK discovery; `rtt_channels` queries actual buffer descriptors. Discovery can take time, but failure does not justify endless retries or target restarts. Channel counts come from the target and driver, not a fixed competitor limit.

`rtt_read` consumes bytes from the SDK channel; it is not independently replayable history for multiple consumers. Share saved recordings for analysis. `rtt_write` accepts up to 256 bytes and returns the number actually submitted. Partial writes are not split and retried, and submission does not establish application execution.

Continuous recording uses `start_job(operation="capture",arguments={kind,duration,path,period,...},...)`. The kind can be variables, peripherals, memory, rtt, or systemview. Variables use names; peripherals require loaded SVD descriptions and register names; memory uses regions. RTT/SystemView uses channel and requires RTT to be started first. kind=systemview still records raw bytes; it does not integrate or start target-side RTOS events.

A recording is limited to one million requested samples and 0.01-3600 seconds. The output must be a new file in an existing directory. Rows include a host monotonic timestamp and sequence number. The adjacent `.meta.json` records completeness, file hash, actual polling intervals, cancellation, and failures. cancel_capture requests a stop while preserving saved data. Do not classify a file as complete when its completion record is missing or invalid.

period is a host request interval. Actual throughput depends on hardware, byte count, and connection. RTT polling frequency is not target sampling frequency, and sequential variable reads are not synchronized sampling. SDK/target-buffer overflow may lose data. Report loss as unknown when target sequence numbers or counters are unavailable.

## Synchronized, fast, or precise-time observations

Read the current project's sample timing, time source, variable consistency, and bandwidth budget. Guide target code to form one packet at a single logical sampling point. Define encoding, byte order, field types, sequence, target timestamp/frequency, restart/wrap rules, buffering, and loss counts. Use bounded nonblocking output and compare application timing with and without instrumentation. Do not assume a large buffer is appropriate or add floating-point formatting to an ISR by default.

The toolkit does not contain sampling code tied to a particular MCU or RTOS. `decode_packets` decodes fixed packets using the caller's struct format, field names, sync bytes, timestamp field/frequency, and sequence field. It checks gaps, duplicates, resets, and wraps and produces the common recording format. It does not validate an unknown protocol's CRC, escaping, or frame-length rules. Use an existing protocol parser when these checks are needed and do not claim packet integrity without them.

## Analysis and display

`summarize_recording` returns channel ranges, means, sample counts, and intervals, and verifies the completion-manifest hash. `compare_recordings` returns both datasets and changes in means without attributing causation. Check load, stimulus, capture conditions, and units before interpreting a difference.

`render_recording` produces offline HTML with channel selection, zoom, pan, a cursor, replay by recorded time, and rising-edge search. It supports up to 100000 samples and preserves original values. Crop larger files to an explicit window rather than silently discarding peaks for display. The viewer does not control hardware.

`export_rtt` concatenates recorded RTT/SystemView bytes in order into raw binary. `decode_systemview` first searches for synchronization and does not guess boundaries when it is absent. It reports events, drop indicators, and trailing partial-packet bytes. decoder_complete describes visible decoder integrity, not proof that the target lost no events. See [rtos.md](rtos.md) for target requirements.

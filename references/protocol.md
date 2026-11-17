# Serial, RS485, and protocol workflows

J-Link provides the debug connection; a separate USB adapter can provide UART/RS485. Confirm electrical interface, wiring, port, baud rate, data bits, parity, stop bits, protocol, and device address. Reusing a port name does not prove device identity.

`serial_ports` lists ports. `serial_exchange` opens an explicit port, sends at most 4096 bytes, and receives at most 65536 bytes. Writes require authorization. It sends once without automatic retry and returns actual TX/RX and the host time interval. Received bytes may include unsolicited messages, so they do not establish request/response correlation. Binary data is passed through data_hex without terminal-text encoding.

`modbus` uses Modbus RTU with zero retries and supports FC1/2/3/4/5/6/15/16. The task supplies slave, address, count, and values. Coil writes accept only 0/1; single writes accept one value; address-space overflow is rejected. Raw TX/RX are retained. A protocol ACK does not establish completion of mechanical or application actions. Inspect state after a lost reply instead of blindly replaying writes.

For custom protocols, DLT645, CAN gateways, and similar workflows, reuse existing project testers and frame definitions. The generic toolkit does not embed application data identifiers, register maps, calibration flows, or action criteria. run_build can execute existing test entry points with explicit argv and collect logs/result files. Process exit codes do not establish physical action.

Associate build/image identity, raw frames, RTT, variables, target events, and instrument records with the same experiment. Distinct host/target clocks need explicit synchronization or error bounds. Report software state changes, driver outputs, and actual contact/sensor outcomes separately.

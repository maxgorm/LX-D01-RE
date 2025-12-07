# LX-D01 RE Notes

- Primary scripts: `LX_D01_test.py` (data path) and `lx_motor_test.py` (motor path).
- Both now log writes (`WRITE ->`) and notifications (`NOTIFY <-`) in hex. Capture full console output for replay.
- Discovery:
  - Set `PRINTER_ADDRESS` in `LX_D01_test.py` or `mac_address` in `lx_motor_test.py` to skip scanning.
  - Otherwise, scripts scan for devices with name containing `LX-D01`.
- Job flow (`LX_D01_test.py`):
  - Build sample blocks, send `5A04` start, stream data, wait for `5A06`, then ACK with `5A04 ...0100`.
- Motor flow (`lx_motor_test.py`):
  - Init `0x01`, latch `0x06`, spacing `0xA7`, energy `0xAF`, speed `0xA4`, feed `0xA9`, execute `0x0E`.
- If repeating tests, power-cycle printer between runs if credits/notify get stuck.
- When feeding logs back, include console output with timestamps (if you add them) to align writes/notifies.

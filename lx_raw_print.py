#!/usr/bin/env python3
"""
LX-D01 Raw Print Driver.

Hypothesis: The printer expects RAW bitmap data after the 0xA1 (Start Job) command,
not packetized 0x55 chunks.

Sequence:
1. Init
2. Start Job (384px width, 500 lines height)
3. Stream 24,000 bytes of 0xFF (Solid Black)
4. Send CRC32
5. Execute
"""

import asyncio
import struct
import zlib
from typing import Optional, Callable, List
from bleak import BleakClient, BleakScanner

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

SERVICE_UUID = "0000FFE6-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID = "0000FFE1-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR_UUID = "0000FFE2-0000-1000-8000-00805f9b34fb"

PRINT_WIDTH = 384
PRINT_HEIGHT = 400 # Print ~5cm of black

# ---------------------------------------------------------------------------
# DRIVER
# ---------------------------------------------------------------------------

class LXD01Raw:
    def __init__(self, mac_address: Optional[str] = None, device_name: str = "LX-D01"):
        self.mac_address = mac_address
        self.device_name = device_name
        self.client: Optional[BleakClient] = None
        self._notify_callbacks: List[Callable[[bytes], None]] = []

    async def connect(self, timeout: float = 20.0) -> None:
        if self.client and self.client.is_connected: return
        
        device = None
        if self.mac_address:
            device = await BleakScanner.find_device_by_address(self.mac_address, timeout=timeout)
        else:
            devices = await BleakScanner.discover(timeout=timeout)
            for d in devices:
                if d.name and self.device_name in d.name:
                    device = d
                    break
        
        if not device: raise RuntimeError(f"{self.device_name} not found")
        
        self.client = BleakClient(device)
        await self.client.connect()
        await self.client.start_notify(NOTIFY_CHAR_UUID, self._handle_notify)

    async def disconnect(self) -> None:
        if self.client:
            try: await self.client.stop_notify(NOTIFY_CHAR_UUID)
            except: pass
            await self.client.disconnect()
            self.client = None

    def _handle_notify(self, _sender, data: bytearray) -> None:
        for cb in self._notify_callbacks: cb(bytes(data))
    
    def add_notify_callback(self, cb): self._notify_callbacks.append(cb)
    def remove_notify_callback(self, cb): 
        if cb in self._notify_callbacks: self._notify_callbacks.remove(cb)

    async def _write(self, data: bytes, chunk_size: int = 20) -> None:
        if not self.client or not self.client.is_connected: return
        for i in range(0, len(data), chunk_size):
            await self.client.write_gatt_char(WRITE_CHAR_UUID, data[i:i+chunk_size], response=False)
            # Flow control: Slightly faster for raw data
            if i + chunk_size < len(data): await asyncio.sleep(0.01) 

    async def wait_for_ack(self, cmd_byte: int, timeout: float = 2.0) -> bool:
        ack_event = asyncio.Event()
        def listener(data):
            if len(data) >= 2 and data[0] == 0x5A and data[1] == cmd_byte:
                ack_event.set()
        
        self.add_notify_callback(listener)
        try:
            await asyncio.wait_for(ack_event.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False
        finally:
            self.remove_notify_callback(listener)

    async def send_command(self, cmd: int, payload: bytes) -> bool:
        length = len(payload)
        pkt = bytes([0x5A, cmd, length & 0xFF, (length >> 8) & 0xFF]) + payload
        await self._write(pkt)
        return await self.wait_for_ack(cmd)

async def main():
    printer = LXD01Raw()
    print("Connecting...")
    await printer.connect()
    
    # 1. Init
    print("Sending Init...")
    await printer.send_command(0x01, b'')
    await asyncio.sleep(0.2)

    # 2. Config
    print("Sending Config (Max Energy)...")
    await printer.send_command(0xAF, b'\xFF\xFF')
    await printer.send_command(0xA4, b'\x02\x00')
    await printer.send_command(0xA7, b'\x20\x00') # Set spacing
    await asyncio.sleep(0.2)

    # 3. Prepare Raw Data (Solid Black)
    # Width 384 / 8 = 48 bytes per line
    row_bytes = PRINT_WIDTH // 8
    total_bytes = row_bytes * PRINT_HEIGHT
    
    print(f"Generating {total_bytes} bytes of raw black data...")
    raw_data = b'\xFF' * total_bytes # All Black
    
    # 4. Start Job (0xA1)
    # Payload: [WidthL] [WidthH] [HeightL] [HeightH] [00] [00]
    # 384 = 0x0180 -> 80 01
    # 400 = 0x0190 -> 90 01
    payload_a1 = struct.pack('<HHH', PRINT_WIDTH, PRINT_HEIGHT, 0)
    print(f"Sending Start Job (0xA1) Payload: {payload_a1.hex().upper()}")
    
    if await printer.send_command(0xA1, payload_a1):
        print("✅ Job Started (ACK Received). Streaming Data...")
    else:
        print("❌ Job Start Failed (No ACK). Aborting.")
        await printer.disconnect()
        return

    # 5. Stream Raw Data
    await printer._write(raw_data, chunk_size=120)
    print("Data Sent.")
    
    # 6. Send CRC32 (4 bytes)
    # zlib.crc32 is standard
    crc = zlib.crc32(raw_data) & 0xFFFFFFFF
    crc_bytes = struct.pack('<I', crc) # Little Endian CRC
    print(f"Sending CRC32: {crc_bytes.hex().upper()}")
    await printer._write(crc_bytes)
    await asyncio.sleep(0.1)

    # 7. Execute
    print("Sending Execute (0x0E)...")
    if await printer.send_command(0x0E, b''):
        print("✅ Execute ACK Received!")
    else:
        print("❌ Execute No ACK.")

    # 8. Extra Feed (Just in case)
    print("Sending Feed (0xA9)...")
    await printer.send_command(0xA9, b'\x64\x00')

    await asyncio.sleep(2.0)
    await printer.disconnect()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
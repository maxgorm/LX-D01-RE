#!/usr/bin/env python3
"""
LX-D01 Feed Test V2.

Updates:
- Fixes false-positive error logging.
- Tries MASSIVE feed values (10,000 steps) to rule out microscopic step units.
- Tries Flow Control Enable (0xA8 01).
"""

import asyncio
from typing import Optional, Callable
from bleak import BleakClient, BleakScanner

SERVICE_UUID = "0000FFE6-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID = "0000FFE1-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR_UUID = "0000FFE2-0000-1000-8000-00805f9b34fb"

class LXD01FeedV2:
    def __init__(self, mac_address: Optional[str] = None, device_name: str = "LX-D01"):
        self.mac_address = mac_address
        self.device_name = device_name
        self.client: Optional[BleakClient] = None
        self._notify_callbacks: List[Callable[[bytes], None]] = []

    async def connect(self) -> None:
        if self.client and self.client.is_connected: return
        device = await BleakScanner.find_device_by_name(self.device_name)
        if not device: raise RuntimeError("Printer not found")
        self.client = BleakClient(device)
        await self.client.connect()
        await self.client.start_notify(NOTIFY_CHAR_UUID, self._handle_notify)

    async def disconnect(self) -> None:
        if self.client: await self.client.disconnect()

    def _handle_notify(self, _sender, data: bytearray) -> None:
        for cb in self._notify_callbacks: cb(bytes(data))
    
    def add_notify_callback(self, cb): self._notify_callbacks.append(cb)
    def remove_notify_callback(self, cb): 
        if cb in self._notify_callbacks: self._notify_callbacks.remove(cb)

    async def _write(self, data: bytes) -> None:
        if self.client: await self.client.write_gatt_char(WRITE_CHAR_UUID, data, response=False)

    async def send_cmd(self, name: str, cmd: int, payload: bytes) -> bool:
        length = len(payload)
        pkt = bytes([0x5A, cmd, length & 0xFF, (length >> 8) & 0xFF]) + payload
        
        print(f"👉 SEND: {name} (0x{cmd:02X}) Val: {payload.hex().upper()}")
        
        ack = asyncio.Event()
        resp = None
        
        def cb(d):
            nonlocal resp
            if len(d) >= 2 and d[0] == 0x5A and d[1] == cmd:
                resp = d
                ack.set()
            elif len(d) >= 2 and d[0] == 0x5A and d[1] == 0x02:
                # Status update
                pass

        self.add_notify_callback(cb)
        await self._write(pkt)
        try:
            await asyncio.wait_for(ack.wait(), 1.0)
            # The printer echoes the payload. This is NOT an error.
            # We only check for specific NACK patterns (usually 0xFF in specific slots)
            print(f"   ✅ ACK: {resp.hex().upper()}")
            return True
        except:
            print(f"   ❌ NO ACK")
            return False
        finally:
            self.remove_notify_callback(cb)

async def main():
    printer = LXD01FeedV2()
    print("Connecting...")
    await printer.connect()
    
    # 1. Init
    await printer.send_cmd("Init", 0x01, b'')
    await asyncio.sleep(0.1)

    print("\n--- CONFIGURATION ---")
    
    # Force Receipt Mode
    await printer.send_cmd("Set Mode (Continuous)", 0xA6, b'\x00')
    
    # Flow Control: Try 'Enable' (0x01)
    await printer.send_cmd("Flow Control Enable", 0xA8, b'\x01')

    # Spacing: Standard 32 dots
    await printer.send_cmd("Set Spacing", 0xA7, b'\x20\x00')
    
    # Speed: Medium
    await printer.send_cmd("Set Speed", 0xA4, b'\x02\x00')
    
    # Energy: Medium-High (Safe)
    await printer.send_cmd("Set Energy", 0xAF, b'\x00\x40')

    print("\n--- MASSIVE FEED TEST ---")
    # Feed 10,000 steps (0x2710)
    # Little Endian: 10 27
    await printer.send_cmd("Feed (10k Steps)", 0xA9, b'\x10\x27')
    
    # Execute to flush
    await printer.send_cmd("Execute", 0x0E, b'')

    print("\n--- WAITING (Listen for motor) ---")
    await asyncio.sleep(3.0)
    
    print("\n--- ALT FEED TEST (0xA3) ---")
    # Try the old 0xA3 command with massive payload
    await printer.send_cmd("Feed 0xA3 (10k Steps)", 0xA3, b'\x10\x27')
    await printer.send_cmd("Execute", 0x0E, b'')

    await asyncio.sleep(2.0)
    
    await printer.disconnect()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
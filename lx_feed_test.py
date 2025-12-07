#!/usr/bin/env python3
"""
LX-D01 Motor Tuning Tool.

Focuses solely on getting the motor to move by permuting configuration parameters.
The printer ACKs 0xA9 (Feed) and 0xA7 (Spacing), but doesn't move.
This script tests different values/endianness for Spacing and Speed.
"""

import asyncio
from typing import Optional, Callable, List
from bleak import BleakClient, BleakScanner

SERVICE_UUID = "0000FFE6-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID = "0000FFE1-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR_UUID = "0000FFE2-0000-1000-8000-00805f9b34fb"

class LXD01Tuner:
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

    async def send_cmd(self, cmd: int, payload: bytes) -> bool:
        length = len(payload)
        pkt = bytes([0x5A, cmd, length & 0xFF, (length >> 8) & 0xFF]) + payload
        
        ack = asyncio.Event()
        def cb(d):
            if len(d) >= 2 and d[0] == 0x5A and d[1] == cmd: ack.set()
        
        self.add_notify_callback(cb)
        await self._write(pkt)
        try:
            await asyncio.wait_for(ack.wait(), 0.5)
            return True
        except:
            return False
        finally:
            self.remove_notify_callback(cb)

async def main():
    tuner = LXD01Tuner()
    print("Connecting...")
    await tuner.connect()
    
    # 1. Init
    await tuner.send_cmd(0x01, b'')
    await asyncio.sleep(0.5)

    print("\n--- STARTING MOTOR TUNING ---")
    
    # TEST CASES: Combinations of Speed (0xA4) and Spacing (0xA7)
    # Param 1: Speed Value (Low, Med, High)
    # Param 2: Spacing Value
    # Param 3: Endianness (LE = Little Endian, BE = Big Endian)
    
    configs = [
        ("Default LE", b'\x02\x00', b'\x20\x00'), # Speed=2, Space=32 (LE)
        ("Default BE", b'\x00\x02', b'\x00\x20'), # Speed=2, Space=32 (BE)
        ("Fast LE",    b'\x05\x00', b'\x40\x00'), # Speed=5, Space=64 (LE)
        ("Fast BE",    b'\x00\x05', b'\x00\x40'), # Speed=5, Space=64 (BE)
        ("Max Spacing",b'\x02\x00', b'\xFF\x00'), # Max spacing byte
    ]

    for name, speed_bytes, space_bytes in configs:
        print(f"\n[TEST] Config: {name}")
        
        # A. Set Energy (Always Max)
        await tuner.send_cmd(0xAF, b'\xFF\xFF')
        
        # B. Set Speed (0xA4)
        print(f"   Setting Speed (0xA4): {speed_bytes.hex().upper()}")
        await tuner.send_cmd(0xA4, speed_bytes)
        
        # C. Set Spacing (0xA7)
        print(f"   Setting Spacing (0xA7): {space_bytes.hex().upper()}")
        await tuner.send_cmd(0xA7, space_bytes)
        
        # D. Send Feed (0xA9) - Try a LONG feed (0x0100 = 256 steps)
        # We try LE first (00 01) then BE (01 00)
        
        # Feed LE
        print("   👉 Triggering Feed (0xA9) [100 steps LE]...")
        await tuner.send_cmd(0xA9, b'\x64\x00')
        await asyncio.sleep(1.0)
        
        # Feed BE
        print("   👉 Triggering Feed (0xA9) [256 steps BE]...")
        await tuner.send_cmd(0xA9, b'\x01\x00') # 0x0100 BE = 256
        await asyncio.sleep(1.0)
        
        # E. Try EXECUTE (0x0E) just in case Feed needs a trigger
        print("   👉 Sending Execute (0x0E)...")
        await tuner.send_cmd(0x0E, b'')
        await asyncio.sleep(1.0)

    print("\n--- FINISHED ---")
    await tuner.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
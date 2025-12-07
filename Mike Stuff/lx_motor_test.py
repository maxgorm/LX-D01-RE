#!/usr/bin/env python3
"""
LX-D01 Motor Kickstart Tool.

Based on the discovery of 0xA9 (Feed) and 0xA7 (Spacing), this script
attempts to initialize all motor parameters and trigger a physical feed.

Sequence:
1. Init (0x01)
2. Latch / Enable (0x06) - Hypothesis: Might wake hardware
3. Set Energy (0xAF) - Max Power
4. Set Speed (0xA4) - Medium Speed
5. Set Spacing (0xA7) - CRITICAL: Sets step distance
6. Feed Command (0xA9) - Queue the feed
7. Execute (0x0E) - Trigger the queue
"""

import asyncio
from typing import Optional, Callable, List
from bleak import BleakClient, BleakScanner

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

SERVICE_UUID = "0000FFE6-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID = "0000FFE1-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR_UUID = "0000FFE2-0000-1000-8000-00805f9b34fb"

# ---------------------------------------------------------------------------
# DRIVER
# ---------------------------------------------------------------------------

class LXD01MotorTest:
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

    async def _write(self, data: bytes) -> None:
        if not self.client or not self.client.is_connected: return
        await self.client.write_gatt_char(WRITE_CHAR_UUID, data, response=False)

    async def send_command(self, name: str, cmd_byte: int, payload: bytes, wait_ack: bool = True) -> bool:
        print(f"👉 SENDING: {name} (0x{cmd_byte:02X})")
        
        length = len(payload)
        pkt = bytes([0x5A, cmd_byte, length & 0xFF, (length >> 8) & 0xFF]) + payload
        
        ack_event = asyncio.Event()
        
        def listener(data):
            if len(data) >= 2 and data[0] == 0x5A and data[1] == cmd_byte:
                ack_event.set()

        if wait_ack:
            self.add_notify_callback(listener)
        
        await self._write(pkt)
        
        if wait_ack:
            try:
                await asyncio.wait_for(ack_event.wait(), timeout=1.5)
                print(f"   ✅ ACK Received")
                return True
            except asyncio.TimeoutError:
                print(f"   ❌ NO ACK (Timeout)")
                return False
            finally:
                self.remove_notify_callback(listener)
        return True

async def main():
    motor = LXD01MotorTest()
    print("Connecting...")
    await motor.connect()
    
    # ---------------------------------------------------------
    # 1. INITIALIZATION SEQUENCE
    # ---------------------------------------------------------
    print("\n--- INITIALIZATION ---")
    await motor.send_command("Init", 0x01, b'')
    await asyncio.sleep(0.2)

    # Latch/Enable: 0x06 is often "Wake" or "Latch buffer"
    await motor.send_command("Latch/Enable", 0x06, b'\x00') 
    await asyncio.sleep(0.2)

    # ---------------------------------------------------------
    # 2. CONFIGURATION SEQUENCE
    # ---------------------------------------------------------
    print("\n--- CONFIGURATION ---")
    
    # Set Spacing (0xA7): 0x20 = 32 dots (Standard line height)
    # If this is 0, motor might think "Move 0 distance".
    await motor.send_command("Set Line Spacing", 0xA7, b'\x20\x00')
    await asyncio.sleep(0.1)

    # Set Energy (0xAF): Max (0xFFFF)
    await motor.send_command("Set Energy", 0xAF, b'\xFF\xFF')
    await asyncio.sleep(0.1)

    # Set Speed (0xA4): Medium (0x0200)
    await motor.send_command("Set Speed", 0xA4, b'\x02\x00')
    await asyncio.sleep(0.1)

    # ---------------------------------------------------------
    # 3. MOVEMENT SEQUENCE
    # ---------------------------------------------------------
    print("\n--- MOVEMENT TRIGGER ---")
    
    # METHOD A: Direct Feed (0xA9)
    # 0x64 = 100 steps
    print("\n[Attempt 1] 0xA9 Direct Feed...")
    await motor.send_command("Queue Feed (0xA9)", 0xA9, b'\x64\x00')
    await asyncio.sleep(0.1)
    
    # Try Executing it immediately
    await motor.send_command("Execute (0x0E)", 0x0E, b'', wait_ack=False)
    
    await asyncio.sleep(2.0)
    
    # METHOD B: Start Job (0xA1) as Feed
    # If 0xA9 failed, maybe 0xA1 is used for feed when no data follows?
    print("\n[Attempt 2] 0xA1 as Feed...")
    # Payload: Width(384) Height(100)
    # 384 = 0x0180, 100 = 0x0064
    payload_a1 = b'\x80\x01\x64\x00\x00\x00'
    await motor.send_command("Start Job (0xA1)", 0xA1, payload_a1)
    await asyncio.sleep(0.1)
    await motor.send_command("Execute (0x0E)", 0x0E, b'', wait_ack=False)

    await asyncio.sleep(2.0)
    
    await motor.disconnect()
    print("\nTest Complete.")

if __name__ == "__main__":
    asyncio.run(main())
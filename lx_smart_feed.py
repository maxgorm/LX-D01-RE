#!/usr/bin/env python3
"""
LX-D01 Smart Feed & Mode Switch Tool.

Diagnosis:
- The printer ACKs commands but refuses to move (Error 0x95).
- Hypothesis: Printer is stuck in 'Label Mode' (expecting gaps) or 'Zero Speed'.

Strategy:
1. Force 'Continuous Paper' Mode (0xA6 00).
2. Set Line Spacing (0xA7) and Speed (0xA4).
3. Attempt Feed (0xA9).
"""

import asyncio
from typing import Optional, Callable
from bleak import BleakClient, BleakScanner

SERVICE_UUID = "0000FFE6-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID = "0000FFE1-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR_UUID = "0000FFE2-0000-1000-8000-00805f9b34fb"

class LXD01Smart:
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
        
        print(f"👉 SEND: {name} (0x{cmd:02X}) Payload: {payload.hex().upper()}")
        
        ack = asyncio.Event()
        resp = None
        
        def cb(d):
            nonlocal resp
            # Capture command ECHO
            if len(d) >= 2 and d[0] == 0x5A and d[1] == cmd:
                resp = d
                ack.set()
            # Capture STATUS updates (0x02) separately
            elif len(d) >= 2 and d[0] == 0x5A and d[1] == 0x02:
                status_byte = d[2] if len(d) > 2 else 0
                print(f"   🔔 STATUS UPDATE: {d.hex().upper()} (Flag: 0x{status_byte:02X})")

        self.add_notify_callback(cb)
        await self._write(pkt)
        try:
            await asyncio.wait_for(ack.wait(), 1.0)
            print(f"   ✅ ACK: {resp.hex().upper()}")
            # Check for error codes in the response payload (usually byte 4)
            if len(resp) > 4 and resp[4] != 0x00:
                 print(f"   ⚠️  POSSIBLE ERROR CODE IN ACK: 0x{resp[4]:02X}")
            return True
        except:
            print(f"   ❌ NO ACK")
            return False
        finally:
            self.remove_notify_callback(cb)

async def main():
    printer = LXD01Smart()
    print("Connecting...")
    await printer.connect()
    
    # 1. Init
    await printer.send_cmd("Init", 0x01, b'')
    await asyncio.sleep(0.2)

    print("\n--- ATTEMPTING MODE SWITCH ---")
    
    # TEST: Set Paper Type (0xA6)
    # Payload: 0x00 (Continuous/Receipt), 0x01 (Label/Gap)
    # Try 0x00 First to unblock "Jam" state
    if await printer.send_cmd("Set Continuous Mode (0xA6)", 0xA6, b'\x00'):
        print("   (Mode switch command accepted)")
    
    await asyncio.sleep(0.5)

    print("\n--- CONFIGURING MOTOR ---")
    # Set Spacing (0xA7) - 32 dots
    await printer.send_cmd("Set Spacing", 0xA7, b'\x20\x00')
    # Set Speed (0xA4) - High
    await printer.send_cmd("Set Speed", 0xA4, b'\x02\x00')
    # Set Energy (0xAF)
    await printer.send_cmd("Set Energy", 0xAF, b'\xFF\xFF')

    print("\n--- TRIGGERING FEED ---")
    # Feed (0xA9) - 150 steps
    await printer.send_cmd("Feed (0xA9)", 0xA9, b'\x96\x00')
    
    # Optional Execute to flush buffer
    await printer.send_cmd("Execute (0x0E)", 0x0E, b'')

    print("\n--- DIAGNOSTIC WAIT (5s) ---")
    await asyncio.sleep(5.0)
    
    await printer.disconnect()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
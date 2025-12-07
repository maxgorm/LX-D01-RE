#!/usr/bin/env python3
"""
LX-D01 Command Discovery Tool.

Systematically tests the "Missing Commands" hypothesis:
- 0xA5: Detailed Status
- 0xA7: Set Vertical Spacing (CRITICAL: If spacing is 0, motor won't move)
- 0xA8: Flow Control / Ready Check
- 0xA9: Direct Line Feed
"""

import asyncio
import struct
from dataclasses import dataclass
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

class LXD01Discovery:
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
        # Simple write without chunking for short commands
        await self.client.write_gatt_char(WRITE_CHAR_UUID, data, response=False)

    async def test_command(self, name: str, cmd_byte: int, payload: bytes) -> bool:
        """
        Sends [5A] [Cmd] [LenL] [LenH] [Payload].
        Waits for [5A] [Cmd] ... echo.
        """
        print(f"\n🧪 TESTING: {name} (0x{cmd_byte:02X})")
        
        # 1. Build Packet
        length = len(payload)
        # Little Endian Length
        pkt = bytes([0x5A, cmd_byte, length & 0xFF, (length >> 8) & 0xFF]) + payload
        
        print(f"   TX: {pkt.hex().upper()}")
        
        # 2. Listen for ACK
        ack_event = asyncio.Event()
        response_data = None
        
        def listener(data):
            nonlocal response_data
            # Filter for 5A <CmdByte>
            if len(data) >= 2 and data[0] == 0x5A and data[1] == cmd_byte:
                response_data = data
                ack_event.set()
            # Also catch generic status responses (0x02) that might trigger
            elif len(data) >= 2 and data[0] == 0x5A and data[1] == 0x02:
                print(f"   (Status Update: {data.hex().upper()})")

        self.add_notify_callback(listener)
        await self._write(pkt)
        
        try:
            await asyncio.wait_for(ack_event.wait(), timeout=2.0)
            print(f"   ✅ ACK RECEIVED: {response_data.hex().upper()}")
            
            # Analyze Response
            if len(response_data) > 4:
                # payload is usually after the 4th byte
                resp_payload = response_data[4:]
                print(f"   📝 Response Payload: {resp_payload.hex().upper()}")
            
            return True
        except asyncio.TimeoutError:
            print(f"   ❌ NO RESPONSE (Timeout)")
            return False
        finally:
            self.remove_notify_callback(listener)

async def main():
    discovery = LXD01Discovery()
    print("Connecting...")
    await discovery.connect()
    
    # 0. Warmup (Init)
    await discovery.test_command("Init (Baseline)", 0x01, b'')
    await asyncio.sleep(0.5)

    # ---------------------------------------------------------
    # TEST 1: 0xA5 - Detailed Status
    # Hypothesis: 1 byte payload (0x00)
    # ---------------------------------------------------------
    await discovery.test_command("Detailed Status", 0xA5, b'\x00')
    await asyncio.sleep(0.5)

    # ---------------------------------------------------------
    # TEST 2: 0xA7 - Set Line Spacing
    # Hypothesis: 2 bytes (Little Endian). Try 0x10 (16 dots).
    # If this works, it might unlock the motor.
    # ---------------------------------------------------------
    success_a7 = await discovery.test_command("Set Spacing", 0xA7, b'\x10\x00')
    await asyncio.sleep(0.5)

    # ---------------------------------------------------------
    # TEST 3: 0xA8 - Flow Control / Ready
    # Hypothesis: Empty payload or 0x00
    # ---------------------------------------------------------
    await discovery.test_command("Flow Control", 0xA8, b'\x00')
    await asyncio.sleep(0.5)

    # ---------------------------------------------------------
    # TEST 4: 0xA9 - Direct Feed
    # Hypothesis: 2 bytes [AmountL] [AmountH]. Try 0x50 (80 steps).
    # If this moves the motor, we are golden.
    # ---------------------------------------------------------
    print("\n⚠️  LISTEN FOR MOTOR MOVEMENT NOW ⚠️")
    success_a9 = await discovery.test_command("Direct Feed", 0xA9, b'\x50\x00')
    
    if success_a9:
        print("\n🎉 0xA9 was ACKed! If paper moved, use 0xA9 for feeding.")
    elif success_a7:
        print("\n🎉 0xA7 (Spacing) was ACKed! This might fix the 'No Print' issue.")
        print("We should update the main driver to send 0xA7 before printing.")
    
    await discovery.disconnect()
    print("\nDiscovery Complete.")

if __name__ == "__main__":
    asyncio.run(main())
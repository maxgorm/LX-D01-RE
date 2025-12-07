#!/usr/bin/env python3
"""
LX-D01 Bluetooth Thermal Printer driver.

v16.0 - Line Alignment Fix
- Changed Packet Payload from 128 bytes to 48 bytes (Exactly 1 line of 384px).
- Changed Header to [55 01 IdxL IdxH] (Indicating 1 line per packet).
- Hypothesis: Printer requires data aligned to print head width.
"""

import asyncio
import struct
from dataclasses import dataclass
from typing import Optional, Callable, List

from bleak import BleakClient, BleakScanner
from PIL import Image, ImageOps, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

SERVICE_UUID = "0000FFE6-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID = "0000FFE1-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR_UUID = "0000FFE2-0000-1000-8000-00805f9b34fb"
DEFAULT_PRINTER_WIDTH = 384
PAYLOAD_SIZE = 48 # CRITICAL FIX: 48 bytes = 1 line (384 dots)

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def crc16_xmodem(data: bytes) -> int:
    """CRC-16-CCITT (XMODEM) polynomial 0x1021"""
    crc = 0
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = (crc << 1)
    return crc & 0xFFFF

@dataclass
class PrinterStatus:
    raw: bytes
    battery_level: int = 0
    
    def __str__(self) -> str:
        return f"PrinterStatus(Battery: {self.battery_level}%, raw={self.raw.hex(' ').upper()})"

# ---------------------------------------------------------------------------
# DRIVER
# ---------------------------------------------------------------------------

class LXD01Printer:
    def __init__(self, mac_address: Optional[str] = None, device_name: str = "LX-D01"):
        self.mac_address = mac_address
        self.device_name = device_name
        self.printer_width = DEFAULT_PRINTER_WIDTH
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

    async def _write(self, data: bytes, chunk_size: int = 20) -> None:
        if not self.client or not self.client.is_connected: return
        for i in range(0, len(data), chunk_size):
            await self.client.write_gatt_char(WRITE_CHAR_UUID, data[i:i+chunk_size], response=False)
            if i + chunk_size < len(data): await asyncio.sleep(0.015) 

    async def _wait_for_ack(self, cmd_id: int, timeout: float = 1.0) -> bool:
        ack_received = asyncio.Event()
        def check(data):
            if len(data) >= 2 and data[0] == 0x5A and data[1] == cmd_id:
                ack_received.set()
        self.add_notify_callback(check)
        try:
            await asyncio.wait_for(ack_received.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False
        finally:
            self._notify_callbacks.remove(check)

    async def query_status(self) -> PrinterStatus:
        last_resp = None
        def cb(d): nonlocal last_resp; last_resp = d
        self.add_notify_callback(cb)
        await self._write(bytes([0x5A, 0x01])) 
        await asyncio.sleep(0.5)
        self._notify_callbacks.remove(cb)
        if not last_resp: return PrinterStatus(b"")
        bat = last_resp[2] if len(last_resp) > 2 else 0
        return PrinterStatus(last_resp, battery_level=bat)

    async def configure_printer(self):
        print("Configuring Printer (Max Energy)...")
        await self._write(bytes([0x5A, 0xAF, 0xFF, 0xFF]))
        await asyncio.sleep(0.1)

    async def print_image(self, img: Image.Image, invert: bool = False) -> None:
        # 1. Format Bitmap
        if img.width != self.printer_width:
            scale = self.printer_width / img.width
            img = img.resize((self.printer_width, int(img.height * scale)))
        
        img = img.convert("L")
        img = ImageOps.autocontrast(img)
        
        if invert:
             img = img.point(lambda v: 0 if v < 128 else 255, mode="1")
        else:
             img = ImageOps.invert(img) 
             img = img.convert("1")
             
        raw_bitmap = img.tobytes()
        
        # Align to 48 bytes (1 line)
        if len(raw_bitmap) % PAYLOAD_SIZE != 0:
            rem = len(raw_bitmap) % PAYLOAD_SIZE
            raw_bitmap += b'\x00' * (PAYLOAD_SIZE - rem)
            
        print(f"Raw Bitmap: {len(raw_bitmap)} bytes")

        # 2. CREATE PACKET STREAM
        packet_stream = bytearray()
        chunk_count = len(raw_bitmap) // PAYLOAD_SIZE
        print(f"Generating {chunk_count} packets (48 bytes payload each)...")
        
        for i in range(chunk_count):
            start = i * PAYLOAD_SIZE
            end = start + PAYLOAD_SIZE
            payload = raw_bitmap[start:end]
            
            # Header: 55 [Lines] [IdxL] [IdxH]
            # Try 01 for 1 line
            idx_l = i & 0xFF
            idx_h = (i >> 8) & 0xFF
            header = bytes([0x55, 0x01, idx_l, idx_h])
            
            packet_stream.extend(header)
            packet_stream.extend(payload)
            
        print(f"Total Stream Size: {len(packet_stream)} bytes")

        # 3. SEND SEQUENCE
        # A. Init
        await self._write(bytes([0x5A, 0x01]))
        if not await self._wait_for_ack(0x01): print("⚠️ Init ACK missing")
        
        # B. Set Job Length
        total_len = len(packet_stream) + 2
        len_seq = struct.pack('<H', total_len) 
        
        print(f"Sending Length: 0x{len_seq.hex().upper()} (Little Endian)")
        await self._write(b'\x5A\x0B' + len_seq)
        
        if await self._wait_for_ack(0x0B):
            print("✅ Length ACK received.")
        else:
            print("❌ No ACK for Length.")

        # C. Send Packets
        chunk_s = 52 # Send exactly 1 packet (4 header + 48 data) at a time
        for i in range(0, len(packet_stream), chunk_s):
            await self._write(packet_stream[i:i+chunk_s], chunk_size=chunk_s)
            if (i // chunk_s) % 10 == 0: print(".", end="", flush=True)
            await asyncio.sleep(0.01)
        print("")
        
        # D. Send CRC16 (XMODEM)
        crc_val = crc16_xmodem(packet_stream)
        crc_seq = struct.pack('>H', crc_val) 
        print(f"Sending CRC16: 0x{crc_seq.hex().upper()}")
        await self._write(crc_seq)
        
        await asyncio.sleep(0.1)
        
        # E. Execute
        print("Sending Execute (5A 0E)...")
        await self._write(bytes([0x5A, 0x0E]))
        
        print("⏳ Waiting up to 10s for print completion...")
        if await self._wait_for_ack(0x0E, timeout=10.0):
            print("✅ Execute ACK received!")
        else:
            print("❌ No ACK for Execute (Timeout).")
        
        print("Done.")

    def generate_test_text(self, text: str) -> Image.Image:
        try: font = ImageFont.truetype("arial.ttf", 100)
        except: font = ImageFont.load_default()
        img = Image.new("1", (384, 150), 1) 
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), text, font=font, fill=0)
        draw.rectangle([0,0, 383, 149], outline=0, width=5)
        return img

async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", default="A", help="Text to print")
    parser.add_argument("--invert", action="store_true", help="Invert colors")
    args = parser.parse_args()

    printer = LXD01Printer()
    print("Connecting...")
    await printer.connect()
    
    def debug(d): 
        if d.hex().upper().startswith("5A02"): return
        print(f"RX: {d.hex().upper()}")
        
    printer.add_notify_callback(debug)
    
    status = await printer.query_status()
    print(f"Status: {status}")
    
    await printer.configure_printer()
    
    img = printer.generate_test_text(args.text)
    await printer.print_image(img, invert=args.invert)
    
    await printer.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
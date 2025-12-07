#!/usr/bin/env python3
"""
LX-D01 Header & CRC32 Test.

Hypothesis derived from PlatformIO:
- The printer requires a fixed HEADER (offset) before the image data.
- The forum suggested 17 bytes. We will test 16 bytes (standard alignment) and 17.
- Re-enabling CRC32 (Little Endian) based on APK 'java.util.zip.CRC32'.

Modes:
1. Default: Raw Data + 16-byte Header.
2. --zlib: ZLIB Data + 16-byte Header.
"""

import asyncio
import struct
import zlib
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

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def crc32(data: bytes) -> int:
    """Standard CRC32"""
    return zlib.crc32(data) & 0xFFFFFFFF

@dataclass
class PrinterStatus:
    raw: bytes
    battery_level: int = 0
    
    def __str__(self) -> str:
        return f"PrinterStatus(Battery: {self.battery_level}%, raw={self.raw.hex(' ').upper()})"

# ---------------------------------------------------------------------------
# DRIVER
# ---------------------------------------------------------------------------

class LXD01HeaderTest:
    def __init__(self, mac_address: Optional[str] = None, device_name: str = "LX-D01"):
        self.mac_address = mac_address
        self.device_name = device_name
        self.printer_width = DEFAULT_PRINTER_WIDTH
        self.client: Optional[BleakClient] = None
        self._notify_callbacks: List[Callable[[bytes], None]] = []

    async def connect(self, timeout: float = 20.0) -> None:
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

    async def print_with_header(self, img: Image.Image, use_zlib: bool = False) -> None:
        # 1. Format Bitmap
        if img.width != self.printer_width:
            scale = self.printer_width / img.width
            img = img.resize((self.printer_width, int(img.height * scale)))
        
        img = img.convert("L")
        img = ImageOps.invert(img) # Black->1
        img = img.convert("1")
        payload_data = img.tobytes()
        
        print(f"Raw Bitmap Size: {len(payload_data)} bytes")

        if use_zlib:
            print("Applying ZLIB Compression...")
            payload_data = zlib.compress(payload_data)
            print(f"Compressed Size: {len(payload_data)} bytes")

        # 2. CONSTRUCT STREAM WITH MAGIC HEADER
        # PlatformIO user mentioned "17 bytes offset".
        # We will try a 16-byte zero header first (Standard alignment).
        # Many printers use 16 bytes of 0x00 as a "Wake/Sync" preamble.
        magic_header = b'\x00' * 16 
        
        full_stream = magic_header + payload_data
        print(f"Total Stream (Header + Data): {len(full_stream)} bytes")

        # 3. SEND SEQUENCE
        
        # A. Init
        await self._write(bytes([0x5A, 0x01]))
        if not await self._wait_for_ack(0x01): print("⚠️ Init ACK missing")
        
        # B. Set Job Length
        # Length = Stream + 4 (CRC32)
        total_len = len(full_stream) + 4
        len_seq = struct.pack('<H', total_len) # Little Endian
        
        print(f"Sending Length: 0x{len_seq.hex().upper()} (Little Endian)")
        await self._write(b'\x5A\x0B' + len_seq)
        
        if await self._wait_for_ack(0x0B):
            print("✅ Length ACK received.")
        else:
            print("❌ No ACK for Length.")

        # C. Send Stream
        chunk_s = 100
        for i in range(0, len(full_stream), chunk_s):
            await self._write(full_stream[i:i+chunk_s], chunk_size=chunk_s)
            if (i // chunk_s) % 10 == 0: print(".", end="", flush=True)
            await asyncio.sleep(0.01)
        print("")
        
        # D. Send CRC32 (Little Endian)
        # Calculate CRC over the WHOLE stream (Header + Data)
        crc_val = crc32(full_stream)
        crc_seq = struct.pack('<I', crc_val) 
        print(f"Sending CRC32: 0x{crc_seq.hex().upper()}")
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
    parser.add_argument("--zlib", action="store_true", help="Use ZLIB compression")
    args = parser.parse_args()

    printer = LXD01HeaderTest()
    print("Connecting...")
    await printer.connect()
    
    def debug(d): 
        if d.hex().upper().startswith("5A02"): return
        print(f"RX: {d.hex().upper()}")
        
    printer.add_notify_callback(debug)
    
    status = await printer.query_status()
    print(f"Status: {status}")
    
    await printer.configure_printer()
    
    img = printer.generate_test_text("HEADER")
    await printer.print_with_header(img, use_zlib=args.zlib)
    
    await printer.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
import asyncio
from dataclasses import dataclass
from typing import List, Optional

from bleak import BleakClient, BleakScanner

# Connection config (match lx_motor_test.py)
PRINTER_ADDRESS = "AA:BB:CC:DD:EE:FF"  # set to MAC; leave placeholder to auto-scan by name
PRINTER_NAME = "LX-D01"

SERVICE_UUID = "0000FFE6-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000FFE1-0000-1000-8000-00805f9b34fb"   # Write Without Response
NOTIFY_UUID = "0000FFE2-0000-1000-8000-00805f9b34fb"  # Notify

# 20-byte ATT payload (MTU 23) → 4 bytes header + 16 bytes data
PAYLOAD_DATA_LEN = 16
MAX_IN_FLIGHT_WRITES = 2  # observed controller credits in log


@dataclass
class JobState:
    block_count: int
    job_id: int
    complete_event: asyncio.Event
    completion_seen: bool = False
    ack_required: bool = True


def le16(value: int) -> bytes:
    return value.to_bytes(2, "little")


def build_sa(op: int, w1: int, w2: int, w3: int = 0, w4: int = 0, w5: int = 0) -> bytes:
    # SA (5A) control frame: op + five 16-bit words
    return bytes([0x5A, op]) + le16(w1) + le16(w2) + le16(w3) + le16(w4) + le16(w5)


def build_data_block(index: int, payload16: bytes) -> bytes:
    if len(payload16) != PAYLOAD_DATA_LEN:
        raise ValueError(f"payload must be {PAYLOAD_DATA_LEN} bytes; got {len(payload16)}")
    return bytes([0x55, 0x00]) + le16(index) + payload16


def chunk_image(image_bytes: bytes) -> List[bytes]:
    padded = image_bytes + b"\x00" * ((PAYLOAD_DATA_LEN - (len(image_bytes) % PAYLOAD_DATA_LEN)) % PAYLOAD_DATA_LEN)
    blocks = []
    for i in range(0, len(padded), PAYLOAD_DATA_LEN):
        idx = i // PAYLOAD_DATA_LEN
        blocks.append(build_data_block(idx, padded[i : i + PAYLOAD_DATA_LEN]))
    return blocks


def parse_notify(data: bytes) -> Optional[tuple[int, List[int]]]:
    if not data or data[0] != 0x5A:
        return None
    op = data[1]
    # remaining words are little-endian 16-bit
    words = [int.from_bytes(data[i : i + 2], "little") for i in range(2, len(data), 2)]
    return op, words


async def send_wwr(client: BleakClient, payload: bytes):
    print(f"WRITE -> {payload.hex(' ')}")
    await client.write_gatt_char(WRITE_UUID, payload, response=False)


async def notify_handler(state: JobState, data: bytearray):
    print(f"NOTIFY <- {bytes(data).hex(' ')}")
    parsed = parse_notify(bytes(data))
    if not parsed:
        print("   (ignored: not 0x5A)")
        return
    op, words = parsed
    print(f"   op=0x{op:02X} words={words}")
    if op == 0x06 and len(words) >= 2:
        state.completion_seen = True
        state.complete_event.set()
        print("   completion seen, setting event")


async def main():
    # Find device by address or by name
    device = None
    if PRINTER_ADDRESS != "AA:BB:CC:DD:EE:FF":
        print(f"Searching by address {PRINTER_ADDRESS} ...")
        device = await BleakScanner.find_device_by_address(PRINTER_ADDRESS, timeout=10.0)
    if device is None:
        devices = await BleakScanner.discover(timeout=10.0)
        print(f"Discovered {len(devices)} devices")
        for d in devices:
            if d.name and PRINTER_NAME in d.name:
                device = d
                break
    if device is None:
        raise SystemExit("Printer not found; set PRINTER_ADDRESS or ensure the device advertises name LX-D01")
    print(f"Using device: {device}")

    # Example image payload (replace with real raster data)
    sample_image = b"\xFF\x00" * 200  # 400 bytes → 25 blocks of 16 bytes
    blocks = chunk_image(sample_image)
    block_count = len(blocks)
    print(f"Prepared {block_count} blocks")

    state = JobState(block_count=block_count, job_id=1, complete_event=asyncio.Event())

    async with BleakClient(device) as client:
        print("Connecting...")
        if not client.is_connected:
            raise SystemExit("Failed to connect")
        print("Connected, enabling notify")
        await client.start_notify(NOTIFY_UUID, lambda _, data: asyncio.create_task(notify_handler(state, data)))

        # Optional: wait a moment for initial 5A02 status
        await asyncio.sleep(0.2)

        # Send start job (5A04) with block_count and job_id
        print(f"Sending start frame for job {state.job_id} with {block_count} blocks")
        start_frame = build_sa(op=0x04, w1=block_count, w2=state.job_id)
        await send_wwr(client, start_frame)

        # Stream data with a small in-flight window
        in_flight = 0
        for pkt in blocks:
            while in_flight >= MAX_IN_FLIGHT_WRITES:
                await asyncio.sleep(0.005)
                # Bleak does not expose credits directly; pacing via sleep
            await send_wwr(client, pkt)
            in_flight += 1
            # crude pacing: assume controller returns credits quickly
            await asyncio.sleep(0.001)
            in_flight = max(0, in_flight - 1)

        print("Waiting for completion notify (5A06)...")
        # Wait for completion notify (5A06)
        try:
            await asyncio.wait_for(state.complete_event.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            raise SystemExit("Timeout waiting for 5A06 completion")

        print("Sending completion ACK")
        # ACK completion with 5A04 …0100…
        ack_frame = build_sa(op=0x04, w1=block_count, w2=0x0100)
        await send_wwr(client, ack_frame)

        await asyncio.sleep(0.5)  # allow repeats/cleanup
        print("Stopping notify and closing connection")
        await client.stop_notify(NOTIFY_UUID)


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import logging
import struct
from bleak import BleakClient, BleakScanner
from PIL import Image, ImageDraw, ImageFont, ImageOps

# --- CONFIGURATION ---
PRINTER_NAME = "LX-D01" # We will search for this
PRINT_WIDTH_PX = 384    # Standard for these 58mm printers

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

# --- CRC8 IMPLEMENTATION (From Article) ---
CRC8_TABLE = [
    0x00, 0x07, 0x0E, 0x09, 0x1C, 0x1B, 0x12, 0x15, 0x38, 0x3F, 0x36, 0x31, 0x24, 0x23, 0x2A, 0x2D,
    0x70, 0x77, 0x7E, 0x79, 0x6C, 0x6B, 0x62, 0x65, 0x48, 0x4F, 0x46, 0x41, 0x54, 0x53, 0x5A, 0x5D,
    0xE0, 0xE7, 0xEE, 0xE9, 0xFC, 0xFB, 0xF2, 0xF5, 0xD8, 0xDF, 0xD6, 0xD1, 0xC4, 0xC3, 0xCA, 0xCD,
    0x90, 0x97, 0x9E, 0x99, 0x8C, 0x8B, 0x82, 0x85, 0xA8, 0xAF, 0xA6, 0xA1, 0xB4, 0xB3, 0xBA, 0xBD,
    0xC7, 0xC0, 0xC9, 0xCE, 0xDB, 0xDC, 0xD5, 0xD2, 0xFF, 0xF8, 0xF1, 0xF6, 0xE3, 0xE4, 0xED, 0xEA,
    0xB7, 0xB0, 0xB9, 0xBE, 0xAB, 0xAC, 0xA5, 0xA2, 0x8F, 0x88, 0x81, 0x86, 0x93, 0x94, 0x9D, 0x9A,
    0x27, 0x20, 0x29, 0x2E, 0x3B, 0x3C, 0x35, 0x32, 0x1F, 0x18, 0x11, 0x16, 0x03, 0x04, 0x0D, 0x0A,
    0x57, 0x50, 0x59, 0x5E, 0x4B, 0x4C, 0x45, 0x42, 0x6F, 0x68, 0x61, 0x66, 0x73, 0x74, 0x7D, 0x7A,
    0x89, 0x8E, 0x87, 0x80, 0x95, 0x92, 0x9B, 0x9C, 0xB1, 0xB6, 0xBF, 0xB8, 0xAD, 0xAA, 0xA3, 0xA4,
    0xF9, 0xFE, 0xF7, 0xF0, 0xE5, 0xE2, 0xEB, 0xEC, 0xC1, 0xC6, 0xCF, 0xC8, 0xDD, 0xDA, 0xD3, 0xD4,
    0x69, 0x6E, 0x67, 0x60, 0x75, 0x72, 0x7B, 0x7C, 0x51, 0x56, 0x5F, 0x58, 0x4D, 0x4A, 0x43, 0x44,
    0x19, 0x1E, 0x17, 0x10, 0x05, 0x02, 0x0B, 0x0C, 0x21, 0x26, 0x2F, 0x28, 0x3D, 0x3A, 0x33, 0x34,
    0x4E, 0x49, 0x40, 0x47, 0x52, 0x55, 0x5C, 0x5B, 0x76, 0x71, 0x78, 0x7F, 0x6A, 0x6D, 0x64, 0x63,
    0x3E, 0x39, 0x30, 0x37, 0x22, 0x25, 0x2C, 0x2B, 0x06, 0x01, 0x08, 0x0F, 0x1A, 0x1D, 0x14, 0x13,
    0xAE, 0xA9, 0xA0, 0xA7, 0xB2, 0xB5, 0xBC, 0xBB, 0x96, 0x91, 0x98, 0x9F, 0x8A, 0x8D, 0x84, 0x83,
    0xDE, 0xD9, 0xD0, 0xD7, 0xC2, 0xC5, 0xCC, 0xCB, 0xE6, 0xE1, 0xE8, 0xEF, 0xFA, 0xFD, 0xF4, 0xF3
]

def calculate_crc8(data):
    crc = 0
    for byte in data:
        crc = CRC8_TABLE[(crc ^ byte) & 0xFF]
    return crc & 0xFF

def format_message(command, data):
    """
    Constructs the 0x51 0x78 Protocol Message:
    [51 78] [Cmd] [00] [Len] [00] [Data...] [CRC] [FF]
    """
    # Header: 51 78
    # Command: command
    # AlwaysZero0: 00
    # DataLen: len(data)
    # AlwaysZero1: 00
    
    # Using bytearray for mutable sequence
    packet = bytearray([0x51, 0x78, command, 0x00, len(data), 0x00])
    
    # Append Data
    packet.extend(data)
    
    # Checksum is calculated on the Data part only? 
    # The article says: bArr5[8] = calcCrc8(bArr5, 6, 2) where 6 is index, 2 is length.
    # It seems CRC is calculated on the DATA bytes.
    crc = calculate_crc8(data)
    packet.append(crc)
    
    # Footer
    packet.append(0xFF)
    
    return packet

# --- IMAGE HELPERS ---
def generate_test_image(text):
    """Generates a 384px wide image with text."""
    try:
        font = ImageFont.truetype("Arial.ttf", 40)
    except IOError:
        font = ImageFont.load_default()
        
    dummy = Image.new('1', (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    h = bbox[3] - bbox[1] + 20
    
    # 1 (White) background, 0 (Black) text
    img = Image.new('1', (PRINT_WIDTH_PX, h), color=1) 
    draw = ImageDraw.Draw(img)
    
    w = bbox[2] - bbox[0]
    x = (PRINT_WIDTH_PX - w) // 2
    draw.text((x, 10), text, font=font, fill=0)
    
    return img

def image_to_bits(img):
    """
    Converts image to the bit format for the printer.
    Returns: list of bytearrays (one per line)
    """
    if img.width != PRINT_WIDTH_PX:
        img = img.resize((PRINT_WIDTH_PX, int(img.height * (PRINT_WIDTH_PX / img.width))))
    
    # Invert (Printer 1=Black)
    img = img.convert('L')
    img = ImageOps.invert(img)
    img = img.convert('1')
    
    width, height = img.size
    row_bytes = width // 8
    data = img.tobytes()
    
    lines = []
    for i in range(height):
        start = i * row_bytes
        end = start + row_bytes
        line_data = data[start:end]
        lines.append(line_data)
        
    return lines

# --- MAIN LOGIC ---
async def main():
    logger.info(f"🔍 Scanning for '{PRINTER_NAME}'...")
    device = await BleakScanner.find_device_by_name(PRINTER_NAME)
    
    if not device:
        logger.error("❌ Printer not found.")
        return

    logger.info(f"🔗 Connecting to {device.address}...")
    
    async with BleakClient(device) as client:
        logger.info("✅ Connected! Searching for Write Characteristic...")
        
        target_char = None
        
        # Hunt for the characteristic
        for service in client.services:
            for char in service.characteristics:
                if "write" in char.properties or "write-without-response" in char.properties:
                    # The article mentions AE01 or AE10. Let's look for those, or fallback to any Write
                    str_uuid = str(char.uuid).upper()
                    if "AE01" in str_uuid or "AE10" in str_uuid:
                        target_char = char
                        logger.info(f"🎯 FOUND KNOWN TARGET: {char.uuid}")
                        break
                    
                    # Fallback
                    if not target_char and "000018" not in str_uuid: # Ignore standard services
                        target_char = char
            if target_char and ("AE01" in str(target_char.uuid).upper() or "AE10" in str(target_char.uuid).upper()):
                break
        
        if not target_char:
            logger.error("❌ No writable characteristic found!")
            return
            
        logger.info(f"🚀 Using Characteristic: {target_char.uuid}")
        
        # --- COMMANDS ---
        CMD_FEED = 0xA1
        CMD_DRAW = 0xA2
        CMD_ENERGY = 0xAF
        
        # 1. Set Energy (Medium)
        energy_pkt = format_message(CMD_ENERGY, [0x01, 0x00]) # Example data
        await client.write_gatt_char(target_char.uuid, energy_pkt)
        await asyncio.sleep(0.1)
        
        # 2. Render Image
        logger.info("🎨 Rendering Image...")
        img = generate_test_image("CAT PROTOCOL!")
        lines = image_to_bits(img)
        
        logger.info(f"🖨️ Printing {len(lines)} lines...")
        
        # 3. Print Loop
        # The article implies: Send Line Data -> Feed 1 unit -> Repeat
        for i, line in enumerate(lines):
            # Send Data (0xA2)
            # Article says: "DrawBitmap command 0xA2 takes an array of bytes... each bit represents one pixel"
            pkt_draw = format_message(CMD_DRAW, line)
            await client.write_gatt_char(target_char.uuid, pkt_draw)
            
            # Feed 1 Step (0xA1) if necessary?
            # Many of these printers require a "print buffer" command. 
            # If 0xA2 is just "load buffer", we might need 0xA1 to "print buffer".
            # Trying 0xA1 with 1 step.
            # Article used [0x70, 0x00] for a big feed. Let's try [0x01, 0x00] for 1 line.
            # pkt_feed = format_message(CMD_FEED, [0x01, 0x00])
            # await client.write_gatt_char(target_char.uuid, pkt_feed)

            # NOTE: Sending feed after every line is extremely slow on BLE.
            # Usually, if you just send 0xA2 consecutively, it prints. 
            # If it doesn't print, uncomment the Feed packet above.
            
            if i % 10 == 0:
                print(".", end="", flush=True)
            
            # Small delay to prevent buffer choke
            await asyncio.sleep(0.01)
            
        print("")
        
        # 4. Final Feed
        logger.info("🛑 Feeding paper...")
        feed_pkt = format_message(CMD_FEED, [0x50, 0x00]) # Feed ~80 lines
        await client.write_gatt_char(target_char.uuid, feed_pkt)
        
        logger.info("✨ Done.")
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
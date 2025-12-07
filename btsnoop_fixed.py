#!/usr/bin/env python3
"""
This script extracts btsnooz content from bugreports and generates
a valid btsnoop log file which can be viewed using standard tools
like Wireshark.

Fixed for Python 3 with proper binary handling and encoding.
"""
import base64
import struct
import sys
import zlib

# Enumeration of the values the 'type' field can take in a btsnooz
# header. These values come from the Bluetooth stack's internal
# representation of packet types.
TYPE_IN_EVT = 0x10
TYPE_IN_ACL = 0x11
TYPE_IN_SCO = 0x12
TYPE_OUT_CMD = 0x20
TYPE_OUT_ACL = 0x21
TYPE_OUT_SCO = 0x22

def type_to_direction(pkt_type):
    """
    Returns the inbound/outbound direction of a packet given its type.
    0 = sent packet
    1 = received packet
    """
    if pkt_type in [TYPE_IN_EVT, TYPE_IN_ACL, TYPE_IN_SCO]:
        return 1
    return 0

def type_to_hci(pkt_type):
    """
    Returns the HCI type of a packet given its btsnooz type.
    """
    if pkt_type == TYPE_OUT_CMD:
        return b'\x01'
    if pkt_type == TYPE_IN_ACL or pkt_type == TYPE_OUT_ACL:
        return b'\x02'
    if pkt_type == TYPE_IN_SCO or pkt_type == TYPE_OUT_SCO:
        return b'\x03'
    if pkt_type == TYPE_IN_EVT:
        return b'\x04'
    return b'\x00'

def decode_snooz(snooz, output_file):
    """
    Decodes all known versions of a btsnooz file into a btsnoop file.
    """
    version, last_timestamp_ms = struct.unpack_from('=bQ', snooz)
    
    if version != 1 and version != 2:
        sys.stderr.write('Unsupported btsnooz version: %s\n' % version)
        exit(1)
    
    sys.stderr.write(f'Found btsnooz version {version}\n')
    
    # Oddly, the file header (9 bytes) is not compressed, but the rest is.
    decompressed = zlib.decompress(snooz[9:])
    
    sys.stderr.write(f'Decompressed {len(decompressed)} bytes of HCI data\n')
    
    # Write btsnoop file header
    output_file.write(b'btsnoop\x00\x00\x00\x00\x01\x00\x00\x03\xea')
    
    if version == 1:
        decode_snooz_v1(decompressed, last_timestamp_ms, output_file)
    elif version == 2:
        decode_snooz_v2(decompressed, last_timestamp_ms, output_file)

def decode_snooz_v1(decompressed, last_timestamp_ms, output_file):
    """
    Decodes btsnooz v1 files into a btsnoop file.
    """
    first_timestamp_ms = last_timestamp_ms + 0x00dcddb30f2f8000
    offset = 0
    packet_count = 0
    
    # First pass to determine the timestamp of the first packet.
    while offset < len(decompressed):
        length, delta_time_ms, pkt_type = struct.unpack_from('=HIb', decompressed, offset)
        offset += 7 + length - 1
        first_timestamp_ms -= delta_time_ms
        packet_count += 1
    
    sys.stderr.write(f'Found {packet_count} packets (v1)\n')
    
    # Second pass does the actual writing out.
    offset = 0
    while offset < len(decompressed):
        length, delta_time_ms, pkt_type = struct.unpack_from('=HIb', decompressed, offset)
        first_timestamp_ms += delta_time_ms
        offset += 7
        
        output_file.write(struct.pack('>II', length, length))
        output_file.write(struct.pack('>II', type_to_direction(pkt_type), 0))
        output_file.write(struct.pack('>II', (first_timestamp_ms >> 32), (first_timestamp_ms & 0xFFFFFFFF)))
        output_file.write(type_to_hci(pkt_type))
        output_file.write(decompressed[offset : offset + length - 1])
        offset += length - 1

def decode_snooz_v2(decompressed, last_timestamp_ms, output_file):
    """
    Decodes btsnooz v2 files into a btsnoop file.
    """
    first_timestamp_ms = last_timestamp_ms + 0x00dcddb30f2f8000
    offset = 0
    packet_count = 0
    
    # First pass to determine the timestamp of the first packet.
    while offset < len(decompressed):
        length, packet_length, delta_time_ms, snooz_type = struct.unpack_from('=HHIb', decompressed, offset)
        offset += 9 + length - 1
        first_timestamp_ms -= delta_time_ms
        packet_count += 1
    
    sys.stderr.write(f'Found {packet_count} packets (v2)\n')
    
    # Second pass does the actual writing out.
    offset = 0
    while offset < len(decompressed):
        length, packet_length, delta_time_ms, snooz_type = struct.unpack_from('=HHIb', decompressed, offset)
        first_timestamp_ms += delta_time_ms
        offset += 9
        
        output_file.write(struct.pack('>II', packet_length, length))
        output_file.write(struct.pack('>II', type_to_direction(snooz_type), 0))
        output_file.write(struct.pack('>II', (first_timestamp_ms >> 32), (first_timestamp_ms & 0xFFFFFFFF)))
        output_file.write(type_to_hci(snooz_type))
        output_file.write(decompressed[offset : offset + length - 1])
        offset += length - 1

def main():
    if len(sys.argv) < 2:
        sys.stderr.write('Usage: %s <bugreport_file> [output_file]\n' % sys.argv[0])
        exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'BTSNOOP.log'
    
    sys.stderr.write(f'Reading: {input_file}\n')
    sys.stderr.write(f'Output:  {output_file}\n')
    
    found = False
    base64_string = ""
    
    # Read file with error handling for mixed encodings
    try:
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if found:
                    if '--- END:BTSNOOP_LOG_SUMMARY' in line:
                        sys.stderr.write(f'Found END marker. Base64 data length: {len(base64_string)}\n')
                        snooz_data = base64.standard_b64decode(base64_string)
                        with open(output_file, 'wb') as out:
                            decode_snooz(snooz_data, out)
                        sys.stderr.write(f'Successfully wrote {output_file}\n')
                        sys.exit(0)
                    base64_string += line.strip()
                if '--- BEGIN:BTSNOOP_LOG_SUMMARY' in line:
                    sys.stderr.write('Found BEGIN:BTSNOOP_LOG_SUMMARY marker\n')
                    found = True
    except Exception as e:
        sys.stderr.write(f'Error reading file: {e}\n')
        sys.exit(1)
    
    if not found:
        sys.stderr.write('No btsnooz section found in bugreport.\n')
        sys.stderr.write('Looking for "--- BEGIN:BTSNOOP_LOG_SUMMARY" marker...\n')
        sys.exit(1)

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Parse btsnoop log file to extract BLE ATT Write commands.
This will help identify the printer protocol bytes.
"""
import struct
import sys

# BTSnoop file format constants
BTSNOOP_HEADER = b'btsnoop\x00'
BTSNOOP_HEADER_LEN = 16

# HCI packet types
HCI_CMD = 0x01
HCI_ACL = 0x02
HCI_SCO = 0x03
HCI_EVT = 0x04

# ATT opcodes we care about
ATT_WRITE_REQ = 0x12        # Write Request
ATT_WRITE_CMD = 0x52        # Write Command (no response)
ATT_WRITE_RSP = 0x13        # Write Response
ATT_HANDLE_VALUE_NTF = 0x1B # Handle Value Notification

def parse_btsnoop(filename):
    """Parse btsnoop file and extract ATT packets."""
    
    with open(filename, 'rb') as f:
        # Read and verify header
        header = f.read(8)
        if header != BTSNOOP_HEADER:
            print(f"Invalid btsnoop header: {header}")
            return
        
        # Skip rest of header (version, datalink type)
        f.read(8)
        
        packet_num = 0
        att_writes = []
        att_notifications = []
        
        while True:
            # Read packet header (24 bytes)
            pkt_header = f.read(24)
            if len(pkt_header) < 24:
                break
            
            original_len, included_len, flags, drops, timestamp_hi, timestamp_lo = \
                struct.unpack('>IIIIII', pkt_header)
            
            # Read packet data
            pkt_data = f.read(included_len)
            if len(pkt_data) < included_len:
                break
            
            packet_num += 1
            
            # Check if it's an ACL packet (BLE data)
            if len(pkt_data) > 0:
                hci_type = pkt_data[0]
                
                if hci_type == HCI_ACL and len(pkt_data) > 9:
                    # ACL packet structure:
                    # 1 byte: HCI type
                    # 2 bytes: handle + flags
                    # 2 bytes: data length
                    # Then L2CAP header (4 bytes): length + CID
                    # Then ATT data
                    
                    acl_handle = struct.unpack('<H', pkt_data[1:3])[0] & 0x0FFF
                    acl_len = struct.unpack('<H', pkt_data[3:5])[0]
                    
                    if len(pkt_data) >= 9:
                        l2cap_len = struct.unpack('<H', pkt_data[5:7])[0]
                        l2cap_cid = struct.unpack('<H', pkt_data[7:9])[0]
                        
                        # CID 0x0004 is ATT (Attribute Protocol)
                        if l2cap_cid == 0x0004 and len(pkt_data) > 9:
                            att_data = pkt_data[9:]
                            att_opcode = att_data[0]
                            
                            direction = "TX" if (flags & 0x01) == 0 else "RX"
                            
                            if att_opcode == ATT_WRITE_CMD and len(att_data) >= 3:
                                # Write Command: opcode (1) + handle (2) + data
                                handle = struct.unpack('<H', att_data[1:3])[0]
                                write_data = att_data[3:]
                                att_writes.append({
                                    'packet': packet_num,
                                    'direction': direction,
                                    'opcode': 'WRITE_CMD',
                                    'handle': handle,
                                    'data': write_data
                                })
                            
                            elif att_opcode == ATT_WRITE_REQ and len(att_data) >= 3:
                                # Write Request: opcode (1) + handle (2) + data
                                handle = struct.unpack('<H', att_data[1:3])[0]
                                write_data = att_data[3:]
                                att_writes.append({
                                    'packet': packet_num,
                                    'direction': direction,
                                    'opcode': 'WRITE_REQ',
                                    'handle': handle,
                                    'data': write_data
                                })
                            
                            elif att_opcode == ATT_HANDLE_VALUE_NTF and len(att_data) >= 3:
                                # Notification: opcode (1) + handle (2) + data
                                handle = struct.unpack('<H', att_data[1:3])[0]
                                ntf_data = att_data[3:]
                                att_notifications.append({
                                    'packet': packet_num,
                                    'direction': direction,
                                    'opcode': 'NOTIFICATION',
                                    'handle': handle,
                                    'data': ntf_data
                                })
        
        print(f"=" * 80)
        print(f"BTSNOOP ANALYSIS RESULTS")
        print(f"=" * 80)
        print(f"Total packets: {packet_num}")
        print(f"ATT Write commands found: {len(att_writes)}")
        print(f"ATT Notifications found: {len(att_notifications)}")
        print()
        
        # Print writes
        if att_writes:
            print(f"=" * 80)
            print(f"ATT WRITE COMMANDS (Phone -> Printer)")
            print(f"=" * 80)
            
            # Group by handle
            handles = {}
            for w in att_writes:
                h = w['handle']
                if h not in handles:
                    handles[h] = []
                handles[h].append(w)
            
            for handle, writes in sorted(handles.items()):
                print(f"\n--- Handle 0x{handle:04X} ({len(writes)} writes) ---")
                for i, w in enumerate(writes[:20]):  # Show first 20
                    hex_data = ' '.join(f'{b:02X}' for b in w['data'])
                    ascii_data = ''.join(chr(b) if 32 <= b < 127 else '.' for b in w['data'])
                    print(f"  [{w['packet']:5d}] {w['direction']} {w['opcode']:10s}: {hex_data[:60]}{'...' if len(hex_data) > 60 else ''}")
                    if len(w['data']) <= 20:
                        print(f"           ASCII: {ascii_data}")
                
                if len(writes) > 20:
                    print(f"  ... and {len(writes) - 20} more writes")
        
        # Print notifications
        if att_notifications:
            print(f"\n" + "=" * 80)
            print(f"ATT NOTIFICATIONS (Printer -> Phone)")
            print(f"=" * 80)
            
            # Group by handle
            handles = {}
            for n in att_notifications:
                h = n['handle']
                if h not in handles:
                    handles[h] = []
                handles[h].append(n)
            
            for handle, ntfs in sorted(handles.items()):
                print(f"\n--- Handle 0x{handle:04X} ({len(ntfs)} notifications) ---")
                for i, n in enumerate(ntfs[:10]):  # Show first 10
                    hex_data = ' '.join(f'{b:02X}' for b in n['data'])
                    print(f"  [{n['packet']:5d}] {n['direction']} {n['opcode']:12s}: {hex_data[:60]}{'...' if len(hex_data) > 60 else ''}")
                
                if len(ntfs) > 10:
                    print(f"  ... and {len(ntfs) - 10} more notifications")
        
        # Try to identify protocol patterns
        print(f"\n" + "=" * 80)
        print(f"PROTOCOL ANALYSIS")
        print(f"=" * 80)
        
        if att_writes:
            # Find unique starting bytes
            start_bytes = {}
            for w in att_writes:
                if len(w['data']) > 0:
                    start = w['data'][0]
                    if start not in start_bytes:
                        start_bytes[start] = 0
                    start_bytes[start] += 1
            
            print("\nCommon starting bytes in write data:")
            for byte, count in sorted(start_bytes.items(), key=lambda x: -x[1])[:10]:
                print(f"  0x{byte:02X} ({byte:3d}): {count} occurrences")
            
            # Find data length distribution
            print("\nWrite data length distribution:")
            lengths = {}
            for w in att_writes:
                l = len(w['data'])
                if l not in lengths:
                    lengths[l] = 0
                lengths[l] += 1
            
            for length, count in sorted(lengths.items())[:15]:
                print(f"  {length:4d} bytes: {count} writes")
        
        return att_writes, att_notifications

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <btsnoop.log>")
        sys.exit(1)
    
    parse_btsnoop(sys.argv[1])

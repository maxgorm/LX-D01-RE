#!/usr/bin/env python3
"""
Comprehensive btsnoop log parser - inspect all packet types.
"""
import struct
import sys

BTSNOOP_HEADER = b'btsnoop\x00'

def parse_btsnoop_all(filename):
    """Parse btsnoop file and show all packet types."""
    
    with open(filename, 'rb') as f:
        # Read and verify header
        header = f.read(8)
        if header != BTSNOOP_HEADER:
            print(f"Invalid btsnoop header: {header.hex()}")
            return
        
        # Read version and datalink type
        version, datalink = struct.unpack('>II', f.read(8))
        print(f"BTSnoop version: {version}, datalink type: {datalink}")
        print()
        
        packet_num = 0
        packet_types = {}
        acl_packets = []
        
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
            
            if len(pkt_data) > 0:
                hci_type = pkt_data[0]
                if hci_type not in packet_types:
                    packet_types[hci_type] = []
                packet_types[hci_type].append({
                    'num': packet_num,
                    'flags': flags,
                    'data': pkt_data
                })
                
                # Save ACL packets for detailed analysis
                if hci_type == 0x02:
                    acl_packets.append({
                        'num': packet_num,
                        'flags': flags,
                        'data': pkt_data
                    })
        
        print(f"=" * 80)
        print(f"PACKET TYPE SUMMARY")
        print(f"=" * 80)
        print(f"Total packets: {packet_num}")
        print()
        
        type_names = {
            0x01: "HCI Command",
            0x02: "HCI ACL Data",
            0x03: "HCI SCO Data",
            0x04: "HCI Event"
        }
        
        for pkt_type, packets in sorted(packet_types.items()):
            name = type_names.get(pkt_type, f"Unknown (0x{pkt_type:02X})")
            print(f"  {name}: {len(packets)} packets")
        
        # Analyze ACL packets more deeply
        if acl_packets:
            print(f"\n" + "=" * 80)
            print(f"ACL PACKET ANALYSIS ({len(acl_packets)} packets)")
            print(f"=" * 80)
            
            l2cap_cids = {}
            
            for pkt in acl_packets:
                data = pkt['data']
                if len(data) >= 9:
                    # ACL: type(1) + handle(2) + len(2) + L2CAP: len(2) + CID(2)
                    l2cap_cid = struct.unpack('<H', data[7:9])[0]
                    if l2cap_cid not in l2cap_cids:
                        l2cap_cids[l2cap_cid] = []
                    l2cap_cids[l2cap_cid].append(pkt)
            
            cid_names = {
                0x0001: "L2CAP Signaling",
                0x0004: "ATT (Attribute Protocol)",
                0x0005: "L2CAP LE Signaling",
                0x0006: "SMP (Security Manager)"
            }
            
            print("\nL2CAP Channel IDs found:")
            for cid, packets in sorted(l2cap_cids.items()):
                name = cid_names.get(cid, f"Dynamic CID")
                print(f"  CID 0x{cid:04X} ({name}): {len(packets)} packets")
            
            # Focus on ATT (CID 0x0004)
            att_packets = l2cap_cids.get(0x0004, [])
            if att_packets:
                print(f"\n" + "=" * 80)
                print(f"ATT PACKET DETAILS ({len(att_packets)} packets)")
                print(f"=" * 80)
                
                att_opcodes = {}
                
                for pkt in att_packets:
                    data = pkt['data']
                    if len(data) > 9:
                        att_data = data[9:]
                        if len(att_data) > 0:
                            opcode = att_data[0]
                            if opcode not in att_opcodes:
                                att_opcodes[opcode] = []
                            att_opcodes[opcode].append({
                                'num': pkt['num'],
                                'flags': pkt['flags'],
                                'att_data': att_data
                            })
                
                opcode_names = {
                    0x01: "Error Response",
                    0x02: "Exchange MTU Request",
                    0x03: "Exchange MTU Response",
                    0x04: "Find Info Request",
                    0x05: "Find Info Response",
                    0x06: "Find By Type Value Request",
                    0x07: "Find By Type Value Response",
                    0x08: "Read By Type Request",
                    0x09: "Read By Type Response",
                    0x0A: "Read Request",
                    0x0B: "Read Response",
                    0x0C: "Read Blob Request",
                    0x0D: "Read Blob Response",
                    0x10: "Read By Group Type Request",
                    0x11: "Read By Group Type Response",
                    0x12: "Write Request",
                    0x13: "Write Response",
                    0x16: "Prepare Write Request",
                    0x17: "Prepare Write Response",
                    0x18: "Execute Write Request",
                    0x19: "Execute Write Response",
                    0x1B: "Handle Value Notification",
                    0x1D: "Handle Value Indication",
                    0x1E: "Handle Value Confirmation",
                    0x52: "Write Command (No Response)"
                }
                
                print("\nATT Opcodes found:")
                for opcode, packets in sorted(att_opcodes.items()):
                    name = opcode_names.get(opcode, "Unknown")
                    print(f"  0x{opcode:02X} ({name}): {len(packets)} packets")
                
                # Show Write Commands (0x52) - these are the print data!
                write_cmds = att_opcodes.get(0x52, [])
                if write_cmds:
                    print(f"\n" + "-" * 80)
                    print(f"WRITE COMMAND PACKETS (0x52) - PRINTER DATA!")
                    print(f"-" * 80)
                    
                    # Group by handle
                    handles = {}
                    for w in write_cmds:
                        att_data = w['att_data']
                        if len(att_data) >= 3:
                            handle = struct.unpack('<H', att_data[1:3])[0]
                            if handle not in handles:
                                handles[handle] = []
                            handles[handle].append({
                                'num': w['num'],
                                'flags': w['flags'],
                                'data': att_data[3:]
                            })
                    
                    for handle, writes in sorted(handles.items()):
                        print(f"\n=== Handle 0x{handle:04X} ({len(writes)} writes) ===")
                        
                        for i, w in enumerate(writes[:30]):
                            direction = "TX" if (w['flags'] & 0x01) == 0 else "RX"
                            hex_data = ' '.join(f'{b:02X}' for b in w['data'][:40])
                            more = "..." if len(w['data']) > 40 else ""
                            print(f"  [{w['num']:5d}] {direction}: {hex_data}{more} ({len(w['data'])} bytes)")
                        
                        if len(writes) > 30:
                            print(f"  ... and {len(writes) - 30} more writes")
                        
                        # Analyze first few bytes pattern
                        print(f"\n  First byte distribution:")
                        first_bytes = {}
                        for w in writes:
                            if len(w['data']) > 0:
                                fb = w['data'][0]
                                if fb not in first_bytes:
                                    first_bytes[fb] = 0
                                first_bytes[fb] += 1
                        
                        for byte, count in sorted(first_bytes.items(), key=lambda x: -x[1])[:5]:
                            print(f"    0x{byte:02X}: {count} times")
                
                # Show Write Requests (0x12)
                write_reqs = att_opcodes.get(0x12, [])
                if write_reqs:
                    print(f"\n" + "-" * 80)
                    print(f"WRITE REQUEST PACKETS (0x12)")
                    print(f"-" * 80)
                    
                    for w in write_reqs[:20]:
                        att_data = w['att_data']
                        if len(att_data) >= 3:
                            handle = struct.unpack('<H', att_data[1:3])[0]
                            data = att_data[3:]
                            direction = "TX" if (w['flags'] & 0x01) == 0 else "RX"
                            hex_data = ' '.join(f'{b:02X}' for b in data)
                            print(f"  [{w['num']:5d}] {direction} Handle 0x{handle:04X}: {hex_data}")
                
                # Show Notifications (0x1B) - printer responses
                notifications = att_opcodes.get(0x1B, [])
                if notifications:
                    print(f"\n" + "-" * 80)
                    print(f"NOTIFICATION PACKETS (0x1B) - PRINTER RESPONSES!")
                    print(f"-" * 80)
                    
                    for n in notifications[:30]:
                        att_data = n['att_data']
                        if len(att_data) >= 3:
                            handle = struct.unpack('<H', att_data[1:3])[0]
                            data = att_data[3:]
                            direction = "TX" if (n['flags'] & 0x01) == 0 else "RX"
                            hex_data = ' '.join(f'{b:02X}' for b in data)
                            print(f"  [{n['num']:5d}] {direction} Handle 0x{handle:04X}: {hex_data}")
                    
                    if len(notifications) > 30:
                        print(f"  ... and {len(notifications) - 30} more")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <btsnoop.log>")
        sys.exit(1)
    
    parse_btsnoop_all(sys.argv[1])

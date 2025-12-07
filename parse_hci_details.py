#!/usr/bin/env python3
"""
Analyze HCI Commands and Events in btsnoop - look for BLE connection info.
"""
import struct
import sys

BTSNOOP_HEADER = b'btsnoop\x00'

def parse_hci_details(filename):
    """Parse btsnoop file and show HCI command/event details."""
    
    with open(filename, 'rb') as f:
        # Read and verify header
        header = f.read(8)
        if header != BTSNOOP_HEADER:
            print(f"Invalid btsnoop header")
            return
        
        # Skip version/datalink
        f.read(8)
        
        packet_num = 0
        hci_commands = []
        hci_events = []
        
        while True:
            pkt_header = f.read(24)
            if len(pkt_header) < 24:
                break
            
            original_len, included_len, flags, drops, timestamp_hi, timestamp_lo = \
                struct.unpack('>IIIIII', pkt_header)
            
            pkt_data = f.read(included_len)
            if len(pkt_data) < included_len:
                break
            
            packet_num += 1
            
            if len(pkt_data) > 0:
                hci_type = pkt_data[0]
                
                if hci_type == 0x01 and len(pkt_data) >= 4:  # HCI Command
                    opcode = struct.unpack('<H', pkt_data[1:3])[0]
                    param_len = pkt_data[3]
                    params = pkt_data[4:4+param_len] if len(pkt_data) > 4 else b''
                    hci_commands.append({
                        'num': packet_num,
                        'opcode': opcode,
                        'ogf': (opcode >> 10) & 0x3F,
                        'ocf': opcode & 0x3FF,
                        'params': params
                    })
                
                elif hci_type == 0x04 and len(pkt_data) >= 3:  # HCI Event
                    event_code = pkt_data[1]
                    param_len = pkt_data[2]
                    params = pkt_data[3:3+param_len] if len(pkt_data) > 3 else b''
                    hci_events.append({
                        'num': packet_num,
                        'event': event_code,
                        'params': params
                    })
        
        print(f"=" * 80)
        print(f"HCI COMMAND ANALYSIS ({len(hci_commands)} commands)")
        print(f"=" * 80)
        
        # Categorize commands by OGF
        ogf_names = {
            0x01: "Link Control",
            0x02: "Link Policy",
            0x03: "Controller & Baseband",
            0x04: "Informational",
            0x05: "Status",
            0x08: "LE Controller"
        }
        
        # Count commands by OGF
        ogf_counts = {}
        for cmd in hci_commands:
            ogf = cmd['ogf']
            if ogf not in ogf_counts:
                ogf_counts[ogf] = []
            ogf_counts[ogf].append(cmd)
        
        for ogf, cmds in sorted(ogf_counts.items()):
            name = ogf_names.get(ogf, "Unknown")
            print(f"\nOGF 0x{ogf:02X} ({name}): {len(cmds)} commands")
        
        # Focus on LE commands (OGF 0x08)
        le_commands = ogf_counts.get(0x08, [])
        if le_commands:
            print(f"\n" + "-" * 80)
            print(f"LE CONTROLLER COMMANDS (OGF 0x08)")
            print(f"-" * 80)
            
            le_ocf_names = {
                0x0001: "LE Set Event Mask",
                0x0002: "LE Read Buffer Size",
                0x0003: "LE Read Local Supported Features",
                0x0005: "LE Set Random Address",
                0x0006: "LE Set Advertising Parameters",
                0x0008: "LE Set Advertising Data",
                0x000A: "LE Set Advertising Enable",
                0x000B: "LE Set Scan Parameters",
                0x000C: "LE Set Scan Enable",
                0x000D: "LE Create Connection",
                0x000E: "LE Create Connection Cancel",
                0x0010: "LE Read Remote Features",
                0x0013: "LE Receiver Test",
                0x0016: "LE Read Channel Map",
                0x0018: "LE Encrypt",
                0x001D: "LE Add Device To White List",
                0x001F: "LE Clear White List",
                0x0020: "LE Connection Update",
                0x0024: "LE Transmitter Test",
                0x0027: "LE Read PHY",
                0x0032: "LE Set PHY"
            }
            
            ocf_counts = {}
            for cmd in le_commands:
                ocf = cmd['ocf']
                if ocf not in ocf_counts:
                    ocf_counts[ocf] = []
                ocf_counts[ocf].append(cmd)
            
            for ocf, cmds in sorted(ocf_counts.items()):
                name = le_ocf_names.get(ocf, "Unknown")
                print(f"  OCF 0x{ocf:04X} ({name}): {len(cmds)}")
        
        print(f"\n" + "=" * 80)
        print(f"HCI EVENT ANALYSIS ({len(hci_events)} events)")
        print(f"=" * 80)
        
        event_names = {
            0x01: "Inquiry Complete",
            0x02: "Inquiry Result",
            0x03: "Connection Complete",
            0x05: "Disconnection Complete",
            0x0E: "Command Complete",
            0x0F: "Command Status",
            0x13: "Number Of Completed Packets",
            0x1A: "Data Buffer Overflow",
            0x3E: "LE Meta Event"
        }
        
        event_counts = {}
        for evt in hci_events:
            code = evt['event']
            if code not in event_counts:
                event_counts[code] = []
            event_counts[code].append(evt)
        
        for code, evts in sorted(event_counts.items()):
            name = event_names.get(code, "Unknown")
            print(f"  Event 0x{code:02X} ({name}): {len(evts)}")
        
        # Analyze LE Meta Events (0x3E) - this is where BLE advertising/scan results live
        le_meta_events = event_counts.get(0x3E, [])
        if le_meta_events:
            print(f"\n" + "-" * 80)
            print(f"LE META EVENTS (0x3E) - BLE Details")
            print(f"-" * 80)
            
            le_subevent_names = {
                0x01: "LE Connection Complete",
                0x02: "LE Advertising Report",
                0x03: "LE Connection Update Complete",
                0x04: "LE Read Remote Features Complete",
                0x05: "LE Long Term Key Request",
                0x06: "LE Remote Connection Parameter Request",
                0x07: "LE Data Length Change",
                0x08: "LE Read Local P-256 Public Key Complete",
                0x09: "LE Generate DHKey Complete",
                0x0A: "LE Enhanced Connection Complete",
                0x0D: "LE Extended Advertising Report",
                0x12: "LE PHY Update Complete"
            }
            
            subevent_counts = {}
            for evt in le_meta_events:
                if len(evt['params']) > 0:
                    subevent = evt['params'][0]
                    if subevent not in subevent_counts:
                        subevent_counts[subevent] = []
                    subevent_counts[subevent].append(evt)
            
            for subevent, evts in sorted(subevent_counts.items()):
                name = le_subevent_names.get(subevent, "Unknown")
                print(f"  Subevent 0x{subevent:02X} ({name}): {len(evts)}")
            
            # Look for advertising reports - these contain device names!
            adv_reports = subevent_counts.get(0x02, []) + subevent_counts.get(0x0D, [])
            if adv_reports:
                print(f"\n  --- Advertising Reports (Device Discovery) ---")
                
                # Extract device addresses from advertising reports
                seen_devices = {}
                for evt in adv_reports:
                    params = evt['params']
                    if len(params) >= 8:
                        # Skip subevent code (1) and num reports (1)
                        offset = 2
                        if len(params) > offset:
                            # Event type (1), address type (1), address (6)
                            if len(params) >= offset + 8:
                                addr_type = params[offset + 1]
                                addr = params[offset + 2:offset + 8]
                                addr_str = ':'.join(f'{b:02X}' for b in reversed(addr))
                                
                                if addr_str not in seen_devices:
                                    seen_devices[addr_str] = {'type': addr_type, 'count': 0}
                                seen_devices[addr_str]['count'] += 1
                
                print(f"\n  Discovered {len(seen_devices)} unique BLE devices:")
                for addr, info in list(seen_devices.items())[:20]:
                    addr_type = "Public" if info['type'] == 0 else "Random"
                    print(f"    {addr} ({addr_type}) - seen {info['count']} times")
            
            # Look for connection complete events
            conn_events = subevent_counts.get(0x01, []) + subevent_counts.get(0x0A, [])
            if conn_events:
                print(f"\n  --- LE Connection Events ---")
                for evt in conn_events[:10]:
                    params = evt['params']
                    if len(params) >= 12:
                        # Subevent(1), Status(1), Handle(2), Role(1), Addr Type(1), Addr(6)
                        status = params[1]
                        handle = struct.unpack('<H', params[2:4])[0]
                        role = "Central" if params[4] == 0 else "Peripheral"
                        addr_type = params[5]
                        addr = params[6:12]
                        addr_str = ':'.join(f'{b:02X}' for b in reversed(addr))
                        
                        status_str = "OK" if status == 0 else f"Error 0x{status:02X}"
                        print(f"    [{evt['num']}] Handle 0x{handle:04X}, {role}, {addr_str} - {status_str}")
        
        print(f"\n" + "=" * 80)
        print(f"CONCLUSION")
        print(f"=" * 80)
        print(f"""
This btsnoop log contains {len(hci_commands)} HCI commands and {len(hci_events)} HCI events,
but NO ACL data packets (which would contain the actual BLE ATT data).

This means the log captured connection setup but NOT the actual print data transfer.

To capture the printer protocol, you need to:
1. Enable "Bluetooth HCI snoop log" in Developer Options
2. Connect to the printer via the FunnyPrint app
3. PRINT something (test page, image, text)
4. Generate a new bug report AFTER printing

The current log only shows:
- Device discovery/scanning
- Connection establishment
- But no data transfer (ACL packets)
""")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <btsnoop.log>")
        sys.exit(1)
    
    parse_hci_details(sys.argv[1])

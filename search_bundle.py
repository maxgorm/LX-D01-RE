import os
import re

def search_bundle(filepath):
    """Search the React Native bundle for BLE and printer patterns"""
    
    with open(filepath, 'rb') as f:
        content = f.read()
    
    # Convert to string for easier searching
    # The bundle is minified JS, so we search for patterns
    
    patterns = {
        # UUIDs - these are the key!
        'ffe0': b'ffe0',
        'ffe1': b'ffe1', 
        'ffe2': b'ffe2',
        'ffe6': b'ffe6',
        'FFE0': b'FFE0',
        'FFE1': b'FFE1',
        'FFE2': b'FFE2',
        'FFE6': b'FFE6',
        'fff0': b'fff0',
        'FFF0': b'FFF0',
        
        # Service/Characteristic patterns
        '0000ffe': b'0000ffe',
        '0000FFE': b'0000FFE',
        
        # Magic bytes in various forms
        '0x5a': b'0x5a',
        '0x5A': b'0x5A',
        '90,': b'90,',  # decimal
        '[90': b'[90',  # array start
        '\\x5a': b'\\x5a',
        '\\x5A': b'\\x5A',
        '5a02': b'5a02',
        '5A02': b'5A02',
        
        # CRC patterns
        'crc8': b'crc8',
        'CRC8': b'CRC8',
        'crc': b'crc',
        'checksum': b'checksum',
        'xor': b'xor',
        
        # Print-related
        'writeCharacteristic': b'writeCharacteristic',
        'writeWithoutResponse': b'writeWithoutResponse',
        'writeWithResponse': b'writeWithResponse',
        'monitorCharacteristic': b'monitorCharacteristic',
        
        # React Native BLE libraries
        'react-native-ble-plx': b'react-native-ble-plx',
        'react-native-ble-manager': b'react-native-ble-manager',
        'BleManager': b'BleManager',
        
        # Printer-related strings
        'LX-D01': b'LX-D01',
        'printer': b'printer',
        'Printer': b'Printer',
        'thermal': b'thermal',
        'printData': b'printData',
        'sendData': b'sendData',
        
        # Command building patterns
        'Uint8Array': b'Uint8Array',
        'ArrayBuffer': b'ArrayBuffer',
        'DataView': b'DataView',
        'Buffer.from': b'Buffer.from',
        'Buffer.alloc': b'Buffer.alloc',
    }
    
    print(f"Searching {filepath}...")
    print(f"File size: {len(content)} bytes\n")
    
    for name, pattern in patterns.items():
        matches = []
        idx = 0
        while True:
            idx = content.find(pattern, idx)
            if idx == -1:
                break
            matches.append(idx)
            idx += 1
        
        if matches:
            print(f"[FOUND] '{name}': {len(matches)} occurrence(s)")
            # Show context for first few matches
            for i, match_idx in enumerate(matches[:3]):
                start = max(0, match_idx - 60)
                end = min(len(content), match_idx + len(pattern) + 100)
                context = content[start:end]
                try:
                    context_str = context.decode('utf-8', errors='replace')
                    # Clean non-printable
                    context_str = ''.join(c if c.isprintable() or c in '\n\r\t' else '.' for c in context_str)
                    print(f"  [{i+1}] ...{context_str}...")
                except:
                    pass
            print()

    # Special search: find any 4-digit hex patterns that look like BLE UUIDs
    print("\n" + "="*80)
    print("SEARCHING FOR POTENTIAL 16-BIT BLE UUID PATTERNS")
    print("="*80)
    
    # Pattern for 16-bit UUID in full format: 0000XXXX-0000-1000-8000
    uuid_pattern = rb'0000[0-9a-fA-F]{4}-0000-1000-8000'
    uuid_matches = re.findall(uuid_pattern, content)
    if uuid_matches:
        print(f"Found {len(uuid_matches)} potential BLE UUIDs:")
        for uuid in set(uuid_matches):
            print(f"  {uuid.decode()}")
    
    # Also search for short UUIDs in quotes
    short_uuid_pattern = rb'["\'][fF]{2}[eEfF][0-9a-fA-F]["\']'
    short_matches = re.findall(short_uuid_pattern, content)
    if short_matches:
        print(f"\nFound {len(short_matches)} potential short UUIDs:")
        for uuid in set(short_matches):
            print(f"  {uuid.decode()}")

    # Search for byte array initialization with 0x5A or 90
    print("\n" + "="*80)
    print("SEARCHING FOR COMMAND PACKET PATTERNS")
    print("="*80)
    
    # Look for patterns like [90, or new Uint8Array([90
    cmd_patterns = [
        rb'\[90\s*,\s*\d+',  # [90, X
        rb'\[0x5[aA]\s*,',   # [0x5a, or [0x5A,
        rb'90\s*,\s*2\s*,',  # 90, 2,  (5A 02)
        rb'90\s*,\s*11\s*,', # 90, 11, (5A 0B)
    ]
    
    for pat in cmd_patterns:
        matches = list(re.finditer(pat, content))
        if matches:
            print(f"\nPattern {pat.decode()}: {len(matches)} matches")
            for m in matches[:5]:
                start = max(0, m.start() - 50)
                end = min(len(content), m.end() + 100)
                context = content[start:end].decode('utf-8', errors='replace')
                context = ''.join(c if c.isprintable() else '.' for c in context)
                print(f"  ...{context}...")

if __name__ == "__main__":
    bundle_path = r"c:\Users\maxgo\Downloads\Sentimo\funnyprint_apk\assets\index.android.bundle"
    search_bundle(bundle_path)

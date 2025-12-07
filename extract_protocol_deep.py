#!/usr/bin/env python3
"""
Deep protocol extraction from FunnyPrint APK.
Focus on BLE write operations and command sequences.
"""

import os
import struct
import re
from pathlib import Path
from androguard.core.dex import DEX

APK_DIR = Path(r"c:\Users\maxgo\Downloads\Sentimo\funnyprint_apk")
BUNDLE_FILE = APK_DIR / "assets" / "index.android.bundle"

print("\n" + "=" * 80)
print("PHASE 1: EXTRACTING BLE SERVICE/CHARACTERISTIC UUIDs")
print("=" * 80)

# Parse all DEX files for UUID strings
all_dex_files = sorted(APK_DIR.glob("classes*.dex"))
uuids_by_hex = {}

for dex_file in all_dex_files:
    print(f"\nAnalyzing {dex_file.name}...")
    try:
        d = DEX(dex_file.read_bytes())
        for string_val in d.get_strings():
            # Look for UUID patterns
            if string_val and len(string_val) >= 8:
                # Match full UUIDs or partial patterns
                if re.match(r'^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$', string_val.lower()):
                    if 'fff' in string_val.lower() or '5833' in string_val:
                        uuids_by_hex[string_val] = True
                        print(f"  Found UUID: {string_val}")
                # Also check for 4-character UUID shortcuts
                elif re.match(r'^[0-9a-f]{4}$', string_val) and int(string_val, 16) > 0:
                    if 'fff' in string_val.lower() or '5833' in string_val.lower():
                        uuids_by_hex[string_val] = True
                        print(f"  Found short UUID: {string_val}")
    except Exception as e:
        print(f"  Error: {e}")

print("\n" + "=" * 80)
print("PHASE 2: SEARCHING FOR COMMAND/WRITE SEQUENCES IN REACT NATIVE BUNDLE")
print("=" * 80)

# Search React Native bundle for command patterns
if BUNDLE_FILE.exists():
    print(f"\nAnalyzing React Native bundle: {BUNDLE_FILE.name}")
    bundle_data = BUNDLE_FILE.read_bytes()
    
    # Look for common printer command patterns
    # ESC sequences, device control codes, print data markers
    patterns_to_search = [
        (b'\x1b@', 'ESC @ (Initialize)'),
        (b'\x1b\x7c', 'ESC | (GS)'),
        (b'\x1d\x21', 'GS ! (character size)'),
        (b'\x1d\x42', 'GS B (white/black mode)'),
        (b'\x1d\x49', 'GS I (transmit status)'),
        (b'\x1d\x4a', 'GS J (execute macro)'),
        (b'\x1d\x4c', 'GS L (label function)'),
        (b'\x1d\x56', 'GS V (select cut mode)'),
        (b'\x1d\x57', 'GS W (set label width)'),
        (b'\x1d\x28\x43', 'GS (C (NFC/RFID)'),
        (b'\x1b\x25\x00', 'ESC % (Default font)'),
        (b'\x1b\x25\x01', 'ESC % (NLQ font)'),
    ]
    
    print("\n  Searching for ESC/GS command sequences...")
    for pattern, description in patterns_to_search:
        count = bundle_data.count(pattern)
        if count > 0:
            print(f"    {description}: {count} occurrences")
            # Find positions
            pos = 0
            occurrences = []
            for _ in range(min(3, count)):  # Show first 3 occurrences
                pos = bundle_data.find(pattern, pos)
                if pos >= 0:
                    # Get surrounding context (20 bytes before and after)
                    start = max(0, pos - 20)
                    end = min(len(bundle_data), pos + len(pattern) + 20)
                    context = bundle_data[start:end]
                    occurrences.append((pos, context))
                    pos += 1
            
            if occurrences:
                for occ_pos, context in occurrences[:1]:
                    hex_context = ' '.join(f'{b:02x}' for b in context)
                    print(f"      @ offset {occ_pos}: ...{hex_context}...")

print("\n" + "=" * 80)
print("PHASE 3: SEARCHING FOR LX-D01 SPECIFIC PATTERNS")
print("=" * 80)

# LX-D01 specific patterns (from previous research)
lx_patterns = {
    'init_sequence': [0x1b, 0x40],  # ESC @
    'font_size': [0x1d, 0x21, 0x00],  # GS ! (normal font)
    'mode': [0x1b, 0x21, 0x00],  # ESC ! (normal mode)
    'quality_command': [0x1d, 0x7e, 0x03],  # Possible quality
    'print_density': [0x1d, 0x7c],  # GS | (?)
    'line_feed': [0x0a],  # LF
    'form_feed': [0x0c],  # FF
}

for name, pattern_bytes in lx_patterns.items():
    pattern = bytes(pattern_bytes)
    count = bundle_data.count(pattern)
    if count > 0:
        print(f"  {name} {pattern.hex()}: {count} occurrences")

print("\n" + "=" * 80)
print("PHASE 4: EXAMINING JAVA CODE FOR WRITE FUNCTIONS")
print("=" * 80)

# Search DEX files for method implementations
for dex_file in all_dex_files[:2]:  # Check first 2 DEX files
    print(f"\nScanning {dex_file.name} for write methods...")
    try:
        d = DEX(dex_file.read_bytes())
        
        # Get all classes
        for cls in d.get_classes():
            class_name = cls.get_name()
            
            # Look for classes related to printing/BLE
            if any(x in class_name.lower() for x in ['print', 'ble', 'write', 'send', 'cmd']):
                methods = cls.get_methods()
                if methods:
                    print(f"\n  Class: {class_name}")
                    for method in methods:
                        method_name = method.get_name()
                        if any(x in method_name.lower() for x in ['send', 'write', 'cmd', 'data', 'print']):
                            print(f"    Method: {method_name}")
                            
                            # Try to get source code
                            try:
                                source = method.get_source()
                                if source and len(source) < 500:
                                    lines = source.split('\n')[:5]
                                    for line in lines:
                                        if line.strip():
                                            print(f"      {line[:100]}")
                            except:
                                pass
                                
    except Exception as e:
        print(f"  Error: {e}")

print("\n" + "=" * 80)
print("EXTRACTION COMPLETE")
print("=" * 80)
print("\nRecommendation: Use online DEX decompiler on classes2.dex for printer SDK")
print("visit: https://www.decompiler.com/")
print("Upload classes2.dex to see the com.ask.printersdk classes")

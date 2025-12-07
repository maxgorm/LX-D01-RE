#!/usr/bin/env python3
"""
Extract LX-D01 printer protocol from FunnyPrint APK DEX files.
Uses androguard to parse DEX bytecode.
"""

import os
import sys
import re
from pathlib import Path
from androguard.misc import AnalyzeAPK
from androguard.core.dex import DEX

# Path to the extracted APK
APK_DIR = Path(r"c:\Users\maxgo\Downloads\Sentimo\funnyprint_apk")

print("=" * 80)
print("LX-D01 PRINTER PROTOCOL EXTRACTION TOOL")
print("=" * 80)

# First, let's search the DEX files for key strings
dex_files = list(APK_DIR.glob("classes*.dex"))
print(f"\nFound {len(dex_files)} DEX files:\n")

all_strings = set()
protocol_candidates = {
    'uuids': set(),
    'command_bytes': set(),
    'function_calls': set(),
    'write_operations': set(),
}

for dex_file in sorted(dex_files):
    print(f"Analyzing {dex_file.name}...")
    try:
        d = DEX(dex_file.read_bytes())
        
        # Extract all strings from the DEX file
        for string_value in d.get_strings():
            if string_value:
                all_strings.add(string_value)
                
                # Look for UUIDs
                if "ffe" in string_value.lower() or "5833" in string_value:
                    protocol_candidates['uuids'].add(string_value)
                
                # Look for command-related strings
                if any(x in string_value.lower() for x in ['send', 'write', 'command', 'data', 'print', 'byte']):
                    protocol_candidates['function_calls'].add(string_value)
                    
    except Exception as e:
        print(f"  Error analyzing {dex_file.name}: {e}")

print("\n" + "=" * 80)
print("EXTRACTED STRINGS - UUIDs AND SERVICE IDENTIFIERS")
print("=" * 80)
for uuid in sorted(protocol_candidates['uuids']):
    print(f"  {uuid}")

print("\n" + "=" * 80)
print("EXTRACTED STRINGS - COMMAND/DATA RELATED FUNCTIONS")
print("=" * 80)
relevant_functions = [s for s in protocol_candidates['function_calls'] 
                     if len(s) > 10 and not s.startswith('/')]
for func in sorted(relevant_functions)[:30]:
    print(f"  {func}")

print("\n" + "=" * 80)
print("SEARCHING FOR BYTE ARRAYS AND COMMAND PATTERNS")
print("=" * 80)

# Look for numeric patterns that might represent byte commands
for dex_file in sorted(dex_files):
    print(f"\nSearching {dex_file.name} for byte patterns...")
    try:
        dex_bytes = dex_file.read_bytes()
        
        # Search for common patterns
        # ESC (0x1B), Device control (0xA0-0xA1), etc.
        patterns = [
            (b'\x1b', 'ESC (0x1B)'),
            (b'\xa0', 'Device control (0xA0)'),
            (b'\xa1', 'Device control (0xA1)'),
            (b'\x5a', 'Command marker (0x5A)'),
            (b'\xbe', 'Possible command (0xBE)'),
            (b'\xff\xe6', 'UUID marker FFE6'),
            (b'\xff\xe1', 'UUID marker FFE1'),
        ]
        
        for pattern, desc in patterns:
            count = dex_bytes.count(pattern)
            if count > 0:
                print(f"  Found {desc}: {count} occurrences")
                
    except Exception as e:
        print(f"  Error: {e}")

print("\n" + "=" * 80)
print("EXTRACTION COMPLETE")
print("=" * 80)
print(f"\nTotal unique strings found: {len(all_strings)}")
print(f"Potential UUIDs: {len(protocol_candidates['uuids'])}")
print(f"Potential functions: {len(protocol_candidates['function_calls'])}")

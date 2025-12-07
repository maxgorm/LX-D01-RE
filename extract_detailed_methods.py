#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated DEX to Smali conversion (disassembly) for protocol analysis
This doesn't require external tools, just uses androguard's built-in capabilities
"""

import os
import sys
from pathlib import Path
from androguard.core.dex import DEX
from androguard.core.analysis.analysis import Analysis

# Fix encoding for Windows
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

APK_DIR = Path(r"c:\Users\maxgo\Downloads\Sentimo\funnyprint_apk")
OUTPUT_DIR = Path(r"c:\Users\maxgo\Downloads\Sentimo\decompiled_output")
OUTPUT_DIR.mkdir(exist_ok=True)

print("\n" + "="*80)
print("DEX DISASSEMBLY - PRINTER SDK FOCUS")
print("="*80)

# Focus on classes2.dex which likely contains printer SDK
target_dex = APK_DIR / "classes2.dex"

if target_dex.exists():
    print(f"\nAnalyzing {target_dex.name}...")
    d = DEX(target_dex.read_bytes())
    dx = Analysis(d)
    
    # Search for printer-related classes
    print("\nSearching for printer/BLE related classes...")
    
    output_file = OUTPUT_DIR / "classes2_extracted_methods.txt"
    with open(output_file, 'w', encoding='utf-8', errors='ignore') as f:
        f.write("="*80 + "\n")
        f.write("PRINTER AND BLE RELATED METHODS\n")
        f.write("="*80 + "\n\n")
        
        for cls in d.get_classes():
            class_name = cls.get_name()
            
            # Filter for interesting classes
            if any(keyword in class_name.lower() for keyword in [
                'printer', 'print', 'send', 'write', 'command', 'cmd', 'ble', 
                'device', 'ask', 'lx', 'thermal'
            ]):
                f.write(f"\n{'='*80}\n")
                f.write(f"CLASS: {class_name}\n")
                f.write(f"{'='*80}\n")
                
                # Get all methods
                for method in cls.get_methods():
                    method_name = method.get_name()
                    
                    f.write(f"\n  METHOD: {method_name}\n")
                    
                    # Try to get source/code
                    try:
                        source = method.get_source()
                        if source and len(source) > 0:
                            lines = source.split('\n')[:20]  # First 20 lines
                            f.write(f"  Source:\n")
                            for line in lines:
                                if line.strip():
                                    f.write(f"    {line}\n")
                    except Exception as e:
                        pass
        
        # Also extract all string constants that look like commands
        f.write("\n\n" + "="*80 + "\n")
        f.write("POTENTIALLY RELEVANT STRING CONSTANTS\n")
        f.write("="*80 + "\n\n")
        
        string_keywords = ['byte', 'command', 'send', 'print', 'ffe', '5833', 'data', 'write']
        relevant_strings = []
        
        for string_val in d.get_strings():
            if any(kw in string_val.lower() for kw in string_keywords):
                if len(string_val) > 3 and len(string_val) < 200:
                    relevant_strings.append(string_val)
        
        # Deduplicate and sort
        relevant_strings = sorted(set(relevant_strings))
        for s in relevant_strings[:100]:  # First 100 unique strings
            f.write(f"  {s}\n")

    print(f"[OK] Extracted methods saved to: {output_file}")
    print(f"     Size: {output_file.stat().st_size} bytes")
    
    # Also scan for specific method implementations
    print("\n[INFO] Looking for key method implementations...")
    
    # Get bytecode for methods of interest
    found_methods = []
    for method in dx.get_methods():
        method_name = method.get_name()
        class_name = method.get_class_name()
        
        if any(kw in method_name.lower() for kw in ['send', 'write', 'print', 'execute']):
            if any(kw in class_name.lower() for kw in ['print', 'ble', 'device', 'ask']):
                found_methods.append({
                    'class': class_name,
                    'method': method_name,
                    'proto': str(method.get_proto()),
                })
                print(f"  [FOUND] {class_name}.{method_name}()")
    
    # Write detailed method analysis
    if found_methods:
        output_file2 = OUTPUT_DIR / "KEY_METHODS_DETAIL.txt"
        with open(output_file2, 'w', encoding='utf-8', errors='ignore') as f:
            f.write("KEY SEND/WRITE/PRINT METHODS\n")
            f.write("="*80 + "\n\n")
            
            for m in found_methods:
                f.write(f"Class: {m['class']}\n")
                f.write(f"Method: {m['method']}\n")
                f.write(f"Signature: {m['proto']}\n")
                f.write("-"*40 + "\n\n")
        
        print(f"[OK] Key methods details saved to: {output_file2}")

print("\n" + "="*80)
print("[SUCCESS] EXTRACTION COMPLETE")
print("="*80)
print(f"Output directory: {OUTPUT_DIR}")
print("\n[NEXT] Use online decompiler for full source code")
print("       https://www.decompiler.com/")
print("       Upload: classes2.dex")

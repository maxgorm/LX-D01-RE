import os
import re

def main():
    filepath = r"c:\Users\maxgo\Downloads\Sentimo\funnyprint_apk\assets\index.android.bundle"
    
    with open(filepath, 'rb') as f:
        content = f.read()
    
    print("="*80)
    print("SEARCHING FOR COMMAND BYTE PATTERNS IN DECIMAL")
    print("="*80)
    
    # From the logs, we know:
    # 5A 02 = 90, 2 (status response)
    # 5A 0B = 90, 11 (some command)
    # 5A 04 = 90, 4
    # 5A 06 = 90, 6
    # 5A 07 = 90, 7
    
    # Search for these patterns as decimal numbers in arrays
    patterns_to_find = [
        # Command IDs we've seen
        (rb'\b90\b.*?\b2\b.*?\b100\b', 'Decimal pattern 90, 2, 100 (5A 02 64)'),
        (rb'\b90\b.*?\b11\b.*?\b11\b', 'Decimal pattern 90, 11, 11 (5A 0B 0B)'),
        
        # Look for "5A" in strings
        (rb'["\']5[aA]', '5A in string'),
        (rb'5[aA]\s*0[02]', '5A0x pattern'),
        
        # Look for characteristic service patterns
        (rb'service.*?ffe', 'service...ffe pattern'),
        (rb'characteristic.*?ffe', 'characteristic...ffe pattern'),
        
        # Command constants
        (rb'CMD_', 'CMD_ constants'),
        (rb'COMMAND_', 'COMMAND_ constants'),
        (rb'cmd[A-Z]', 'cmdX pattern'),
    ]
    
    for pattern, name in patterns_to_find:
        matches = list(re.finditer(pattern, content, re.IGNORECASE))
        if matches:
            print(f"\n[{name}]: {len(matches)} matches")
            for m in matches[:3]:
                start = max(0, m.start() - 50)
                end = min(len(content), m.end() + 100)
                ctx = content[start:end].decode('utf-8', errors='replace')
                ctx = ''.join(c if c.isprintable() else '.' for c in ctx)
                print(f"  ...{ctx}...")

    print("\n" + "="*80)
    print("SEARCHING FOR 'crystools' CONTEXT (app-specific code)")
    print("="*80)
    
    # 'crystools' seems to be app-specific
    idx = 0
    count = 0
    while count < 10:
        idx = content.find(b'crystools', idx)
        if idx == -1:
            break
        ctx = content[max(0, idx-100):min(len(content), idx+300)]
        try:
            s = ctx.decode('utf-8', errors='replace')
            s = ''.join(c if c.isprintable() else '.' for c in s)
            print(f"\n--- crystools occurrence {count+1} ---")
            print(s)
        except:
            pass
        idx += 1
        count += 1

    print("\n" + "="*80)
    print("SEARCHING FOR FUNCTION NAMES WITH 'print' or 'send'")
    print("="*80)
    
    # Look for function definitions
    func_patterns = [
        rb'function\s+\w*[pP]rint\w*',
        rb'function\s+\w*[sS]end\w*',
        rb'function\s+\w*[wW]rite\w*Data',
        rb'function\s+\w*[cC]rc\w*',
        rb'function\s+\w*[cC]hecksum\w*',
    ]
    
    for pattern in func_patterns:
        matches = list(re.finditer(pattern, content))
        if matches:
            print(f"\nPattern '{pattern.decode()}': {len(matches)} matches")
            for m in matches[:5]:
                start = max(0, m.start() - 30)
                end = min(len(content), m.end() + 200)
                ctx = content[start:end].decode('utf-8', errors='replace')
                ctx = ''.join(c if c.isprintable() else '.' for c in ctx)
                print(f"  ...{ctx}...")

    print("\n" + "="*80)
    print("SEARCHING FOR ERROR MESSAGE PATTERNS")
    print("="*80)
    
    error_patterns = [
        b'crc error',
        b'checksum error',
        b'invalid crc',
        b'crc failed',
        b'bad crc',
        b'crc mismatch',
    ]
    
    for pattern in error_patterns:
        idx = content.find(pattern)
        if idx != -1:
            ctx = content[max(0, idx-200):min(len(content), idx+300)]
            try:
                s = ctx.decode('utf-8', errors='replace')
                s = ''.join(c if c.isprintable() else '.' for c in s)
                print(f"\n[{pattern.decode()}]:")
                print(s)
            except:
                pass

    print("\n" + "="*80)
    print("SEARCHING FOR DATA ENCODING PATTERNS")
    print("="*80)
    
    # Look for base64 or hex encoding of data
    encoding_patterns = [
        rb'base64ToUint8Array',
        rb'hexToBytes',
        rb'bytesToHex',
        rb'stringToBytes',
        rb'toByteArray',
        rb'fromByteArray',
    ]
    
    for pattern in encoding_patterns:
        idx = content.find(pattern)
        if idx != -1:
            ctx = content[max(0, idx-100):min(len(content), idx+300)]
            try:
                s = ctx.decode('utf-8', errors='replace')
                s = ''.join(c if c.isprintable() else '.' for c in s)
                print(f"\n[{pattern.decode()}]:")
                print(s)
            except:
                pass

    print("\n" + "="*80)
    print("SEARCHING FOR PROTOCOL-RELATED STRINGS")
    print("="*80)
    
    protocol_strings = [
        b'header',
        b'payload',
        b'packet',
        b'frame',
        b'magic',
    ]
    
    for pattern in protocol_strings:
        # Find in context of 'print' or 'ble' or 'write'
        combined = rb'(?:print|ble|write|send).{0,50}' + pattern
        matches = list(re.finditer(combined, content, re.IGNORECASE))
        if matches:
            print(f"\n[{pattern.decode()} near print/ble/write/send]: {len(matches)} matches")
            for m in matches[:3]:
                start = max(0, m.start() - 30)
                end = min(len(content), m.end() + 100)
                ctx = content[start:end].decode('utf-8', errors='replace')
                ctx = ''.join(c if c.isprintable() else '.' for c in ctx)
                print(f"  ...{ctx}...")

if __name__ == "__main__":
    main()

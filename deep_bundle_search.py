import os
import re

def extract_context(content, search_bytes, context_before=300, context_after=500):
    """Extract larger context around a pattern"""
    idx = content.find(search_bytes)
    if idx == -1:
        return None
    start = max(0, idx - context_before)
    end = min(len(content), idx + len(search_bytes) + context_after)
    return content[start:end]

def main():
    filepath = r"c:\Users\maxgo\Downloads\Sentimo\funnyprint_apk\assets\index.android.bundle"
    
    with open(filepath, 'rb') as f:
        content = f.read()
    
    print("="*80)
    print("1. SEARCHING FOR 'low crc error' CONTEXT")
    print("="*80)
    
    # This is the key - "low crc error" suggests CRC validation
    context = extract_context(content, b'low crc error', 500, 800)
    if context:
        try:
            s = context.decode('utf-8', errors='replace')
            s = ''.join(c if c.isprintable() or c in '\n\r\t' else '.' for c in s)
            print(s)
        except:
            pass
    
    print("\n" + "="*80)
    print("2. SEARCHING FOR 'ffe1 characteristic not found' CONTEXT")
    print("="*80)
    
    context = extract_context(content, b'ffe1 characteristic not found', 300, 500)
    if context:
        try:
            s = context.decode('utf-8', errors='replace')
            s = ''.join(c if c.isprintable() or c in '\n\r\t' else '.' for c in s)
            print(s)
        except:
            pass
    
    print("\n" + "="*80)
    print("3. SEARCHING FOR 'ffe2 characteristic not found' CONTEXT")
    print("="*80)
    
    context = extract_context(content, b'ffe2 characteristic not found', 300, 500)
    if context:
        try:
            s = context.decode('utf-8', errors='replace')
            s = ''.join(c if c.isprintable() or c in '\n\r\t' else '.' for c in s)
            print(s)
        except:
            pass
    
    print("\n" + "="*80)
    print("4. SEARCHING FOR 'sendDataToDevice' CONTEXT")
    print("="*80)
    
    context = extract_context(content, b'sendDataToDevice', 300, 500)
    if context:
        try:
            s = context.decode('utf-8', errors='replace')
            s = ''.join(c if c.isprintable() or c in '\n\r\t' else '.' for c in s)
            print(s)
        except:
            pass
    
    print("\n" + "="*80)
    print("5. SEARCHING FOR 'monitorCharacteristic' CONTEXTS (all)")
    print("="*80)
    
    idx = 0
    count = 0
    while count < 5:
        idx = content.find(b'monitorCharacteristic', idx)
        if idx == -1:
            break
        context = content[max(0, idx-200):min(len(content), idx+400)]
        try:
            s = context.decode('utf-8', errors='replace')
            s = ''.join(c if c.isprintable() or c in '\n\r\t' else '.' for c in s)
            print(f"\n--- Match {count+1} ---")
            print(s)
        except:
            pass
        idx += 1
        count += 1

    print("\n" + "="*80)
    print("6. SEARCHING FOR SERVICE UUID PATTERNS")
    print("="*80)
    
    # Search for quoted hex strings that look like UUIDs
    # Looking for patterns like "ffe6" or "FFE6" in context of services
    uuid_patterns = [
        (b'"ffe', 'Double-quoted ffe'),
        (b"'ffe", 'Single-quoted ffe'),
        (b'"FFE', 'Double-quoted FFE'),
        (b"'FFE", 'Single-quoted FFE'),
    ]
    
    for pattern, name in uuid_patterns:
        idx = 0
        while True:
            idx = content.find(pattern, idx)
            if idx == -1:
                break
            context = content[max(0, idx-50):min(len(content), idx+100)]
            try:
                s = context.decode('utf-8', errors='replace')
                s = ''.join(c if c.isprintable() or c in '\n\r\t' else '.' for c in s)
                print(f"\n[{name}] at {idx}: ...{s}...")
            except:
                pass
            idx += 1
    
    print("\n" + "="*80)
    print("7. SEARCHING FOR 'writeCharacteristicForDevice' CONTEXT")
    print("="*80)
    
    context = extract_context(content, b'writeCharacteristicForDevice', 400, 600)
    if context:
        try:
            s = context.decode('utf-8', errors='replace')
            s = ''.join(c if c.isprintable() or c in '\n\r\t' else '.' for c in s)
            print(s)
        except:
            pass

    print("\n" + "="*80)
    print("8. SEARCHING FOR 'printData' or 'PrintData' CONTEXT")
    print("="*80)
    
    for pattern in [b'printData', b'PrintData']:
        context = extract_context(content, pattern, 300, 500)
        if context:
            try:
                s = context.decode('utf-8', errors='replace')
                s = ''.join(c if c.isprintable() or c in '\n\r\t' else '.' for c in s)
                print(f"\n[{pattern.decode()}]:")
                print(s)
            except:
                pass
    
    print("\n" + "="*80)
    print("9. SEARCHING FOR HEX/BYTE ARRAY PATTERNS")
    print("="*80)
    
    # Look for things like [0x5a, 0x02] or similar
    hex_patterns = [
        rb'0x5[aA]\s*,\s*0x',
        rb'\[0x5[aA]',
        rb'new\s+Uint8Array\s*\(\s*\[',
    ]
    
    for pattern in hex_patterns:
        matches = list(re.finditer(pattern, content))
        print(f"\nPattern '{pattern.decode()}': {len(matches)} matches")
        for m in matches[:3]:
            start = max(0, m.start() - 30)
            end = min(len(content), m.end() + 150)
            context = content[start:end].decode('utf-8', errors='replace')
            context = ''.join(c if c.isprintable() else '.' for c in context)
            print(f"  ...{context}...")

    print("\n" + "="*80)
    print("10. SEARCHING FOR CRC CALCULATION PATTERNS")
    print("="*80)
    
    # CRC patterns
    crc_patterns = [
        b'crc8',
        b'CRC8',
        b'calcCrc',
        b'calculateCrc',
        b'crcTable',
        b'crc_table',
        b'crcCalc',
    ]
    
    for pattern in crc_patterns:
        context = extract_context(content, pattern, 200, 400)
        if context:
            try:
                s = context.decode('utf-8', errors='replace')
                s = ''.join(c if c.isprintable() or c in '\n\r\t' else '.' for c in s)
                print(f"\n[{pattern.decode()}]:")
                print(s)
            except:
                pass

if __name__ == "__main__":
    main()

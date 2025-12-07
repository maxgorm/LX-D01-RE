import os
import re

def search_files(directory):
    uuid_pattern = re.compile(b'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
    # Search for strings that might indicate the magic bytes or checksums
    # We search for byte sequences that represent the ASCII strings, or just the strings if they are in code
    text_patterns = [
        (b'UUID', "UUID"),
        (b'service', "service"),
        (b'characteristic', "characteristic"),
        (b'CRC', "CRC"),
        (b'checksum', "checksum"),
        (b'xor', "xor"),
        (b'compress', "compress"),
        (b'bitmap', "bitmap"),
        (b'0x5a', "0x5a"),
        (b'0x51', "0x51"),
        (b'LX-D01', "LX-D01"),
    ]

    for root, dirs, files in os.walk(directory):
        for file in files:
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'rb') as f:
                    content = f.read()
                    
                    # Search for UUIDs
                    uuids = uuid_pattern.findall(content)
                    if uuids:
                        print(f"Found UUIDs in {filepath}:")
                        for uuid in set(uuids):
                            print(f"  {uuid.decode('utf-8', errors='ignore')}")
                    
                    # Search for other text patterns
                    for pattern, label in text_patterns:
                        if pattern in content:
                            # Try to find context? It's binary, so context is hard.
                            # Just report presence for now.
                            print(f"Found '{label}' in {filepath}")
                            
                            # If it's a small number of matches, maybe print context?
                            # Let's try to print a bit of context if it looks like text
                            matches = [m.start() for m in re.finditer(re.escape(pattern), content)]
                            if len(matches) < 10:
                                for m in matches:
                                    start = max(0, m - 20)
                                    end = min(len(content), m + len(pattern) + 20)
                                    snippet = content[start:end]
                                    try:
                                        print(f"    Context: {snippet}")
                                    except:
                                        pass

            except Exception as e:
                print(f"Could not read {filepath}: {e}")

if __name__ == "__main__":
    search_files(r"c:\Users\maxgo\Downloads\Sentimo\funnyprint_apk")

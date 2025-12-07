import re

def extract_strings(filepath):
    with open(filepath, 'rb') as f:
        content = f.read()
    
    # Regex for printable strings (ASCII)
    # 4 or more characters
    string_pattern = re.compile(b'[ -~]{4,}')
    
    found_strings = string_pattern.findall(content)
    
    print(f"Extracted {len(found_strings)} strings from {filepath}")
    
    keywords = [b"UUID", b"0000", b"LX-D01", b"CRC", b"checksum", b"xor", b"compress", b"0x5a", b"0x51", b"service", b"characteristic"]
    
    for s in found_strings:
        for k in keywords:
            if k in s:
                try:
                    print(f"Match '{k.decode()}': {s.decode()}")
                except:
                    pass

if __name__ == "__main__":
    extract_strings(r"c:\Users\maxgo\Downloads\Sentimo\funnyprint_apk\assets\index.android.bundle")

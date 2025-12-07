import os
import re

def search_in_dex_files(directory, patterns):
    """Search for patterns in all DEX files"""
    results = {}
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.dex'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'rb') as f:
                        content = f.read()
                        
                    for pattern_name, pattern in patterns.items():
                        if isinstance(pattern, bytes):
                            if pattern in content:
                                if pattern_name not in results:
                                    results[pattern_name] = []
                                # Find context around the match
                                idx = content.find(pattern)
                                start = max(0, idx - 50)
                                end = min(len(content), idx + len(pattern) + 100)
                                context = content[start:end]
                                results[pattern_name].append({
                                    'file': filepath,
                                    'context': context
                                })
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")
    
    return results

def main():
    directory = r"c:\Users\maxgo\Downloads\Sentimo\funnyprint_apk"
    
    # Patterns to search for
    patterns = {
        # BLE Core Classes
        'BluetoothGatt': b'BluetoothGatt',
        'BluetoothGattCallback': b'BluetoothGattCallback',
        'BluetoothGattCharacteristic': b'BluetoothGattCharacteristic',
        'BluetoothGattService': b'BluetoothGattService',
        'BluetoothDevice': b'BluetoothDevice',
        'BluetoothAdapter': b'BluetoothAdapter',
        'BluetoothLeScanner': b'BluetoothLeScanner',
        'BluetoothManager': b'BluetoothManager',
        
        # BLE Callbacks
        'onConnectionStateChange': b'onConnectionStateChange',
        'onServicesDiscovered': b'onServicesDiscovered',
        'onCharacteristicChanged': b'onCharacteristicChanged',
        'onCharacteristicWrite': b'onCharacteristicWrite',
        'setCharacteristicNotification': b'setCharacteristicNotification',
        'writeCharacteristic': b'writeCharacteristic',
        
        # Package imports
        'android.bluetooth.BluetoothGatt': b'android/bluetooth/BluetoothGatt',
        'android.bluetooth.BluetoothDevice': b'android/bluetooth/BluetoothDevice',
        'android.bluetooth.BluetoothAdapter': b'android/bluetooth/BluetoothAdapter',
        
        # UUIDs - lowercase
        'ffe0': b'ffe0',
        'ffe1': b'ffe1',
        'ffe2': b'ffe2',
        'ffe6': b'ffe6',
        'fff0': b'fff0',
        'fff1': b'fff1',
        'fff2': b'fff2',
        
        # UUIDs - uppercase
        'FFE0': b'FFE0',
        'FFE1': b'FFE1',
        'FFE2': b'FFE2',
        'FFE6': b'FFE6',
        'FFF0': b'FFF0',
        'FFF1': b'FFF1',
        'FFF2': b'FFF2',
        
        # Full UUID format
        'uuid_base': b'-0000-1000-8000-00805f9b34fb',
        'uuid_base_upper': b'-0000-1000-8000-00805F9B34FB',
        
        # Magic bytes
        '0x5a': b'0x5a',
        '0x5A': b'0x5A',
        '0x51': b'0x51',
        
        # CRC related
        'crc8': b'crc8',
        'CRC8': b'CRC8',
        'calcCrc': b'calcCrc',
        'checkCrc': b'checkCrc',
        'crc_table': b'crc_table',
        
        # Print/Command related class names
        'PrintData': b'PrintData',
        'PrintUtils': b'PrintUtils', 
        'PrintCmd': b'PrintCmd',
        'BluetoothOrder': b'BluetoothOrder',
        'ThermalPrinter': b'ThermalPrinter',
        'BleManager': b'BleManager',
        'BtManager': b'BtManager',
        
        # Third party BLE libraries
        'fastble': b'fastble',
        'nordicsemi': b'nordicsemi',
        'inuker': b'inuker',
        'react-native-ble': b'react-native-ble',
        'react-native-bluetooth': b'react-native-bluetooth',
        
        # Chinese characters for print/checksum
        'print_chinese': b'\xe6\x89\x93\xe5\x8d\xb0',  # 打印
        'checksum_chinese': b'\xe6\xa0\xa1\xe9\xaa\x8c',  # 校验
    }
    
    print("Searching DEX files for BLE patterns...")
    results = search_in_dex_files(directory, patterns)
    
    print("\n" + "="*80)
    print("SEARCH RESULTS")
    print("="*80)
    
    for pattern_name, matches in sorted(results.items()):
        print(f"\n[FOUND] {pattern_name}: {len(matches)} match(es)")
        for match in matches[:3]:  # Show first 3 matches
            print(f"  File: {match['file']}")
            # Try to decode context as ASCII where possible
            try:
                context_str = match['context'].decode('utf-8', errors='replace')
                # Clean up non-printable chars
                context_str = ''.join(c if c.isprintable() or c in '\n\r\t' else '.' for c in context_str)
                print(f"  Context: {context_str[:200]}")
            except:
                print(f"  Context (hex): {match['context'][:100].hex()}")
    
    # Patterns not found
    not_found = [p for p in patterns.keys() if p not in results]
    if not_found:
        print(f"\n[NOT FOUND] {len(not_found)} patterns: {', '.join(not_found[:20])}")
        if len(not_found) > 20:
            print(f"  ... and {len(not_found) - 20} more")

if __name__ == "__main__":
    main()

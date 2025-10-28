#!/usr/bin/env python3
"""Debug script to compare sent vs received payload bits"""

# Expected payload: b'Hi\n' = [0x48, 0x69, 0x0A, checksum]
# 'H' = 0x48 = 01001000
# 'i' = 0x69 = 01101001  
# '\n'= 0x0A = 00001010
# checksum = sum([0x48, 0x69, 0x0A]) & 0xFF = 187 = 10111011

expected_payload_bytes = b'Hi\n'
expected_checksum = sum(expected_payload_bytes) & 0xFF
print(f"Expected payload: {expected_payload_bytes}")
print(f"Expected checksum: {expected_checksum}")

expected_bits = []
for byte in expected_payload_bytes:
    for i in range(8):
        expected_bits.append((byte >> (7-i)) & 1)
        
# Add checksum bits
for i in range(8):
    expected_bits.append((expected_checksum >> (7-i)) & 1)

print(f"Expected payload+checksum bits: {expected_bits}")
print(f"Expected payload+checksum bits (first 32): {expected_bits[:32]}")

# What we actually received: b'@\x00\x00' + checksum 0
received_payload_bytes = b'@\x00\x00'
received_checksum = 0
print(f"\nReceived payload: {received_payload_bytes}")
print(f"Received checksum: {received_checksum}")

received_bits = []
for byte in received_payload_bytes:
    for i in range(8):
        received_bits.append((byte >> (7-i)) & 1)
        
# Add checksum bits  
for i in range(8):
    received_bits.append((received_checksum >> (7-i)) & 1)

print(f"Received payload+checksum bits: {received_bits}")
print(f"Received payload+checksum bits (first 32): {received_bits[:32]}")

print("\nBit comparison (first 32):")
for i in range(min(32, len(expected_bits), len(received_bits))):
    match = "✓" if expected_bits[i] == received_bits[i] else "✗"
    print(f"  Bit {i:2d}: expected {expected_bits[i]}, got {received_bits[i]} {match}")
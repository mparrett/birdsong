#!/usr/bin/env python3
"""Test the bit conversion pipeline from modem.py"""

import sys

sys.path.append(".")
from modem import bits_to_bitmap, bitmap_to_bits, bits_to_bytes, ModemConfig


def test_bit_pipeline():
    config = ModemConfig()

    # Test data: header bits from sender
    original_bits = [
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        1,
        0,
        0,
        1,
        1,
        0,
        0,
        0,
        1,
        0,
        0,
        1,
        1,
    ]
    print(f"Original bits: {original_bits}")

    # Convert to bitmap
    bitmap = bits_to_bitmap(original_bits, config.freq_bands, config.header_slots)
    print(f"Bitmap shape: {len(bitmap)}x{len(bitmap[0])}")
    print("Bitmap:")
    for i, row in enumerate(bitmap):
        print(f"  Band {i}: {row}")

    # Convert back to bits
    recovered_bits = bitmap_to_bits(bitmap)
    print(f"Recovered bits: {recovered_bits}")

    # Check if they match
    match = original_bits == recovered_bits[: len(original_bits)]
    print(f"Bits match: {match}")

    if not match:
        print("MISMATCH DETECTED!")
        for i, (orig, recv) in enumerate(
            zip(original_bits, recovered_bits[: len(original_bits)])
        ):
            if orig != recv:
                print(f"  Bit {i}: sent {orig}, got {recv}")

    # Test bytes conversion
    recovered_bytes = bits_to_bytes(recovered_bits[: len(original_bits)])
    print(f"Recovered bytes: {recovered_bytes}")


if __name__ == "__main__":
    test_bit_pipeline()

# --- Compact Display ---


def display_bit_sequence_compactly(label, sequence):
    """Displays a sequence of bits using Unicode block characters for a compact view."""
    if not sequence:
        print(f"{label}: (empty)")
        return

    # Make a copy to avoid modifying the original list
    padded_sequence = list(sequence)
    if len(padded_sequence) % 2 != 0:
        # Pad with a 0 if odd length, affects the last character representation
        padded_sequence.append(0)

        mapping = {
            # (left, right) -> character
            (0, 0): " ",  # Both halves empty
            (1, 0): "▕",  # Left half filled
            (0, 1): "▏",  # Right half filled
            (1, 1): "█",  # Both halves filled
        }

    # Pair up bits and map them to characters
    output_chars = []
    for i in range(0, len(padded_sequence), 2):
        # The first bit in the pair determines the top/left half of the character
        # The second bit determines the bottom/right half
        bit_pair = (padded_sequence[i], padded_sequence[i + 1])
        output_chars.append(mapping.get(bit_pair, ""))  # '' for invalid pairs

    print(f"{label:<22} {''.join(output_chars)}")

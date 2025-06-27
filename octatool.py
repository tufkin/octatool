import argparse
import os
import struct
from pydub import AudioSegment
from pydub.silence import detect_leading_silence


def find_audio_files(directory):
    """Finds all supported audio files in a directory."""
    audio_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.wav', '.aif', '.aiff', '.mp3')):
                audio_files.append(os.path.join(root, file))
    return sorted(audio_files)


def process_sample(file_path, normalize, trim_silence, headroom, mono, threshold_db=-48, fade_in_ms=0, fade_out_ms=0):
    """Loads and processes a single audio sample."""
    try:
        sample = AudioSegment.from_file(file_path)

        # Set to 44.1kHz for Octatrack compatibility only if needed
        if sample.frame_rate != 44100:
            sample = sample.set_frame_rate(44100)

        if trim_silence:
            if threshold_db < 0:
                # Use threshold-based silence detection (AudioHit style)
                # Convert dB to pydub's silence threshold (which expects positive values)
                silence_thresh = threshold_db
                start_trim = detect_leading_silence(
                    sample, silence_threshold=silence_thresh)

                # Also detect trailing silence
                # Reverse sample, detect leading silence, then calculate trailing silence
                reversed_sample = sample.reverse()
                end_trim = detect_leading_silence(
                    reversed_sample, silence_threshold=silence_thresh)

                if end_trim > 0:
                    sample = sample[start_trim:-end_trim]
                else:
                    sample = sample[start_trim:]
            else:
                # Original simple leading silence trim
                start_trim = detect_leading_silence(sample)
                sample = sample[start_trim:]

        # Apply fade in/out if specified
        if fade_in_ms > 0:
            sample = sample.fade_in(fade_in_ms)
        if fade_out_ms > 0:
            sample = sample.fade_out(fade_out_ms)

        if normalize:
            # Normalize audio to provide headroom
            sample = sample.normalize(headroom=headroom)

        if mono:
            # Convert to mono to save Flex RAM
            sample = sample.set_channels(1)

        return sample
    except Exception as e:
        print(
            f"  - Could not process file: {os.path.basename(file_path)}. Error: {e}")
        return None


def generate_ot_file(slice_points, output_file, sample_rate=44100, audio_length_samples=0, gain=12):
    """
    Generate .ot slice file using DigiChain's FORM format for maximum Octatrack compatibility.
    This version is streamlined for one-shot sample chains with hardcoded metadata defaults.
    """
    ot_file = output_file.replace('.wav', '.ot')

    # --- Hardcoded defaults for one-shot chains ---
    tempo = 120
    bars = None  # Auto-calculate
    quantize = 16
    trim_start = 0
    trim_end = None  # Auto-set to audio_length_samples
    loop_mode = False
    # ---

    # Convert milliseconds to samples for slice positions
    slice_samples = [int(ms * sample_rate / 1000) for ms in slice_points]

    # Create 832-byte (0x340) buffer matching DigiChain format
    buffer = bytearray(0x340)

    # FORM header (bytes 0-23)
    form_header = [
        0x46, 0x4F, 0x52, 0x4D,  # "FORM"
        0x00, 0x00, 0x00, 0x00,  # Size (will be calculated)
        0x44, 0x50, 0x53, 0x31,  # "DPS1"
        0x53, 0x4D, 0x50, 0x41,  # "SMPA"
        0x00, 0x00, 0x00, 0x00,  # Chunk size
        0x00, 0x02, 0x00        # Additional header
    ]

    for i, byte in enumerate(form_header):
        buffer[i] = byte

    # Calculate BPM value (tempo * 6 * 4 as per DigiChain)
    bpm_value = tempo * 6 * 4
    struct.pack_into('<I', buffer, 0x17, bpm_value)

    # Calculate bars and loop bars
    if bars is None:
        if audio_length_samples > 0:
            total_seconds = audio_length_samples / sample_rate
            bars_calc = total_seconds / ((60 / tempo) * 4)
            bars_value = int(bars_calc * 100)
        else:
            bars_value = 400  # Default 4 bars * 100
    else:
        bars_value = int(bars * 100)

    loop_bars_value = bars_value  # Same as total for now

    # Set trim_end if not specified
    if trim_end is None:
        trim_end = audio_length_samples

    # Convert gain from dB to OT internal format
    # OT uses a scale where 0x30 = +12dB, so we adjust accordingly
    gain_value = int(0x30 + ((gain - 12) * 4))  # Approximate scaling
    gain_value = max(0, min(0xFF, gain_value))  # Clamp to valid range

    struct.pack_into('<I', buffer, 0x1B, bars_value)  # trim length
    struct.pack_into('<I', buffer, 0x1F, loop_bars_value)  # loop length
    struct.pack_into('<I', buffer, 0x23, 0)  # time stretch off
    struct.pack_into('<I', buffer, 0x27, 1 if loop_mode else 0)  # loop on/off
    struct.pack_into('<H', buffer, 0x2B, gain_value)  # gain
    # quantize (clamp to byte range)
    buffer[0x2D] = min(0xFF, max(0, quantize))
    struct.pack_into('<I', buffer, 0x2E, trim_start)  # trim start
    struct.pack_into('<I', buffer, 0x32, trim_end)  # trim end
    struct.pack_into('<I', buffer, 0x36, 0)  # loop start

    # Write slice data starting at offset 0x3A (12 bytes per slice)
    offset = 0x3A
    for i in range(64):
        if i < len(slice_samples):
            start_pos = slice_samples[i]
            # Calculate end position (next slice start or audio end)
            if i < len(slice_samples) - 1:
                end_pos = slice_samples[i + 1]
            else:
                end_pos = audio_length_samples

            struct.pack_into('<I', buffer, offset, start_pos)  # start
            struct.pack_into('<I', buffer, offset + 4, end_pos)  # end
            # loop point (-1 = no loop)
            struct.pack_into('<i', buffer, offset + 8, -1)
        else:
            # Padding for unused slices
            struct.pack_into('<I', buffer, offset, 0)  # start
            struct.pack_into('<I', buffer, offset + 4, 0)  # end
            struct.pack_into('<i', buffer, offset + 8, -1)  # loop point

        offset += 12

    # Write slice count at offset 0x33A
    slice_count = len(slice_samples)
    struct.pack_into('<I', buffer, 0x33A, slice_count)

    # Calculate checksum (sum of all bytes from 0x10 to end)
    checksum = 0
    for i in range(0x10, len(buffer)):
        checksum += buffer[i]

    # Write checksum at offset 0x33E (16-bit)
    struct.pack_into('<H', buffer, 0x33E, checksum & 0xFFFF)

    # Write the file
    with open(ot_file, 'wb') as f:
        f.write(buffer)

    print(
        f"Generated .ot file: {ot_file} (DigiChain FORM format, {len(buffer)} bytes)")


def run_chain_mode(input_dir, output_file, normalize, trim_silence, headroom, mono, bit_depth, slices, max_slice_length,
                   no_padding=False, ot_gain=12, threshold_db=-48, fade_in_ms=0, fade_out_ms=0):
    """Finds, processes, and chains all audio files into a single, evenly-sliced file."""
    audio_files = find_audio_files(input_dir)
    if not audio_files:
        print("No audio files found to process.")
        return

    # If --slices is used, it dictates the final number of slices.
    if slices:
        if len(audio_files) > slices:
            print(
                f"Found {len(audio_files)} files, but using only the first {slices} as requested by --slices.")
            audio_files = audio_files[:slices]
    # If --slices is not used, limit to 64 to match Octatrack's max slice grid
    elif len(audio_files) > 64:
        print(
            f"Warning: Found {len(audio_files)} files. Only the first 64 will be used for the chain.")
        audio_files = audio_files[:64]

    print(f"Found {len(audio_files)} audio files to chain.")
    processed_samples = []

    for i, file_path in enumerate(audio_files):
        print(
            f"Processing [{i+1}/{len(audio_files)}]: {os.path.basename(file_path)}")
        # Process samples WITHOUT normalization first to avoid clipping when chaining
        sample = process_sample(
            file_path, False, trim_silence, headroom, mono, threshold_db, fade_in_ms, fade_out_ms)
        if sample:
            processed_samples.append(sample)

    if not processed_samples:
        print("No valid audio files were processed.")
        return

    # Handle padding options
    if no_padding:
        print("Joining samples without padding (variable-length slices)")
        padded_samples = processed_samples.copy()
    else:
        # --- Improved Implementation to Reduce Excessive Silence ---
        # 1. Determine slice length more intelligently
        sample_lengths = [len(s) for s in processed_samples]
        longest_sample_ms = max(sample_lengths)

        if max_slice_length and max_slice_length < longest_sample_ms:
            print(
                f"Warning: Longest sample ({longest_sample_ms}ms) exceeds max slice length ({max_slice_length}ms).")
            print("The longest sample will be truncated.")
            slice_len_ms = max_slice_length
        elif max_slice_length:
            slice_len_ms = max_slice_length
            print(f"Using specified max slice length: {slice_len_ms}ms")
        else:
            # Use a more reasonable approach: cap at a sensible maximum
            # Most drum samples and short musical phrases are under 3 seconds
            reasonable_max = 3000  # 3 seconds in milliseconds
            if longest_sample_ms > reasonable_max:
                print(
                    f"Longest sample is {longest_sample_ms}ms ({longest_sample_ms/1000:.1f}s).")
                print(
                    "This seems quite long for a sample chain. Consider using --max-slice-length to cap it.")
                print(
                    f"Using the full length of {longest_sample_ms}ms, but this will add significant silence to shorter samples.")
                slice_len_ms = longest_sample_ms
            else:
                slice_len_ms = longest_sample_ms
                print(
                    f"Using uniform slice length: {slice_len_ms}ms ({slice_len_ms/1000:.1f}s)")

        # 2. Process each sample and pad to uniform length (only if not no-padding)
        padded_samples = []
        for i, sample in enumerate(processed_samples):
            if not no_padding:
                # Truncate if sample is longer than slice length
                if len(sample) > slice_len_ms:
                    sample = sample[:slice_len_ms]
                    print(f"  - Truncated sample {i+1} to {slice_len_ms}ms")

                # Pad with silence to reach uniform slice length
                silence_needed = slice_len_ms - len(sample)
                if silence_needed > 0:
                    padded_sample = sample + \
                        AudioSegment.silent(duration=silence_needed)
                else:
                    padded_sample = sample
            else:
                # No padding - use original sample length
                padded_sample = sample

            padded_samples.append(padded_sample)

        # 3. If the user specifies a slice count (e.g., 16, 32, 64), pad the
        #    entire chain with empty slices to reach that count (only if not no-padding).
        if slices and len(processed_samples) < slices and not no_padding:
            if slices > 64:
                print("Warning: Specified slices > 64. Capping at 64.")
                slices = 64

            num_slices_to_add = slices - len(processed_samples)
            print(
                f"Padding chain with {num_slices_to_add} silent slices to reach {slices} total slices.")
            silent_slice = AudioSegment.silent(duration=slice_len_ms)
            for _ in range(num_slices_to_add):
                padded_samples.append(silent_slice)

    # Final chain assembly
    print(f"\nAssembling chain with {len(padded_samples)} samples...")
    final_chain = sum(padded_samples)

    # Apply normalization to the final chain if requested
    if normalize:
        print("Normalizing final chain...")
        final_chain = final_chain.normalize(headroom=headroom)

    # Export the final chain
    print(f"Exporting chain: {os.path.basename(output_file)}")
    final_chain.export(output_file, format="wav",
                       parameters=["-acodec", f"pcm_s{bit_depth}le"])

    # Generate .ot file
    print("\nGenerating .ot slice file...")

    # Calculate slice points based on the padded samples (start positions in ms)
    slice_points = []
    current_position_ms = 0

    for i, sample in enumerate(padded_samples):
        slice_points.append(current_position_ms)
        # len(sample) gives duration in ms
        current_position_ms += len(sample)

    # Generate .ot slice file
    ot_file_path = output_file.replace('.wav', '.ot')
    total_samples = len(final_chain.get_array_of_samples())
    generate_ot_file(slice_points, ot_file_path,
                     final_chain.frame_rate, total_samples, ot_gain)

    print("\nChain creation complete!")
    print(f"Output: {output_file}")
    print(f"Slice file: {ot_file_path}")
    print(f"Total samples: {len(processed_samples)}")
    print(f"Chain length: {len(final_chain) / 1000:.2f} seconds")
    if no_padding:
        print("Variable-length slices (no padding)")
    else:
        print(f"Slice length: {slice_len_ms} ms each")


def run_info_mode(input_dir):
    """Scans and displays information about audio files in a directory."""
    audio_files = find_audio_files(input_dir)
    if not audio_files:
        print("No audio files found to inspect.")
        return

    print(f"Found {len(audio_files)} audio files to inspect.")
    total_duration_ms = 0

    for i, file_path in enumerate(audio_files):
        try:
            sample = AudioSegment.from_file(file_path)
            duration_ms = len(sample)
            total_duration_ms += duration_ms
            channels = "Stereo" if sample.channels == 2 else "Mono"
            frame_rate = sample.frame_rate
            bit_depth = sample.sample_width * 8

            print(
                f"\n--- File [{i+1}/{len(audio_files)}]: {os.path.basename(file_path)} ---\n"
                f"  - Duration: {duration_ms / 1000:.2f}s\n"
                f"  - Channels: {channels}\n"
                f"  - Sample Rate: {frame_rate} Hz\n"
                f"  - Bit Depth: {bit_depth}-bit"
            )
        except Exception as e:
            print(
                f"  - Could not process file: {os.path.basename(file_path)}. Error: {e}")

    print(f"\n--- Summary ---\n"
          f"  - Total files: {len(audio_files)}\n"
          f"  - Combined duration: {total_duration_ms / 1000:.2f}s")


def main():
    """Main function to set up and run the command-line tool."""
    parser = argparse.ArgumentParser(
        description="A versatile tool to prepare samples for the Elektron Octatrack.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(
        dest='command', required=True, help="Available commands")

    processing_parser = argparse.ArgumentParser(add_help=False)
    processing_parser.add_argument(
        '--no-normalize', action='store_true', help="Disable audio normalization.")
    processing_parser.add_argument(
        '--no-trim', action='store_true', help="Disable trimming of leading silence.")
    processing_parser.add_argument('--headroom', type=float, default=1.0,
                                   help="Normalization headroom in dBFS. Default: 1.0")
    processing_parser.add_argument(
        '--mono', action='store_true', help="Convert output to mono to conserve Flex RAM.")
    processing_parser.add_argument('--bit-depth', type=int, default=24, choices=[16, 24],
                                   help="Output bit depth (16 or 24). Default: 24")

    chain_parser = subparsers.add_parser(
        'chain', help='Create a sample chain from multiple audio files', parents=[processing_parser])
    chain_parser.add_argument('input_directory',
                              help='Directory containing audio files to chain')
    chain_parser.add_argument('output_file', help='Output WAV file path')

    chain_parser.add_argument('--no-padding', action='store_true',
                              help='Join samples without padding to uniform length')
    chain_parser.add_argument('--slices', type=int,
                              choices=[2, 4, 8, 12, 16, 24, 32, 48, 64],
                              help='Pad chain to specific number of slices with silence')

    chain_parser.add_argument('--max-slice-length', type=int,
                              help='Maximum slice length in milliseconds')

    # Advanced trimming and fade options
    chain_parser.add_argument('--threshold', type=float, default=-48,
                              help='Silence threshold in dB for advanced trimming (default: -48)')
    chain_parser.add_argument('--fade-in', type=int, default=0,
                              help='Fade in duration in milliseconds (default: 0)')
    chain_parser.add_argument('--fade-out', type=int, default=0,
                              help='Fade out duration in milliseconds (default: 0)')

    # .ot file metadata options
    chain_parser.add_argument('--ot-gain', type=float, default=12,
                              help='Gain setting for .ot file in dB (default: +12)')

    parser_info = subparsers.add_parser(
        'info', help="Display information about samples without processing.")
    parser_info.add_argument(
        'input_dir', type=str, help="Directory containing audio samples.")

    args = parser.parse_args()

    # --- Route to the correct function based on the command ---
    if args.command == 'chain':
        run_chain_mode(args.input_directory, args.output_file,
                       not args.no_normalize, not args.no_trim, args.headroom, args.mono, args.bit_depth,
                       args.slices, args.max_slice_length, args.no_padding,
                       args.ot_gain, args.threshold, args.fade_in, args.fade_out)
    elif args.command == 'info':
        run_info_mode(args.input_dir)


if __name__ == "__main__":
    main()

import argparse
import os
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


def process_sample(file_path, normalize, trim_silence, headroom, mono):
    """Loads and processes a single audio sample."""
    try:
        sample = AudioSegment.from_file(file_path)

        if trim_silence:
            start_trim = detect_leading_silence(sample)
            sample = sample[start_trim:]

        if normalize:
            sample = sample.normalize(headroom=headroom)

        if mono:
            sample = sample.set_channels(1)

        return sample
    except Exception as e:
        print(
            f"  - Could not process file: {os.path.basename(file_path)}. Error: {e}")
        return None


def run_chain_mode(input_dir, output_file, normalize, trim_silence, headroom, mono, bit_depth, slices):
    """Finds, processes, and chains all audio files into a single output file."""
    audio_files = find_audio_files(input_dir)
    if not audio_files:
        print("No audio files found to process.")
        return

    print(f"Found {len(audio_files)} audio files to chain.")
    processed_samples = []

    for i, file_path in enumerate(audio_files):
        print(
            f"Processing [{i+1}/{len(audio_files)}]: {os.path.basename(file_path)}")
        sample = process_sample(
            file_path, normalize, trim_silence, headroom, mono)
        if sample:
            processed_samples.append(sample)

    if not processed_samples:
        print("No valid audio files were processed.")
        return

    # Determine the length of the longest sample to use as the slice length
    slice_len_ms = max(len(s) for s in processed_samples)

    # Pad each sample to the slice length and create the chain
    final_chain = AudioSegment.empty()
    for sample in processed_samples:
        silence_needed = slice_len_ms - len(sample)
        padded_sample = sample + AudioSegment.silent(duration=silence_needed)
        final_chain += padded_sample

    # Pad the entire chain with silent slices if requested
    if slices and len(processed_samples) < slices:
        num_slices_to_add = slices - len(processed_samples)
        print(f"Padding chain with {num_slices_to_add} silent slices to reach {slices} total slices.")
        silent_slice = AudioSegment.silent(duration=slice_len_ms)
        for _ in range(num_slices_to_add):
            final_chain += silent_slice

    if len(final_chain) > 0:
        print(f"\nExporting sample chain to: {output_file}")
        codec = f"pcm_s{bit_depth}le"
        final_chain.export(output_file, format="wav",
                           parameters=["-acodec", codec])
        print("Done!")


def run_info_mode(input_dir):
    """Scans and displays information about audio files."""
    audio_files = find_audio_files(input_dir)
    if not audio_files:
        print("No audio files found to inspect.")
        return

    print(f"Found {len(audio_files)} audio files to inspect.")
    for i, file_path in enumerate(audio_files):
        try:
            sample = AudioSegment.from_file(file_path)
            duration_ms = len(sample)
            channels = sample.channels
            frame_rate = sample.frame_rate
            sample_width = sample.sample_width
            print(
                f"\n--- File [{i+1}/{len(audio_files)}]: {os.path.basename(file_path)} ---\n"
                f"  - Duration: {duration_ms / 1000:.2f}s\n"
                f"  - Channels: {'Stereo' if channels == 2 else 'Mono'}\n"
                f"  - Sample Rate: {frame_rate} Hz\n"
                f"  - Bit Depth: {sample_width * 8}-bit"
            )
        except Exception as e:
            print(
                f"  - Could not process file: {os.path.basename(file_path)}. Error: {e}")


def run_batch_mode(input_dir, output_dir, normalize, trim_silence, headroom, mono, bit_depth):
    """Finds and processes each audio file, saving them individually."""
    audio_files = find_audio_files(input_dir)
    if not audio_files:
        print("No audio files found to process.")
        return

    print(f"Found {len(audio_files)} audio files for batch processing.")
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    for i, file_path in enumerate(audio_files):
        print(
            f"Processing [{i+1}/{len(audio_files)}]: {os.path.basename(file_path)}")
        sample = process_sample(
            file_path, normalize, trim_silence, headroom, mono)
        if sample:
            # Create a new filename with a .wav extension
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_filename = os.path.join(output_dir, f"{base_name}.wav")
            codec = f"pcm_s{bit_depth}le"
            sample.export(output_filename, format="wav",
                          parameters=["-acodec", codec])

    print(f"\nBatch processing complete. Files saved in: {output_dir}")


def main():
    """Main function to set up and run the command-line tool."""
    parser = argparse.ArgumentParser(
        description="A versatile tool to prepare samples for the Elektron Octatrack.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(
        dest='command', required=True, help="Available commands")

    # --- Parent Parser for common processing options ---
    processing_parser = argparse.ArgumentParser(add_help=False)
    processing_parser.add_argument(
        '--no-normalize', action='store_true', help="Disable audio normalization.")
    processing_parser.add_argument(
        '--no-trim', action='store_true', help="Disable trimming of leading silence.")
    processing_parser.add_argument('--headroom', type=float, default=3.0,
                                   help="Normalization headroom in dBFS. Default: 3.0")
    processing_parser.add_argument(
        '--mono', action='store_true', help="Convert output to mono.")
    processing_parser.add_argument('--bit-depth', type=int, default=24, choices=[16, 24],
                                   help="Output bit depth (16 or 24). Default: 24")

    # --- Chain Command ---
    parser_chain = subparsers.add_parser(
        'chain', help="Chain multiple samples into one file.", parents=[processing_parser])
    parser_chain.add_argument(
        'input_dir', type=str, help="The directory containing the audio samples.")
    parser_chain.add_argument('output_file', type=str,
                              help="The path for the final output WAV file.")
    parser_chain.add_argument('--slices', type=int,
                              help="Pad the chain with silence to a specific number of slices (e.g., 16, 32, 64).")

    # --- Batch Command ---
    parser_batch = subparsers.add_parser(
        'batch', help="Process each sample individually.", parents=[processing_parser])
    parser_batch.add_argument(
        'input_dir', type=str, help="The directory containing the audio samples.")
    parser_batch.add_argument('output_dir', type=str,
                              help="The directory to save processed files.")

    # --- Info Command ---
    parser_info = subparsers.add_parser(
        'info', help="Display information about samples without processing.")
    parser_info.add_argument(
        'input_dir', type=str, help="The directory containing the audio samples.")

    args = parser.parse_args()

    if args.command == 'chain':
        run_chain_mode(args.input_dir, args.output_file,
                       not args.no_normalize, not args.no_trim, args.headroom, args.mono, args.bit_depth, args.slices)
    elif args.command == 'batch':
        run_batch_mode(args.input_dir, args.output_dir,
                       not args.no_normalize, not args.no_trim, args.headroom, args.mono, args.bit_depth)
    elif args.command == 'info':
        run_info_mode(args.input_dir)


if __name__ == "__main__":
    main()

# octatool

A streamlined command-line tool for creating Octatrack-compatible **one-shot sample chains** with advanced audio processing. Inspired by OctaChainer, DigiChain, and AudioHit.

## Core Features

- **Sample Chaining**: Concatenates multiple audio files into a single chain, perfect for drum kits and one-shots.
- **Automatic .ot File Generation**: Always creates a `.ot` slice file alongside your chain for instant loading on the Octatrack.
- **Advanced Silence Trimming**: Uses a configurable threshold to trim leading and trailing silence, ensuring tight samples.
- **Fade In/Out**: Applies smooth fades to prevent clicks.
- **Audio Normalization**: Normalizes the final chain to a user-defined headroom.
- **Format Support**: Reads `.wav`, `.aif`, `.aiff`, and `.mp3` files.
- **High-Quality Output**: Exports to 16 or 24-bit WAV at the Octatrack's native 44.1kHz sample rate.

## Requirements

- Python 3
- [FFmpeg](https://ffmpeg.org/download.html): Must be installed and accessible in your system's PATH.
- `pydub` Python library.

## Installation

1. **Install FFmpeg:**
   Follow the instructions on the [official FFmpeg website](https://ffmpeg.org/download.html) to install it for your operating system. Make sure it's added to your system's PATH.

2. **Install Python dependencies:**
   Navigate to the project directory and install the required library using pip:

   ```bash
   pip install pydub
   ```

## Usage

To see all available commands and options, run:

```bash
python octatool.py -h
```

### `chain` Command

Finds all audio files in a source directory, processes them, and concatenates them into a single output WAV file. An `.ot` slice file is always created automatically.

**Syntax:**

```bash
python octatool.py chain <input_dir> <output_file.wav> [options]
```

**Options:**

- `--no-normalize`: Disables the audio normalization step.
- `--no-trim`: Disables the trimming of leading silence.
- `--headroom <dBFS>`: Sets the normalization headroom in dBFS (default: 1.0).
- `--mono`: Converts the output file to mono.
- `--bit-depth <16|24>`: Sets the output bit depth (default: 24).
- `--slices <2|4|...|64>`: Pads the sample chain with silent slices to a specific total.
- `--max-slice-length <ms>`: Sets the maximum length for each slice in milliseconds.
- `--no-padding`: Joins samples without padding to uniform length (creates variable-length slices).
- `--threshold <dB>`: Silence threshold in dB for advanced trimming (default: -48).
- `--fade-in <ms>`: Fade in duration in milliseconds (default: 0).
- `--fade-out <ms>`: Fade out duration in milliseconds (default: 0).
- `--ot-gain <dB>`: Gain setting for the `.ot` file in dB (default: +12).

### `info` Command

Scans a directory and displays technical information about each audio file without performing any processing.

**Syntax:**

```bash
python octatool.py info <input_dir>
```

---

## Examples

### Basic Usage

Create a chain from all samples in the `my-kicks` directory and pad it to 16 slices. A `kicks.wav` and `kicks.ot` file will be created.

```bash
python octatool.py chain path/to/my-kicks kicks.wav --slices 16
```

### Advanced Trimming and Fades

Create a chain with a tighter silence threshold, a 10ms fade-in, and a 25ms fade-out.

```bash
python octatool.py chain path/to/my-snares snares.wav --slices 16 --threshold -32 --fade-in 10 --fade-out 25
```

### No Padding

Create a chain where each sample retains its original length. The `.ot` file will have slices of varying lengths.

```bash
python octatool.py chain path/to/vocal-chops chops.wav --no-padding
```

## License

This project is licensed under the MIT License.

# OctaTool

A versatile command-line tool written in Python to prepare audio samples for hardware samplers, with a focus on the Elektron Octatrack. It can process samples in batches or chain them together into a single file, making it easy to create sample chains.

## Features

- **Batch Processing**: Individually process a directory of audio files.
- **Sample Chaining**: Concatenate multiple audio files into a single sample chain.
- **Audio Normalization**: Normalizes audio to -3.0 dBFS to provide headroom (can be disabled).
- **Silence Trimming**: Automatically trims leading silence from samples (can be disabled).
- **Format Support**: Reads `.wav`, `.aif`, `.aiff`, and `.mp3` files.
- **High-Quality Output**: Exports processed files as 24-bit WAV (`pcm_s24le`), ideal for the Octatrack.

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

3. **Place the script:**
    Keep `octatool.py` in a convenient location.

## Usage

The tool is operated from the command line and has two main commands: `batch` and `chain`.

### General Help

To see all available commands and options, run:

```bash
python octatool.py -h
```

---

### `batch` Command

Processes each audio file in a source directory and saves the processed versions individually to a destination directory.

**Syntax:**

```bash
python octatool.py batch <input_dir> <output_dir> [options]
```

**Example:**
This command will find all audio files in `~/Music/Samples/FieldRecordings`, process each one, and save the results in `~/Music/Samples/Processed_Recordings`.

```bash
python octatool.py batch ~/Music/Samples/FieldRecordings ~/Music/Samples/Processed_Recordings
```

**Options:**

- `--no-normalize`: Disables the audio normalization step.
- `--no-trim`: Disables the trimming of leading silence.
- `--headroom <dBFS>`: Sets the normalization headroom in dBFS (default: 3.0).
- `--mono`: Converts the output file to mono.
- `--bit-depth <16|24>`: Sets the output bit depth (default: 24).
- `--slices <number>`: Pads the sample chain with silent slices to a specific total number of slices. For best results with the Octatrack, use a power of two (e.g., 16, 32, 64).

---

### `chain` Command

Finds all audio files in a source directory, processes them, and concatenates them into a single output WAV file.

**Syntax:**

```bash
python octatool.py chain <input_dir> <output_file.wav> [options]
```

**Example:**
This command will create a single sample chain named `MySampleChain.wav` from all the audio files located in `~/Music/Samples/DrumKits/Kit01`.

```bash
python octatool.py chain ~/Music/Samples/DrumKits/Kit01 ~/Music/Samples/Chains/MySampleChain.wav
```

**Options:**

- `--no-normalize`: Disables the audio normalization step.
- `--no-trim`: Disables the trimming of leading silence.
- `--headroom <dBFS>`: Sets the normalization headroom in dBFS (default: 3.0).
- `--mono`: Converts the output file to mono.
- `--bit-depth <16|24>`: Sets the output bit depth (default: 24).

---

### `info` Command

Scans a directory and displays technical information about each audio file without performing any processing.

**Syntax:**

```bash
python octatool.py info <input_dir>
```

**Example:**
This command will display information for all audio files in `~/Music/Samples/FieldRecordings`.

```bash
python octatool.py info ~/Music/Samples/FieldRecordings
```

## License

This project is licensed under the MIT License.

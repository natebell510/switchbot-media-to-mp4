# SwitchBot Camera → MP4 Converter

Batch-converts SwitchBot camera SD card recordings (`.media` + `.info` files) into standard MP4 videos with audio.

## Download

**[⬇ Download SwitchBot_Converter.exe](https://github.com/natebell510/switchbot-media-to-mp4/releases/download/v1.2.0/SwitchBot_Converter.exe)** — double-click and run. FFmpeg installs automatically on first launch.

Or clone and run the Python script directly (see [Script usage](#python-script)).

---

## Requirements

| Requirement | Where to get it |
|---|---|
| **FFmpeg** | Installed automatically on first run — nothing to do |
| Python 3.8+ (script only) | [python.org](https://www.python.org/downloads/) — check "Add to PATH" |

---

## Quick Start

### Executable (easiest)

1. [Download `SwitchBot_Converter.exe`](https://github.com/natebell510/switchbot-media-to-mp4/releases/download/v1.2.0/SwitchBot_Converter.exe)
2. Double-click it — FFmpeg installs automatically if needed
3. Paste the path to your SD card folder when prompted
4. MP4 files appear in a `converted_mp4` subfolder

### Python script

```bash
pip install -r requirements.txt
python switchbot_converter.py "C:\path\to\recordings"
```

Optional: specify a custom output folder:

```bash
python switchbot_converter.py "C:\recordings" --output "D:\MP4s"
```

---

## How It Works

SwitchBot cameras write each recording as a folder containing:
- one or more `.media` fragments (raw H.264 video + AAC audio stream)
- a `.info` metadata file

This tool scans every subfolder, concatenates the `.media` fragments in order using FFmpeg's concat demuxer, and muxes them into a standard `.mp4` container. Stream-copy is tried first (fast, lossless); if that fails it falls back to H.264/AAC re-encode.

**Your original files are never modified.**

---

## Expected SD card structure

```
recordings/
├── 1778497595_0015/
│   ├── 0.media
│   └── 0.info
├── 1778497948_0017/
│   ├── 0.media
│   ├── 1.media
│   └── 0.info
└── ...
```

Output:

```
recordings/converted_mp4/
├── 1778497595_0015.mp4
├── 1778497948_0017.mp4
└── ...
```

---

## Build the EXE yourself

Requires Python 3.8+ and pip.

```bat
BUILD.bat
```

The executable is written to `dist\SwitchBot_Converter.exe`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `FFmpeg not found` | Install FFmpeg and **restart your terminal** |
| `No valid video folders found` | Make sure the folder you selected contains subfolders that each have `.media` and `.info` files |
| Video won't play | Open with [VLC](https://www.videolan.org/) — or re-run; the script will re-encode automatically on the second attempt |
| Conversion very slow | Normal for long recordings. A 1-hour clip takes ~3–8 minutes |

---

## License

MIT

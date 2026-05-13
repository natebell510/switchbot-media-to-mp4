# SwitchBot Camera → MP4 Converter
<img width="1362" height="1180" alt="converter" src="https://github.com/user-attachments/assets/262c507a-7339-4d3a-8ab1-2d322c1ecb48" />


Batch-converts SwitchBot camera SD card recordings (`.media` + `.info` files) into standard MP4 videos — drag, drop, done.

> **Not affiliated with or endorsed by SwitchBot / Wonderlabs Inc.**  
> "SwitchBot" is used purely as a descriptive reference to the camera format this tool supports.

## Download

**[⬇ Download SwitchBot_Converter.exe](https://github.com/natebell510/switchbot-media-to-mp4/releases/download/v1.3.0/SwitchBot_Converter.exe)** — graphical app, drag & drop, no setup required. Windows 10/11.

Or clone and run the Python script directly (see [Script usage](#python-script)).

---

## Quick Start

### Executable (easiest)

1. [Download `SwitchBot_Converter.exe`](https://github.com/natebell510/switchbot-media-to-mp4/releases/download/v1.3.0/SwitchBot_Converter.exe)
2. Double-click it — FFmpeg installs automatically on first run
3. Drag your recordings folder onto the drop zone (or click Browse)
4. Pick where to save the MP4s, then click **Convert**
5. The output folder opens automatically when done

### Python script

```bash
pip install -r requirements.txt
python switchbot_converter.py
```

Optional arguments:

```bash
python switchbot_converter.py "C:\path\to\recordings" --output "D:\MP4s"
```

---

## How It Works

SwitchBot cameras write each recording as a subfolder containing:
- one or more `.media` fragments (H.264 video + AAC audio)
- a `.info` metadata file

This tool scans every subfolder, concatenates the `.media` fragments in order via FFmpeg's concat demuxer, and muxes them into a standard `.mp4` container. Stream-copy is tried first (fast, lossless); if that fails it re-encodes to H.264/AAC automatically.

**Your original files are never modified or deleted.**

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

## Requirements

| Requirement | Notes |
|---|---|
| **Windows 10 / 11** | The `.exe` is Windows-only; the Python script runs on any OS |
| **FFmpeg** | Installed automatically on first run via `winget` — nothing to do manually |
| **Python 3.8+** | Only needed if running the script directly |

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
| FFmpeg install fails | Run `winget install --id Gyan.FFmpeg -e` manually in Command Prompt, then restart the app |
| No recordings found | Drop a parent folder — the app searches subfolders automatically |
| Video won't play | Open with [VLC](https://www.videolan.org/); the app will re-encode on the next run if stream-copy failed |
| Conversion very slow | Normal for long clips — a 1-hour recording takes ~3–8 minutes |

---

## Privacy

This tool processes video files locally on your computer. No data is uploaded or transmitted anywhere.

If you share or publish the converted MP4 files, you are responsible for ensuring you have the right to do so and that the content does not violate the privacy of any individuals recorded.

---

## Dependencies & Licenses

| Dependency | License | Notes |
|---|---|---|
| [FFmpeg](https://ffmpeg.org/) | LGPL 2.1+ / GPL 2+ | Installed separately; not bundled |
| [tkinterdnd2](https://github.com/pmgagne/tkinterdnd2) | MIT | Drag-and-drop support |
| Python standard library | PSF License | Bundled in the exe |

All dependencies are open-source and license-compatible with this project.

---

## License

[MIT](LICENSE) — free to use, modify, and distribute.

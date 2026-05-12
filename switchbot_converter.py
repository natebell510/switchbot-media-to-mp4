#!/usr/bin/env python3
"""SwitchBot camera .media/.info to MP4 batch converter."""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


def check_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def find_video_folders(parent: Path) -> list[tuple[str, list[Path], Path]]:
    """Return list of (folder_name, sorted_media_files, info_file) tuples."""
    results = []
    for entry in sorted(parent.iterdir()):
        if not entry.is_dir():
            continue
        info_files = list(entry.glob("*.info"))
        media_files = sorted(entry.glob("*.media"))
        if media_files and info_files:
            results.append((entry.name, media_files, info_files[0]))
        elif media_files:
            print(f"  Warning: no .info file in {entry.name} — skipping")
        elif info_files:
            print(f"  Warning: no .media files in {entry.name} — skipping")
    return results


def convert_video(
    media_files: list[Path],
    output_path: Path,
) -> tuple[bool, str]:
    """Concat-convert media fragments to MP4. Returns (success, message)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        concat_path = f.name
        for mf in media_files:
            # FFmpeg concat demuxer requires forward slashes and escaped paths
            safe = str(mf).replace("\\", "/").replace("'", "\\'")
            f.write(f"file '{safe}'\n")

    base_cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", concat_path,
    ]

    # Try stream-copy first (fast, lossless), fall back to re-encode
    attempts = [
        ([*base_cmd, "-c:v", "copy", "-c:a", "copy", "-y", str(output_path)], "stream-copy"),
        ([*base_cmd, "-c:v", "libx264", "-preset", "fast", "-crf", "18",
          "-c:a", "aac", "-b:a", "128k", "-y", str(output_path)], "re-encode"),
    ]

    for cmd, mode in attempts:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            if result.returncode == 0 and output_path.stat().st_size > 0:
                Path(concat_path).unlink(missing_ok=True)
                return True, f"{mode}, {len(media_files)} fragment(s)"
        except subprocess.TimeoutExpired:
            Path(concat_path).unlink(missing_ok=True)
            return False, "timeout (>15 min)"
        except Exception as exc:
            Path(concat_path).unlink(missing_ok=True)
            return False, str(exc)

    last_err = result.stderr[-300:] if result.stderr else "unknown"
    Path(concat_path).unlink(missing_ok=True)
    return False, f"ffmpeg: {last_err}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert SwitchBot .media/.info files to MP4.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  python switchbot_converter.py C:\\SD\\recordings",
    )
    parser.add_argument(
        "input", nargs="?",
        help="Folder containing per-video subfolders with .media/.info files",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output folder (default: <input>/converted_mp4)",
    )
    args = parser.parse_args()

    print("=" * 58)
    print("  SwitchBot Camera → MP4 Converter")
    print("=" * 58)

    # Resolve input folder
    input_folder_str = args.input or input("\nPath to SwitchBot recordings folder:\n> ").strip().strip('"')
    input_folder = Path(input_folder_str)
    if not input_folder.is_dir():
        print(f"\nError: not a directory: {input_folder}")
        return 1

    # Check FFmpeg
    if not check_ffmpeg():
        print("\nError: FFmpeg not found in PATH.")
        print("Install it with:  winget install --id BtbN.FFmpeg -e")
        print("Then restart your terminal.")
        return 1

    # Find videos
    print(f"\nScanning {input_folder} ...")
    videos = find_video_folders(input_folder)
    if not videos:
        print("No valid video folders found (need .media + .info pairs).")
        return 1
    print(f"Found {len(videos)} video(s) to convert.\n")

    # Output folder
    output_folder = Path(args.output) if args.output else input_folder / "converted_mp4"
    output_folder.mkdir(parents=True, exist_ok=True)
    print(f"Output → {output_folder}\n")

    # Convert
    ok = fail = 0
    errors: list[str] = []
    iterator = tqdm(videos, unit="video") if HAS_TQDM else videos

    for folder_name, media_files, info_file in iterator:
        out = output_folder / f"{folder_name}.mp4"
        success, msg = convert_video(media_files, out)
        if success:
            ok += 1
            if not HAS_TQDM:
                print(f"  OK  {folder_name}.mp4  ({msg})")
        else:
            fail += 1
            errors.append(f"{folder_name}: {msg}")
            if not HAS_TQDM:
                print(f"  FAIL  {folder_name}  — {msg}")

    # Summary
    print("\n" + "=" * 58)
    print(f"  Done: {ok} converted, {fail} failed  (total {len(videos)})")
    if errors:
        print("\nFailed videos:")
        for e in errors[:20]:
            print(f"  • {e}")
        if len(errors) > 20:
            print(f"  … and {len(errors) - 20} more")
    print(f"\n  MP4 files saved to: {output_folder}")
    print("=" * 58)

    return 0 if fail == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)

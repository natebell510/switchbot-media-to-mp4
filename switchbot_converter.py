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

_FFMPEG_SEARCH_PATHS = [
    Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "FFmpeg" / "bin" / "ffmpeg.exe",
    Path("C:/ffmpeg/bin/ffmpeg.exe"),
    Path("C:/tools/ffmpeg/bin/ffmpeg.exe"),
]


def _find_ffmpeg_in_winget() -> Path | None:
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if not base.is_dir():
        return None
    for exe in base.rglob("ffmpeg.exe"):
        return exe
    return None


def find_ffmpeg() -> str | None:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return "ffmpeg"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    for p in _FFMPEG_SEARCH_PATHS:
        if p.is_file():
            return str(p)
    found = _find_ffmpeg_in_winget()
    if found:
        return str(found)
    return None


def ensure_ffmpeg() -> str:
    exe = find_ffmpeg()
    if exe:
        return exe

    print("\nFFmpeg not found — installing automatically via winget...")
    print("(This only happens once and takes about 1-2 minutes)\n")

    try:
        result = subprocess.run(
            ["winget", "install", "--id", "Gyan.FFmpeg", "-e",
             "--accept-source-agreements", "--accept-package-agreements"],
            timeout=300,
        )
    except FileNotFoundError:
        print("Error: winget not found. Please install FFmpeg manually:")
        print("  https://ffmpeg.org/download.html")
        input("\nPress Enter to exit.")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("Error: FFmpeg installation timed out.")
        input("\nPress Enter to exit.")
        sys.exit(1)

    if result.returncode != 0:
        print("Trying alternate FFmpeg package...")
        subprocess.run(
            ["winget", "install", "--id", "BtbN.FFmpeg", "-e",
             "--accept-source-agreements", "--accept-package-agreements"],
            timeout=300,
        )

    exe = find_ffmpeg()
    if exe:
        print(f"\nFFmpeg installed: {exe}\n")
        return exe

    # Refresh PATH from registry and try once more
    try:
        new_path = subprocess.check_output(
            ["powershell", "-Command",
             "[System.Environment]::GetEnvironmentVariable('PATH','Machine') + ';' + "
             "[System.Environment]::GetEnvironmentVariable('PATH','User')"],
            text=True,
        ).strip()
        os.environ["PATH"] = new_path + ";" + os.environ.get("PATH", "")
        exe = find_ffmpeg()
        if exe:
            print(f"\nFFmpeg installed: {exe}\n")
            return exe
    except Exception:
        pass

    print("\nFFmpeg was installed but couldn't be located.")
    print("Please restart the program — it will work on the next run.")
    input("\nPress Enter to exit.")
    sys.exit(1)


def find_video_folders(parent: Path) -> list[tuple[str, list[Path], Path]]:
    """Return (folder_name, sorted_media_files, info_file) for each valid subfolder."""
    results = []
    for entry in sorted(parent.iterdir()):
        if not entry.is_dir():
            continue
        info_files = list(entry.glob("*.info"))
        media_files = sorted(entry.glob("*.media"))
        if media_files and info_files:
            results.append((entry.name, media_files, info_files[0]))
    return results


def find_media_root(start: Path, max_depth: int = 5) -> list[Path]:
    """
    Recursively search for folders that contain .media files.
    Returns unique parent directories that hold video subfolders.
    """
    candidates: set[Path] = set()

    def _walk(folder: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            for entry in folder.iterdir():
                if not entry.is_dir():
                    continue
                if list(entry.glob("*.media")):
                    # entry itself has .media files — its parent is the recordings root
                    candidates.add(folder)
                else:
                    _walk(entry, depth + 1)
        except PermissionError:
            pass

    _walk(start, 0)
    return sorted(candidates)


def pick_folder(initial: str | None) -> Path:
    """
    Ask the user for a folder, then validate it contains video subfolders.
    If not found at the given level, search deeper and offer to use the
    correct location automatically. Loops until a valid folder is chosen
    or the user quits.
    """
    prompt_path = initial

    while True:
        if prompt_path is None:
            prompt_path = input("\nPath to SwitchBot recordings folder:\n> ").strip().strip('"')

        folder = Path(prompt_path)

        if not folder.exists():
            print(f"\n  Folder not found: {folder}")
            prompt_path = None
            continue

        if not folder.is_dir():
            print(f"\n  That is a file, not a folder: {folder}")
            prompt_path = None
            continue

        print(f"\nScanning {folder} ...")
        videos = find_video_folders(folder)

        if videos:
            return folder  # good — caller will use this

        # Nothing found at this level — search deeper
        print("  No .media files found here. Searching subfolders...")
        roots = find_media_root(folder)

        if not roots:
            print("\n  No SwitchBot recordings found anywhere under that folder.")
            print("  Make sure you are pointing to the SD card or the folder that")
            print("  contains the dated subfolders (e.g. DCIM\\2026\\05\\12\\).")
            print("\n  [R] Try a different path   [Q] Quit")
            choice = input("> ").strip().lower()
            if choice == "q":
                sys.exit(0)
            prompt_path = None
            continue

        if len(roots) == 1:
            found = roots[0]
            print(f"\n  Found recordings in: {found}")
            confirm = input("  Use this folder? [Y/n]: ").strip().lower()
            if confirm in ("", "y", "yes"):
                return found
            prompt_path = None
            continue

        # Multiple candidate roots — let user pick
        print(f"\n  Found recordings in {len(roots)} location(s):")
        for i, r in enumerate(roots, 1):
            count = len(find_video_folders(r))
            print(f"  [{i}] {r}  ({count} video(s))")
        print(f"  [R] Enter a different path   [Q] Quit")
        choice = input("\nChoose a number: ").strip().lower()
        if choice == "q":
            sys.exit(0)
        if choice == "r":
            prompt_path = None
            continue
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(roots):
                return roots[idx]
        except ValueError:
            pass
        print("  Invalid choice.")
        prompt_path = None


def convert_video(ffmpeg: str, media_files: list[Path], output_path: Path) -> tuple[bool, str]:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        concat_path = f.name
        for mf in media_files:
            safe = str(mf).replace("\\", "/").replace("'", "\\'")
            f.write(f"file '{safe}'\n")

    base_cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", concat_path,
    ]
    attempts = [
        ([*base_cmd, "-c:v", "copy", "-c:a", "copy", "-y", str(output_path)], "stream-copy"),
        ([*base_cmd, "-c:v", "libx264", "-preset", "fast", "-crf", "18",
          "-c:a", "aac", "-b:a", "128k", "-y", str(output_path)], "re-encode"),
    ]

    result = None
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

    last_err = result.stderr[-300:] if result and result.stderr else "unknown"
    Path(concat_path).unlink(missing_ok=True)
    return False, f"ffmpeg: {last_err}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert SwitchBot .media/.info files to MP4.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  SwitchBot_Converter.exe C:\\SD\\recordings",
    )
    parser.add_argument("input", nargs="?",
                        help="Folder with per-video subfolders containing .media/.info files")
    parser.add_argument("--output", "-o",
                        help="Output folder (default: <input>/converted_mp4)")
    args = parser.parse_args()

    print("=" * 58)
    print("  SwitchBot Camera  →  MP4 Converter")
    print("=" * 58)

    ffmpeg = ensure_ffmpeg()

    input_folder = pick_folder(args.input)

    videos = find_video_folders(input_folder)
    print(f"Found {len(videos)} video(s) to convert.\n")

    output_folder = Path(args.output) if args.output else input_folder / "converted_mp4"
    output_folder.mkdir(parents=True, exist_ok=True)
    print(f"Output → {output_folder}\n")

    ok = fail = 0
    errors: list[str] = []
    iterator = tqdm(videos, unit="video") if HAS_TQDM else videos

    for folder_name, media_files, info_file in iterator:
        out = output_folder / f"{folder_name}.mp4"
        success, msg = convert_video(ffmpeg, media_files, out)
        if success:
            ok += 1
            if not HAS_TQDM:
                print(f"  OK  {folder_name}.mp4  ({msg})")
        else:
            fail += 1
            errors.append(f"{folder_name}: {msg}")
            if not HAS_TQDM:
                print(f"  FAIL  {folder_name}  — {msg}")

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
    input("\nPress Enter to exit.")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)

#!/usr/bin/env python3
"""SwitchBot camera .media/.info to MP4 converter — GUI edition."""

import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

# ─── FFmpeg helpers ──────────────────────────────────────────────────────────

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
    for p in [
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "FFmpeg/bin/ffmpeg.exe",
        Path("C:/ffmpeg/bin/ffmpeg.exe"),
        Path("C:/tools/ffmpeg/bin/ffmpeg.exe"),
    ]:
        if p.is_file():
            return str(p)
    found = _find_ffmpeg_in_winget()
    return str(found) if found else None

def install_ffmpeg(log) -> str | None:
    """Install FFmpeg via winget, logging to callback. Returns path or None."""
    log("FFmpeg not found — installing via winget (one-time, ~2 min)…")
    try:
        for pkg in ("Gyan.FFmpeg", "BtbN.FFmpeg"):
            r = subprocess.run(
                ["winget", "install", "--id", pkg, "-e",
                 "--accept-source-agreements", "--accept-package-agreements"],
                capture_output=True, text=True, timeout=300,
            )
            if r.returncode == 0:
                break
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        log(f"winget error: {e}")
        return None
    # Refresh PATH
    try:
        new_path = subprocess.check_output(
            ["powershell", "-Command",
             "[System.Environment]::GetEnvironmentVariable('PATH','Machine')+';'+"
             "[System.Environment]::GetEnvironmentVariable('PATH','User')"],
            text=True,
        ).strip()
        os.environ["PATH"] = new_path + ";" + os.environ.get("PATH", "")
    except Exception:
        pass
    return find_ffmpeg()

# ─── Conversion helpers ───────────────────────────────────────────────────────

def find_video_folders(parent: Path):
    results = []
    for entry in sorted(parent.iterdir()):
        if not entry.is_dir():
            continue
        media = sorted(entry.glob("*.media"))
        info  = list(entry.glob("*.info"))
        if media and info:
            results.append((entry.name, media, info[0]))
    return results

def find_media_root(start: Path, max_depth=5):
    candidates: set[Path] = set()
    def _walk(folder, depth):
        if depth > max_depth:
            return
        try:
            for e in folder.iterdir():
                if not e.is_dir():
                    continue
                if list(e.glob("*.media")):
                    candidates.add(folder)
                else:
                    _walk(e, depth + 1)
        except PermissionError:
            pass
    _walk(start, 0)
    return sorted(candidates)

def convert_video(ffmpeg: str, media_files: list, output_path: Path):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        concat = f.name
        for mf in media_files:
            safe = str(mf).replace("\\", "/").replace("'", "\\'")
            f.write(f"file '{safe}'\n")

    base = [ffmpeg, "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", concat]
    attempts = [
        ([*base, "-c:v", "copy", "-c:a", "copy", "-y", str(output_path)], "stream-copy"),
        ([*base, "-c:v", "libx264", "-preset", "fast", "-crf", "18",
          "-c:a", "aac", "-b:a", "128k", "-y", str(output_path)], "re-encode"),
    ]
    result = None
    for cmd, mode in attempts:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            if result.returncode == 0 and output_path.stat().st_size > 0:
                Path(concat).unlink(missing_ok=True)
                return True, mode
        except subprocess.TimeoutExpired:
            Path(concat).unlink(missing_ok=True)
            return False, "timeout"
        except Exception as exc:
            Path(concat).unlink(missing_ok=True)
            return False, str(exc)
    err = result.stderr[-200:] if result and result.stderr else "unknown"
    Path(concat).unlink(missing_ok=True)
    return False, err

# ─── GUI ─────────────────────────────────────────────────────────────────────

ACCENT   = "#4A90D9"
BG       = "#1E1E2E"
CARD     = "#2A2A3E"
TEXT     = "#E0E0F0"
SUBTEXT  = "#888899"
SUCCESS  = "#4CAF50"
FAIL     = "#F44336"
WARN     = "#FF9800"

class App(TkinterDnD.Tk if HAS_DND else tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SwitchBot → MP4 Converter")
        self.geometry("680x560")
        self.minsize(560, 480)
        self.configure(bg=BG)
        self.resizable(True, True)

        self.input_folder: Path | None = None
        self.output_folder: Path | None = None
        self.ffmpeg: str | None = None
        self._running = False

        self._build_ui()
        self.after(100, self._check_ffmpeg_async)

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        # Title bar
        hdr = tk.Frame(self, bg=ACCENT, height=4)
        hdr.pack(fill="x")

        tk.Label(self, text="SwitchBot  →  MP4 Converter",
                 bg=BG, fg=TEXT, font=("Segoe UI", 16, "bold"),
                 pady=14).pack()

        # Status badge
        self.status_var = tk.StringVar(value="Checking FFmpeg…")
        self.status_lbl = tk.Label(self, textvariable=self.status_var,
                                   bg=BG, fg=WARN, font=("Segoe UI", 9))
        self.status_lbl.pack()

        # ── Drop zone ────────────────────────────────────────────────────────
        drop_frame = tk.Frame(self, bg=CARD, bd=0, relief="flat",
                              highlightthickness=2, highlightbackground=ACCENT)
        drop_frame.pack(fill="x", padx=24, pady=(16, 6))

        self.drop_lbl = tk.Label(
            drop_frame,
            text="⬇  Drag your recordings folder here\n"
                 "or click Browse to select it",
            bg=CARD, fg=SUBTEXT,
            font=("Segoe UI", 11),
            pady=28, padx=20, cursor="hand2",
        )
        self.drop_lbl.pack(fill="both")

        if HAS_DND:
            self.drop_lbl.drop_target_register(DND_FILES)
            self.drop_lbl.dnd_bind("<<Drop>>", self._on_drop)
        self.drop_lbl.bind("<Button-1>", lambda _: self._browse_input())

        # Selected input path
        self.input_var = tk.StringVar(value="")
        self.input_path_lbl = tk.Label(self, textvariable=self.input_var,
                                       bg=BG, fg=ACCENT,
                                       font=("Segoe UI", 9),
                                       wraplength=600, justify="center")
        self.input_path_lbl.pack(pady=(0, 4))

        # ── Output folder row ─────────────────────────────────────────────────
        out_row = tk.Frame(self, bg=BG)
        out_row.pack(fill="x", padx=24, pady=4)

        tk.Label(out_row, text="Save MP4s to:", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(side="left")

        self.output_var = tk.StringVar(value="Same folder as recordings  (converted_mp4 subfolder)")
        tk.Label(out_row, textvariable=self.output_var,
                 bg=BG, fg=TEXT, font=("Segoe UI", 9),
                 wraplength=420, justify="left").pack(side="left", padx=8)

        tk.Button(out_row, text="Change…", bg=CARD, fg=TEXT,
                  font=("Segoe UI", 8), bd=0, padx=8, pady=3,
                  activebackground=ACCENT, activeforeground="white",
                  cursor="hand2",
                  command=self._browse_output).pack(side="right")

        # ── Convert button ────────────────────────────────────────────────────
        self.convert_btn = tk.Button(
            self, text="Convert",
            bg=ACCENT, fg="white",
            font=("Segoe UI", 12, "bold"),
            bd=0, padx=32, pady=10,
            activebackground="#357ABD", activeforeground="white",
            cursor="hand2", state="disabled",
            command=self._start_conversion,
        )
        self.convert_btn.pack(pady=(12, 6))

        # ── Progress ──────────────────────────────────────────────────────────
        prog_frame = tk.Frame(self, bg=BG)
        prog_frame.pack(fill="x", padx=24)

        self.progress = ttk.Progressbar(prog_frame, mode="determinate", length=400)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TProgressbar", troughcolor=CARD, background=ACCENT, thickness=8)
        self.progress.pack(fill="x", pady=(0, 4))

        self.prog_lbl = tk.Label(prog_frame, text="", bg=BG, fg=SUBTEXT,
                                 font=("Segoe UI", 8))
        self.prog_lbl.pack()

        # ── Log box ───────────────────────────────────────────────────────────
        log_frame = tk.Frame(self, bg=BG)
        log_frame.pack(fill="both", expand=True, padx=24, pady=(8, 16))

        self.log_box = tk.Text(log_frame, bg=CARD, fg=TEXT,
                               font=("Consolas", 8),
                               bd=0, padx=8, pady=6,
                               state="disabled", wrap="word",
                               height=8)
        self.log_box.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(log_frame, command=self.log_box.yview)
        sb.pack(side="right", fill="y")
        self.log_box.configure(yscrollcommand=sb.set)

        self.log_box.tag_config("ok",   foreground=SUCCESS)
        self.log_box.tag_config("fail", foreground=FAIL)
        self.log_box.tag_config("info", foreground=SUBTEXT)
        self.log_box.tag_config("warn", foreground=WARN)

    # ── FFmpeg check ──────────────────────────────────────────────────────────

    def _check_ffmpeg_async(self):
        def _run():
            exe = find_ffmpeg()
            if exe:
                self.ffmpeg = exe
                self._set_status("FFmpeg ready", SUCCESS)
                self._try_enable_convert()
            else:
                self._set_status("FFmpeg not found — will install on first convert", WARN)
        threading.Thread(target=_run, daemon=True).start()

    def _ensure_ffmpeg_blocking(self) -> bool:
        if self.ffmpeg:
            return True
        self._set_status("Installing FFmpeg…", WARN)
        exe = install_ffmpeg(self._log)
        if exe:
            self.ffmpeg = exe
            self._set_status("FFmpeg ready", SUCCESS)
            return True
        self._set_status("FFmpeg installation failed", FAIL)
        messagebox.showerror(
            "FFmpeg missing",
            "Could not install FFmpeg automatically.\n\n"
            "Please install it manually:\n"
            "  winget install --id Gyan.FFmpeg -e\n\n"
            "Then restart this app.",
        )
        return False

    # ── Folder selection ──────────────────────────────────────────────────────

    def _browse_input(self):
        folder = filedialog.askdirectory(title="Select SwitchBot recordings folder")
        if folder:
            self._set_input(Path(folder))

    def _browse_output(self):
        folder = filedialog.askdirectory(title="Select output folder for MP4 files")
        if folder:
            self.output_folder = Path(folder)
            self.output_var.set(str(self.output_folder))

    def _on_drop(self, event):
        raw = event.data.strip()
        # tkinterdnd2 wraps paths with spaces in braces
        if raw.startswith("{") and raw.endswith("}"):
            raw = raw[1:-1]
        self._set_input(Path(raw))

    def _set_input(self, folder: Path):
        if not folder.is_dir():
            self._log(f"Not a folder: {folder}", "fail")
            return

        # Check for videos directly
        videos = find_video_folders(folder)
        if videos:
            self.input_folder = folder
            self.input_var.set(str(folder))
            self._log(f"Found {len(videos)} video(s) in {folder}", "ok")
            self._try_enable_convert()
            return

        # Search deeper
        self._log(f"No recordings found directly in {folder.name} — searching…", "info")
        roots = find_media_root(folder)
        if not roots:
            self._log("No SwitchBot recordings found in that folder or any subfolder.", "fail")
            self._log("Make sure you selected the right SD card / recordings folder.", "warn")
            return

        if len(roots) == 1:
            found = roots[0]
            count = len(find_video_folders(found))
            self.input_folder = found
            self.input_var.set(str(found))
            self._log(f"Auto-detected: {found}  ({count} video(s))", "ok")
            self._try_enable_convert()
            return

        # Multiple — show picker dialog
        self._pick_root_dialog(roots)

    def _pick_root_dialog(self, roots: list):
        dlg = tk.Toplevel(self)
        dlg.title("Multiple recording folders found")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        tk.Label(dlg, text="Multiple recording locations were found.\nChoose one:",
                 bg=BG, fg=TEXT, font=("Segoe UI", 10), pady=12, padx=16).pack()

        var = tk.IntVar(value=0)
        for i, r in enumerate(roots):
            count = len(find_video_folders(r))
            tk.Radiobutton(
                dlg, text=f"{r}  ({count} video(s))",
                variable=var, value=i,
                bg=BG, fg=TEXT, selectcolor=CARD,
                activebackground=BG, font=("Segoe UI", 9),
            ).pack(anchor="w", padx=20)

        def _ok():
            chosen = roots[var.get()]
            count = len(find_video_folders(chosen))
            self.input_folder = chosen
            self.input_var.set(str(chosen))
            self._log(f"Selected: {chosen}  ({count} video(s))", "ok")
            self._try_enable_convert()
            dlg.destroy()

        tk.Button(dlg, text="Use selected folder",
                  bg=ACCENT, fg="white", font=("Segoe UI", 10, "bold"),
                  bd=0, padx=16, pady=6, command=_ok).pack(pady=14)

    def _try_enable_convert(self):
        if self.input_folder:
            self.convert_btn.configure(state="normal")

    # ── Conversion ────────────────────────────────────────────────────────────

    def _start_conversion(self):
        if self._running:
            return
        if not self._ensure_ffmpeg_blocking():
            return

        out = self.output_folder or (self.input_folder / "converted_mp4")
        out.mkdir(parents=True, exist_ok=True)
        if not self.output_folder:
            self.output_var.set(str(out))

        videos = find_video_folders(self.input_folder)
        if not videos:
            messagebox.showwarning("Nothing to convert",
                                   "No .media + .info pairs found in the selected folder.")
            return

        self._running = True
        self.convert_btn.configure(state="disabled", text="Converting…")
        self.progress["maximum"] = len(videos)
        self.progress["value"] = 0
        self._log(f"Starting conversion of {len(videos)} video(s)…", "info")
        self._log(f"Output → {out}", "info")

        threading.Thread(
            target=self._run_conversion,
            args=(videos, out),
            daemon=True,
        ).start()

    def _run_conversion(self, videos, out: Path):
        ok = fail = 0
        for i, (name, media, info) in enumerate(videos, 1):
            output_path = out / f"{name}.mp4"
            success, msg = convert_video(self.ffmpeg, media, output_path)
            if success:
                ok += 1
                self._log(f"  ✓  {name}.mp4  ({msg})", "ok")
            else:
                fail += 1
                self._log(f"  ✗  {name}  — {msg}", "fail")
            self.after(0, self._update_progress, i, len(videos), ok, fail)

        self.after(0, self._done, ok, fail, out)

    def _update_progress(self, current, total, ok, fail):
        self.progress["value"] = current
        self.prog_lbl.configure(
            text=f"{current}/{total}  —  {ok} done, {fail} failed"
        )

    def _done(self, ok, fail, out: Path):
        self._running = False
        total = ok + fail
        self.convert_btn.configure(state="normal", text="Convert")
        self.progress["value"] = total

        if fail == 0:
            self._set_status(f"Done — {ok} MP4(s) saved", SUCCESS)
            self._log(f"\nAll {ok} video(s) converted successfully.", "ok")
            if messagebox.askyesno("Done!", f"{ok} video(s) converted.\n\nOpen output folder?"):
                os.startfile(out)
        else:
            self._set_status(f"Done — {ok} ok, {fail} failed", WARN)
            self._log(f"\nFinished: {ok} ok, {fail} failed.", "warn")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, color: str = TEXT):
        self.after(0, lambda: (
            self.status_var.set(msg),
            self.status_lbl.configure(fg=color),
        ))

    def _log(self, msg: str, tag: str = ""):
        def _insert():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n", tag)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, _insert)


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()

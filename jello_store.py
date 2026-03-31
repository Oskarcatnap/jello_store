"""
Jello Store — Repository Manager
Created by Oskarcatnap
"""

import customtkinter as ctk
import threading
import os
import sys
import requests
import tempfile
import subprocess
import re
from tkinter import messagebox

# ── Theme ──────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

TEAL   = "#00FFCC"
YELLOW = "#FFE033"
BG     = "#0A0D12"
CARD   = "#111620"
CARD2  = "#161C2A"
CARD3  = "#1C2436"
TEXT   = "#E8EDF5"
MUTED  = "#4A5568"
MUTED2 = "#2D3748"
DANGER = "#FF4D6A"
SUCCESS= "#00E5A0"


# ══════════════════════════════════════════════════════════════════════════
#  DATA LAYER
# ══════════════════════════════════════════════════════════════════════════

def fetch_description(base_url: str) -> dict[str, str]:
    """
    Downloads <base_url>/description.txt and parses it.
    Each non-blank line must match:  filename = (description)
    Returns {filename: description, …}
    """
    url = base_url.rstrip("/") + "/description.txt"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()

    items: dict[str, str] = {}
    pattern = re.compile(r"^\s*(\S+)\s*=\s*\((.+)\)\s*$")
    for line in resp.text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = pattern.match(line)
        if m:
            fname, desc = m.group(1).strip(), m.group(2).strip()
            items[fname] = desc
    return items


def download_and_run_file(base_url: str, filename: str,
                           on_progress=None, on_done=None, on_error=None):
    """
    Downloads <base_url>/<filename> to a temp file and launches it.
    Callbacks run on the download thread — wrap in app.after() if needed.
    """
    url = base_url.rstrip("/") + "/" + filename

    # Guess extension: prefer what's in the filename, fallback to .exe
    ext = os.path.splitext(filename)[-1] or ".exe"

    try:
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                tmp.write(chunk)
                downloaded += len(chunk)
                if on_progress and total:
                    on_progress(downloaded / total)
        tmp.close()

        subprocess.Popen([tmp.name], shell=True)
        if on_done:
            on_done()

    except Exception as exc:
        if on_error:
            on_error(str(exc))


# ══════════════════════════════════════════════════════════════════════════
#  WIDGETS
# ══════════════════════════════════════════════════════════════════════════

class AppCard(ctk.CTkFrame):
    """A single repository item card."""

    def __init__(self, master, base_url: str, filename: str, description: str, **kw):
        super().__init__(master, fg_color=CARD2, corner_radius=14, **kw)
        self.base_url    = base_url
        self.filename    = filename
        self.description = description

        self.columnconfigure(0, weight=1)

        # ── Icon badge ────────────────────────────────────────────────────
        badge = ctk.CTkFrame(self, width=46, height=46,
                              fg_color=CARD3, corner_radius=10)
        badge.grid(row=0, column=0, rowspan=2, padx=(14, 0), pady=14, sticky="w")
        badge.grid_propagate(False)
        ctk.CTkLabel(badge, text="⬡",
                     font=ctk.CTkFont(size=22),
                     text_color=TEAL).place(relx=.5, rely=.5, anchor="center")

        # ── Text ──────────────────────────────────────────────────────────
        text_frame = ctk.CTkFrame(self, fg_color="transparent")
        text_frame.grid(row=0, column=0, padx=(72, 130), pady=(12, 0), sticky="w")

        ctk.CTkLabel(text_frame, text=filename,
                     font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
                     text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(text_frame, text=description,
                     font=ctk.CTkFont(family="Courier New", size=10),
                     text_color=MUTED, wraplength=240, justify="left").pack(anchor="w")

        # ── Progress bar (hidden) ─────────────────────────────────────────
        self.prog = ctk.CTkProgressBar(self, height=4, progress_color=TEAL,
                                        fg_color=MUTED2, corner_radius=2)
        self.prog.set(0)
        self.prog.grid(row=1, column=0, padx=14, pady=(0, 10), sticky="ew")
        self.prog.grid_remove()

        # ── GET button ────────────────────────────────────────────────────
        self.get_btn = ctk.CTkButton(
            self,
            text="GET",
            width=72,
            height=32,
            font=ctk.CTkFont(family="Courier New", size=12, weight="bold"),
            fg_color=TEAL,
            text_color="#000000",
            hover_color="#00CCAA",
            corner_radius=8,
            command=self._on_get,
        )
        self.get_btn.grid(row=0, column=0, padx=(0, 14), pady=14, sticky="e")

    # ── Handlers ──────────────────────────────────────────────────────────

    def _on_get(self):
        self.get_btn.configure(state="disabled", text="…", fg_color=MUTED)
        self.prog.grid()
        self.prog.set(0)

        def on_prog(frac):
            self.after(0, lambda: self.prog.set(frac))

        def on_done():
            self.after(0, self._reset_btn)
            self.after(0, lambda: self.prog.grid_remove())

        def on_err(msg):
            self.after(0, self._reset_btn)
            self.after(0, lambda: self.prog.grid_remove())
            self.after(0, lambda: messagebox.showerror(
                "Jello Store — Error",
                f"Could not download '{self.filename}':\n{msg}",
            ))

        threading.Thread(
            target=download_and_run_file,
            args=(self.base_url, self.filename),
            kwargs={"on_progress": on_prog, "on_done": on_done, "on_error": on_err},
            daemon=True,
        ).start()

    def _reset_btn(self):
        self.get_btn.configure(state="normal", text="GET", fg_color=TEAL)


class RepoSection(ctk.CTkFrame):
    """Container that holds all cards for one repository URL."""

    def __init__(self, master, base_url: str, items: dict[str, str], **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.columnconfigure(0, weight=1)

        short = base_url.rstrip("/").split("/")[-1] or base_url
        header = ctk.CTkFrame(self, fg_color=CARD3, corner_radius=10)
        header.grid(row=0, column=0, pady=(0, 8), sticky="ew")
        ctk.CTkLabel(header, text=f"  ⬡  {short}",
                     font=ctk.CTkFont(family="Courier New", size=11, weight="bold"),
                     text_color=YELLOW).pack(anchor="w", padx=10, pady=6)

        for idx, (fname, desc) in enumerate(items.items()):
            card = AppCard(self, base_url=base_url,
                           filename=fname, description=desc)
            card.grid(row=idx + 1, column=0, pady=(0, 8), sticky="ew")


# ══════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════════

class JelloStore(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("Jello Store")
        self.geometry("600x720")
        self.minsize(540, 560)
        self.configure(fg_color=BG)

        # Center
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - 600) // 2
        y = (self.winfo_screenheight() - 720) // 2
        self.geometry(f"600x720+{x}+{y}")

        self._repos: dict[str, dict[str, str]] = {}   # url → {fname: desc}
        self._build_ui()

    # ── Layout ────────────────────────────────────────────────────────────

    def _build_ui(self):
        import tkinter as tk

        # Background grid
        self._canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self._canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.bind("<Configure>", self._redraw_grid)

        # ── Header bar ────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=64)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        ctk.CTkLabel(header,
                     text="JELLO",
                     font=ctk.CTkFont(family="Courier New", size=26, weight="bold"),
                     text_color=TEAL).place(x=20, rely=0.5, anchor="w")
        ctk.CTkLabel(header,
                     text="STORE",
                     font=ctk.CTkFont(family="Courier New", size=26, weight="bold"),
                     text_color=YELLOW).place(x=88, rely=0.5, anchor="w")
        ctk.CTkLabel(header,
                     text="repository manager",
                     font=ctk.CTkFont(family="Courier New", size=10),
                     text_color=MUTED).place(x=200, rely=0.5, anchor="w")
        ctk.CTkLabel(header,
                     text="Created by Oskarcatnap",
                     font=ctk.CTkFont(family="Courier New", size=9),
                     text_color=MUTED).place(relx=1.0, rely=0.5, anchor="e", x=-14)

        # ── Input strip ───────────────────────────────────────────────────
        input_bar = ctk.CTkFrame(self, fg_color=CARD2, corner_radius=0, height=72)
        input_bar.pack(fill="x")
        input_bar.pack_propagate(False)

        self.url_entry = ctk.CTkEntry(
            input_bar,
            placeholder_text="https://raw.githubusercontent.com/…/repo/",
            font=ctk.CTkFont(family="Courier New", size=11),
            fg_color=CARD3,
            border_color=MUTED2,
            text_color=TEXT,
            placeholder_text_color=MUTED,
            corner_radius=10,
            height=40,
        )
        self.url_entry.place(relx=0.02, rely=0.5, relwidth=0.68, anchor="w")
        self.url_entry.bind("<Return>", lambda _: self._add_repo())

        self.add_btn = ctk.CTkButton(
            input_bar,
            text="Add Repository",
            font=ctk.CTkFont(family="Courier New", size=12, weight="bold"),
            fg_color=TEAL,
            text_color="#000000",
            hover_color="#00CCAA",
            corner_radius=10,
            height=40,
            command=self._add_repo,
        )
        self.add_btn.place(relx=0.72, rely=0.5, relwidth=0.26, anchor="w")

        # ── Status strip ──────────────────────────────────────────────────
        self.status_bar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=28)
        self.status_bar.pack(fill="x")
        self.status_bar.pack_propagate(False)

        self.status_lbl = ctk.CTkLabel(
            self.status_bar,
            text="  ◈  Add a GitHub raw repo URL to get started.",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color=MUTED,
        )
        self.status_lbl.pack(side="left", padx=6)

        self.spinner_lbl = ctk.CTkLabel(
            self.status_bar, text="",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color=TEAL,
        )
        self.spinner_lbl.pack(side="right", padx=10)

        # ── Scrollable cards area ─────────────────────────────────────────
        self.scroll_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent", scrollbar_button_color=MUTED2,
            scrollbar_button_hover_color=MUTED,
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)
        self.scroll_frame.columnconfigure(0, weight=1)

        self._empty_lbl = ctk.CTkLabel(
            self.scroll_frame,
            text="No repositories yet.\nPaste a URL above and click Add Repository.",
            font=ctk.CTkFont(family="Courier New", size=12),
            text_color=MUTED,
            justify="center",
        )
        self._empty_lbl.grid(row=0, column=0, pady=80)

        self._section_row = 0

    # ── Grid background ───────────────────────────────────────────────────

    def _redraw_grid(self, event=None):
        w, h = self.winfo_width(), self.winfo_height()
        self._canvas.delete("all")
        for i in range(0, w, 40):
            self._canvas.create_line(i, 0, i, h, fill="#0F1520", width=1)
        for j in range(0, h, 40):
            self._canvas.create_line(0, j, w, j, fill="#0F1520", width=1)

    # ── Logic ─────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, color=MUTED):
        self.status_lbl.configure(text=f"  ◈  {msg}", text_color=color)

    def _add_repo(self):
        url = self.url_entry.get().strip()
        if not url:
            self._set_status("Please enter a repository URL.", DANGER)
            return
        if url in self._repos:
            self._set_status("Repository already added.", YELLOW)
            return

        self.add_btn.configure(state="disabled", text="Loading…", fg_color=MUTED)
        self._set_status("Fetching description.txt …", TEAL)

        def task():
            try:
                items = fetch_description(url)
                if not items:
                    self.after(0, lambda: self._set_status(
                        "description.txt found but no valid entries parsed.", YELLOW))
                    self.after(0, self._reset_add_btn)
                    return

                self._repos[url] = items
                self.after(0, lambda: self._render_repo(url, items))
            except requests.exceptions.ConnectionError:
                self.after(0, lambda: self._set_status(
                    "Network error — check your connection.", DANGER))
                self.after(0, self._reset_add_btn)
            except requests.exceptions.Timeout:
                self.after(0, lambda: self._set_status("Request timed out.", DANGER))
                self.after(0, self._reset_add_btn)
            except requests.exceptions.HTTPError as e:
                self.after(0, lambda: self._set_status(
                    f"HTTP error: {e}", DANGER))
                self.after(0, self._reset_add_btn)
            except Exception as e:
                self.after(0, lambda: self._set_status(f"Error: {e}", DANGER))
                self.after(0, self._reset_add_btn)

        threading.Thread(target=task, daemon=True).start()

    def _reset_add_btn(self):
        self.add_btn.configure(state="normal", text="Add Repository", fg_color=TEAL)

    def _render_repo(self, url: str, items: dict[str, str]):
        # Remove empty label
        self._empty_lbl.grid_remove()

        section = RepoSection(self.scroll_frame, base_url=url, items=items)
        section.grid(row=self._section_row, column=0,
                     padx=16, pady=(12, 4), sticky="ew")
        self._section_row += 1

        n = len(items)
        self._set_status(
            f"Loaded {n} item{'s' if n != 1 else ''} from {url.split('/')[-2] or url}.",
            SUCCESS,
        )
        self._reset_add_btn()
        self.url_entry.delete(0, "end")


# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = JelloStore()
    app.mainloop()

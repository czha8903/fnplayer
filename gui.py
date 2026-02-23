import json
import subprocess
import threading
from datetime import datetime
from pathlib import Path
import os

from flask import Flask, request, jsonify

import tkinter as tk
from tkinter import filedialog, messagebox

# Config
CONFIG_PATH = Path("./config.json")
LOG_DIR = Path("./recv_logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "received.jsonl"

DEFAULT_CONFIG = {
    "potplayer_exe": r" ",
    "web_prefix": " ",
    "unc_root": r" ",
    "host": "127.0.0.1",
    "port": 8080,
}

_config_lock = threading.Lock()
_config = None  # loaded at runtime


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            merged = DEFAULT_CONFIG.copy()
            merged.update({k: v for k, v in data.items() if v is not None})
            return merged
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict):
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(obj: dict):
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def normalize_prefix(s: str) -> str:
    return (s or "").strip().rstrip("/").rstrip("\\")


def map_web_path_to_unc(web_path: str, web_prefix: str, unc_root: str) -> str:

    web_path = (web_path or "").strip()
    if not web_path:
        return ""

    web_prefix = normalize_prefix(web_prefix)
    unc_root = normalize_prefix(unc_root)

    wp = web_path.replace("\\", "/")

    if web_prefix:
        if wp.startswith(web_prefix):
            wp = wp[len(web_prefix):]
        elif wp.startswith(web_prefix + "/"):
            wp = wp[len(web_prefix) + 1:]
        else:
            key = "/NAS 的文件/"
            idx = wp.find(key)
            if idx >= 0:
                wp = wp[idx + len(key):]
    wp = wp.lstrip("/")
    rel = wp.replace("/", "\\")
    if rel:
        return unc_root + "\\" + rel
    return unc_root


def run_potplayer(potplayer_exe: str, file_path: str):
    potplayer_exe = (potplayer_exe or "").strip().strip('"')
    file_path = (file_path or "").strip().strip('"')

    if not potplayer_exe or not Path(potplayer_exe).exists():
        raise FileNotFoundError(f"PotPlayer exe not found: {potplayer_exe}")
    cmd = [potplayer_exe, file_path]
    subprocess.Popen(cmd, shell=False)

# Flask
app = Flask(__name__)


@app.get("/ping")
def ping():
    return jsonify(ok=True)


@app.post("/push")
def push():
    data = request.get_json(silent=True) or request.form.to_dict() or {}

    url = data.get("url", "")
    web_path = data.get("path", "")
    meta = data.get("meta", None)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with _config_lock:
        cfg = _config.copy()

    potplayer_exe = cfg.get("potplayer_exe", "")
    web_prefix = cfg.get("web_prefix", "")
    unc_root = cfg.get("unc_root", "")

    mapped = map_web_path_to_unc(web_path, web_prefix, unc_root)

    print(f"[{ts}] url={url}")
    print(f"[{ts}] web_path={web_path}")
    print(f"[{ts}] mapped={mapped}")
    if meta is not None:
        print(f"[{ts}] meta={meta}")

    append_jsonl({
        "ts": ts,
        "url": url,
        "web_path": web_path,
        "mapped": mapped,
        "meta": meta,
        "remote_addr": request.remote_addr,
        "user_agent": request.headers.get("User-Agent", ""),
    })
    print("-" * 50)

    try:
        run_potplayer(potplayer_exe, mapped)
        return jsonify(ok=True, mapped=mapped)
    except Exception as e:
        print("ERROR:", repr(e))
        return jsonify(ok=False, error=str(e), mapped=mapped), 500


def start_flask_in_thread():
    def _run():
        with _config_lock:
            host = _config.get("host", "127.0.0.1")
            port = int(_config.get("port", 8080))
        # threaded=True 让 push 不会卡 GUI
        app.run(host=host, port=port, debug=False, threaded=True)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

# GUI (Tkinter)
class AppGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("NAS PotPlayer Receiver")
        root.geometry("760x260")

        # Vars
        self.var_pot = tk.StringVar()
        self.var_prefix = tk.StringVar()
        self.var_unc = tk.StringVar()
        self.var_host = tk.StringVar()
        self.var_port = tk.StringVar()
        self.var_status = tk.StringVar(value="Ready")

        # Layout
        frm = tk.Frame(root, padx=12, pady=10)
        frm.pack(fill="both", expand=True)

        # Row 1: PotPlayer exe
        tk.Label(frm, text="PotPlayer EXE:").grid(row=0, column=0, sticky="w")
        tk.Entry(frm, textvariable=self.var_pot, width=80).grid(row=0, column=1, sticky="we", padx=6)
        tk.Button(frm, text="Browse...", command=self.browse_pot).grid(row=0, column=2, padx=6)

        # Row 2: Web prefix
        tk.Label(frm, text="Web 前缀:").grid(row=1, column=0, sticky="w", pady=8)
        tk.Entry(frm, textvariable=self.var_prefix, width=80).grid(row=1, column=1, sticky="we", padx=6, pady=8)
        tk.Button(frm, text="Fill sample", command=self.fill_sample_prefix).grid(row=1, column=2, padx=6)

        # Row 3: UNC root
        tk.Label(frm, text="UNC 根目录:").grid(row=2, column=0, sticky="w")
        tk.Entry(frm, textvariable=self.var_unc, width=80).grid(row=2, column=1, sticky="we", padx=6)
        tk.Button(frm, text="Fill sample", command=self.fill_sample_unc).grid(row=2, column=2, padx=6)

        # Row 4: host/port + buttons
        row4 = tk.Frame(frm)
        row4.grid(row=3, column=0, columnspan=3, sticky="we", pady=10)

        tk.Label(row4, text="Host:").pack(side="left")
        tk.Entry(row4, textvariable=self.var_host, width=16).pack(side="left", padx=6)
        tk.Label(row4, text="Port:").pack(side="left")
        tk.Entry(row4, textvariable=self.var_port, width=8).pack(side="left", padx=6)

        tk.Button(row4, text="Save Config", command=self.save_cfg).pack(side="left", padx=10)
        #tk.Button(row4, text="Test Map", command=self.test_map).pack(side="left")

        # Status
        tk.Label(frm, textvariable=self.var_status, fg="#333").grid(row=4, column=0, columnspan=3, sticky="w")

        frm.columnconfigure(1, weight=1)

        # Load config into GUI
        self.load_to_gui()

    def load_to_gui(self):
        with _config_lock:
            cfg = _config.copy()
        self.var_pot.set(cfg.get("potplayer_exe", ""))
        self.var_prefix.set(cfg.get("web_prefix", ""))
        self.var_unc.set(cfg.get("unc_root", ""))
        self.var_host.set(cfg.get("host", "127.0.0.1"))
        self.var_port.set(str(cfg.get("port", 8080)))

    def browse_pot(self):
        path = filedialog.askopenfilename(
            title="Select PotPlayerMini64.exe",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")]
        )
        if path:
            self.var_pot.set(path)

    def fill_sample_prefix(self):
        self.var_prefix.set("存储空间 2/NAS 的文件/video/emby")

    def fill_sample_unc(self):
        self.var_unc.set(r"\\192.168.31.241\video\emby")

    def save_cfg(self):
        # Validate basic
        pot = self.var_pot.get().strip()
        prefix = self.var_prefix.get().strip()
        unc = self.var_unc.get().strip()
        host = self.var_host.get().strip() or "127.0.0.1"
        port = self.var_port.get().strip() or "8080"

        try:
            port_i = int(port)
        except ValueError:
            messagebox.showerror("Invalid port", "Port must be an integer.")
            return

        new_cfg = DEFAULT_CONFIG.copy()
        new_cfg.update({
            "potplayer_exe": pot,
            "web_prefix": prefix,
            "unc_root": unc,
            "host": host,
            "port": port_i,
        })

        with _config_lock:
            global _config
            _config = new_cfg

        save_config(new_cfg)
        self.var_status.set("Config saved to config.json (Flask 仍使用启动时的 host/port).")

    """def test_map(self):
        sample = "存储空间 2/NAS 的文件/video/emby/电影/Nice.View.2022.BluRay.1080p.DD5.1.x264-BMDru/Nice.View.2022.BluRay.1080p.DD5.1.x264-BMDru.mkv"
        mapped = map_web_path_to_unc(sample, self.var_prefix.get(), self.var_unc.get())
        messagebox.showinfo("Map Test", f"Input:\n{sample}\n\nMapped:\n{mapped}")"""


if __name__ == "__main__":
    # Load config
    _config = load_config()
    save_config(_config)  # ensure file exists

    # Start Flask server in background thread
    start_flask_in_thread()

    # Start GUI
    root = tk.Tk()
    gui = AppGUI(root)
    root.mainloop()
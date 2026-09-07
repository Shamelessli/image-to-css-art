"""Image to CSS Art 转换器 GUI —— 纯标准库壳，转换由项目 venv 子进程完成。"""

import os
import queue
import subprocess
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None

ROOT = Path(__file__).resolve().parent
VENV_PY = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
CLI = ROOT / "skills/image-to-css-art/scripts/image_to_css.py"
REQ = ROOT / "skills/image-to-css-art/requirements.txt"
PRESETS = ("preview", "balanced", "faithful")


def resolve_output_names(sources):
    """同名输入追加原扩展名区分，返回与输入一一对应的输出文件名。"""
    used, names = set(), []
    for src in sources:
        name = src.stem + ".html"
        if name in used:
            name = src.stem + src.suffix + ".html"
        used.add(name)
        names.append(name)
    return names


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}


def scan_images(paths):
    """文件或目录混合列表 -> 顶层图片文件去重列表。"""
    found = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            found.extend(f for f in p.iterdir()
                         if f.is_file() and f.suffix.lower() in IMAGE_EXTS)
        elif p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            found.append(p)
    result, seen = [], set()
    for f in found:
        key = f.resolve()
        if key not in seen:
            seen.add(key)
            result.append(f)
    return result


def parse_dnd_data(raw):
    """tkdnd 拖拽数据 -> 路径列表（处理 {花括号} 包裹的空格路径）。"""
    items, i = [], 0
    while i < len(raw):
        if raw[i] == "{":
            end = raw.find("}", i + 1)
            if end == -1:
                break
            items.append(raw[i + 1:end])
            i = end + 1
        else:
            end = raw.find(" ", i)
            if end == -1:
                items.append(raw[i:])
                break
            items.append(raw[i:end])
            i = end
        while i < len(raw) and raw[i] == " ":
            i += 1
    return [x for x in items if x]


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Image to CSS Art 转换器")
        self.root.geometry("720x560")
        self.files = []
        self.queue = queue.Queue()
        self.busy = False
        self._build()
        self.root.after(100, self._poll)
        self._check_deps()

    def _build(self):
        frm = ttk.Frame(self.root, padding=8)
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="输入图片（可多选）").grid(row=0, column=0, columnspan=4, sticky=tk.W)
        self.listbox = tk.Listbox(frm, selectmode=tk.EXTENDED, height=7)
        self.listbox.grid(row=1, column=0, columnspan=4, sticky=tk.NSEW)
        sb = ttk.Scrollbar(frm, orient=tk.VERTICAL, command=self.listbox.yview)
        sb.grid(row=1, column=4, sticky=tk.NS)
        self.listbox.configure(yscrollcommand=sb.set)
        if TkinterDnD:
            self.listbox.drop_target_register(DND_FILES)
            self.listbox.dnd_bind("<<Drop>>", self._on_drop)
        ttk.Button(frm, text="添加图片", command=self._add).grid(row=2, column=0, sticky=tk.W)
        ttk.Button(frm, text="移除选中", command=self._remove).grid(row=2, column=1, sticky=tk.W)
        ttk.Button(frm, text="清空", command=self._clear).grid(row=2, column=2, sticky=tk.W)
        ttk.Label(frm, text="预设").grid(row=3, column=0, sticky=tk.W)
        self.preset = ttk.Combobox(frm, values=PRESETS, state="readonly", width=10)
        self.preset.set("faithful")
        self.preset.grid(row=3, column=1, sticky=tk.W)
        ttk.Label(frm, text="背景色").grid(row=3, column=2, sticky=tk.W)
        self.bg = ttk.Entry(frm, width=10)
        self.bg.insert(0, "#ffffff")
        self.bg.grid(row=3, column=3, sticky=tk.W)
        ttk.Label(frm, text="目标体积 MiB（可选）").grid(row=4, column=0, sticky=tk.W)
        self.fit = ttk.Entry(frm, width=10)
        self.fit.grid(row=4, column=1, sticky=tk.W)
        ttk.Label(frm, text="输出目录（留空=与输入同目录）").grid(row=5, column=0, sticky=tk.W)
        self.outdir = ttk.Entry(frm)
        self.outdir.grid(row=5, column=1, columnspan=2, sticky=tk.EW)
        ttk.Button(frm, text="浏览", command=self._browse).grid(row=5, column=3, sticky=tk.W)
        self.start = ttk.Button(frm, text="开始转换", command=self._start)
        self.start.grid(row=6, column=0, columnspan=4, sticky=tk.EW)
        ttk.Button(frm, text="打开输出文件夹", command=self._open_dir).grid(row=7, column=0, columnspan=4, sticky=tk.EW)
        ttk.Label(frm, text="日志").grid(row=8, column=0, columnspan=4, sticky=tk.W)
        self.log = tk.Text(frm, height=12, state=tk.DISABLED, wrap=tk.NONE)
        self.log.grid(row=9, column=0, columnspan=4, sticky=tk.NSEW)
        lsb = ttk.Scrollbar(frm, orient=tk.VERTICAL, command=self.log.yview)
        lsb.grid(row=9, column=4, sticky=tk.NS)
        self.log.configure(yscrollcommand=lsb.set)
        frm.rowconfigure(1, weight=1)
        frm.rowconfigure(9, weight=2)
        frm.columnconfigure(1, weight=1)

    def _add(self):
        paths = filedialog.askopenfilenames(
            title="选择图片",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.webp *.gif"), ("全部文件", "*.*")],
        )
        for p in paths:
            p = Path(p).resolve()
            if p not in self.files:
                self.files.append(p)
        self._refresh_list()

    def _on_drop(self, event):
        self.files.extend(p for p in scan_images([Path(x) for x in parse_dnd_data(event.data)])
                          if p not in self.files)
        self._refresh_list()

    def _remove(self):
        for i in reversed(self.listbox.curselection()):
            del self.files[i]
        self._refresh_list()

    def _clear(self):
        self.files.clear()
        self._refresh_list()

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        for p in self.files:
            self.listbox.insert(tk.END, f"{p.name}  （{p.parent}）")

    def _browse(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.outdir.delete(0, tk.END)
            self.outdir.insert(0, d)

    def _open_dir(self):
        if self.outdir.get().strip():
            target = Path(self.outdir.get().strip())
        elif self.files:
            target = self.files[0].parent
        else:
            return
        if os.name == "nt":
            os.startfile(str(target))
        else:
            subprocess.Popen(["xdg-open", str(target)])

    def _check_deps(self):
        if not VENV_PY.exists():
            messagebox.showerror("错误", f"未找到虚拟环境: {VENV_PY}\n请先执行: python -m venv .venv")
            self.start.state(["disabled"])
            return
        if not CLI.exists():
            messagebox.showerror("错误", f"未找到转换脚本: {CLI}")
            self.start.state(["disabled"])
            return
        if subprocess.run([str(VENV_PY), "-c", "import numpy, cv2, PIL, tkinterdnd2"], capture_output=True).returncode != 0:
            if messagebox.askyesno("缺少依赖", "虚拟环境缺少 numpy / OpenCV / Pillow / tkinterdnd2。\n现在自动安装吗？（需要联网）"):
                self._install_deps()

    def _install_deps(self):
        def run():
            self._put("安装 pip（ensurepip）...")
            r = subprocess.run([str(VENV_PY), "-m", "ensurepip", "--upgrade"], capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.stdout.strip():
                self._put(r.stdout.strip())
            if r.stderr.strip():
                self._put(r.stderr.strip())
            if r.returncode != 0:
                self._put("ensurepip 失败，请手动安装依赖")
                return
            self._put("安装依赖（pip install -r requirements.txt）...")
            r = subprocess.run([str(VENV_PY), "-m", "pip", "install", "-r", str(REQ), "tkinterdnd2"], capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.stdout.strip():
                self._put(r.stdout.strip())
            if r.stderr.strip():
                self._put(r.stderr.strip())
            self._put("依赖安装完成" if r.returncode == 0 else "依赖安装失败")
        threading.Thread(target=run, daemon=True).start()

    def _start(self):
        if self.busy or not self.files:
            if not self.files:
                messagebox.showwarning("提示", "请先添加图片")
            return
        outdir = Path(self.outdir.get().strip()) if self.outdir.get().strip() else None
        tasks = [(src, (outdir if outdir else src.parent) / name)
                 for src, name in zip(self.files, resolve_output_names(self.files))]
        self.busy = True
        self.start.state(["disabled"])
        threading.Thread(target=self._worker, args=(tasks,), daemon=True).start()

    def _worker(self, tasks):
        preset = self.preset.get()
        bg = self.bg.get().strip()
        fit = self.fit.get().strip()
        for src, out in tasks:
            self._put(f"=== 转换: {src.name}")
            cmd = [str(VENV_PY), str(CLI), "convert", str(src), "-o", str(out), "--preset", preset, "--force"]
            if bg:
                cmd += ["--background", bg]
            if fit:
                cmd += ["--fit", fit]
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
                for line in proc.stdout:
                    self._put(line.rstrip())
                proc.wait()
                self._put(f"OK → {out}" if proc.returncode == 0 else f"失败（退出码 {proc.returncode}）")
            except OSError as exc:
                self._put(f"无法启动转换进程: {exc}")
        self.queue.put(None)

    def _put(self, line):
        self.queue.put(line)

    def _poll(self):
        try:
            while True:
                item = self.queue.get_nowait()
                if item is None:
                    self.busy = False
                    self.start.state(["!disabled"])
                else:
                    self._log(item)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _log(self, text):
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)


def main():
    root = (TkinterDnD.Tk() if TkinterDnD else tk.Tk())
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

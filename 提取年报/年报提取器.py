#!/usr/bin/env python3
"""年报智能提取器 —— 图形界面"""

import sys
import threading
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

SCRIPT_DIR = Path(__file__).parent
EXTRACT_SCRIPT = SCRIPT_DIR / "annrpt_extract.py"

C = {
    "bg":      "#0f1117",
    "surface": "#1a1d27",
    "border":  "#2a2d3a",
    "accent":  "#4f8ef7",
    "accent2": "#7c5cfc",
    "success": "#34d399",
    "error":   "#f87171",
    "warning": "#fbbf24",
    "text":    "#e2e8f0",
    "muted":   "#64748b",
    "drop_bg": "#161926",
}

MONO = ("SF Mono", 10) if sys.platform == "darwin" else ("Consolas", 10)


def run_extraction(pdf_path: Path, output_dir: Path, log_cb, done_cb):
    output_path = output_dir / (pdf_path.stem + ".md")
    try:
        proc = subprocess.Popen(
            [sys.executable, str(EXTRACT_SCRIPT), str(pdf_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True, encoding="utf-8",
        )
        stdout, stderr = proc.communicate()
        for line in (stderr or "").strip().splitlines():
            log_cb(line, "info")
        if proc.returncode == 0 and stdout.strip():
            output_path.write_text(stdout, encoding="utf-8")
            log_cb(f"✓ 已输出：{output_path}", "success")
            done_cb(True)
        else:
            log_cb(f"✗ 提取失败（返回码 {proc.returncode}）", "error")
            done_cb(False)
    except Exception as e:
        log_cb(f"✗ 错误：{e}", "error")
        done_cb(False)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("年报智能提取器")
        self.geometry("720x640")
        self.minsize(600, 560)
        self.configure(bg=C["bg"])
        self.resizable(True, True)

        self._queue: list[Path] = []
        self._running = False
        self._output_dir: Path | None = None

        self._build_ui()
        self._setup_drag_drop()
        self._check_script()

    # ── UI ──────────────────────────────────────────────────
    def _build_ui(self):
        # 标题栏
        hdr = tk.Frame(self, bg=C["bg"])
        hdr.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(hdr, text="年报智能提取器",
                 font=("Helvetica Neue", 20, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(side="left")
        tk.Label(hdr, text="管理层讨论 · 附注三表",
                 font=("Helvetica Neue", 11),
                 bg=C["bg"], fg=C["muted"]).pack(side="left", padx=(10, 0), pady=(4, 0))

        # 分隔线
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x", padx=24, pady=(14, 0))

        # 拖拽 / 选择区域
        self.drop_frame = tk.Frame(
            self, bg=C["drop_bg"],
            highlightbackground=C["border"], highlightthickness=1,
            cursor="hand2",
        )
        self.drop_frame.pack(fill="x", padx=24, pady=(16, 0), ipady=20)

        tk.Label(self.drop_frame, text="↓", font=("Helvetica Neue", 28),
                 bg=C["drop_bg"], fg=C["accent"]).pack()
        tk.Label(self.drop_frame, text="点击选择年报 PDF（支持多选）",
                 font=("Helvetica Neue", 14),
                 bg=C["drop_bg"], fg=C["text"]).pack()
        self.drop_sub = tk.Label(
            self.drop_frame, text="或将文件拖入此处",
            font=("Helvetica Neue", 11),
            bg=C["drop_bg"], fg=C["muted"],
        )
        self.drop_sub.pack(pady=(2, 0))

        for w in [self.drop_frame] + list(self.drop_frame.winfo_children()):
            w.bind("<Button-1>", self._browse)
            w.bind("<Enter>", lambda e: self.drop_frame.config(
                highlightbackground=C["accent"]))
            w.bind("<Leave>", lambda e: self.drop_frame.config(
                highlightbackground=C["border"]))

        # ── 输出目录选择行 ──
        out_row = tk.Frame(self, bg=C["bg"])
        out_row.pack(fill="x", padx=24, pady=(14, 0))

        tk.Label(out_row, text="输出目录",
                 font=("Helvetica Neue", 12, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(side="left")

        self.out_path_lbl = tk.Label(
            out_row, text="与 PDF 同目录（默认）",
            font=MONO, bg=C["bg"], fg=C["muted"],
            anchor="w",
        )
        self.out_path_lbl.pack(side="left", padx=(10, 0), fill="x", expand=True)

        tk.Button(
            out_row, text="选择…",
            font=("Helvetica Neue", 11),
            bg=C["surface"], fg=C["text"],
            activebackground=C["border"], activeforeground=C["text"],
            relief="flat", padx=10, pady=4, cursor="hand2",
            command=self._browse_output,
        ).pack(side="right")

        tk.Button(
            out_row, text="重置",
            font=("Helvetica Neue", 11),
            bg=C["surface"], fg=C["muted"],
            activebackground=C["border"], activeforeground=C["text"],
            relief="flat", padx=10, pady=4, cursor="hand2",
            command=self._reset_output,
        ).pack(side="right", padx=(0, 6))

        # 分隔线
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x", padx=24, pady=(12, 0))

        # 队列标题
        qhdr = tk.Frame(self, bg=C["bg"])
        qhdr.pack(fill="x", padx=24, pady=(12, 4))
        tk.Label(qhdr, text="处理队列",
                 font=("Helvetica Neue", 12, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(side="left")
        self.queue_lbl = tk.Label(qhdr, text="",
                                   font=("Helvetica Neue", 11),
                                   bg=C["bg"], fg=C["muted"])
        self.queue_lbl.pack(side="left", padx=8)

        # 队列列表
        lf = tk.Frame(self, bg=C["surface"],
                       highlightbackground=C["border"], highlightthickness=1)
        lf.pack(fill="both", expand=True, padx=24)
        sb = tk.Scrollbar(lf, bg=C["surface"], troughcolor=C["surface"])
        sb.pack(side="right", fill="y")
        self.listbox = tk.Listbox(
            lf, bg=C["surface"], fg=C["text"],
            selectbackground=C["accent"], selectforeground="white",
            font=MONO, borderwidth=0, highlightthickness=0,
            activestyle="none", yscrollcommand=sb.set,
        )
        self.listbox.pack(fill="both", expand=True, padx=8, pady=8)
        sb.config(command=self.listbox.yview)

        # 按钮栏
        bf = tk.Frame(self, bg=C["bg"])
        bf.pack(fill="x", padx=24, pady=(10, 0))
        tk.Button(bf, text="清空队列",
                   font=("Helvetica Neue", 11),
                   bg=C["surface"], fg=C["muted"],
                   activebackground=C["border"], activeforeground=C["text"],
                   relief="flat", padx=14, pady=7, cursor="hand2",
                   command=self._clear).pack(side="left")
        self.run_btn = tk.Button(
            bf, text="开始提取",
            font=("Helvetica Neue", 12, "bold"),
            bg=C["accent"], fg="white",
            activebackground=C["accent2"], activeforeground="white",
            relief="flat", padx=20, pady=7, cursor="hand2",
            command=self._start,
        )
        self.run_btn.pack(side="right")

        # 日志区
        tk.Label(self, text="运行日志",
                  font=("Helvetica Neue", 12, "bold"),
                  bg=C["bg"], fg=C["text"]).pack(anchor="w", padx=24, pady=(14, 4))
        lf2 = tk.Frame(self, bg="#0a0c12",
                        highlightbackground=C["border"], highlightthickness=1)
        lf2.pack(fill="x", padx=24, pady=(0, 20))
        self.log_text = tk.Text(
            lf2, height=5, bg="#0a0c12", fg=C["muted"],
            font=MONO, borderwidth=0, highlightthickness=0,
            state="disabled", wrap="word",
        )
        self.log_text.pack(fill="x", padx=10, pady=8)
        self.log_text.tag_config("info",    foreground=C["muted"])
        self.log_text.tag_config("success", foreground=C["success"])
        self.log_text.tag_config("error",   foreground=C["error"])
        self.log_text.tag_config("warning", foreground=C["warning"])

    # ── 拖拽 ────────────────────────────────────────────────
    def _setup_drag_drop(self):
        try:
            self.tk.eval('package require tkdnd')
            self.drop_frame.drop_target_register('DND_Files')
            self.drop_frame.dnd_bind('<<Drop>>', self._on_drop)
        except Exception:
            self.drop_sub.config(text="（当前环境不支持拖拽，请点击选择）")

    def _on_drop(self, event):
        paths = self.tk.splitlist(event.data)
        pdfs = [Path(p) for p in paths if p.lower().endswith(".pdf")]
        if pdfs:
            self._add(pdfs)
        else:
            self._log("请拖入 PDF 文件", "warning")

    # ── 输出目录 ─────────────────────────────────────────────
    def _browse_output(self):
        d = filedialog.askdirectory(
            title="选择输出目录",
            initialdir=str(self._output_dir or SCRIPT_DIR),
        )
        if d:
            self._output_dir = Path(d)
            # 截断显示过长路径
            display = str(self._output_dir)
            if len(display) > 55:
                display = "…" + display[-54:]
            self.out_path_lbl.config(text=display, fg=C["success"])
            self._log(f"输出目录：{self._output_dir}", "info")

    def _reset_output(self):
        self._output_dir = None
        self.out_path_lbl.config(text="与 PDF 同目录（默认）", fg=C["muted"])
        self._log("输出目录已重置为 PDF 同目录", "info")

    # ── 交互逻辑 ────────────────────────────────────────────
    def _browse(self, event=None):
        paths = filedialog.askopenfilenames(
            title="选择年报 PDF",
            filetypes=[("PDF 文件", "*.pdf"), ("所有文件", "*.*")],
            initialdir=str(SCRIPT_DIR),
        )
        if paths:
            self._add([Path(p) for p in paths])

    def _add(self, paths: list[Path]):
        added = 0
        for p in paths:
            if p not in self._queue:
                self._queue.append(p)
                self.listbox.insert("end", f"  {p.name}")
                added += 1
        if added:
            self.queue_lbl.config(text=f"{len(self._queue)} 个文件")
            self._log(f"已添加 {added} 个文件", "info")

    def _clear(self):
        if self._running:
            return
        self._queue.clear()
        self.listbox.delete(0, "end")
        self.queue_lbl.config(text="")

    def _start(self):
        if self._running:
            return
        if not self._queue:
            messagebox.showwarning("提示", "请先添加 PDF 文件")
            return
        if not EXTRACT_SCRIPT.exists():
            messagebox.showerror("错误", f"未找到提取脚本：\n{EXTRACT_SCRIPT}")
            return
        self._running = True
        self.run_btn.config(text="提取中…", state="disabled", bg=C["border"])
        self._process(0)

    def _process(self, idx: int):
        if idx >= len(self._queue):
            self._running = False
            self.run_btn.config(text="开始提取", state="normal", bg=C["accent"])
            self._log("─── 全部完成 ───", "success")
            return
        pdf = self._queue[idx]
        # 确定实际输出目录
        out_dir = self._output_dir if self._output_dir else pdf.parent
        self.listbox.itemconfig(idx, fg=C["warning"])
        self.listbox.see(idx)
        self._log(f"处理：{pdf.name}  →  {out_dir}", "info")

        def log_cb(msg, tag):
            self.after(0, lambda: self._log(msg, tag))

        def done_cb(ok):
            color = C["success"] if ok else C["error"]
            self.after(0, lambda: self.listbox.itemconfig(idx, fg=color))
            self.after(0, lambda: self._process(idx + 1))

        threading.Thread(
            target=run_extraction,
            args=(pdf, out_dir, log_cb, done_cb),
            daemon=True,
        ).start()

    def _log(self, msg: str, tag: str = "info"):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n", tag)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _check_script(self):
        if not EXTRACT_SCRIPT.exists():
            self._log("⚠ 未找到 annrpt_extract.py，请确认脚本在同一目录", "error")
        else:
            self._log(f"脚本路径：{EXTRACT_SCRIPT}", "info")
            self._log("就绪，请点击区域选择年报 PDF", "info")


if __name__ == "__main__":
    App().mainloop()

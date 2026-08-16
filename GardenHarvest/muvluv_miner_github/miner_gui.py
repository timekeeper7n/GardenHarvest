# -*- coding: utf-8 -*-
"""
miner_gui.py —— 自动挖矿的图形窗口
====================================
双击运行（或打包后的 MuvLuvMiner.exe）：

- 开始 / 停止按钮，F12 全局热键停止
- 目标轮数、画面适配模式设置
- 实时日志和完成轮数显示

坐标全部是 1280x720 标准坐标，运行时自动适配任意分辨率/缩放/窗口大小，
不需要选择分辨率。唯一要求：游戏窗口最大化或不被遮挡。
"""

import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk

import miner

ADAPT_MODES = {
    "自动适配（推荐，任意分辨率/缩放）": True,
    "直接整窗（窗口内容正好铺满16:9时用）": False,
}


class MinerGUI:
    def __init__(self, root):
        self.root = root
        self.logq = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None

        root.title("MUV-LUV 少女庭园 · 自动挖矿")
        root.geometry("560x470")
        root.minsize(520, 420)

        # 窗口左上角图标 (exe 文件本身的图标在打包时已用 --icon 嵌入)
        ico = None
        for p in (os.path.join(miner.get_base_dir(), "app.ico"),
                  os.path.join(miner.resource_dir(), "app.ico")):
            if os.path.exists(p):
                ico = p
                break
        if ico:
            try:
                root.iconbitmap(ico)
            except Exception:
                pass

        # ---- 设置区 ----
        setfrm = ttk.LabelFrame(root, text="设置")
        setfrm.pack(fill="x", padx=10, pady=(10, 5))

        row1 = ttk.Frame(setfrm)
        row1.pack(fill="x", padx=8, pady=6)
        ttk.Label(row1, text="目标轮数:").pack(side="left")
        self.runs_var = tk.StringVar(value="0")
        spin = ttk.Spinbox(row1, from_=0, to=999, width=5, textvariable=self.runs_var)
        spin.pack(side="left", padx=(4, 12))
        ttk.Label(row1, text="(0 = 一直跑，按停止或F12才停)").pack(side="left")

        row2 = ttk.Frame(setfrm)
        row2.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Label(row2, text="画面适配:").pack(side="left")
        self.adapt_var = tk.StringVar(value=list(ADAPT_MODES)[0])
        cb = ttk.Combobox(row2, textvariable=self.adapt_var, state="readonly",
                          values=list(ADAPT_MODES), width=34)
        cb.pack(side="left", padx=(4, 0))

        tip = ttk.Label(setfrm, foreground="#666",
                        text="坐标为标准坐标，自动适配任意屏幕分辨率和缩放比例，无需选择\n"
                             "运行要求：游戏窗口最大化、不被其他窗口挡住、挂机时别动鼠标")
        tip.pack(anchor="w", padx=8, pady=(0, 6))

        # ---- 按钮区 ----
        btnfrm = ttk.Frame(root)
        btnfrm.pack(fill="x", padx=10, pady=5)
        self.start_btn = ttk.Button(btnfrm, text="▶ 开始", command=self.on_start)
        self.start_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = ttk.Button(btnfrm, text="⏹ 停止 (F12)", command=self.on_stop, state="disabled")
        self.stop_btn.pack(side="left")
        self.status_var = tk.StringVar(value="状态: 待机")
        ttk.Label(btnfrm, textvariable=self.status_var).pack(side="right")

        # ---- 日志区 ----
        logfrm = ttk.LabelFrame(root, text="运行日志")
        logfrm.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        self.logbox = scrolledtext.ScrolledText(logfrm, height=14, state="disabled",
                                                font=("Consolas", 9))
        self.logbox.pack(fill="both", expand=True, padx=6, pady=6)

        # F12 全局热键
        try:
            import keyboard
            keyboard.add_hotkey("f12", self.on_stop)
        except Exception:
            pass  # 热键不可用时仍可用停止按钮

        # 日志刷新
        self.root.after(200, self.pump_log)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 自动化自检模式: MINER_GUI_SELFTEST=1 python miner_gui.py
        if os.environ.get("MINER_GUI_SELFTEST"):
            self.log("自检模式：1.5秒后自动关闭")
            tpl_n = len([f for f in os.listdir(miner.TEMPLATE_DIR)
                         if f.endswith(".png")]) if os.path.isdir(miner.TEMPLATE_DIR) else -1
            cfg_ok = os.path.exists(miner.CONFIG_PATH)
            self.log(f"自检: 模板目录={miner.TEMPLATE_DIR}, 模板数={tpl_n}, "
                     f"config={'OK' if cfg_ok else '缺失!'}")
            try:
                with open(os.path.join(miner.get_base_dir(), "selftest_result.txt"),
                          "w", encoding="utf-8") as f:
                    f.write(f"templates={tpl_n}\nconfig={'OK' if cfg_ok else 'MISSING'}\n")
            except Exception:
                pass
            self.root.after(1500, self.on_close)

    # ---------- 日志 ----------
    def log(self, msg):
        self.logq.put(str(msg))

    def pump_log(self):
        try:
            while True:
                line = self.logq.get_nowait()
                self.logbox.configure(state="normal")
                self.logbox.insert("end", line + "\n")
                self.logbox.see("end")
                self.logbox.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(200, self.pump_log)

    # ---------- 控制 ----------
    def on_start(self):
        if self.worker and self.worker.is_alive():
            return
        if not os.path.exists(miner.CONFIG_PATH):
            self.log("[错误] 找不到 config.json，请确认程序放在完整项目文件夹里。")
            return

        try:
            target = int(self.runs_var.get())
        except ValueError:
            target = 0
        auto_crop = ADAPT_MODES[self.adapt_var.get()]

        self.stop_event.clear()
        miner.STOP = False
        self.worker = threading.Thread(
            target=self._work, args=(target, auto_crop), daemon=True)
        self.worker.start()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_var.set("状态: 运行中")

    def _work(self, target, auto_crop):
        try:
            miner.run(
                log=self.log,
                should_stop=self.stop_event.is_set,
                overrides={"target_runs": target, "auto_crop": auto_crop},
                # 注意: 这里在工作线程里, 不能直接改界面控件(线程不安全),
                # 用 root.after 调度回主线程执行
                on_run_complete=lambda n: self._ui(lambda n=n: self.status_var.set(
                    f"状态: 运行中 | 已完成 {n} 轮")),
            )
        except Exception as e:
            self.log(f"[异常] {e}")
        self.log("线程已结束。")
        self._ui(self._reset_buttons)

    def _ui(self, func):
        """安全地把函数调度到主线程执行(窗口可能已销毁)。"""
        try:
            self.root.after(0, func)
        except Exception:
            pass

    def _reset_buttons(self):
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        cur = self.status_var.get()
        if "已完成" in cur:
            self.status_var.set("状态: 已停止 | " + cur.split("|", 1)[1].strip())
        else:
            self.status_var.set("状态: 已停止")

    def on_stop(self):
        self.stop_event.set()
        miner.STOP = True

    def on_close(self):
        if getattr(self, "_closed", False):
            return
        self._closed = True
        self.on_stop()
        # 最多等 3 秒让脚本走完当前这一次点击(避免鼠标按键被截在按下一半的状态)
        if self.worker and self.worker.is_alive():
            self.status_var.set("状态: 正在停止…")
            self.worker.join(timeout=3.0)
        try:
            import keyboard
            keyboard.unhook_all()  # 释放 F12 全局热键钩子
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    MinerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

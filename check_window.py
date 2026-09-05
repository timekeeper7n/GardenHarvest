# -*- coding: utf-8 -*-
"""诊断工具：检查窗口匹配、黑边裁剪、标准画面生成是否正常。"""
import json
import sys

sys.path.insert(0, ".")

import win32gui

from core import GameView, WindowCapture, find_game_window

with open("config.json", "r", encoding="utf-8") as f:
    cfg = json.load(f)

keyword = cfg["window_keyword"]
print(f"当前关键词: {keyword}")
hwnd = find_game_window(keyword)
if not hwnd:
    print("没匹配到。当前可见窗口：")
    def _enum(h, _):
        if win32gui.IsWindowVisible(h):
            t = win32gui.GetWindowText(h)
            if t.strip():
                print("  ", t)
    win32gui.EnumWindows(_enum, None)
    sys.exit(1)

print(f"匹配成功: 标题「{win32gui.GetWindowText(hwnd)}」")

view = GameView(hwnd, cfg.get("ref_width", 1280), cfg.get("ref_height", 720),
                cfg.get("auto_crop", True), cfg.get("manual_rect"))
raw = view.cap.grab()
ref = view.grab()
x, y, w, h = view.area
rh, rw = raw.shape[:2]
print(f"原始客户区: {rw}x{rh}")
print(f"检测到游戏区域: 位置({x},{y}) 大小 {w}x{h}, 宽高比 {w/h:.3f} (16:9=1.778)")
print(f"标准画面: {ref.shape[1]}x{ref.shape[0]}")
WindowCapture.save(raw, "screenshots/check_raw.png")
WindowCapture.save(ref, "screenshots/check_ref.png")
print("已存 screenshots/check_raw.png 和 check_ref.png，可打开对比确认裁剪正确")

# -*- coding: utf-8 -*-
"""验证屏幕截图修复: 前台化游戏 -> 新方式截图找按钮 -> 鼠标移过去 -> 取色验证。"""
import ctypes
import json
import sys
import time

sys.path.insert(0, ".")

import cv2
import numpy as np
import win32con
import win32gui
import win32ui

from core import GameView, WindowCapture, find_game_window, find_image

def foreground(hwnd):
    """把窗口带到前台 (ALT键技巧绕过系统限制)。"""
    ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)          # Alt down
    ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)          # Alt up
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.8)

cfg = json.load(open("config.json", encoding="utf-8"))
hwnd = find_game_window(cfg["window_keyword"])
foreground(hwnd)

view = GameView(hwnd, cfg.get("ref_width", 1280), cfg.get("ref_height", 720),
                cfg.get("auto_crop", True), cfg.get("manual_rect"))
ref = view.grab()
WindowCapture.save(ref, "screenshots/verify_ref.png")

pos = find_image(ref, "templates/mode_start.png", 0.75)
if not pos:
    print("没找到出击按钮 -- 请确认游戏前台显示且停在模式主界面")
    sys.exit(1)

click_client = view.to_client(*pos)
sx, sy = win32gui.ClientToScreen(hwnd, click_client)
print(f"按钮标准位置 {pos} -> 屏幕坐标 ({sx},{sy})")

ctypes.windll.user32.SetCursorPos(int(sx), int(sy))
time.sleep(0.4)

hdc = win32gui.GetDC(0)
mfc = win32ui.CreateDCFromHandle(hdc)
save = mfc.CreateCompatibleDC()
bmp = win32ui.CreateBitmap()
bmp.CreateCompatibleBitmap(mfc, 120, 90)
save.SelectObject(bmp)
save.BitBlt((0, 0), (120, 90), mfc, (int(sx) - 60, int(sy) - 45), 0x00CC0020)
arr = np.frombuffer(bmp.GetBitmapBits(True), np.uint8).reshape(90, 120, 4)
patch = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
win32gui.DeleteObject(bmp.GetHandle())
save.DeleteDC()
mfc.DeleteDC()
win32gui.ReleaseDC(0, hdc)

hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
red = cv2.bitwise_or(cv2.inRange(hsv, (0, 120, 100), (8, 255, 255)),
                     cv2.inRange(hsv, (172, 120, 100), (180, 255, 255)))
ratio = red.mean()
print(f"鼠标中心取色 BGR={patch[45, 60].tolist()}, 周围红色占比 {ratio*100:.1f}%")
WindowCapture.save(patch, "screenshots/verify_patch.png")
print("\n>>> 修复成功! 鼠标正下方就是按钮" if ratio > 0.25 else "\n>>> 仍有偏移!")

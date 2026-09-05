# -*- coding: utf-8 -*-
"""
实时校验坐标映射: 抓当前游戏画面 -> 检测区域 -> 找模板 ->
和"正确映射下模板应在的标准位置"比对, 输出系统偏差。

用法: 游戏停在任意有已知按钮的画面(如模式主界面/商店), 运行本脚本。
"""
import glob
import json
import os
import sys

sys.path.insert(0, ".")

import cv2
import numpy as np

from core import GameView, WindowCapture, find_game_window, find_image

# ---- 第一步: 从当初做模板的原始截图算出每个模板的"标准位置" ----
ORIGIN_SHOTS = "screenshots/shot_*.png"  # 用户当初截的正确映射截图


def load(p):
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)


expected = {}  # 模板名 -> 在正确标准画面里的中心坐标
for tp in sorted(glob.glob("templates/*.png")):
    name = os.path.basename(tp)
    t = load(tp)
    if t.shape[0] < 8:
        continue  # 跳过占位图
    best = (0, None)
    for sp in sorted(glob.glob(ORIGIN_SHOTS)):
        if "_raw" in sp:
            continue
        s = load(sp)
        if t.shape[0] >= s.shape[0] or t.shape[1] >= s.shape[1]:
            continue
        r = cv2.matchTemplate(s, t, cv2.TM_CCOEFF_NORMED)
        _, mv, _, ml = cv2.minMaxLoc(r)
        if mv > best[0]:
            best = (mv, (ml[0] + t.shape[1] // 2, ml[1] + t.shape[0] // 2))
    if best[1]:
        expected[name] = best[1]

print("各模板在正确映射下的标准中心位置:")
for k, v in expected.items():
    print(f"  {k}: {v}")

# ---- 第二步: 实时抓当前窗口, 检测区域, 找模板, 比对 ----
cfg = json.load(open("config.json", encoding="utf-8"))
hwnd = find_game_window(cfg["window_keyword"])
if not hwnd:
    print("没找到游戏窗口!")
    sys.exit(1)

view = GameView(hwnd, cfg.get("ref_width", 1280), cfg.get("ref_height", 720),
                cfg.get("auto_crop", True), cfg.get("manual_rect"))
raw = view.cap.grab()
ref = view.grab()
x, y, w, h = view.area
rh, rw = raw.shape[:2]
print(f"\n当前窗口: {rw}x{rh} (比例 {rw/rh:.3f})")
print(f"检测到的游戏区域: 位置({x},{y}) 大小{w}x{h}, 比例 {w/h:.3f}")

WindowCapture.save(raw, "screenshots/mapcheck_raw.png")
WindowCapture.save(ref, "screenshots/mapcheck_ref.png")

print("\n当前画面匹配到的模板及偏差 (正偏差=实际点偏右/偏下):")
found = 0
for name, exp in expected.items():
    pos = find_image(ref, os.path.join("templates", name), 0.75)
    if pos:
        found += 1
        dx, dy = pos[0] - exp[0], pos[1] - exp[1]
        print(f"  {name}: 应在{exp}, 实际在{pos}, 偏差 dx={dx:+d} dy={dy:+d}")
if not found:
    print("  (当前画面没有已知模板, 请切到模式主界面或商店再运行)")

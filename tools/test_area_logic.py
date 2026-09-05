# -*- coding: utf-8 -*-
"""模拟 F11居中 / 最大化贴底 / 贴顶 三种布局, 验证 detect_game_area 的判断。"""
import sys

sys.path.insert(0, ".")

import cv2
import numpy as np

from core import detect_game_area

canvas = cv2.imdecode(np.fromfile("screenshots/diag_raw.png", dtype=np.uint8), cv2.IMREAD_COLOR)
canvas = cv2.resize(canvas, (2560, 1440))  # 标准 16:9 画布 (顶部自带约14px纯色条, 正是真实干扰源)


def make_case(name, W, H, top_gap, busy_top=False):
    frame = np.zeros((H, W, 3), np.uint8)
    if busy_top:
        # 模拟浏览器界面: 有文字图标的"繁忙"内容(随机噪点)
        noise = np.random.randint(60, 200, (top_gap, W, 3), np.uint8)
        frame[0:top_gap] = noise
    frame[top_gap:top_gap + 1440] = canvas
    x, y, w, h = detect_game_area(frame)
    err = abs(y - top_gap)
    ok = err <= 24 and w == W and h == 1440
    print(f"{name}: 画布真实位置 y={top_gap}, 检测结果 y={y} {w}x{h} "
          f"(偏差{err}px) {'<-- 正确' if ok else '<-- 错误!'}")
    return ok


ok1 = make_case("F11全屏(居中, 上下各80黑边)", 2560, 1600, 80)
ok2 = make_case("最大化(上方126px浏览器界面, 贴底)", 2560, 1566, 126, busy_top=True)
ok3 = make_case("贴顶布局(下方留白)", 2560, 1566, 0)
print("\n全部通过!" if (ok1 and ok2 and ok3) else "\n有失败用例!")

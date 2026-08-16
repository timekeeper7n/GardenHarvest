# -*- coding: utf-8 -*-
r"""
crop_tool.py —— 抠图（模板制作）工具
====================================
把 capture_tool 截好的标准画面，框选出按钮部分，保存成识别用的小模板。

用法：
    python tools\crop_tool.py screenshots\shot_123456_0.png
    （也可以不带参数运行，会自动选取 screenshots 里最新的一张 shot_*.png，
     注意用不带 _raw 后缀的——那才是标准画面）

操作：
    1. 弹出图片窗口，用鼠标拖一个框，框住你想识别的按钮（尽量贴边、别框进背景）
    2. 松开鼠标 -> 按回车(Enter)确认；不满意可以重新拖框
    3. 框选并确认后窗口标题会显示保存路径，按 ESC 退出
"""

import glob
import os
import sys

import cv2
import numpy as np

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")


def main():
    if len(sys.argv) > 1:
        src = sys.argv[1]
    else:
        shots = sorted(glob.glob(os.path.join(os.path.dirname(TEMPLATE_DIR), "screenshots", "shot_*.png")))
        shots = [s for s in shots if "_raw" not in os.path.basename(s)]
        if not shots:
            print("[错误] screenshots 文件夹里没有截图，请先用 capture_tool.py 截图。")
            return
        src = shots[-1]
        print(f"自动选择最新截图: {src}")

    img = cv2.imdecode(np.fromfile(src, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        print(f"[错误] 读不到图片: {src}")
        return

    os.makedirs(TEMPLATE_DIR, exist_ok=True)

    while True:
        # 弹窗选择区域：拖框 -> 按 Enter/空格 确认，c 取消重选
        roi = cv2.selectROI("框选按钮后按Enter确认 (ESC退出程序)", img, showCrosshair=True)
        if roi == (0, 0, 0, 0):
            break  # 直接按了 ESC
        x, y, w, h = roi
        if w < 5 or h < 5:
            print("框太小了，重新框一次。")
            continue

        piece = img[y:y + h, x:x + w]
        name = input("给这个按钮起个英文名(比如 start_button): ").strip()
        if not name:
            name = "template"
        if not name.endswith(".png"):
            name += ".png"
        out = os.path.join(TEMPLATE_DIR, name)
        cv2.imencode(".png", piece)[1].tofile(out)
        print(f"已保存模板: {out}  (尺寸 {w}x{h})\n可以继续框选下一个按钮，或按 ESC 结束。")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

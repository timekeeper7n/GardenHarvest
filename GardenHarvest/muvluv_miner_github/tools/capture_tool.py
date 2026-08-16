# -*- coding: utf-8 -*-
r"""
capture_tool.py —— 截图工具
===========================
用法：
    1. 先打开游戏，进入想要截图的画面
    2. 双击运行 start_capture.bat
    3. 按 F2 键 -> 同时保存两张图到 screenshots 文件夹：
         shot_时间_编号.png       标准画面（1280x720，做模板用这张！）
         shot_时间_编号_raw.png   原始画面（排查问题用）
    4. 想截哪一屏就切到哪一屏再按 F2（节点选择、buff选择、结算画面……）
    5. 按 F10 退出工具

标准画面与窗口实际大小无关：脚本会自动裁掉黑边、缩放到统一分辨率，
所以以后改窗口大小也不影响识别（和 MAA 一个原理）。
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import keyboard
import win32gui

from core import GameView, WindowCapture, find_game_window

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "screenshots")


def load_config():
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    cfg = load_config()
    keyword = cfg.get("window_keyword", "ガールズガーデン")
    hwnd = find_game_window(keyword)
    if not hwnd:
        print(f"[错误] 没找到标题包含「{keyword}」的窗口！请先打开游戏。")
        print("（如果游戏已开着，把窗口标题里的文字更新到 config.json 的 window_keyword）")
        return

    view = GameView(
        hwnd,
        ref_w=cfg.get("ref_width", 1280),
        ref_h=cfg.get("ref_height", 720),
        auto_crop=cfg.get("auto_crop", True),
        manual_rect=cfg.get("manual_rect"),
    )
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"已锁定游戏窗口: {win32gui.GetWindowText(hwnd)}")
    print("按 F2 截图（主文件=标准画面，用于做模板），按 F10 退出。")

    count = 0
    while True:
        key = keyboard.read_event()
        if key.event_type != "down":
            continue
        if key.name == "f2":
            try:
                raw = view.cap.grab()
                ref = view.grab()
            except RuntimeError as e:
                print(f"[错误] {e}")
                continue
            ts = time.strftime("%H%M%S")
            main_path = os.path.join(OUT_DIR, f"shot_{ts}_{count}.png")
            raw_path = os.path.join(OUT_DIR, f"shot_{ts}_{count}_raw.png")
            WindowCapture.save(ref, main_path)
            WindowCapture.save(raw, raw_path)
            print(f"已保存: {main_path} (标准画面 {view.ref_w}x{view.ref_h})")
            print(f"        {raw_path} (原始画面)")
            count += 1
        elif key.name == "f10":
            print("退出。")
            break


if __name__ == "__main__":
    main()

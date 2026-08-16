# -*- coding: utf-8 -*-
"""
miner.py —— 自动挖矿主脚本
==========================
整个脚本的运行逻辑就是一个循环：

    截图 -> 对照 templates 文件夹里的按钮图片，判断现在游戏在哪一屏
         -> 按照配置文件里写的动作，点击对应的按钮
         -> 等待加载 -> 回到第一步，直到完成设定次数或停止

所有"点什么、等多久"都写在同目录的 config.json 里，改行为不用改代码。

可以直接命令行运行（python miner.py，F12 停止），
也可以被 miner_gui.py 的窗口调用（传入日志函数和停止信号）。
"""

import json
import os
import shutil
import sys
import time

from core import GameView, WindowCapture, find_game_window, find_image, find_red_button

STOP = False  # 命令行模式下的全局停止标记 (F12)


def get_base_dir():
    """exe/源码所在目录: 用户可编辑的 config.json 放这里。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resource_dir():
    """内置资源目录: 打包时模板/默认配置嵌在 exe 里(解包到 _MEIPASS)。"""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return get_base_dir()


BASE_DIR = get_base_dir()
TEMPLATE_DIR = os.path.join(resource_dir(), "templates")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
UNKNOWN_DIR = os.path.join(BASE_DIR, "screenshots", "unknown")

# 单文件exe首次运行: 身边没有 config.json 就从内置默认复制一份(用户可改)
if getattr(sys, "frozen", False) and not os.path.exists(CONFIG_PATH):
    try:
        shutil.copy(os.path.join(resource_dir(), "config.json"), CONFIG_PATH)
    except Exception:
        pass


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def run(log=print, should_stop=None, overrides=None, on_run_complete=None):
    """主循环。

    log            : 日志输出函数（窗口模式传 GUI 的日志函数）
    should_stop    : 返回 True 时停止循环（窗口模式传停止事件）
    overrides      : 临时覆盖 config 的字段，如 {"target_runs": 10}
    on_run_complete: 每完成一轮调用一次，参数是已完成轮数（用于界面显示）
    """
    if should_stop is None:
        should_stop = lambda: STOP

    cfg = load_config()
    if overrides:
        cfg.update(overrides)

    keyword = cfg.get("window_keyword", "ガールズガーデン")
    threshold = cfg.get("threshold", 0.8)
    loop_delay = cfg.get("loop_delay", 1.2)
    target_runs = cfg.get("target_runs", 0)  # 0 = 无限循环

    hwnd = find_game_window(keyword)
    if not hwnd:
        log(f"[错误] 没找到标题包含「{keyword}」的窗口，请先打开游戏。")
        return
    view = GameView(
        hwnd,
        ref_w=cfg.get("ref_width", 1280),
        ref_h=cfg.get("ref_height", 720),
        auto_crop=cfg.get("auto_crop", True),
        manual_rect=cfg.get("manual_rect"),
    )
    log(f"已锁定游戏窗口。目标次数: {target_runs if target_runs else '无限'}")
    log("提示：脚本会自动适配窗口大小；挂机时请勿使用鼠标。")

    save_unknown = cfg.get("save_unknown", False)  # 未知画面截图开关(调试用)
    completed_runs = 0
    unknown_shots = 0
    warned_missing = set()
    prev_template = None  # 上一轮识别到的画面(用于"进入画面只计数一次")

    while not should_stop():
        try:
            screen = view.grab()
        except RuntimeError as e:
            log(f"[错误] {e}")
            time.sleep(2)
            continue

        matched = False
        # 按配置文件里的顺序逐个尝试识别，谁先匹配上就执行谁的动作
        # （顺序很重要：矿残留弹窗要排在商店前面，其他靠专属模板区分）
        for scr in cfg["screens"]:
            tpl = os.path.join(TEMPLATE_DIR, scr["template"])
            if not os.path.exists(tpl):
                if scr["template"] not in warned_missing:
                    log(f"[提示] 模板缺失, 先跳过: {scr['template']} "
                        f"(请用 crop_tool 制作后放入 templates 文件夹)")
                    warned_missing.add(scr["template"])
                continue
            pos = find_image(screen, tpl, threshold)
            if pos is None and scr.get("detect_color"):
                # 颜色兜底: 模板没匹配上时, 找"白色弹窗里的红色确定键"
                # (带弹窗校验, 避免误点道中地图上的红色关卡节点)
                pos = find_red_button(screen, require_dialog=True)
            if pos is None:
                continue
            # 可选的"与"校验: and_template 也必须匹配上, 这个画面才算数
            # (防止单一模板在别的画面碰巧相似而误触发, 比如矿石计数器)
            if scr.get("and_template"):
                tpl2 = os.path.join(TEMPLATE_DIR, scr["and_template"])
                if not os.path.exists(tpl2) or find_image(screen, tpl2, threshold) is None:
                    continue

            matched = True
            name = scr.get("name", scr["template"])
            log(f"[{time.strftime('%H:%M:%S')}] 识别到: {name}")

            action = scr.get("action", "click_template")
            off = scr.get("click_offset", [0, 0])  # 点击微调: [右移px, 下移px]
            if action == "click_template":
                view.click(pos[0] + off[0], pos[1] + off[1],
                           delay_after=scr.get("wait", 1.0), calibrated=False)
            elif action == "click_point":
                px, py = scr["point"]
                view.click(px + off[0], py + off[1], delay_after=scr.get("wait", 1.0))
            elif action == "wait":
                time.sleep(scr.get("wait", 1.0))
            elif action == "sequence":
                # 连招: 依次执行 steps 里的一串动作, 商店流程这类多步操作用它
                for step in scr.get("steps", []):
                    if should_stop():
                        break
                    soff = step.get("click_offset", [0, 0])
                    if "click_point" in step:
                        view.click(step["click_point"][0] + soff[0],
                                   step["click_point"][1] + soff[1],
                                   delay_after=step.get("wait", 0.6))
                    elif "click_template" in step:
                        fresh = view.grab()
                        p2 = find_image(fresh, os.path.join(TEMPLATE_DIR, step["click_template"]), threshold)
                        if p2:
                            view.click(p2[0] + soff[0], p2[1] + soff[1],
                                       delay_after=step.get("wait", 1.0), calibrated=False)
                            if step.get("verify"):
                                # 点完看结果: 退成了没有? 弹窗出来了吗? 还停在原地?
                                # (点完"完了"如果有矿没花完会弹确认窗, 要点红色确定才算退出)
                                for _ in range(5):
                                    time.sleep(1.2)
                                    fresh = view.grab()
                                    popup = find_image(
                                        fresh, os.path.join(TEMPLATE_DIR, "ore_popup_ok.png"), threshold)
                                    if popup is None:
                                        popup = find_red_button(fresh, require_dialog=True)  # 颜色兜底(带弹窗校验)
                                    if popup:
                                        log("      出现矿残留弹窗, 点击红色确定...")
                                        view.click(*popup, delay_after=1.5, calibrated=False)
                                        continue
                                    if find_image(fresh, os.path.join(TEMPLATE_DIR, step["click_template"]), threshold) is None:
                                        log(f"      已确认离开({step['click_template']})")
                                        break
                                    log(f"      {step['click_template']} 还在, 重新点击...")
                                    p3 = find_image(fresh, os.path.join(TEMPLATE_DIR, step["click_template"]), threshold)
                                    if p3:
                                        view.click(p3[0], p3[1], delay_after=step.get("wait", 1.0), calibrated=False)
                        else:
                            log(f"      [警告] 连招中没找到 {step['click_template']}, 跳过")
                    elif "wait" in step:
                        time.sleep(step["wait"])

            if scr.get("count_run") and prev_template != scr["template"]:
                # 只在"刚进入这个画面"时计数一次: 如果点击没点上,
                # 下一轮循环还是这个画面, 不会重复计数(并会自动重点)
                completed_runs += 1
                log(f"===== 第 {completed_runs} 轮完成 =====")
                if on_run_complete:
                    on_run_complete(completed_runs)
                if target_runs and completed_runs >= target_runs:
                    log("达到目标次数，脚本结束。")
                    return
            prev_template = scr["template"]
            break

        if not matched:
            # 一屏都没认出来(战斗/加载画面属于正常情况,不用管)
            unknown_shots += 1
            if save_unknown:
                os.makedirs(UNKNOWN_DIR, exist_ok=True)
                ts = time.strftime("%H%M%S")
                WindowCapture.save(screen, os.path.join(UNKNOWN_DIR, f"unk_{ts}.png"))
                log(f"[警告] 没有识别出当前画面，已存图 screenshots/unknown/unk_{ts}.png")
            else:
                log(f"[提示] 未识别画面(战斗/加载中属正常) "
                    f"{unknown_shots}/{cfg.get('max_unknown', 20)}")
            if unknown_shots >= cfg.get("max_unknown", 20):
                log("连续识别失败太多次，自动停止。"
                    + ("请把 unknown 里的截图做成新模板。" if save_unknown else
                       "如需排查可把 config.json 的 save_unknown 改为 true 再复现。"))
                return
        else:
            unknown_shots = 0

        time.sleep(loop_delay)

    log("已停止。")


if __name__ == "__main__":
    import keyboard

    keyboard.add_hotkey("f12", lambda: setattr(sys.modules[__name__], "STOP", True))
    print("按 F12 停止。")
    try:
        run()
    except KeyboardInterrupt:
        print("已手动停止 (Ctrl+C)。")

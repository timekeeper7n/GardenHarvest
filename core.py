# -*- coding: utf-8 -*-
"""
core.py —— 核心工具库
=====================
这个文件提供三个最基础的能力，主脚本 miner.py 会用到：

1. find_game_window() : 找到游戏窗口（按标题关键词）
2. WindowCapture     : 对游戏窗口截图（即使窗口被别的窗口挡住也能截）
3. click / find_image : 在截图里找按钮图片并模拟鼠标点击

不需要改动这个文件，直接用就行。
"""

import ctypes
import time

import cv2
import numpy as np
import win32gui
import win32ui


def _enable_dpi_awareness():
    """告诉 Windows 本程序感知 DPI 缩放。

    不加这一段的话，在 150% 缩放的屏幕（如 2560x1600 默认设置）上，
    截图会被系统缩小到 2/3 尺寸（1706x1044），白白损失清晰度。
    三种写法按新旧系统依次尝试，成功一个即可。
    """
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4 (Win10 1703+)
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Win 8.1+
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # 最老的兜底
    except Exception:
        pass


_enable_dpi_awareness()

# ---------- 鼠标动作的底层定义（Windows API 常量，无需理解） ----------
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def find_game_window(keyword: str):
    """按标题关键词查找游戏窗口，返回句柄；找不到返回 0。

    keyword: 窗口标题里包含的文字，比如 "少女庭園" 或 "Muv-Luv"
    """
    result = []

    def _enum_handler(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if keyword in title:
                result.append(hwnd)

    win32gui.EnumWindows(_enum_handler, None)
    return result[0] if result else 0


class WindowCapture:
    """游戏窗口截图器。

    用法:
        cap = WindowCapture(窗口句柄)
        img = cap.grab()          # 得到一张 numpy 图像（BGR 格式）
        cap.save(img, "xx.png")   # 存成 png 文件
    """

    def __init__(self, hwnd):
        self.hwnd = hwnd
        self._update_rect()

    def _update_rect(self):
        # 客户区 = 窗口里不含标题栏/边框的纯画面区域
        left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
        self.width = right - left
        self.height = bottom - top

    def grab(self) -> np.ndarray:
        """截取窗口客户区画面（直接从屏幕复制真实像素）。

        为什么不用 PrintWindow: Edge/Chromium 的自绘窗口在 PrintWindow
        渲染时和真实屏幕像素存在偏移, 且偏移量随窗口大小/边框形态变化,
        会导致点击位置系统性偏移。直接 BitBlt 屏幕像素则所见即所得。

        前提：游戏窗口不能最小化、不能被其他窗口遮挡（点击本来也要求
        窗口可见，所以没有额外代价）。
        """
        self._update_rect()
        if self.width <= 0 or self.height <= 0:
            raise RuntimeError("窗口尺寸异常，游戏窗口是不是最小化了？")
        if win32gui.IsIconic(self.hwnd):
            raise RuntimeError("游戏窗口最小化了，请先恢复窗口再运行")

        left, top = win32gui.ClientToScreen(self.hwnd, (0, 0))
        hdc = win32gui.GetDC(0)
        mfc_dc = win32ui.CreateDCFromHandle(hdc)
        save_dc = mfc_dc.CreateCompatibleDC()

        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(mfc_dc, self.width, self.height)
        save_dc.SelectObject(bmp)
        save_dc.BitBlt((0, 0), (self.width, self.height), mfc_dc,
                       (left, top), 0x00CC0020)  # SRCCOPY

        img = np.frombuffer(bmp.GetBitmapBits(True), dtype=np.uint8)
        img = img.reshape(self.height, self.width, 4)  # BGRA 四通道
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        win32gui.DeleteObject(bmp.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(0, hdc)
        return img

    @staticmethod
    def save(img: np.ndarray, path: str):
        cv2.imencode(".png", img)[1].tofile(path)  # tofile 支持中文路径


def find_image(screen: np.ndarray, template_path: str, threshold: float = 0.8):
    """在整张截图里找模板图片（比如某个按钮），找到返回中心坐标，找不到返回 None。

    screen        : WindowCapture.grab() 截出来的图
    template_path : 按钮小图片的路径（用工具截出来的）
    threshold     : 相似度门槛，0.8 表示 80% 像像就认为找到了。误识别就调高，识别不到就调低
    """
    template = cv2.imdecode(
        np.fromfile(template_path, dtype=np.uint8), cv2.IMREAD_COLOR
    )
    if template is None:
        raise FileNotFoundError(f"读不到模板图片: {template_path}")

    th, tw = template.shape[:2]
    if th >= screen.shape[0] or tw >= screen.shape[1]:
        return None  # 模板比截图还大，肯定不在这一屏

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val >= threshold:
        return max_loc[0] + tw // 2, max_loc[1] + th // 2  # 模板中心的 (x, y)
    return None


def _send_mouse_event(flags, dx=0, dy=0):
    """组装一个鼠标输入事件发给 Windows（底层细节，无需理解）。"""
    ULONG_PTR = ctypes.c_ulonglong

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", ctypes.c_long),
            ("dy", ctypes.c_long),
            ("mouseData", ctypes.c_ulong),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class _INPUT(ctypes.Structure):
        _fields_ = [
            ("type", ctypes.c_ulong),
            ("mi", _MOUSEINPUT),
        ]

    inp = _INPUT(type=INPUT_MOUSE, mi=_MOUSEINPUT(dx, dy, 0, flags, 0, 0))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def client_to_screen(hwnd, x, y):
    """把"窗口内坐标"换算成"整个屏幕的绝对坐标"。"""
    left, top = win32gui.ClientToScreen(hwnd, (0, 0))
    return left + x, top + y


def detect_game_area(img: np.ndarray, target_ratio: float = 16 / 9):
    """自动找出截图里真正的游戏画面区域，返回 (x, y, w, h)。

    策略（按顺序）：
    1. 裁掉四周"纯色边条"（任何颜色，黑边/白边都行）——游戏窗口比例
       和游戏画面不一致时，网页会加边条；裁完正好 16:9(误差0.5%内)直接用；
    2. 画布占满窗口宽度时，它上下的位置有三种可能：
       - 最大化窗口：上方是浏览器界面(有文字图标)，画布贴窗口底边
       - F11全屏：上下都是接近纯色的页面留白，画布垂直居中
       - 少数情况：画布贴顶、留白在下方
       通过"画布下方是否也是纯色留白"来区分这三种布局。
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # ---- 第 1 步：从四边向内裁掉纯色条（行/列像素几乎没有波动） ----
    row_std = gray.std(axis=1)
    col_std = gray.std(axis=0)
    y0 = 0
    while y0 < h - 1 and row_std[y0] < 6:
        y0 += 1
    y1 = h - 1
    while y1 > y0 and row_std[y1] < 6:
        y1 -= 1
    x0 = 0
    while x0 < w - 1 and col_std[x0] < 6:
        x0 += 1
    x1 = w - 1
    while x1 > x0 and col_std[x1] < 6:
        x1 -= 1
    cw, ch = x1 - x0 + 1, y1 - y0 + 1
    if cw > 0 and ch > 0 and abs(cw / ch - target_ratio) / target_ratio < 0.005:
        return x0, y0, cw, ch  # 裁完正好是 16:9(误差0.5%内)，直接用

    # ---- 第 2 步：画布占满宽度，判断它的垂直位置 ----
    if w / h <= target_ratio:
        # 窗口比 16:9 更"高"：画布占满宽度，上下可能有多余部分
        game_h = int(round(w / target_ratio))
        if game_h <= h:
            # 分别数一下窗口顶部/底部有多少行接近纯色(页面留白/黑边)
            top_uni = 0
            while top_uni < h - 1 and row_std[top_uni] < 10:
                top_uni += 1
            bot_uni = 0
            while bot_uni < h - 1 and row_std[h - 1 - bot_uni] < 10:
                bot_uni += 1
            if bot_uni > 8:
                # 底部有大片留白 -> 画布不贴底。留白之间的内容区如果
                # 高度正好接近 16:9 画布高度(误差24px内, 容忍画布自身
                # 边缘的纯色条), 画布就占满这个内容区
                content_h = h - top_uni - bot_uni
                if abs(content_h - game_h) <= 24:
                    top = top_uni
                else:
                    top = (h - game_h) // 2  # 兜底: 垂直居中
            else:
                top = h - game_h  # 画布贴窗口底边(上方是浏览器界面)
            return 0, top, w, game_h
    else:
        # 窗口比 16:9 更"宽"：画布占满高度（第 1 步没裁出结果时才走到这，
        # 这种情况不常见，按左右留边处理）
        game_w = int(round(h * target_ratio))
        return (w - game_w) // 2, 0, game_w, h

    return 0, 0, w, h  # 实在算不出来就当整张都是


class GameView:
    """MAA 式的分辨率无关视图。

    思路：不管窗口实际多大（2560x1600 也好 1280x720 也好，150% 缩放
    也好），都统一处理成 ref_w x ref_h（默认 1280x720）的标准画面再做
    识别；点击时再把标准坐标换算回真实窗口。

    所有模板图片都必须用处理后的标准画面来制作（capture_tool 截出来
    的主文件就是标准画面），点击配置里的 point 坐标也写标准坐标。

    锚点校准：几何检测在某些窗口比例下会有偏差（比如窗口正好16:9但
    页面把画布往下压时）。grab() 会顺手找一两个"锚点模板"（templates/
    anchors.json 里记录了它们的正确位置），量出当前画面的整体偏移，
    click() 对固定坐标自动补偿。模板点击天然自校准，不需要补偿。
    """

    def __init__(self, hwnd, ref_w=1280, ref_h=720, auto_crop=True, manual_rect=None):
        self.cap = WindowCapture(hwnd)
        self.ref_w = ref_w
        self.ref_h = ref_h
        self.auto_crop = auto_crop
        self.manual_rect = manual_rect  # [x, y, w, h]，配置文件里的手动兜底
        self.area = (0, 0, self.cap.width, self.cap.height)  # 最近一次检测到的游戏区域
        self._grab_size = (self.cap.width, self.cap.height)  # 最近一次截图时的窗口尺寸
        self.ref_offset = (0, 0)  # 锚点测出的当前画面整体偏移 (dx, dy)
        self.calib = (0.0, 0.0, float(ref_w), float(ref_h))  # 画布在标准画面中的真实区域
        self._calib_locked = False  # 锁定标记: sequence 执行期间禁止更新校准
        self._anchors = self._load_anchors()

    def _load_anchors(self):
        """读取锚点表: {模板名: [标准x, 标准y]}。文件不存在就跳过校准。"""
        import json
        import os
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "templates", "anchors.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            anchors = []
            base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
            for name, pos in data.items():
                p = os.path.join(base, name)
                if os.path.exists(p):
                    t = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if t is not None and t.shape[0] >= 8:
                        anchors.append((name, t, pos))
            return anchors
        except Exception:
            return []

    def _update_offset(self, ref):
        """在当前标准画面里找锚点模板，推算 画布在标准画面里的真实区域。

        几何检测在部分窗口比例下找不到画布边界(比如窗口正好16:9但
        画布被页面压低、两侧留白又不是纯色时)，固定坐标会整体缩放偏移。
        这里利用锚点+「画布贴着检测区域底边」的约束，反推出画布当前的
        缩放和平移，click() 用它修正固定坐标。优先用位置靠上的锚点
        (离底边远，算缩放更稳)。
        """
        if not self._anchors or self._calib_locked:
            return
        # 收集所有匹配的锚点, 按(720-期望y)从大到小排 = 离底边越远越优先
        hits = []
        for name, tpl, exp in self._anchors:
            if tpl.shape[0] >= ref.shape[0] or tpl.shape[1] >= ref.shape[1]:
                continue
            r = cv2.matchTemplate(ref, tpl, cv2.TM_CCOEFF_NORMED)
            _, mv, _, ml = cv2.minMaxLoc(r)
            # 阈值比普通识别高(0.87), 排除跨画面碰巧相似的情况
            if mv >= 0.87:
                found = (ml[0] + tpl.shape[1] // 2, ml[1] + tpl.shape[0] // 2)
                hits.append((720 - exp[1], mv, found, exp))
        if not hits:
            return
        hits.sort(key=lambda t: -t[0])
        margin, mv, found, exp = hits[0]
        self.ref_offset = (found[0] - exp[0], found[1] - exp[1])

        if margin < 50:
            return  # 锚点太靠底(离底边<50px), 缩放算不准, 只用平移偏移

        # 底部锚定公式: 画布底边贴着标准画面底边(y=720)
        H = 720.0 * (720 - found[1]) / (720 - exp[1])
        W = H * self.ref_w / self.ref_h
        X = found[0] - exp[0] / self.ref_w * W
        Y = 720.0 - H
        # 合理性约束: 缩放限制在 0.8~1.25 之间
        if not (0.8 * self.ref_w <= W <= 1.25 * self.ref_w):
            return
        # 平滑+防跳变: 和上次校准接近才采信(取平均), 避免单帧噪声抖动;
        # 偏离超过 5% 说明这一帧锚点大概率匹配错了(跨画面碰巧相似),
        # 直接丢弃, 防止坏数据把坐标映射带偏——商店流程里中途弹窗/转场
        # 画面触发错误锚点后, 校准值一旦被覆盖就会累积漂移, 多轮后
        # 固定坐标点错位置。从未采信过校准(还是初始整屏)时允许直接采用。
        oX, oY, oW, oH = self.calib
        if abs(W - oW) / oW <= 0.05:
            W, H = (W + oW) / 2, (H + oH) / 2
            X, Y = (X + oX) / 2, (Y + oY) / 2
            self.calib = (X, Y, W, H)
        elif (oX, oY, oW, oH) == (0.0, 0.0, float(self.ref_w), float(self.ref_h)):
            self.calib = (X, Y, W, H)  # 首次校准, 建立起点
        # 其余情况: 偏离过大, 丢弃这一帧的估计, 沿用上一次校准

    def lock_calibration(self):
        """锁定校准: sequence 执行期间调用, 防止多次 grab 污染校准参数。"""
        self._calib_locked = True

    def unlock_calibration(self):
        """解锁校准: sequence 结束后调用, 恢复正常校准更新。"""
        self._calib_locked = False

    def map_fixed(self, rx: float, ry: float):
        """把配置里的固定标准坐标映射到当前标准画面的实际位置。"""
        X, Y, W, H = self.calib
        return X + rx * W / self.ref_w, Y + ry * H / self.ref_h

    def grab(self) -> np.ndarray:
        """截图并处理成标准分辨率的画面。"""
        raw = self.cap.grab()
        if self.manual_rect:
            x, y, w, h = self.manual_rect
        elif self.auto_crop:
            x, y, w, h = detect_game_area(raw)
        else:
            x, y, w, h = 0, 0, raw.shape[1], raw.shape[0]
        self.area = (x, y, w, h)
        self._grab_size = (self.cap.width, self.cap.height)  # 截图时的窗口尺寸
        game = raw[y:y + h, x:x + w]
        ref = cv2.resize(game, (self.ref_w, self.ref_h), interpolation=cv2.INTER_AREA)
        self._update_offset(ref)
        return ref

    def to_client(self, rx: float, ry: float):
        """标准坐标 -> 窗口客户区坐标。"""
        x, y, w, h = self.area
        cx = x + rx * w / self.ref_w
        cy = y + ry * h / self.ref_h
        return int(round(cx)), int(round(cy))

    def click(self, rx: float, ry: float, delay_after: float = 0.5, calibrated: bool = True):
        """点击标准坐标 (rx, ry)，内部自动换算到当前窗口的真实位置。

        calibrated=True  : 用于配置文件里的固定坐标，先经过锚点校准
                           (缩放+平移) 再换算（倍率/商品位这类盲点坐标需要）
        calibrated=False : 用于模板/颜色匹配出来的坐标——匹配和点击用的
                           同一套映射，天然自校准，再补偿反而会点偏
        """
        # 截图之后窗口尺寸如果变了（被还原/调整过），先重新检测游戏区域，
        # 避免用旧的映射把点击位置算偏
        self.cap._update_rect()
        if (self.cap.width, self.cap.height) != self._grab_size:
            self.grab()
        if calibrated:
            rx, ry = self.map_fixed(rx, ry)
        cx, cy = self.to_client(rx, ry)
        click_screen(self.cap.hwnd, cx, cy, delay_after)


def find_red_button(ref, region=(400, 380, 900, 680), min_area=2500, require_dialog=False,
                    expected=None, tol=70):
    """在标准画面的指定区域里找大块红色按钮(弹窗的红色确定键等)。

    比像素模板抗变化: 按钮位置/周边文字变了也能找到。
    region: (x0, y0, x1, y1) 标准画面坐标, 默认中央区域。
    require_dialog: 弹窗校验 -- 红色按钮周围 340x260 范围必须大面积
    偏亮(白色对话框本体)。道中地图上也有红色关卡节点, 但周围是
    地图背景不满足这个条件, 不会被误判。找到返回中心坐标, 否则 None。
    expected: 按钮的已知标准位置 [x, y](一般取 anchors.json 里的记录)。
    弹窗是居中模态框, 按钮位置基本固定; 而结算界面角色头像(红发角色)、
    路径地图关卡节点这类"长得像按钮的红色块"离按钮真实位置都很远,
    传入此参数后只接受 tol 像素范围内的红色块, 一刀排除远处的冒牌货,
    且不受窗口大小/映射偏移影响(标准坐标是画面相对坐标, 游戏UI位置固定)。
    """
    x0, y0, x1, y1 = region
    roi = ref[y0:y1, x0:x1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    red = cv2.bitwise_or(cv2.inRange(hsv, (0, 120, 100), (8, 255, 255)),
                         cv2.inRange(hsv, (172, 120, 100), (180, 255, 255)))
    red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    cnts, _ = cv2.findContours(red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for c in cnts:
        bx, by, bw, bh = cv2.boundingRect(c)
        if bw * bh < min_area or not 0.8 < bw / max(bh, 1) < 8:
            continue
        ccx, ccy = bx + bw // 2 + x0, by + bh // 2 + y0
        # 位置门: 只考虑"弹窗按钮应在的位置"附近的红色块
        if expected and (abs(ccx - expected[0]) > tol or abs(ccy - expected[1]) > tol):
            continue
        if best is None or bw * bh > best[2] * best[3]:
            best = (ccx, ccy, bw, bh)
    if not best:
        return None
    cx, cy = best[0], best[1]
    if require_dialog:
        bx0 = max(0, cx - 170)
        by0 = max(0, cy - 130)
        box = ref[by0:cy + 130, bx0:cx + 170]
        gray = cv2.cvtColor(box, cv2.COLOR_BGR2GRAY)
        if (gray > 170).mean() < 0.45:  # 周围亮色不足一半 -> 不是白色弹窗
            return None
    return cx, cy


def find_all_images(screen: np.ndarray, template_path: str, threshold: float = 0.8,
                    max_results: int = 12):
    """在截图里找模板的"所有"出现位置(不止第一个)。

    find_image 只返回分数最高的一个; 最终商店一屏有最多6个商品按钮
    处于相同状态, 用它逐个找会漏。这里把所有 >=threshold 的位置按
    分数从高到低收集, 相邻的重复命中只留一个(非极大值抑制)。
    返回 [(中心x, 中心y), ...], 按先上后下、先左后右排序。
    """
    template = cv2.imdecode(
        np.fromfile(template_path, dtype=np.uint8), cv2.IMREAD_COLOR
    )
    if template is None:
        raise FileNotFoundError(f"读不到模板图片: {template_path}")
    th, tw = template.shape[:2]
    if th >= screen.shape[0] or tw >= screen.shape[1]:
        return []

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(result >= threshold)
    if len(xs) == 0:
        return []
    order = np.argsort(result[ys, xs])[::-1]
    picks = []
    for idx in order:
        px, py = int(xs[idx]), int(ys[idx])
        # 同一个按钮的相邻命中只保留一个(距离小于模板尺寸一半算重复)
        if all(abs(px - qx) > tw * 0.6 or abs(py - qy) > th * 0.6 for _, qx, qy in picks):
            picks.append((float(result[py, px]), px + tw // 2, py + th // 2))
        if len(picks) >= max_results:
            break
    picks.sort(key=lambda p: (p[2], p[1]))  # 先上后下、先左后右
    return [(p[1], p[2]) for p in picks]


def click_screen(hwnd, x, y, delay_after=0.5):
    """点击窗口内坐标 (x, y)。

    使用前提（由使用者保证）：游戏窗口保持最大化、且不被其他窗口挡住。
    不做任何窗口还原/抢前台操作——那些操作会取消最大化、干扰其他窗口。
    delay_after: 点完之后等多久（秒），给游戏加载画面留时间。
    """
    sx, sy = client_to_screen(hwnd, x, y)
    ctypes.windll.user32.SetCursorPos(int(sx), int(sy))
    time.sleep(0.08)
    _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.06)
    _send_mouse_event(MOUSEEVENTF_LEFTUP)
    time.sleep(delay_after)

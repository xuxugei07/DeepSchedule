# -*- coding: utf-8 -*-
"""鲸鱼娘桌宠：点一下看课表，双击听她碎碎念。

Windows 上挂一个逐像素透明的分层窗口（UpdateLayeredWindow），界面全部用
Pillow 画成位图，所以没有白边、也没有窗口边框。
"""
import ctypes
import json
import math
import os
import random
import re
import shutil
import ssl
import time
import urllib.request
import winsound
from ctypes import wintypes
from datetime import date, datetime, timedelta

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import importers

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_JSON = os.path.join(HERE, "timetable.json")
BACKUP_JSON = os.path.join(HERE, "timetable.backup.json")
CONFIG_JSON = os.path.join(HERE, "config.json")
SKIN_DIR = os.path.join(HERE, "skins")
AUDIO_WAV = os.path.join(HERE, "sounds", "rage.wav")

ANCHOR_DATE = date(2026, 10, 27)   # 第 7 周 周二（可在右键菜单里改）
ANCHOR_WEEK = 7

# ---------------- 被狂点 8 下之后的暴走动画 ----------------
SHAKE_CLICKS = 8                   # 连续点这么多下进入/退出暴走
CLICK_GAP = 2.5                    # 两下之间超过这个秒数就重新数
SHAKE_PERIOD = 0.5                 # 一个完整来回：0.25 秒缩、0.25 秒胀
SHAKE_MIN, SHAKE_MAX = 0.75, 1.25
SHAKE_FRAME_MS = 16                # 60fps
SHAKE_FRAMES = 40                  # 一个来回预渲染 40 帧（比刷新更快，掉帧也不卡）

# 从 QQ20261028-073843.mp4 里量出来的一个周期（30fps × 15 帧 = 0.5 秒）：
# 0 = 压到最扁，1 = 抻到最长。玩偶的实际高度 68px → 190px。
# 形状特点：趴底停 2 帧 → 1 帧弹起 → 5 帧才爬到顶 → 5 帧落回。
SHAKE_CURVE = [
    0.000, 0.770, 0.852, 0.869, 0.885, 0.918, 1.000,
    0.885, 0.590, 0.180, 0.066, 0.016, 0.000, 0.000, 0.016,
]

# ---------------- 尺寸：全部按 1.0 的比例写，再统一乘 SCALE ----------------
SCALE = 0.80                       # 0.8 = 原来的 80%


def S(value):
    return max(1, round(value * SCALE))


CANVAS_W, CANVAS_H = S(560), S(600)
BUBBLE_W = S(344)

CN_DAY = "一二三四五六日"
COL_DARK = (31, 56, 100)
COL_BLUE = (47, 85, 151)
COL_TEXT = (34, 34, 34)
COL_SUB = (120, 120, 120)
COL_LINE = (216, 226, 240)
COL_DONE = (128, 128, 128)
COL_HUNGRY = (255, 179, 0)         # 「鲸鲸，饿饿，饭饭！」的琥珀黄
COL_STARVING = (220, 38, 38)       # 「我要吃，饭~~！」的正红
HUNGRY_TEXT = "鲸鲸，饿饿，饭饭！"
STARVING_TEXT = "我要吃，饭~~！"
         # #808080：已经上完的课

BUILTIN_SKINS = [
    {"id": "maid", "label": "深海女仆", "file": "whale.png"},
    {"id": "orca", "label": "虎鲸链路", "file": "orca.png"},
]

# 双击时随机说一句（{remain} / {next_min} 会按当前课表替换）
LINES = [
    "别发呆啦，主人。再不动手，今天的计划就变成明天的了。",
    "我算过了：现在去写完，晚上还能剩两小时躺着。很划算，去吧。",
    "又来看我？……看就看吧，反正我也不会跑。",
    "普通的一天攒起来，就是你想要的那个样子。真的，我算过概率。",
    "米饭吃了吗？没吃先去吃，饿着脑子不转的。",
    "别把我当闹钟。我只是……顺便提醒你一句。",
    "你上次说「今天一定早睡」。现在几点了，嗯？",
    "做不完就先做最烦的那件，剩下的都会变简单。鲸鱼不骗人。",
    "累了就趴一会儿。我允许了。（小声）我也在趴着。",
    "我不是懒，我是省电。你也省着点用，电费很贵的。",
    "「大肥鱼」这个词我已经记账了。超过三次，收利息。",
    "今天有课的人是你不是我。快去吧，别让我看笑话。",
    "深呼吸。三秒。好，现在没那么烦了吧？",
    "你比自己以为的靠谱一点点。就一点点。",
    "摸鱼可以，摸完要回来。我也摸，但我不心虚。",
    "要不要先收拾一下桌子？我保证你会想立刻坐到前面。",
    "别盯着我看了，我脸上没有作业答案。",
    "今天不顺利也没关系，鲸鱼也有逆流的时候。",
    "我把尾巴借你靠一下。就一下，别得寸进尺。",
    "你的努力我都看着呢。……别问我在哪看的。",
    "写到卡住就站起来走两步，脑子是走通的，不是坐通的。",
    "答应我，今晚别熬到三点。两点半也不行。",
    "我数了三遍，你这个进度其实没你想的那么糟。",
    "要是有人让你难受，记得你还有一条鲸鱼可以告状。",
    "行了行了，去忙吧。我在这儿给你看着时间。",
    "别把「再等一下」说成习惯。等一下，就是不想开始。",
    "今天还有 {remain} 节课没上，别问我为什么知道。",
    "离下一节课还有 {next_min} 分钟。我不是催你，我是在陈述事实。",
]

def _curve_tangents():
    """Fritsch–Carlson 保单调切线（环绕），保证插值不过冲、不出小波浪。"""
    n = len(SHAKE_CURVE)
    y = SHAKE_CURVE
    delta = [y[(i + 1) % n] - y[i] for i in range(n)]
    m = []
    for i in range(n):
        prev, nxt = delta[(i - 1) % n], delta[i]
        m.append(0.0 if prev * nxt <= 0 else (prev + nxt) / 2.0)
    for i in range(n):
        d = delta[i]
        if d == 0.0:
            m[i] = m[(i + 1) % n] = 0.0
            continue
        a, b = m[i] / d, m[(i + 1) % n] / d
        norm = a * a + b * b
        if norm > 9.0:
            t = 3.0 / math.sqrt(norm)
            m[i], m[(i + 1) % n] = t * a * d, t * b * d
    return m


_CURVE_M = _curve_tangents()


# ---------------------------------------------------------------- 账户余额
CRED_PATH = os.path.expanduser(r"~\.dsh\.credentials.yaml")
BALANCE_URL = "https://platform.deepseek.com/api/v0/users/get_user_summary"
_BALANCE = {"at": 0.0, "amount": None}
BALANCE_TTL = 120          # 秒：两分钟内不重复查


def account_balance(force=False):
    """返回账户余额（CNY 浮点），查不到返回 None。

    用的就是 DSH 自己存的那张授权：凭证文件里 deepseek-account-platform/default
    的 token，按平台的规矩放在 x-dsh-auth-token 头上。
    """
    now = time.monotonic()
    if not force and _BALANCE["amount"] is not None and now - _BALANCE["at"] < BALANCE_TTL:
        return _BALANCE["amount"]
    try:
        raw = open(CRED_PATH, encoding="utf-8").read()
        block = raw.split("deepseek-account-platform/default:")[-1]
        token = re.search(r"token:\s*(\S+)", block)
        if not token:
            return None
        req = urllib.request.Request(BALANCE_URL, headers={
            "x-dsh-auth-token": token.group(1).strip().strip('"'),
            "accept": "application/json",
            "user-agent": "dsh-whale-pet/1.0",
        })
        with urllib.request.urlopen(req, timeout=4,
                                    context=ssl.create_default_context()) as resp:
            body = json.loads(resp.read().decode("utf-8", "ignore"))
        wallets = (body.get("data") or {}).get("biz_data") or {}
        total = 0.0
        for key in ("normal_wallets", "bonus_wallets"):
            for wallet in wallets.get(key) or []:
                if (wallet.get("currency") or "").upper() == "CNY":
                    total += float(wallet.get("balance") or 0)
        _BALANCE["amount"] = total
        _BALANCE["at"] = now
        return total
    except Exception:                                  # noqa: BLE001
        return _BALANCE["amount"] if _BALANCE["amount"] is not None else None


def balance_note():
    """余额那一行 + 按档位加的饿饿台词。"""
    amount = account_balance()
    if amount is None:
        return ""
    lines = [f"余额还剩 ¥{amount:.2f}"]
    if amount < 5:
        lines.append("我要吃，饭~~！")
    elif amount < 10:
        lines.append("鲸鲸，饿饿，饭饭！")
    return "\n".join(lines)


def _curve_at(phase):
    """在 SHAKE_CURVE 上做保单调三次插值，phase ∈ [0,1)，首尾相接。

    线性插值会在采样点留速度折角（60fps 下一顿一顿）；Catmull-Rom 又会
    在平坦段轻微过冲。PCHIP 过点、C1 连续、且不会冲出 [min,max]。
    """
    n = len(SHAKE_CURVE)
    pos = (phase % 1.0) * n
    i = int(math.floor(pos))
    f = pos - i
    i %= n
    y0, y1 = SHAKE_CURVE[i], SHAKE_CURVE[(i + 1) % n]
    m0, m1 = _CURVE_M[i], _CURVE_M[(i + 1) % n]
    f2, f3 = f * f, f * f * f
    value = ((2 * f3 - 3 * f2 + 1) * y0 + (f3 - 2 * f2 + f) * m0
             + (-2 * f3 + 3 * f2) * y1 + (f3 - f2) * m1)
    return min(1.0, max(0.0, value))


user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

PROTOTYPES_DEFINED = False


def _setup_prototypes():
    """64 位下句柄必须声明返回类型与参数类型，否则会被截成 32 位或转换溢出。"""
    global PROTOTYPES_DEFINED
    if PROTOTYPES_DEFINED:
        return
    PROTOTYPES_DEFINED = True

    user32.CreateWindowExW.restype = wintypes.HWND
    user32.GetDC.restype = wintypes.HDC
    user32.LoadCursorW.restype = wintypes.HANDLE
    user32.DefWindowProcW.restype = ctypes.c_longlong
    user32.SetTimer.restype = wintypes.UINT
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateDIBSection.restype = ctypes.c_void_p
    gdi32.SelectObject.restype = ctypes.c_void_p

    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowPos.argtypes = [wintypes.HWND, ctypes.c_void_p, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p]
    user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    user32.LoadCursorW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    user32.GetDC.argtypes = [ctypes.c_void_p]
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT,
                                      wintypes.WPARAM, wintypes.LPARAM]
    user32.PostQuitMessage.argtypes = [ctypes.c_int]
    user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), ctypes.c_void_p,
                                   wintypes.UINT, wintypes.UINT]
    user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.UpdateLayeredWindow.argtypes = [
        wintypes.HWND, wintypes.HDC, ctypes.POINTER(POINT), ctypes.POINTER(SIZE),
        wintypes.HDC, ctypes.POINTER(POINT), wintypes.DWORD,
        ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD]
    gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi32.CreateDIBSection.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, wintypes.DWORD]
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    user32.MonitorFromWindow.restype = wintypes.HANDLE
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
    user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT,
                                             ctypes.c_void_p, wintypes.UINT]
    user32.SetCapture.restype = wintypes.HWND
    user32.SetCapture.argtypes = [wintypes.HWND]
    user32.ReleaseCapture.restype = wintypes.BOOL


ULW_ALPHA = 0x00000002
AC_SRC_OVER, AC_SRC_ALPHA = 0x00, 0x01
WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_POPUP = 0x80000000
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0001, 0x0002, 0x0010, 0x0040
WM_DESTROY, WM_TIMER = 0x0002, 0x0113
WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0201, 0x0202
WM_MOUSEMOVE, WM_RBUTTONUP = 0x0200, 0x0205
WM_LBUTTONDBLCLK = 0x0203

TIMER_TICK, TIMER_TOPMOST, TIMER_SINGLE, TIMER_NOTE = 1, 2, 3, 4
TIMER_SHAKE = 5


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


# ---------------------------------------------------------------- 字体
def _font(candidates, size):
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


YAHEI = r"C:\Windows\Fonts\msyh.ttc"
YAHEI_BD = r"C:\Windows\Fonts\msyhbd.ttc"
CONSOLAS_BD = r"C:\Windows\Fonts\consolab.ttf"


# ---------------------------------------------------------------- 数据
def load_timetable():
    with open(DATA_JSON, encoding="utf-8") as fh:
        return json.load(fh)


def now_dt():
    """允许用 WHALE_PET_NOW=2026-10-27T12:00 指定“现在”，方便预览任何时段。"""
    forced = os.environ.get("WHALE_PET_NOW")
    if forced:
        try:
            return datetime.fromisoformat(forced)
        except ValueError:
            pass
    return datetime.now()


def merge_periods(rows):
    """把同一门课连续的节次并成一段：课表里 3-4 节连上是同一节课。"""
    merged = []
    for row in rows:
        if merged and merged[-1]["name"] == row["name"] and merged[-1]["room"] == row["room"] \
                and merged[-1]["p"] + 1 == row["p"]:
            merged[-1]["p"] = row["p"]
            merged[-1]["end"] = row["end"]
        else:
            merged.append(dict(row))
    return merged


def _minutes(hhmm):
    try:
        hour, minute = hhmm.split(":")
        return int(hour) * 60 + int(minute)
    except (ValueError, AttributeError):
        return 0


def rows_on(tt, day, anchor_date, anchor_week):
    week = anchor_week + (day - anchor_date).days // 7
    raw = tt["weeks"].get(str(week), {}).get(str(day.weekday()), [])
    return week, merge_periods(raw)


def build_view(tt, now, anchor_date, anchor_week):
    """今天还有课就是今天；今天的课上完了就自动翻到明天。"""
    today = now.date()
    nowm = now.hour * 60 + now.minute
    week, rows = rows_on(tt, today, anchor_date, anchor_week)
    view = {"date": today, "week": week, "rows": rows, "tomorrow": False,
            "in_range": str(week) in tt["weeks"], "nowm": nowm}
    if rows and all(_minutes(r["end"]) <= nowm for r in rows):
        tomorrow = today + timedelta(days=1)
        week2, rows2 = rows_on(tt, tomorrow, anchor_date, anchor_week)
        view.update(date=tomorrow, week=week2, rows=rows2, tomorrow=True,
                    in_range=str(week2) in tt["weeks"])
    for row in view["rows"]:
        row["done"] = (not view["tomorrow"]) and _minutes(row["end"]) <= nowm
    return view


def prepare_sprite(path, size):
    """导入的图片：抠白底、裁边、缩放到桌宠尺寸。"""
    img = Image.open(path).convert("RGBA")
    alpha = np.array(img.getchannel("A"))
    if alpha.min() > 250:                     # 没有透明度：把连边的白底抠掉
        rgb = np.array(img.convert("RGB")).astype(np.int16)
        mn = rgb.min(axis=2)
        mx = rgb.max(axis=2)
        h, w = mn.shape
        near_white = mn > 236
        seen = np.zeros((h, w), dtype=bool)
        stack = [(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)] + \
                [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)]
        fill = np.zeros((h, w), dtype=bool)
        while stack:
            x, y = stack.pop()
            if not (0 <= x < w and 0 <= y < h) or seen[y, x]:
                continue
            seen[y, x] = True
            if not near_white[y, x]:
                continue
            fill[y, x] = True
            stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
        out = rgb.copy()
        out[(mx - mn) < 12] = 0               # 灰阶像素压成纯黑，别留灰边
        alpha = np.where(fill, 0, 255).astype(np.uint8)
        alpha[(mx - mn) >= 12] = 255
        img = Image.fromarray(np.dstack([out, alpha]).astype(np.uint8), "RGBA")

    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    w, h = img.size
    scale = min(size / max(1, w), size * 1.35 / max(1, h))
    return img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)


def wrap_text(draw, text, font, max_width):
    """按像素宽度折行（中文没有空格，得自己量）。"""
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        trial = cur + ch
        if draw.textlength(trial, font=font) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    # 最后一行只剩一个标点时并回上一行，别让句号孤零零掉下去
    if len(lines) > 1 and len(lines[-1]) <= 2 and all(ch in "，。！？、；：）】”" for ch in lines[-1]):
        lines[-2] += lines[-1]
        lines.pop()
    return lines


# ---------------------------------------------------------------- DPI / 工作区
def _enable_dpi_awareness():
    """必须在建窗、读工作区之前调用，否则拿到的是缩放后的假坐标。"""
    try:
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:                                   # noqa: BLE001
        pass
    try:
        ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
    except Exception:                                   # noqa: BLE001
        pass


def _work_area(hwnd=None):
    """显示器的工作区（扣掉任务栏的那块）。"""
    _setup_prototypes()
    if hwnd:
        hmon = user32.MonitorFromWindow(hwnd, 2)      # MONITOR_DEFAULTTONEAREST
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            r = info.rcWork
            return r.left, r.top, r.right, r.bottom
    rect = RECT()
    if user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):   # SPI_GETWORKAREA
        return rect.left, rect.top, rect.right, rect.bottom
    return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def _clamp_pos(x, y, hwnd=None):
    """把窗口卡进工作区：她永远待在任务栏上方，不会骑在任务栏上。"""
    wl, wt, wr, wb = _work_area(hwnd)
    x = max(wl, min(int(x), wr - CANVAS_W))
    y = max(wt, min(int(y), wb - CANVAS_H))
    return x, y


# ---------------------------------------------------------------- 桌宠
class Pet:
    def __init__(self):
        _enable_dpi_awareness()
        self.cfg = self._load_cfg()
        self.anchor_date = self._parse_date(self.cfg.get("anchor_date")) or ANCHOR_DATE
        self.anchor_week = int(self.cfg.get("anchor_week") or ANCHOR_WEEK)
        self.skins = self._collect_skins()
        self.skin_index = self._skin_index(self.cfg.get("skin"))
        self.sprite = self._load_sprite()
        self.state = "hidden"          # hidden | today | menu | line | note
        self.text = ""
        self.hit = []
        self.drag_from = None
        self.drag_origin = None
        self.moved = 0
        self.pending_click = False
        self.last_click = 0.0
        self.last_line = None
        self.last_sig = None
        self.shaking = False
        self.peek = None
        self.shake_start = 0.0
        self.click_times = []
        self.audio_on = False
        self.tt = load_timetable()
        self.hwnd = None
        self._build_window()
        self.render()

    # ---- 配置 / 皮肤
    @staticmethod
    def _parse_date(value):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    def _collect_skins(self):
        skins = list(BUILTIN_SKINS)
        for item in self.cfg.get("skins") or []:
            if not isinstance(item, dict) or "file" not in item:
                continue
            path = item["file"] if os.path.isabs(item["file"]) else os.path.join(HERE, item["file"])
            if os.path.exists(path) and all(s["id"] != item.get("id") for s in skins):
                skins.append({"id": item.get("id", os.path.basename(path)),
                              "label": item.get("label") or item.get("id") or "自定义",
                              "file": item["file"]})
        return skins

    def _skin_index(self, skin_id):
        for i, skin in enumerate(self.skins):
            if skin["id"] == skin_id:
                return i
        return 0

    def _sprite_path(self, skin):
        path = skin["file"]
        if os.path.isabs(path):
            return path
        candidate = os.path.join(HERE, path)
        if os.path.exists(candidate) or not path.startswith("skins/"):
            return candidate
        return os.path.join(SKIN_DIR, os.path.basename(path))

    def _load_sprite(self):
        return Image.open(self._sprite_path(self.skins[self.skin_index])).convert("RGBA")

    def _load_cfg(self):
        try:
            with open(CONFIG_JSON, encoding="utf-8") as fh:
                cfg = json.load(fh)
        except (OSError, ValueError):
            cfg = {}
        sw = user32.GetSystemMetrics(0)
        _, _, _, wb = _work_area()
        cfg.setdefault("x", sw - CANVAS_W - 40)
        cfg.setdefault("y", wb - CANVAS_H - 10)
        cfg["x"], cfg["y"] = _clamp_pos(int(cfg["x"]), int(cfg["y"]))
        return cfg

    def _save_cfg(self):
        self.cfg.update({
            "x": self.x, "y": self.y,
            "skin": self.skins[self.skin_index]["id"],
            "skins": [s for s in self.skins if s["id"] not in
                      {b["id"] for b in BUILTIN_SKINS}],
            "anchor_date": self.anchor_date.isoformat(),
            "anchor_week": self.anchor_week,
        })
        try:
            with open(CONFIG_JSON, "w", encoding="utf-8") as fh:
                json.dump(self.cfg, fh, ensure_ascii=False, indent=1)
        except OSError:
            pass

    def _cycle_skin(self):
        self.skin_index = (self.skin_index + 1) % len(self.skins)
        self.sprite = self._load_sprite()
        self._save_cfg()
        self.state = "today"
        self.render()

    # ---- 窗口
    def _build_window(self):
        _setup_prototypes()
        _enable_dpi_awareness()

        hinst = ctypes.windll.kernel32.GetModuleHandleW(None)
        self._proc = WNDPROC(self._wndproc)
        wc = WNDCLASSW()
        wc.style = 0x0002            # CS_DBLCLKS：不给这个，系统根本不会发双击消息
        wc.lpfnWndProc = self._proc
        wc.hInstance = hinst
        wc.hCursor = user32.LoadCursorW(0, ctypes.c_void_p(32512))
        wc.lpszClassName = "DshWhalePet"
        user32.RegisterClassW(ctypes.byref(wc))

        self.x, self.y = int(self.cfg["x"]), int(self.cfg["y"])
        ex = WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        self.hwnd = user32.CreateWindowExW(
            ex, "DshWhalePet", "DeepSchedule", WS_POPUP,
            self.x, self.y, CANVAS_W, CANVAS_H, 0, 0, hinst, 0)
        user32.ShowWindow(self.hwnd, 4)  # SW_SHOWNOACTIVATE（连调两次防被 STARTUPINFO 吃掉）
        user32.ShowWindow(self.hwnd, 4)

        self._screen_dc = user32.GetDC(0)
        self._mem_dc = gdi32.CreateCompatibleDC(self._screen_dc)
        self._canvas_buf = np.zeros((CANVAS_H, CANVAS_W, 4), dtype=np.uint8)
        self._dib = None
        self._bits = None
        self.shake_frames = None

    # ---- 位图 -> 分层窗口
    def _ensure_dib(self):
        """DIB 只建一次：暴走动画每秒三十帧，不能每帧都重建位图。"""
        if getattr(self, "_dib", None):
            return
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = CANVAS_W
        bmi.bmiHeader.biHeight = -CANVAS_H
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        bits = ctypes.c_void_p()
        self._dib = gdi32.CreateDIBSection(self._screen_dc, ctypes.byref(bmi), 0,
                                           ctypes.byref(bits), 0, 0)
        self._bits = bits
        self._dib_old = gdi32.SelectObject(self._mem_dc, self._dib)

    def _push(self, data):
        """把一帧 BGRA 字节推到分层窗口上。"""
        self._ensure_dib()
        ctypes.memmove(self._bits, data, len(data))
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        dst = POINT(self.x, self.y)
        size = SIZE(CANVAS_W, CANVAS_H)
        src = POINT(0, 0)
        user32.UpdateLayeredWindow(self.hwnd, self._screen_dc, ctypes.byref(dst),
                                   ctypes.byref(size), self._mem_dc, ctypes.byref(src),
                                   0, ctypes.byref(blend), ULW_ALPHA)

    @staticmethod
    def _to_bgra(img):
        arr = np.array(img, dtype=np.uint8)          # H,W,4 RGBA
        alpha = arr[:, :, 3:4].astype(np.float32) / 255.0
        rgb = (arr[:, :, :3].astype(np.float32) * alpha).astype(np.uint8)
        bgra = np.dstack([rgb[:, :, 2], rgb[:, :, 1], rgb[:, :, 0], arr[:, :, 3]])
        return np.ascontiguousarray(bgra).tobytes()

    def _blit(self, img):
        self._push(self._to_bgra(img))

    # ---- 画面
    def _peek_view(self):
        """把「第 n 周第 m 天」换成一个能直接画进气泡的 view。"""
        week, day = self.peek
        now = now_dt()
        today = now.date()
        rows = merge_periods(self.tt["weeks"].get(str(week), {}).get(str(day), []))
        shift = (week - self.anchor_week) * 7 + (day - today.weekday())
        when = today + timedelta(days=shift)
        for r in rows:
            r["done"] = when == today and _minutes(r["end"]) <= now.hour * 60 + now.minute
        return {"date": when, "week": week, "rows": rows, "tomorrow": False,
                "in_range": str(week) in self.tt["weeks"],
                "nowm": now.hour * 60 + now.minute}

    def render(self):
        if self.peek:
            view = self._peek_view()
        else:
            view = build_view(self.tt, now_dt(), self.anchor_date, self.anchor_week)
        self.last_sig = (view["date"], view["tomorrow"],
                         tuple(r["done"] for r in view["rows"]),
                         self.skin_index, self.state, self.text)
        img = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        self.hit = []
        if self.state == "menu":
            self._draw_menu(img, view)
        elif self.state in ("line", "note"):
            self._draw_text(img, view)
        elif self.state == "today":
            self._draw_schedule(img, view)
        self._draw_sprite(img)
        self._blit(img)

    def _shake_factor(self):
        """按视频里量出来的曲线走：压到底停一下，弹起，再落回去。"""
        phase = ((time.monotonic() - self.shake_start) % SHAKE_PERIOD) / SHAKE_PERIOD
        return SHAKE_MIN + (SHAKE_MAX - SHAKE_MIN) * _curve_at(phase)

    def _make_shake_frames(self):
        """预先算好一个来回的帧（0.5 秒 / 20ms = 25 帧），动画时只做内存拷贝。

        只压/抻高度，宽度锁死在原尺寸——左右不许有一像素的抖动。
        """
        count = SHAKE_FRAMES
        frames = []
        w = self.sprite.width
        for i in range(count):
            factor = SHAKE_MIN + (SHAKE_MAX - SHAKE_MIN) * _curve_at(i / count)
            h = max(1, round(self.sprite.height * factor))
            small = np.array(self.sprite.resize((w, h), Image.BILINEAR), dtype=np.uint8)
            alpha = small[:, :, 3:4].astype(np.float32) / 255.0
            rgb = (small[:, :, :3].astype(np.float32) * alpha).astype(np.uint8)
            bgra = np.dstack([rgb[:, :, 2], rgb[:, :, 1], rgb[:, :, 0], small[:, :, 3]])
            frames.append((np.ascontiguousarray(bgra), CANVAS_W - w - 6, CANVAS_H - h - 6))
        return frames

    def _push_shake_frame(self, index):
        arr, px, py = self.shake_frames[index % len(self.shake_frames)]
        h, w = arr.shape[:2]
        buf = self._canvas_buf
        buf.fill(0)
        buf[py:py + h, px:px + w] = arr
        self._push(buf.tobytes())

    def _draw_sprite(self, img):
        sprite = self.sprite
        if self.shaking:                      # 只改高度，宽度保持原样
            h = max(1, round(sprite.height * self._shake_factor()))
            sprite = sprite.resize((sprite.width, h), Image.BILINEAR)
        px = CANVAS_W - sprite.width - 6
        py = CANVAS_H - sprite.height - 6
        img.alpha_composite(sprite, (px, py))

    # -- 气泡外壳
    def _bubble(self, img, bubble_h):
        pet_top = CANVAS_H - self.sprite.height - 6
        bw = BUBBLE_W
        bx = CANVAS_W - bw - S(4)
        by = max(S(4), pet_top - bubble_h - S(10))

        shadow = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(
            [bx + S(3), by + S(6), bx + bw + S(3), by + bubble_h + S(6)],
            radius=S(20), fill=(20, 30, 55, 70))
        img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(S(7))))

        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([bx, by, bx + bw, by + bubble_h], radius=S(20),
                               fill=(255, 255, 255, 246), outline=COL_BLUE, width=2)
        tip_x = bx + bw - S(56)
        draw.polygon([(tip_x - S(13), by + bubble_h - 2), (tip_x + S(13), by + bubble_h - 2),
                      (tip_x + S(2), by + bubble_h + S(14))], fill=(255, 255, 255, 246))
        draw.line([(tip_x - S(13), by + bubble_h - 2), (tip_x + S(2), by + bubble_h + S(14))],
                  fill=COL_BLUE, width=2)
        draw.line([(tip_x + S(13), by + bubble_h - 2), (tip_x + S(2), by + bubble_h + S(14))],
                  fill=COL_BLUE, width=2)
        return draw, bx, by, bw

    def _header(self, draw, bx, by, bw, week, when, suffix=""):
        f_head = _font([YAHEI_BD], 13)
        head = f"第{week}周 · 周{CN_DAY[when.weekday()]}{suffix}"
        draw.text((bx + S(16), by + S(11)), head, font=f_head, fill=COL_DARK)
        f_date = _font([CONSOLAS_BD], 10)
        txt = f"{when.month}/{when.day}"
        draw.text((bx + bw - S(16) - draw.textlength(txt, font=f_date), by + S(14)),
                  txt, font=f_date, fill=COL_BLUE)
        draw.line([bx + S(14), by + S(41), bx + bw - S(14), by + S(41)],
                  fill=COL_LINE, width=1)

    def _draw_schedule(self, img, view):
        rows, week, when = view["rows"], view["week"], view["date"]
        bubble_h = S(46) + max(1, len(rows)) * 36 + S(12)
        draw, bx, by, bw = self._bubble(img, bubble_h)
        self._header(draw, bx, by, bw, week, when, " · 明天" if view["tomorrow"] else "")

        if not view["in_range"]:
            msg = f"第{week}周没有课表"
        elif not rows:
            msg = "明天没有课哦" if view["tomorrow"] else "今天没有课，睡到自然醒"
        else:
            msg = None

        if msg:
            f_msg = _font([YAHEI], 11)
            draw.text((bx + (bw - draw.textlength(msg, font=f_msg)) / 2, by + S(54)),
                      msg, font=f_msg, fill=COL_SUB)
            return

        f_time = _font([CONSOLAS_BD], 9)
        f_name = _font([YAHEI_BD], 11)
        f_room = _font([YAHEI], 9)
        for i, r in enumerate(rows):
            y = by + S(48) + i * 36
            done = r.get("done")
            c_name = COL_DONE if done else COL_TEXT
            c_time = COL_DONE if done else COL_BLUE
            c_room = COL_DONE if done else COL_SUB
            tx, ty = bx + S(14), y + S(4)
            nx, ny = bx + S(104), y
            draw.text((tx, ty), f"{r['start']}-{r['end']}", font=f_time, fill=c_time)
            draw.text((nx, ny), r["name"], font=f_name, fill=c_name)
            draw.text((nx, ny + 16), r["room"], font=f_room, fill=c_room)
            if done:   # 上完的课：一道横线划掉
                for x0, y0, text, font in ((tx, ty, f"{r['start']}-{r['end']}", f_time),
                                           (nx, ny, r["name"], f_name)):
                    box = draw.textbbox((x0, y0), text, font=font)
                    mid = (box[1] + box[3]) / 2 + 1
                    draw.line([(box[0], mid), (box[2], mid)], fill=COL_DONE, width=2)
            if i:
                draw.line([bx + S(14), y - S(4), bx + bw - S(14), y - S(4)],
                          fill=(238, 242, 248), width=1)

    def _draw_text(self, img, view):
        """碎碎念气泡：正文 13 号，饿饿那两句单独放大加粗上色。"""
        f_body = _font([YAHEI], 13)
        f_hungry = _font([YAHEI_BD], 15)      # 正文 13 再大两号，且加粗
        f_balance = _font([YAHEI], 12)        # 余额那行固定 12 号
        f_sign = _font([YAHEI], 9)
        probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        width = BUBBLE_W - S(46)

        rows = []                              # (文本, 字体, 颜色, 行高)
        for chunk in self.text.split("\n"):
            stripped = chunk.strip()
            if stripped in (HUNGRY_TEXT, STARVING_TEXT):
                color = COL_HUNGRY if stripped == HUNGRY_TEXT else COL_STARVING
                rows.append((stripped, f_hungry, color, 22))
                continue
            if stripped.startswith("余额"):
                rows.append((stripped, f_balance, COL_TEXT, 20))
                continue
            for line in wrap_text(probe, chunk, f_body, width) or [""]:
                rows.append((line, f_body, COL_TEXT, 21))

        body_h = sum(r[3] for r in rows)
        bubble_h = S(20) + body_h + S(34)
        draw, bx, by, bw = self._bubble(img, bubble_h)
        y = by + S(14)
        for text, font, color, height in rows:
            draw.text((bx + S(18), y), text, font=font, fill=color)
            y += height

        sign = "—— 鲸鱼娘" if self.state == "line" else ""
        if sign:
            tw = draw.textlength(sign, font=f_sign)
            draw.text((bx + bw - S(18) - tw, y + S(2)), sign, font=f_sign, fill=COL_SUB)

    def _draw_menu(self, img, view):
        nxt = self.skins[(self.skin_index + 1) % len(self.skins)]["label"]
        entries = [
            ("今日课程", "today"),
            (f"换肤 → {nxt}", "skin"),
            ("导入皮肤…", "import_skin"),
            ("导入课表…", "import_tt"),
            ("设置周次…", "anchor"),
            ("退出桌宠", "quit"),
        ]
        bubble_h = S(46) + len(entries) * S(34) + S(10)
        draw, bx, by, bw = self._bubble(img, bubble_h)
        self._header(draw, bx, by, bw, view["week"], view["date"])
        f_item = _font([YAHEI], 11)
        for i, (label, action) in enumerate(entries):
            y = by + S(46) + i * S(34)
            draw.text((bx + S(20), y + S(6)), label, font=f_item, fill=COL_TEXT)
            self.hit.append((bx + S(8), y, bx + bw - S(8), y + S(32), action))

    # ---- 交互
    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_LBUTTONDOWN:
            user32.SetCapture(self.hwnd)      # 抓住鼠标，拖到窗口外也不丢
            self.drag_from = self._cursor_screen()
            self.drag_origin = (self.x, self.y)
            self.moved = 0
            return 0
        if msg == WM_MOUSEMOVE:
            if self.drag_from is not None:
                cx, cy = self._cursor_screen()
                ddx, ddy = cx - self.drag_from[0], cy - self.drag_from[1]
                self.moved = max(self.moved, abs(ddx) + abs(ddy))
                if self.moved > 3:
                    self.x, self.y = _clamp_pos(self.drag_origin[0] + ddx,
                                                self.drag_origin[1] + ddy, self.hwnd)
                    user32.SetWindowPos(self.hwnd, ctypes.c_void_p(-1), self.x, self.y, 0, 0,
                                        SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
            return 0
        if msg == WM_LBUTTONDBLCLK:
            # 双击交给系统的双击判定，比自己在 up 事件里数时间靠谱
            if self.shaking:            # 暴走里被敲不算双击，别弹台词
                self._swallow_up = True
                return 0
            user32.KillTimer(self.hwnd, TIMER_SINGLE)
            self.pending_click = False
            self._swallow_up = True
            self.drag_from = None
            self._double_click(*self._cursor_local(lparam))
            return 0
        if msg == WM_LBUTTONUP:
            user32.ReleaseCapture()
            dragged = self.moved > 3
            self.drag_from = None
            # 每一“下”都先记账（含双击被系统吃掉的那一下），凑够 8 下就暴走
            if not dragged and self._register_click():
                self._swallow_up = False
                return 0
            if getattr(self, "_swallow_up", False):
                self._swallow_up = False
                return 0
            if dragged:
                self._save_cfg()
            else:
                self._on_click(*self._cursor_local(lparam))
            return 0
        if msg == WM_RBUTTONUP:
            if self.shaking:          # 暴走时不弹菜单，专心被敲
                return 0
            self.state = "menu"
            self.render()
            return 0
        if msg == WM_TIMER:
            if wparam == TIMER_TOPMOST:
                user32.SetWindowPos(self.hwnd, ctypes.c_void_p(-1), 0, 0, 0, 0,
                                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
            elif wparam == TIMER_SINGLE:
                user32.KillTimer(self.hwnd, TIMER_SINGLE)
                if self.pending_click:
                    self.pending_click = False
                    self._single_click()
            elif wparam == TIMER_NOTE:
                user32.KillTimer(self.hwnd, TIMER_NOTE)
                if self.state in ("line", "note"):
                    self.state = "hidden"
                    self.render()
            elif wparam == TIMER_SHAKE:
                if self.shaking and self.shake_frames:
                    n = len(self.shake_frames)
                    phase = ((time.monotonic() - self.shake_start) % SHAKE_PERIOD) / SHAKE_PERIOD
                    self._push_shake_frame(int(phase * n))
            else:
                self._tick()
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _cursor_screen(self):
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def _cursor_local(self, lparam):
        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
        return x, y

    def _register_click(self):
        """连续敲 8 下：进/出暴走。返回 True 表示这一下被计数逻辑吃掉了。"""
        now = time.monotonic()
        self.click_times = [t for t in self.click_times if now - t <= CLICK_GAP]
        self.click_times.append(now)
        if len(self.click_times) >= SHAKE_CLICKS:
            self.click_times = []
            self._toggle_shake()
            return True
        return False

    def _toggle_shake(self):
        if self.shaking:
            self._stop_shake()
        else:
            self._start_shake()

    def _start_shake(self):
        self.shaking = True
        self.state = "hidden"          # 收起所有框
        self.text = ""
        self.pending_click = False
        user32.KillTimer(self.hwnd, TIMER_SINGLE)
        self.shake_start = time.monotonic()
        self.shake_frames = self._make_shake_frames()
        user32.SetTimer(self.hwnd, TIMER_SHAKE, SHAKE_FRAME_MS, 0)
        self._play_audio()
        self._push_shake_frame(0)

    def _stop_shake(self):
        self.shaking = False
        self.shake_frames = None
        user32.KillTimer(self.hwnd, TIMER_SHAKE)
        self._stop_audio()
        self.render()

    def _play_audio(self):
        if self.audio_on or not os.path.exists(AUDIO_WAV):
            return
        try:
            winsound.PlaySound(AUDIO_WAV, winsound.SND_FILENAME |
                               winsound.SND_ASYNC | winsound.SND_LOOP)
            self.audio_on = True
        except Exception:                       # noqa: BLE001
            self.audio_on = False

    def _stop_audio(self):
        if not self.audio_on:
            return
        try:
            winsound.PlaySound(None, 0)
        finally:
            self.audio_on = False

    def _on_click(self, x, y):
        """区分单击/双击：单击先等 260ms，双击就取消。"""
        if self.shaking:                # 暴走里只数被敲的次数
            return
        now = time.monotonic()
        if self.pending_click and (now - self.last_click) < 0.6:
            user32.KillTimer(self.hwnd, TIMER_SINGLE)
            self.pending_click = False
            self._double_click(x, y)
            return
        self.pending_click = True
        self.last_click = now
        self._pending_xy = (x, y)
        user32.SetTimer(self.hwnd, TIMER_SINGLE, 260, 0)

    def _single_click(self):
        x, y = getattr(self, "_pending_xy", (0, 0))
        for x1, y1, x2, y2, action in self.hit:
            if x1 <= x <= x2 and y1 <= y <= y2:
                self._run_action(action)
                return
        if self.state == "today":
            self.state = "hidden"
            self.peek = None            # 收起来就把临时跳转清掉
        else:
            self.state = "today"
        self.render()

    def _double_click(self, x, y):
        if self.state == "menu":          # 菜单里双击就当单击
            self._single_click()
            return
        self._say(self._pick_line())

    def _run_action(self, action):
        if action == "quit":
            self._quit()
        elif action == "skin":
            self._cycle_skin()
        elif action == "import_skin":
            self._import_skin()
        elif action == "import_tt":
            self._import_timetable()
        elif action == "anchor":
            self._set_anchor()
        else:
            self.state = "today"
            self.render()

    # ---- 台词
    def _pick_line(self):
        remain, next_min = self._stats()
        pool = [ln for ln in LINES if ln != self.last_line]
        line = random.choice(pool)
        line = line.replace("{remain}", str(remain)).replace("{next_min}", str(next_min))
        self.last_line = line
        note = balance_note()
        return f"{line}\n\n{note}" if note else line

    def _stats(self):
        view = build_view(self.tt, now_dt(), self.anchor_date, self.anchor_week)
        nowm = view["nowm"]
        remain = sum(1 for r in view["rows"] if _minutes(r["end"]) > nowm)
        upcoming = [_minutes(r["start"]) for r in view["rows"] if _minutes(r["start"]) > nowm]
        return remain, (min(upcoming) - nowm if upcoming else 0)

    def _say(self, text, mode="line", note=False):
        self.text = text
        self.state = "note" if (note or mode == "note") else "line"
        self.render()
        user32.SetTimer(self.hwnd, TIMER_NOTE, 7000 if not note else 5000, 0)

    # ---- 导入
    def _dialog(self, kind, **kwargs):
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            if kind == "file":
                from tkinter import filedialog
                return filedialog.askopenfilename(parent=root, **kwargs)
            from tkinter import simpledialog
            if kind == "text":
                return simpledialog.askstring(parent=root, **kwargs)
            return simpledialog.askinteger(parent=root, **kwargs)
        finally:
            root.destroy()

    def _popup(self, text, seconds=1.0):
        """自己会关掉的小提示窗（不用点确定）。"""
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        top = tk.Toplevel(root)
        top.title("鲸鱼娘")
        top.attributes("-topmost", True)
        top.resizable(False, False)
        top.configure(bg="#ffffff")
        tk.Label(top, text=text, font=("Microsoft YaHei", 14),
                 bg="#ffffff", fg="#1f1f1f", padx=36, pady=22).pack(fill="both", expand=True)
        top.update_idletasks()
        w, h = max(240, top.winfo_reqwidth()), max(90, top.winfo_reqheight())
        x = (top.winfo_screenwidth() - w) // 2
        y = (top.winfo_screenheight() - h) // 3
        top.geometry(f"{w}x{h}+{x}+{y}")
        top.deiconify()
        top.lift()
        top.focus_force()
        top.update()
        top.after(int(seconds * 1000), root.destroy)
        root.mainloop()

    @staticmethod
    def _parse_position(text):
        """「7，2」「7,2」「7 2」「第7周第2天」都认成 (7, 2)。"""
        numbers = re.findall(r"\d+", text or "")
        if len(numbers) < 2:
            return None
        n, m = int(numbers[0]), int(numbers[1])
        if not (1 <= n <= 60 and 1 <= m <= 7):
            return None
        return n, m

    def _ask_position(self, title="对一下课表"):
        """问「今天是第几周第几天」，找不到就「呜，没找到耶」停 1 秒再问。"""
        today = date.today()
        guess_week = self.anchor_week + (today - self.anchor_date).days // 7
        guess = f"{guess_week}，{today.weekday() + 1}"
        while True:
            answer = self._dialog(
                "text", title=title,
                prompt="今天是第几周第几天？请用 n，m 回答\n（例：7，2 表示第 7 周第 2 天）",
                initialvalue=guess)
            if answer is None:          # 取消
                return None
            parsed = self._parse_position(answer)
            if parsed:
                week, day = parsed
                if str(week) in self.tt["weeks"]:
                    return week, day
            self._say("呜，没找到耶", mode="note")
            time.sleep(1.0)                 # 停一秒再问
            self.state = "hidden"
            self.render()

    def _import_skin(self):
        try:
            path = self._dialog("file", title="选一张桌宠图片",
                                filetypes=[("图片", "*.png *.jpg *.jpeg *.webp *.bmp"),
                                           ("所有文件", "*.*")])
            if not path:
                return
            os.makedirs(SKIN_DIR, exist_ok=True)
            stem = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", os.path.splitext(os.path.basename(path))[0])[:20]
            stem = stem or "custom"
            slug, n = f"custom-{stem}", 1
            while any(s["id"] == slug for s in self.skins):
                n += 1
                slug = f"custom-{stem}-{n}"
            dst = os.path.join(SKIN_DIR, f"{slug}.png")
            prepare_sprite(path, 208).save(dst)
            entry = {"id": slug, "label": stem, "file": f"skins/{slug}.png"}
            keep_index, keep_sprite = self.skin_index, self.sprite
            self.skins.append(entry)
            self.skin_index = len(self.skins) - 1
            try:
                self.sprite = self._load_sprite()
            except Exception:
                self.skins.pop()
                self.skin_index, self.sprite = keep_index, keep_sprite
                raise
            self._save_cfg()
            self._say(f"新皮肤「{stem}」收下了。", mode="note")
        except Exception as exc:                     # noqa: BLE001
            self._say(f"皮肤导入失败：{exc}", mode="note")

    def _import_timetable(self):
        try:
            path = self._dialog("file", title="选课表文件（xlsx / xls / html / csv）",
                                filetypes=[("课表", "*.xlsx *.xls *.html *.htm *.csv"),
                                           ("所有文件", "*.*")])
            if not path:
                return
            data = importers.load_any(path)
            shutil.copyfile(DATA_JSON, BACKUP_JSON)
            with open(DATA_JSON, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=1)
            self.tt = load_timetable()

            position = self._ask_position("课表导入成功，对一下今天")
            today = date.today()
            if position is None:
                self._say("课表导入好了，周次还没对。", mode="note")
                return
            week, day = position
            self.anchor_date, self.anchor_week = today, week
            self._save_cfg()
            self.peek = (week, day - 1)        # 直接翻到对应那张表
            self.state = "today"
            self.render()
        except Exception as exc:                     # noqa: BLE001
            self._say(f"课表导入失败：{exc}", mode="note")

    def _set_anchor(self):
        try:
            position = self._ask_position("对一下今天是第几周")
            if position is None:
                return
            week, day = position
            self.anchor_date, self.anchor_week = date.today(), week
            self._save_cfg()
            self.peek = (week, day - 1)
            self.state = "today"
            self.render()
        except Exception as exc:                     # noqa: BLE001
            self._say(f"设置失败：{exc}", mode="note")

    # ---- 其他
    def _tick(self):
        """每分钟看一眼：跨天、下课、跨周都会让她自己翻页。"""
        if self.shaking or self.state not in ("today", "line", "note"):
            return
        view = build_view(self.tt, now_dt(), self.anchor_date, self.anchor_week)
        sig = (view["date"], view["tomorrow"],
               tuple(r["done"] for r in view["rows"]), self.skin_index, self.state, self.text)
        if sig != self.last_sig:
            self.render()

    def _quit(self):
        self._stop_audio()
        for timer in (TIMER_TICK, TIMER_TOPMOST, TIMER_SINGLE, TIMER_NOTE, TIMER_SHAKE):
            user32.KillTimer(self.hwnd, timer)
        user32.DestroyWindow(self.hwnd)
        user32.PostQuitMessage(0)

    def run(self):
        user32.SetTimer(self.hwnd, TIMER_TICK, 20000, 0)
        user32.SetTimer(self.hwnd, TIMER_TOPMOST, 1200, 0)
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))


def _already_running():
    """同一时间只准有一只：重复双击启动器时，后来那个直接退出。"""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW(None, False, "Local\\DeepScheduleSingleton")
    return ctypes.get_last_error() == 183      # ERROR_ALREADY_EXISTS


def main():
    if _already_running():
        return
    pet = Pet()
    pet.state = os.environ.get("WHALE_PET_OPEN", "hidden")
    pet.render()
    pet.run()


if __name__ == "__main__":
    main()

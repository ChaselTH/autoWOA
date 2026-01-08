#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
cliclick 自动化 + 第三步 Vision OCR gate（你已验证成功的方案）
"""

# =========================
# ✅ 你只需要改这一段
# =========================
from typing import Tuple
Point = Tuple[int, int]

CAILM: Point = (1061,790)

SELECT_1: Point = (1405, 633)
SELECT_2: Point = (1408, 665)
SELECT_3: Point = (1407, 695)

FILTER_1: Point = (1410, 633)
FILTER_2: Point = (1410, 664)
FILTER_3: Point = (1409, 694)

ADD_BTN: Point = (1133, 759)

# 三种方式共同的第一个点击点
START_POINT: Point = (1350, 605)

CONFIRM: Point = (871, 861)

# 操作2：START_POINT -> 再点 2 个点
A2_P2: Point = (979, 857)

TAP_WINDOW: Point = (1250,642)

# OCR ROI（来自 cliclick p，单位 points）——用你验证“截图准确”的坐标体系
CREW_TL: Point = (1001, 622)
CREW_BR: Point = (1027, 632)

OCR_1_TL: Point = (1403,619)
OCR_1_BR: Point = (1430,626)
OCR_2_TL: Point = (1403,650)
OCR_2_BR: Point = (1430,656)
OCR_3_TL: Point = (1403,678)
OCR_3_BR: Point = (1430,688)

# points -> pixels 缩放（你验证截图准确就保持不动）
COORD_SCALE = 2

# 多显示器
ALL_SCREENS = True

# 操作3：通过 gate 后，拖动滑块（按下点 -> 松开点）
SLIDER_FROM: Point = (1006, 758)
SLIDER_TO: Point = (1116, 758)

# 操作3：拖动后再点击两个点
A3_AFTER_1: Point = (1134, 790)

# gate 规则：当 right - left > 20 才执行第三步后续动作
GATE_DELTA = 11

# 节奏参数（毫秒）
GAP_MS = 200                 # 同一步内部点击间隔（cliclick 的 w:）
BETWEEN_ACTIONS_MS = 100    # 三个操作之间间隔（Python sleep）
BETWEEN_ROUNDS_MS = 100     # 一轮结束后间隔

# OCR 重试
OCR_MAX_ATTEMPTS = 10
OCR_RETRY_SLEEP_MS = 200

# Vision OCR 预处理（你验证成功那套）
OCR_SCALE = 10
OCR_CONTRAST = 1.6
OCR_SHARPNESS = 1.2
OCR_INVERT = False
# =========================


import time
import subprocess
import re
import io
from typing import Optional, List, Tuple as PyTuple
import threading
from pynput import keyboard

from PIL import ImageGrab, ImageOps, ImageEnhance, Image

# macOS Vision
import Vision
import Quartz
import Foundation


NUM_PATTERN = re.compile(r"\d+")
RATIO_PATTERN = re.compile(r"(\d{1,3})\s*/\s*(\d{1,3})")


# ------------------ cliclick helpers ------------------

def run_cliclick(*ops: str) -> None:
    subprocess.run(["cliclick", *ops], check=True)

def c(p: Point) -> str:
    return f"c:{p[0]},{p[1]}"

def w(ms: int) -> str:
    return f"w:{ms}"

def drag(from_p: Point, to_p: Point) -> List[str]:
    return [
        f"dd:{from_p[0]},{from_p[1]}",
        f"w:{GAP_MS}",
        f"m:{to_p[0]},{to_p[1]}",
        f"w:{GAP_MS}",
        f"du:{to_p[0]},{to_p[1]}",
    ]

def slow_drag(from_p: Point, to_p: Point, steps: int = 16, hold_ms: int = 180, step_ms: int = 45) -> List[str]:
    """
    慢速拖拽：按住 -> 分段移动 -> 松开
    steps 越大越慢；step_ms 越大越慢；hold_ms 是按住后等待再开始拖
    """
    fx, fy = from_p
    tx, ty = to_p

    ops: List[str] = []
    ops.append(f"dd:{fx},{fy}")
    ops.append(f"w:{hold_ms}")

    for i in range(1, steps + 1):
        x = int(fx + (tx - fx) * i / steps)
        y = int(fy + (ty - fy) * i / steps)
        ops.append(f"m:{x},{y}")
        ops.append(f"w:{step_ms}")

    ops.append(f"du:{tx},{ty}")
    return ops

def add_crew(num):
    for _ in range(num):
        run_cliclick(c(ADD_BTN), w(1))



# ------------------ Vision OCR ------------------

def grab_full():
    try:
        return ImageGrab.grab(all_screens=ALL_SCREENS)
    except TypeError:
        return ImageGrab.grab()

def preprocess_for_vision(img: Image.Image) -> Image.Image:
    img = ImageOps.grayscale(img)
    try:
        resample = Image.Resampling.LANCZOS
    except Exception:
        resample = Image.LANCZOS

    img = img.resize((img.size[0] * OCR_SCALE, img.size[1] * OCR_SCALE), resample=resample)
    img = ImageEnhance.Contrast(img).enhance(OCR_CONTRAST)
    img = ImageEnhance.Sharpness(img).enhance(OCR_SHARPNESS)

    if OCR_INVERT:
        img = ImageOps.invert(img)

    return img

def vision_digits_only(pil_img: Image.Image) -> str:
    parts = vision_ocr_parts(pil_img)
    text = " ".join(parts)
    nums = NUM_PATTERN.findall(text)
    return "".join(nums)  # 把所有数字拼起来

def fix_6_9_by_ink(img: Image.Image, digit: int) -> int:
    if digit not in (6, 9):
        return digit

    g = img.convert("L")
    w, h = g.size
    if w == 0 or h == 0:
        return digit

    # 统计暗像素（墨迹）——阈值可微调 140~180
    thresh = 160
    px = g.load()
    top_black = 0
    bot_black = 0
    for y in range(h):
        for x in range(w):
            if px[x, y] < thresh:
                if y < h // 2:
                    top_black += 1
                else:
                    bot_black += 1

    # bot 明显更黑：更像 6；top 明显更黑：更像 9
    if digit == 9 and bot_black > top_black * 1.15:
        return 6
    if digit == 6 and top_black > bot_black * 1.15:
        return 9
    return digit


def vision_ocr_parts(pil_img: Image.Image) -> List[str]:
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    raw = buf.getvalue()

    data = Foundation.NSData.dataWithBytes_length_(raw, len(raw))
    src = Quartz.CGImageSourceCreateWithData(data, None)
    cg_img = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)

    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)

    orientation = Quartz.kCGImagePropertyOrientationUp
    opts = Foundation.NSDictionary.dictionaryWithObject_forKey_(
        orientation, "VNImageOptionCGImagePropertyOrientation"
    )
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg_img, opts)

    ok, _ = handler.performRequests_error_([req], None)
    if not ok:
        return []

    results = list(req.results() or [])

    def x_of(obs):
        bb = obs.boundingBox()
        return float(bb.origin.x)

    results.sort(key=x_of)

    parts = []
    for obs in results:
        top = obs.topCandidates_(1)
        if top and len(top) > 0:
            parts.append(str(top[0].string()))
    return parts


def vision_ocr_text(pil_img: Image.Image) -> str:
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    raw = buf.getvalue()

    data = Foundation.NSData.dataWithBytes_length_(raw, len(raw))
    src = Quartz.CGImageSourceCreateWithData(data, None)
    cg_img = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)

    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)

    # 强制方向 Up（可以保留，但关键是下面的 bbox 排序）
    orientation = Quartz.kCGImagePropertyOrientationUp
    opts = Foundation.NSDictionary.dictionaryWithObject_forKey_(
        orientation, "VNImageOptionCGImagePropertyOrientation"
    )
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg_img, opts)

    ok, _ = handler.performRequests_error_([req], None)
    if not ok:
        return ""

    results = list(req.results() or [])

    # ⭐ 关键：按每个识别块的 boundingBox 的 x 坐标从左到右排序
    # boundingBox 是归一化坐标（0~1），原点在左下
    def x_of(obs):
        bb = obs.boundingBox()
        return float(bb.origin.x)

    results.sort(key=x_of)

    parts = []
    for obs in results:
        top = obs.topCandidates_(1)
        if top and len(top) > 0:
            parts.append(str(top[0].string()))

    return " ".join(parts)


def ocr_read_left_right(TL, BR) -> Optional[PyTuple[int, int]]:
    full = grab_full()

    (x1, y1), (x2, y2) = TL, BR
    left, right = sorted([x1, x2])
    top, bottom = sorted([y1, y2])

    bbox = (left * COORD_SCALE, top * COORD_SCALE,
            right * COORD_SCALE, bottom * COORD_SCALE)

    roi = full.crop(bbox)
    proc = preprocess_for_vision(roi)

    text = vision_ocr_text(proc)
    print("[Vision OCR]", repr(text))

    m = RATIO_PATTERN.search(text)
    if m:
        return int(m.group(1)), int(m.group(2))

    nums = [int(x) for x in NUM_PATTERN.findall(text)]
    if len(nums) >= 2:
        return nums[0], nums[1]
    if len(nums) == 1:
        return 0, nums[0]
    return None

def find_separator_x(img: Image.Image) -> int:
    """
    在 ROI 的“中间区域”寻找最干净的一列，作为左右分割线
    防止被 0/8/9 的内部空洞误导
    """
    g = img.convert("L")
    w, h = g.size
    px = g.load()

    thresh = 160  # 暗像素阈值

    # ⭐ 关键：只在中间 30%~70% 搜索
    x_start = int(w * 0.30)
    x_end   = int(w * 0.70)

    best_x = None
    best_cnt = None

    for x in range(x_start, x_end):
        cnt = 0
        for y in range(h):
            if px[x, y] < thresh:
                cnt += 1

        if best_cnt is None or cnt < best_cnt:
            best_cnt = cnt
            best_x = x

    return best_x if best_x is not None else w // 2




# ------------------ actions ------------------

def checkDone(TL, BR):
    for _ in range(OCR_MAX_ATTEMPTS):
        last = ocr_read_left_right(TL, BR)
        if last:
            l, r = last
            if l == 0 or r == 0:
                print("LIST CLEAR!!!")
                return False
            return True
        time.sleep(OCR_RETRY_SLEEP_MS / 1000)


def departure(skip):
    if skip:
        print("SKIP DEPARTURE")
        return 0
    print("CHECK DEPARTURE...")
    global STOP
    run_cliclick(c(SELECT_3), w(GAP_MS))
    while checkDone(OCR_3_TL, OCR_3_BR):
        print("DEPARTURE...")
        run_cliclick(c(START_POINT), w(GAP_MS), c(CONFIRM), w(GAP_MS), c(CAILM), w(GAP_MS))
        if STOP:
            print("Stopped.")
            break

def approach(skip):
    if skip:
        print("SKIP APPROACH")
        return 0
    print("CHECK APPROACH")
    global STOP
    run_cliclick(c(SELECT_1),w(GAP_MS))
    while checkDone(OCR_1_TL, OCR_1_BR):
        print("APPROACH...")
        run_cliclick(c(START_POINT), w(GAP_MS),
            c(CONFIRM), w(GAP_MS),
            c(A2_P2), w(GAP_MS),
            c(CONFIRM), w(1500),
            c(CONFIRM), w(GAP_MS))
        if STOP:
            print("Stopped.")
            break

def handling():
    print("CHECK HANDLING...")
    global STOP
    run_cliclick(c(SELECT_2),w(GAP_MS))
    while checkDone(OCR_2_TL, OCR_2_BR):
        print("HANDLING...")
        if STOP:
            print("Stopped.")
            break
        last = None
        passed = False
        last = ocr_read_left_right(CREW_TL, CREW_BR)
        if last:
            l, r = last
            if (r - l) > GATE_DELTA:
                passed = True
        if not passed:
            print("[action3] gate not passed:", last)
            return

        run_cliclick(c(START_POINT), w(GAP_MS), c(CONFIRM), w(1000), c(CAILM), w(1500), c(CONFIRM), w(GAP_MS))
        add_crew(20)
        ops = []
        # ops += slow_drag(SLIDER_FROM, SLIDER_TO, steps=16, hold_ms=180, step_ms=45)
        ops += [c(A3_AFTER_1), w(GAP_MS), c(CONFIRM)]
        run_cliclick(*ops)
        time.sleep(5)


STOP = False
def start_global_stop_by_esc():
    """
    全局停止：按 Esc => STOP=True
    """
    def worker():
        global STOP

        def on_press(key):
            global STOP
            if STOP:
                return False
            if key == keyboard.Key.esc:
                STOP = True
                print("\n[GLOBAL STOP] Esc detected. Stopping...")
                return False

        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()

    threading.Thread(target=worker, daemon=True).start()

def checkSkip():
    for _ in range(OCR_MAX_ATTEMPTS):
        last = ocr_read_left_right(OCR_1_TL, OCR_1_BR)
        next = ocr_read_left_right(OCR_3_TL, OCR_3_BR)
        if last and next:
            l, r = last
            cl, cr = next
            if r < cr + 10:
                return False
            return True
# ------------------ loop ------------------

def main():
    global STOP
    print("Automation running... Press ESC to stop.")
    start_global_stop_by_esc()

    run_cliclick(c(TAP_WINDOW))
    try:
        while not STOP:
            # check = checkSkip()
            departure(False)  # check
            if STOP:
                print("Stopped.")
                break
            time.sleep(BETWEEN_ACTIONS_MS / 1000)

            approach(False)   # not check
            if STOP:
                print("Stopped.")
                break
            time.sleep(BETWEEN_ACTIONS_MS / 1000)

            handling()
            if STOP:
                print("Stopped.")
                break
            time.sleep(BETWEEN_ACTIONS_MS / 1000)

    except KeyboardInterrupt:
        print("Stopped.")

if __name__ == "__main__":
    main()

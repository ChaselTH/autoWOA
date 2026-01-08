#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
把你这份“截图准确”的脚本改成用 macOS Vision OCR（替代 pytesseract）。

依赖：
  pip install pyobjc

说明：
- 截图/裁剪 bbox 逻辑完全保持不变（你说这是准确的）
- OCR 改用 Vision（更适合 UI 字体/抗锯齿）
- 先尝试识别 xxx/xxx；失败就退化为“只抓数字”，并按规则返回 (left,right)
- 仍会输出 roi_raw.png / roi_proc.png 方便调参
"""

from typing import Tuple, Optional, List
import re
import io

from PIL import ImageGrab, ImageOps, ImageEnhance, ImageFilter, Image

# Vision (macOS)
import Vision
import Quartz
import Foundation

Point = Tuple[int, int]

# ====== 你填：用 cliclick p 测到的 ROI 左上/右下（逻辑坐标 points）======
ROI_TL: Point = (1403,678)
ROI_BR: Point = (1430,688)

# 先试 2；如果不对再改 1（你说截图对，那就保持这个不动）
SCALE = 2

# 多显示器时：Pillow 新版本可用 all_screens=True；旧版本没有这个参数就会报错
ALL_SCREENS = True
# ===========================================================

# ====== 预处理参数（只影响识别，不影响截图范围）======
# Vision 通常不需要很狠的二值化，这里用“温和增强”，更贴合 UI 字体
OCR_SCALE = 10        # 放大（建议 6~12）
OCR_CONTRAST = 1.2   # 1.2~3
OCR_SHARPNESS = 1.6 # 1~3
OCR_INVERT = False    # 白字黑底可试 True（看 roi_proc.png 哪个更清晰）
# ===================================================

RATIO_PATTERN = re.compile(r"(\d{1,3})\s*/\s*(\d{1,3})")
NUM_PATTERN = re.compile(r"\d+")


def grab_full():
    try:
        return ImageGrab.grab(all_screens=ALL_SCREENS)
    except TypeError:
        return ImageGrab.grab()


def preprocess_for_vision(img: Image.Image) -> Image.Image:
    """
    温和预处理（适合 Vision）：
    灰度 -> 放大 -> 对比度 -> 锐化
    注意：不做强二值化（避免把 / 和细笔画吃掉）
    """
    img = ImageOps.grayscale(img)

    # 放大（LANCZOS 更清晰）
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


def vision_ocr_text(pil_img: Image.Image) -> str:
    """
    用 macOS Vision 识别文本，返回拼接后的字符串
    """
    # Pillow -> PNG bytes
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    raw = buf.getvalue()

    data = Foundation.NSData.dataWithBytes_length_(raw, len(raw))
    src = Quartz.CGImageSourceCreateWithData(data, None)
    cg_img = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)

    # VNRecognizeTextRequest
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)

    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg_img, None)
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        # 失败就返回空字符串
        return ""

    results = req.results() or []
    texts: List[str] = []
    for r in results:
        top = r.topCandidates_(1)
        if top and len(top) > 0:
            texts.append(str(top[0].string()))
    return " ".join(texts)


def parse_ratio_or_digits(text: str) -> Optional[Tuple[int, int]]:
    """
    先尝试解析 xxx/xxx；失败再提取所有数字：
    - >=2 个数字：返回 (nums[0], nums[1])
    - 只有 1 个：返回 (0, nums[0])
    """
    m = RATIO_PATTERN.search(text)
    if m:
        return int(m.group(1)), int(m.group(2))

    nums = [int(x) for x in NUM_PATTERN.findall(text)]
    if len(nums) >= 2:
        return nums[0], nums[1]
    if len(nums) == 1:
        return 0, nums[0]
    return None


def main():
    # ======= 这段截图逻辑保持和你的一模一样 =======
    full = grab_full()
    full.save("full.png")
    print("full size(px):", full.size)

    (x1, y1), (x2, y2) = ROI_TL, ROI_BR
    left, right = sorted([x1, x2])
    top, bottom = sorted([y1, y2])

    bbox = (left * SCALE, top * SCALE, right * SCALE, bottom * SCALE)
    print("bbox(px):", bbox)

    roi = full.crop(bbox)
    roi.save("roi_raw.png")
    print("Saved: full.png, roi_raw.png")
    # ===============================================

    proc = preprocess_for_vision(roi)
    proc.save("roi_proc.png")

    text = vision_ocr_text(proc)
    print("Vision OCR raw:", repr(text))

    res = parse_ratio_or_digits(text)
    print("Parsed (left,right):", res)
    print("Saved: roi_proc.png (for debugging)")


if __name__ == "__main__":
    main()

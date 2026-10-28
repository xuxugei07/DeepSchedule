# -*- coding: utf-8 -*-
"""从皮肤包里取立绘，裁边缩放到桌宠用的尺寸（原图已带透明通道）。"""
import numpy as np
from PIL import Image

SKIN_ROOT = (r"C:\Users\dwxzs\.dsh\profiles\desktop\node_modules\@smalltailqwq")
OUT_DIR = r"D:\ai\bff\whale-pet"
SIZE = 208          # 260 * 0.8

ASSETS = [
    # (源文件, 输出名, 是否要抠白底)
    (rf"{SKIN_ROOT}\dsh-client-ui-skin-maid-atelier\assets\runtime"
     r"\06eaf23edd8d5efcf8dfd2ff573307d92ad4422f4a5c022064e9659d34258b8d.png",
     "whale.png", False),
    (rf"{SKIN_ROOT}\dsh-client-ui-skin-orca-link\assets\runtime"
     r"\1d63b2ee2d7e70678527d58d65ae382d41b2af878886e97f86002c57e313e416.png",
     "orca.png", True),
]


def cut_white(img):
    """把纯白底抠成透明：黑形状照旧，彩色的方块保留。"""
    rgb = np.array(img.convert("RGB")).astype(np.int16)
    mn = rgb.min(axis=2)
    mx = rgb.max(axis=2)
    alpha = (255 - mn).clip(0, 255).astype(np.uint8)
    out = rgb.copy()
    gray = (mx - mn) < 12          # 灰阶像素（含抗锯齿边）压成纯黑
    out[gray] = 0
    return Image.fromarray(np.dstack([out, alpha]).astype(np.uint8), "RGBA")


def main():
    for src, name, white_bg in ASSETS:
        img = Image.open(src).convert("RGBA")
        if white_bg:
            img = cut_white(img)
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        scale = SIZE / max(img.size)
        img = img.resize((max(1, round(img.width * scale)),
                          max(1, round(img.height * scale))), Image.LANCZOS)
        out = rf"{OUT_DIR}\{name}"
        img.save(out)
        print("saved", out, img.size)


if __name__ == "__main__":
    main()

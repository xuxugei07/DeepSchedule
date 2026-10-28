# -*- coding: utf-8 -*-
"""从 QQ20261028-073843.mp4 里量出玩偶一个周期的纵向运动，生成 SHAKE_CURVE。

用法：python analyze_motion.py <视频路径>
原理：玩偶是暖色（比天空红），按颜色抠出来，逐帧取行投影的外接高度；
     自相关找周期，再把一个周期归一化到 0..1 输出。
"""
import sys

import av
import numpy as np

SRC = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\dwxzs\Downloads\QQ20261028-073843.mp4"


def main():
    container = av.open(SRC)
    vs = container.streams.video[0]
    fps = float(vs.average_rate)
    heights = []
    for frame in container.decode(vs):
        rgb = np.array(frame.to_image().convert("RGB"), dtype=np.int16)
        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        warm = (r - b > 18) & (r > 85) & (g > 55)
        warm[220:, :] = False                       # 底部那排小人不算
        rows = np.where(warm.sum(axis=1) > 12)[0]
        heights.append(int(rows[-1] - rows[0] + 1) if rows.size else 0)

    h = np.array(heights, dtype=float)
    x = h - h.mean()
    ac = np.correlate(x, x, mode="full")[len(x) - 1:]
    ac /= ac[0]
    period = max(range(6, 120), key=lambda k: ac[k])

    cycle = h[1:1 + period]
    norm = (cycle - cycle.min()) / (cycle.max() - cycle.min())
    print(f"fps={fps:.2f}  period={period} 帧 ({period / fps:.3f}s)")
    print(f"高度 {cycle.min():.0f}..{cycle.max():.0f} px  (比例 {cycle.max() / cycle.min():.2f}x)")
    print("SHAKE_CURVE = [" + ", ".join(f"{v:.3f}" for v in norm) + "]")


if __name__ == "__main__":
    main()

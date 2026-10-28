# -*- coding: utf-8 -*-
"""把 mp4 里的音轨抽成循环用的 wav（22.05kHz 单声道），一次生成，之后 winsound 直接循环。"""
import wave

import av
import numpy as np

SRC = r"C:\Users\dwxzs\Downloads\41667726578-1-192.mp4"
DST = r"D:\ai\bff\whale-pet\sounds\rage.wav"
RATE = 22050


def main():
    container = av.open(SRC)
    stream = container.streams.audio[0]
    resampler = av.AudioResampler(format="s16", layout="mono", rate=RATE)
    chunks = []
    for frame in container.decode(stream):
        for out in resampler.resample(frame):
            chunks.append(out.to_ndarray().reshape(-1))
    for out in resampler.resample(None):
        chunks.append(out.to_ndarray().reshape(-1))

    data = np.concatenate(chunks).astype(np.int16)
    with wave.open(DST, "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(RATE)
        fh.writeframes(data.tobytes())
    seconds = len(data) / RATE
    print(f"saved {DST}  {seconds:.1f}s  {len(data) * 2 / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()

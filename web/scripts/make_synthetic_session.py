#!/usr/bin/env python3
"""Gera uma sessão SINTÉTICA com amostras válidas — para testar o heatmap.

As 11 sessões reais têm 0 amostras válidas (eye tracker descalibrado), então não exercitam
o heatmap. Esta gera frames pequenos + um caminho de olhar (uv) varrendo a tela, com algumas
amostras inválidas no meio para testar o filtro.

Exemplo:
  py -3.12 scripts/make_synthetic_session.py ./synthetic
  py -3.12 scripts/replay_session.py ./synthetic
"""
import argparse
import json
import math
import os

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser(description="Gera uma sessão sintética (frames + gaze.json com uv válido).")
    ap.add_argument("out_dir", help="pasta de saída (será criada)")
    ap.add_argument("--frames", type=int, default=30, help="número de frames de vídeo")
    ap.add_argument("--fps", type=float, default=10.0, help="videoFps")
    ap.add_argument("--w", type=int, default=256)
    ap.add_argument("--h", type=int, default=256)
    ap.add_argument("--sample-hz", type=float, default=30.0, help="taxa das amostras de gaze")
    args = ap.parse_args()

    frames_dir = os.path.join(args.out_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    dt = 1.0 / args.fps
    frames = []
    for i in range(1, args.frames + 1):
        t = i * dt
        img = np.zeros((args.h, args.w, 3), dtype=np.uint8)
        img[:, :, 0] = np.linspace(30, 200, args.w, dtype=np.uint8)[None, :]   # B em x
        img[:, :, 1] = np.linspace(60, 160, args.h, dtype=np.uint8)[:, None]   # G em y
        for gx in range(0, args.w, 32):
            img[:, gx] = (80, 80, 80)
        for gy in range(0, args.h, 32):
            img[gy, :] = (80, 80, 80)
        cv2.imwrite(os.path.join(frames_dir, f"{i:06d}.jpg"), img)
        frames.append({"idx": i, "t": round(t, 6), "file": f"frames/{i:06d}.jpg"})

    total_t = args.frames * dt
    n = max(1, int(total_t * args.sample_hz))
    samples = []
    for k in range(n):
        t = k / args.sample_hz
        if k % 11 == 0:  # ~9% inválidas, como piscadas
            samples.append({"t": round(t, 6), "valid": False, "world": [0, 0, 0],
                            "uv": [-1, -1], "confidence": 0.0})
            continue
        u = 0.5 + 0.3 * math.sin(2 * math.pi * 0.5 * t)        # caminho Lissajous em [0.2, 0.8]
        v = 0.5 + 0.3 * math.sin(2 * math.pi * 0.8 * t + 1.0)
        samples.append({"t": round(t, 6), "valid": True, "world": [u * 100, v * 100, 50.0],
                        "uv": [round(u, 4), round(v, 4)], "confidence": 0.9})

    meta = {"captureFovDeg": 82, "frameWidth": args.w, "frameHeight": args.h,
            "videoFps": args.fps, "uvOrigin": "top-left"}
    with open(os.path.join(args.out_dir, "gaze.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "frames": frames, "samples": samples}, f, indent=2)

    valid = sum(1 for s in samples if s["valid"])
    print(f"sessão sintética em {args.out_dir}: {len(frames)} frames, {len(samples)} samples ({valid} válidas)")


if __name__ == "__main__":
    main()

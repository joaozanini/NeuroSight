#!/usr/bin/env python3
"""
heatmap_overlay.py
==================

Gera um heatmap (ou um vídeo de validação) sobre os frames gravados pelo app de
eye tracking, usando o gaze.json exportado.

A pasta da sessão (puxada do Quest via `adb pull`) deve conter:

    <session_dir>/
        gaze.json
        frames/000001.jpg, 000002.jpg, ...

Modos:
  --mode heatmap   (padrão) acumula o olhar numa janela temporal, colore e sobrepõe
                   ao vídeo -> MP4.
  --mode validate  desenha o ponto 2D (u,v) instantâneo sobre cada frame. O marcador
                   verde deve cair EXATAMENTE em cima da bolinha vermelha (validação 2D<->3D).

Exemplos:
  python tools/heatmap_overlay.py ./session
  python tools/heatmap_overlay.py ./session --mode validate
  python tools/heatmap_overlay.py ./session --mode heatmap --window 2.0 --sigma 40 --out heat.mp4
  python tools/heatmap_overlay.py ./session --static-heatmap aggregate.png

Requisitos: pip install -r tools/requirements.txt  (opencv-python, numpy)
"""

import argparse
import json
import os
import sys

import numpy as np
import cv2


# --------------------------------------------------------------------------- #
# Carregamento
# --------------------------------------------------------------------------- #
def load_session(session_dir):
    json_path = os.path.join(session_dir, "gaze.json")
    if not os.path.isfile(json_path):
        sys.exit(f"gaze.json não encontrado em {session_dir}")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    meta = data.get("meta", {})
    frames = data.get("frames", [])
    samples = data.get("samples", [])
    frames.sort(key=lambda fr: fr.get("t", 0.0))
    samples.sort(key=lambda s: s.get("t", 0.0))
    return meta, frames, samples


def frame_dims(meta):
    return int(meta.get("frameWidth", 1024)), int(meta.get("frameHeight", 1024))


def out_fps(args, meta):
    if args.fps and args.fps > 0:
        return float(args.fps)
    return float(meta.get("videoFps", 15)) or 15.0


def read_frame(session_dir, fr, w, h):
    img = cv2.imread(os.path.join(session_dir, fr["file"]))
    if img is None:
        return None
    if img.shape[1] != w or img.shape[0] != h:
        img = cv2.resize(img, (w, h))
    return img


# --------------------------------------------------------------------------- #
# Heatmap
# --------------------------------------------------------------------------- #
def samples_in_window(samples, t0, t1):
    out = []
    for s in samples:
        if not s.get("valid"):
            continue
        t = s.get("t", 0.0)
        if t0 <= t <= t1:
            uv = s.get("uv", [-1.0, -1.0])
            if 0.0 <= uv[0] <= 1.0 and 0.0 <= uv[1] <= 1.0:
                out.append(s)
    return out


def gaussian_splat(acc, cx, cy, sigma, weight=1.0):
    """Soma uma gaussiana centrada em (cx, cy) ao acumulador."""
    h, w = acc.shape
    r = max(1, int(3 * sigma))
    x0, x1 = max(0, cx - r), min(w, cx + r + 1)
    y0, y1 = max(0, cy - r), min(h, cy + r + 1)
    if x0 >= x1 or y0 >= y1:
        return
    xs = np.arange(x0, x1) - cx
    ys = np.arange(y0, y1) - cy
    gx = np.exp(-(xs ** 2) / (2.0 * sigma ** 2))
    gy = np.exp(-(ys ** 2) / (2.0 * sigma ** 2))
    acc[y0:y1, x0:x1] += weight * np.outer(gy, gx)


def colorize_over(acc, frame, alpha):
    """Colore o acumulador (JET) e mescla sobre o frame onde há sinal."""
    peak = acc.max()
    if peak <= 1e-8:
        return frame
    norm = np.clip(acc / peak, 0.0, 1.0)
    heat = cv2.applyColorMap((norm * 255).astype(np.uint8), cv2.COLORMAP_JET)
    mask = (norm > 0.02)[..., None].astype(np.float32) * float(alpha)
    out = frame.astype(np.float32) * (1.0 - mask) + heat.astype(np.float32) * mask
    return out.astype(np.uint8)


def run_heatmap(session_dir, meta, frames, samples, args):
    w, h = frame_dims(meta)
    fps = out_fps(args, meta)
    out_path = args.out or os.path.join(session_dir, "heatmap.mp4")
    writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        sys.exit(f"não consegui abrir o VideoWriter em {out_path}")

    written = 0
    for fr in frames:
        frame = read_frame(session_dir, fr, w, h)
        if frame is None:
            continue
        t = fr.get("t", 0.0)
        acc = np.zeros((h, w), dtype=np.float32)
        for s in samples_in_window(samples, t - args.window, t):
            uv = s["uv"]
            cx, cy = int(uv[0] * w), int(uv[1] * h)
            age = t - s["t"]
            weight = max(0.0, 1.0 - age / max(args.window, 1e-6))  # decay linear na janela
            gaussian_splat(acc, cx, cy, args.sigma, weight)
        writer.write(colorize_over(acc, frame, args.alpha))
        written += 1

    writer.release()
    print(f"[heatmap] {written} frames -> {out_path}")


def run_validate(session_dir, meta, frames, samples, args):
    w, h = frame_dims(meta)
    fps = out_fps(args, meta)
    out_path = args.out or os.path.join(session_dir, "validate.mp4")
    writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        sys.exit(f"não consegui abrir o VideoWriter em {out_path}")

    valid = [s for s in samples if s.get("valid")]
    times = np.array([s["t"] for s in valid]) if valid else np.array([])

    def nearest(t):
        if times.size == 0:
            return None
        return valid[int(np.argmin(np.abs(times - t)))]

    written = 0
    for fr in frames:
        frame = read_frame(session_dir, fr, w, h)
        if frame is None:
            continue
        s = nearest(fr.get("t", 0.0))
        if s is not None:
            uv = s["uv"]
            if 0.0 <= uv[0] <= 1.0 and 0.0 <= uv[1] <= 1.0:
                cx, cy = int(uv[0] * w), int(uv[1] * h)
                cv2.circle(frame, (cx, cy), 14, (0, 255, 0), 2)
                cv2.drawMarker(frame, (cx, cy), (0, 255, 0), cv2.MARKER_CROSS, 28, 2)
        writer.write(frame)
        written += 1

    writer.release()
    print(f"[validate] {written} frames -> {out_path}")
    print("           o marcador verde deve coincidir com a bolinha vermelha.")


def run_static(session_dir, meta, frames, samples, args):
    w, h = frame_dims(meta)
    acc = np.zeros((h, w), dtype=np.float32)
    for s in samples:
        if not s.get("valid"):
            continue
        uv = s.get("uv", [-1.0, -1.0])
        if 0.0 <= uv[0] <= 1.0 and 0.0 <= uv[1] <= 1.0:
            gaussian_splat(acc, int(uv[0] * w), int(uv[1] * h), args.sigma, 1.0)

    bg = None
    if frames:
        bg = read_frame(session_dir, frames[len(frames) // 2], w, h)
    if bg is None:
        bg = np.zeros((h, w, 3), dtype=np.uint8)

    cv2.imwrite(args.static_heatmap, colorize_over(acc, bg, args.alpha))
    print(f"[static] -> {args.static_heatmap}")


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Heatmap/validação de eye tracking sobre o vídeo gravado in-app.")
    ap.add_argument("session_dir", help="pasta da sessão (contém gaze.json e frames/)")
    ap.add_argument("--mode", choices=["heatmap", "validate"], default="heatmap")
    ap.add_argument("--window", type=float, default=1.5, help="janela temporal do heatmap (s)")
    ap.add_argument("--sigma", type=float, default=35.0, help="raio da gaussiana (px)")
    ap.add_argument("--alpha", type=float, default=0.5, help="opacidade do heatmap (0..1)")
    ap.add_argument("--fps", type=float, default=0.0, help="fps de saída (0 = usa o videoFps do meta)")
    ap.add_argument("--out", default=None, help="caminho do MP4 de saída")
    ap.add_argument("--static-heatmap", dest="static_heatmap", default=None,
                    help="também salva um PNG com o heatmap agregado da sessão inteira")
    args = ap.parse_args()

    if not os.path.isdir(args.session_dir):
        sys.exit(f"pasta não encontrada: {args.session_dir}")

    meta, frames, samples = load_session(args.session_dir)
    n_valid = sum(1 for s in samples if s.get("valid"))
    print(f"meta={meta}")
    print(f"frames={len(frames)}  samples={len(samples)} (válidas={n_valid})")
    if not frames:
        print("AVISO: nenhum frame na sessão — verifique se VideoFps > 0 e se a captura rodou.")

    if args.mode == "heatmap":
        run_heatmap(args.session_dir, meta, frames, samples, args)
    else:
        run_validate(args.session_dir, meta, frames, samples, args)

    if args.static_heatmap:
        run_static(args.session_dir, meta, frames, samples, args)


if __name__ == "__main__":
    main()

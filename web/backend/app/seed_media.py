"""Arquivos de exemplo do `python -m app.seed --demo`, gerados na hora (nada de mídia no repositório):
imagens e vídeos em cores chapadas, no estilo das ilustrações dos protótipos (W09, W13), e o PDF
mínimo usado como termo de consentimento.

As imagens têm 1600 × 1000 (16:10, como as miniaturas); os vídeos, 640 × 400 a 24 fps, sem áudio.
"""
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from .services.media import ffmpeg_exe

IMAGE_SIZE = (1600, 1000)
VIDEO_SIZE = (640, 400)
VIDEO_FPS = 24


def _bgr(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return b, g, r


def _canvas(size: tuple[int, int], color: str) -> np.ndarray:
    width, height = size
    img = np.empty((height, width, 3), np.uint8)
    img[:] = _bgr(color)
    return img


def _poly(img: np.ndarray, points, color: str) -> None:
    cv2.fillPoly(img, [np.array(points, np.int32)], _bgr(color), lineType=cv2.LINE_AA)


def _scaled(points, sx: float, sy: float):
    return [(round(x * sx), round(y * sy)) for x, y in points]


# ---- Imagens ----------------------------------------------------------------------------------

def mountains(size=IMAGE_SIZE) -> np.ndarray:
    w, h = size
    sx, sy = w / 320, h / 200
    img = _canvas(size, "#d4d9dd")
    cv2.circle(img, (round(237 * sx), round(74 * sy)), round(19 * sx), _bgr("#e9e4da"), -1, cv2.LINE_AA)
    _poly(img, _scaled([(0, 160), (80, 90), (140, 128), (205, 63), (320, 135), (320, 200), (0, 200)], sx, sy), "#9aa5ac")
    _poly(img, _scaled([(0, 175), (95, 117), (175, 178), (255, 128), (320, 165), (320, 200), (0, 200)], sx, sy), "#5e6a72")
    return img


def lake(size=IMAGE_SIZE) -> np.ndarray:
    w, h = size
    img = _canvas(size, "#d5dbde")
    _poly(img, [(0, int(h * .62)), (int(w * .3), int(h * .5)), (int(w * .7), int(h * .55)), (w, int(h * .5)), (w, h), (0, h)], "#8f9c96")
    for x, tree_w, tree_h in ((.1, .07, .22), (.17, .06, .28), (.24, .05, .18), (.78, .06, .26), (.86, .05, .2)):
        cx, base = int(w * x), int(h * .64)
        _poly(img, [(cx - int(w * tree_w / 2), base), (cx, base - int(h * tree_h)), (cx + int(w * tree_w / 2), base)], "#4b5e55")
    cv2.rectangle(img, (0, int(h * .64)), (w, h), _bgr("#6f8a99"), -1)
    for x0, x1, y in ((.08, .25, .74), (.45, .7, .8), (.3, .5, .9), (.75, .92, .7)):
        cv2.line(img, (int(w * x0), int(h * y)), (int(w * x1), int(h * y)), _bgr("#a9bcc6"), max(2, h // 160), cv2.LINE_AA)
    return img


def fruits(size=IMAGE_SIZE) -> np.ndarray:
    w, h = size
    img = _canvas(size, "#ddd8d0")
    cv2.rectangle(img, (0, int(h * .68)), (w, h), _bgr("#a89a88"), -1)
    cv2.circle(img, (int(w * .32), int(h * .62)), int(h * .15), _bgr("#a5524a"), -1, cv2.LINE_AA)
    cv2.line(img, (int(w * .32), int(h * .47)), (int(w * .34), int(h * .4)), _bgr("#5b4636"), max(3, h // 120), cv2.LINE_AA)
    cv2.circle(img, (int(w * .52), int(h * .64)), int(h * .13), _bgr("#c9934a"), -1, cv2.LINE_AA)
    cv2.ellipse(img, (int(w * .69), int(h * .6)), (int(h * .1), int(h * .16)), 0, 0, 360, _bgr("#9aa678"), -1, cv2.LINE_AA)
    return img


def face(expression: str, size=IMAGE_SIZE) -> np.ndarray:
    """Rosto neutro, alegre ou surpreso, como nas miniaturas da W13."""
    w, h = size
    cx = w // 2
    img = _canvas(size, "#cfd4d8")
    cv2.ellipse(img, (cx, h), (int(h * .42), int(h * .36)), 0, 180, 360, _bgr("#5f6b75"), -1, cv2.LINE_AA)
    cv2.rectangle(img, (cx - int(h * .06), int(h * .5)), (cx + int(h * .06), int(h * .68)), _bgr("#c9ae95"), -1)
    head = (cx, int(h * .38))
    radius = int(h * .2)
    cv2.circle(img, head, radius, _bgr("#d8bba0"), -1, cv2.LINE_AA)
    cv2.ellipse(img, (cx, head[1] - int(radius * .15)), (radius, int(radius * .92)), 0, 180, 360, _bgr("#4a3b33"), -1, cv2.LINE_AA)
    cv2.ellipse(img, head, (radius, int(radius * .35)), 0, 180, 360, _bgr("#d8bba0"), -1, cv2.LINE_AA)
    eye_y = head[1] + int(radius * .05)
    dx = int(radius * .38)
    eye = int(radius * (.12 if expression == "surprised" else .08))
    brow_y = eye_y - int(radius * (.31 if expression == "surprised" else .23))
    thick = max(3, h // 140)
    for side in (-1, 1):
        cv2.circle(img, (cx + side * dx, eye_y), eye, _bgr("#2f2723"), -1, cv2.LINE_AA)
        cv2.line(img, (cx + side * int(dx * .55), brow_y), (cx + side * int(dx * 1.45), brow_y), _bgr("#3a2f29"), thick, cv2.LINE_AA)
    mouth_y = head[1] + int(radius * .5)
    if expression == "happy":
        cv2.ellipse(img, (cx, mouth_y - int(radius * .1)), (int(radius * .32), int(radius * .2)), 0, 20, 160, _bgr("#8a4b43"), thick, cv2.LINE_AA)
    elif expression == "surprised":
        cv2.ellipse(img, (cx, mouth_y), (int(radius * .12), int(radius * .17)), 0, 0, 360, _bgr("#6d3a34"), -1, cv2.LINE_AA)
    else:
        cv2.line(img, (cx - int(radius * .22), mouth_y), (cx + int(radius * .22), mouth_y), _bgr("#8a4b43"), thick, cv2.LINE_AA)
    return img


# ---- Vídeos -----------------------------------------------------------------------------------

def beach_frame(t: float, size=VIDEO_SIZE) -> np.ndarray:
    w, h = size
    img = _canvas(size, "#d9d5ce")
    cv2.circle(img, (w // 2, int(h * .52)), int(h * .1), _bgr("#ebe2d0"), -1, cv2.LINE_AA)
    cv2.rectangle(img, (0, int(h * .52)), (w, h), _bgr("#6e8c99"), -1)
    for row, speed in ((.6, 40), (.68, 60), (.75, 30)):
        offset = (t * speed) % w
        for start in range(-w, w, 160):
            x = int(start + offset)
            cv2.line(img, (x, int(h * row)), (x + 70, int(h * row)), _bgr("#c3d2d8"), 2, cv2.LINE_AA)
    shore = [(x, int(h * .8 + math.sin(x / 70 + t * 1.6) * h * .025)) for x in range(0, w + 8, 8)]
    _poly(img, [*shore, (w, h), (0, h)], "#d8c9b0")
    return img


def forest_frame(t: float, size=VIDEO_SIZE) -> np.ndarray:
    w, h = size
    img = _canvas(size, "#d2d9dc")
    cv2.rectangle(img, (0, int(h * .75)), (w, h), _bgr("#6f7d63"), -1)
    for i, x in enumerate(range(20, w, 70)):
        sway = math.sin(t * 1.3 + i) * 8
        base = int(h * .78)
        top = int(h * (.18 + (i % 3) * .07))
        _poly(img, [(x - 34, base), (int(x + sway), top), (x + 34, base)], "#3f5a4d" if i % 2 else "#4e6a5c")
    return img


@dataclass(frozen=True)
class DemoImage:
    name: str
    filename: str
    tags: tuple[str, ...]
    draw: Callable[[], np.ndarray]
    description: str | None = None


@dataclass(frozen=True)
class DemoVideo:
    name: str
    filename: str
    tags: tuple[str, ...]
    seconds: float
    frame: Callable[[float], np.ndarray]


EXPRESSIONS = (("neutral", "Rosto neutro", "neutro"), ("happy", "Rosto alegre", "alegria"), ("surprised", "Rosto surpreso", "surpresa"))

IMAGES: list[DemoImage] = [
    DemoImage("Montanhas ao amanhecer", "montanhas-ao-amanhecer.jpg", ("paisagem", "natureza"), mountains,
              "Cordilheira com o sol nascendo atrás das montanhas."),
    DemoImage("Frutas sobre a mesa", "frutas-sobre-a-mesa.jpg", ("alimento",), fruits),
    DemoImage("Lago e floresta", "lago-e-floresta.png", ("paisagem", "natureza"), lake),
    *[
        DemoImage(f"{label} {i:02d}", f"rosto-{tag}-{i:02d}.jpg", ("rosto", tag),
                  lambda expression=expression: face(expression))
        for i in range(1, 13)
        for expression, label, tag in [EXPRESSIONS[(i - 1) % 3]]
    ],
]

VIDEOS: list[DemoVideo] = [
    DemoVideo("Ondas na praia", "ondas-na-praia.mp4", ("paisagem", "mar"), 45, beach_frame),
    DemoVideo("Floresta com vento", "floresta-com-vento.mp4", ("paisagem", "natureza"), 80, forest_frame),
]


def write_image(item: DemoImage, folder: Path) -> Path:
    path = folder / item.filename
    ext = path.suffix.lower()
    ok, buf = cv2.imencode(ext, item.draw(), [cv2.IMWRITE_JPEG_QUALITY, 90] if ext == ".jpg" else [])
    assert ok
    path.write_bytes(buf.tobytes())
    return path


def write_video(item: DemoVideo, folder: Path) -> Path:
    """H.264 pelo ffmpeg, recebendo os quadros crus pelo stdin."""
    path = folder / item.filename
    w, h = VIDEO_SIZE
    process = subprocess.Popen(
        [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
         "-s", f"{w}x{h}", "-r", str(VIDEO_FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)],
        stdin=subprocess.PIPE,
    )
    for n in range(round(item.seconds * VIDEO_FPS)):
        process.stdin.write(item.frame(n / VIDEO_FPS).tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError(f"ffmpeg falhou ao gerar {item.filename}")
    return path


def minimal_pdf(text: str) -> bytes:
    """PDF de uma página com uma linha de texto (só ASCII), válido para os leitores de PDF."""
    stream = f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    body = b"%PDF-1.4\n"
    offsets = []
    for number, obj in enumerate(objects, 1):
        offsets.append(len(body))
        body += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    body += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    body += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return body

"""Processamento dos arquivos de estímulo (decisão 7 do plano), com o OpenCV e o ffmpeg que vem no
imageio-ffmpeg, as duas dependências que a API já tinha.

- O formato vem do conteúdo (magic bytes), não da extensão: JPG, PNG ou MP4. Um vídeo do
  QuickTime (.mov, marca `qt`) é recusado mesmo renomeado para .mp4.
- Resolução e duração são lidas na hora do envio, o que também recusa arquivo corrompido.
- A miniatura (JPEG, cobrindo 640 × 400) alimenta os cartões da biblioteca.
- A versão para o óculos tem no máximo 2048 px no lado maior: a imagem é regravada no mesmo
  formato, já na orientação certa (o UE não lê a rotação do EXIF); o vídeo vira H.264 yuv420p com
  áudio AAC e faststart, ou só é remontado com faststart quando já está nesse formato.
"""
import hashlib
import logging
import os
import re
import subprocess
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)

JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
# Marca do QuickTime no box ftyp: é um .mov, mesmo que o nome diga .mp4.
QUICKTIME_BRANDS = {b"qt  "}

# Lado maior da versão para o óculos.
DEVICE_MAX_SIDE = 2048
THUMB_SIZE = (640, 400)
# Proteção contra imagens gigantes (decodificar 100 MP já ocupa 300 MB de memória).
MAX_IMAGE_PIXELS = 100_000_000

UNREADABLE_IMAGE = "não foi possível ler a imagem. Confira se o arquivo não está corrompido"
UNREADABLE_VIDEO = "não foi possível ler o vídeo. Confira se o arquivo é um MP4 válido"


class MediaError(Exception):
    """Arquivo recusado; a mensagem vai para a pessoa (em português, sem ponto final)."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class MediaInfo:
    width: int
    height: int
    duration: float | None = None
    has_audio: bool | None = None
    video_codec: str | None = None
    pix_fmt: str | None = None
    audio_codec: str | None = None
    rotation: int = 0


@dataclass
class DeviceVersion:
    format: str
    path: str
    width: int
    height: int
    size_bytes: int
    sha256: str


def detect_format(head: bytes) -> str | None:
    """jpg, png, mp4 ou None, pelos primeiros bytes do arquivo (16 bastam)."""
    if head.startswith(JPEG_MAGIC):
        return "jpg"
    if head.startswith(PNG_MAGIC):
        return "png"
    if head[4:8] == b"ftyp" and head[8:12] not in QUICKTIME_BRANDS:
        return "mp4"
    return None


def kind_of(fmt: str) -> str:
    return "video" if fmt == "mp4" else "image"


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---- Imagens ----------------------------------------------------------------------------------

_JPEG_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def _jpeg_header_size(f) -> tuple[int, int] | None:
    f.seek(2)
    while True:
        byte = f.read(1)
        while byte and byte != b"\xff":
            byte = f.read(1)
        while byte == b"\xff":  # bytes de preenchimento
            byte = f.read(1)
        if not byte:
            return None
        marker = byte[0]
        if marker == 0x01 or 0xD0 <= marker <= 0xD9:  # marcadores sem tamanho
            continue
        length = f.read(2)
        if len(length) < 2:
            return None
        if marker in _JPEG_SOF:
            data = f.read(5)
            if len(data) < 5:
                return None
            return int.from_bytes(data[3:5], "big"), int.from_bytes(data[1:3], "big")
        f.seek(int.from_bytes(length, "big") - 2, os.SEEK_CUR)


def image_header_size(path: str, fmt: str) -> tuple[int, int] | None:
    """Largura e altura gravadas no cabeçalho, sem decodificar a imagem."""
    with open(path, "rb") as f:
        if fmt == "png":
            head = f.read(24)
            if len(head) < 24 or head[12:16] != b"IHDR":
                return None
            return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
        return _jpeg_header_size(f)


def load_image(path: str, fmt: str) -> np.ndarray:
    """Imagem decodificada: BGR, ou BGRA num PNG com transparência. Um JPEG sai já girado pelo EXIF."""
    size = image_header_size(path, fmt)
    if size is None:
        raise MediaError(UNREADABLE_IMAGE)
    if size[0] * size[1] > MAX_IMAGE_PIXELS:
        raise MediaError(
            f"a imagem é grande demais ({size[0]} × {size[1]}). Use até {MAX_IMAGE_PIXELS // 1_000_000} megapixels", 413,
        )
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED if fmt == "png" else cv2.IMREAD_COLOR)
    if img is None or img.size == 0:
        raise MediaError(UNREADABLE_IMAGE)
    if img.dtype != np.uint8:  # PNG de 16 bits
        img = (img / 257).astype(np.uint8)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 2:  # cinza com transparência
        img = cv2.cvtColor(img[:, :, 0], cv2.COLOR_GRAY2BGR)
    return img


def _flatten(img: np.ndarray, background=(255, 255, 255)) -> np.ndarray:
    """BGRA -> BGR sobre um fundo liso (a miniatura é JPEG, sem transparência)."""
    if img.ndim == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3:4].astype(np.float32) / 255.0
        base = np.empty_like(img[:, :, :3])
        base[:] = background
        return (img[:, :, :3] * alpha + base * (1 - alpha)).astype(np.uint8)
    return img


def _fit(img: np.ndarray, max_side: int) -> np.ndarray:
    h, w = img.shape[:2]
    scale = max_side / max(w, h)
    if scale >= 1:
        return img
    return cv2.resize(img, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA)


def _write(path: str, img: np.ndarray, fmt: str, quality: int = 92) -> None:
    ext = ".png" if fmt == "png" else ".jpg"
    params = [cv2.IMWRITE_PNG_COMPRESSION, 6] if fmt == "png" else [cv2.IMWRITE_JPEG_QUALITY, quality]
    ok, buf = cv2.imencode(ext, img, params)
    if not ok:
        raise MediaError("não foi possível gravar a imagem")
    with open(path, "wb") as f:
        f.write(buf.tobytes())


def write_thumbnail(img: np.ndarray, out_path: str) -> None:
    """Miniatura que cobre 640 × 400 (o cartão corta o que sobrar), sem ampliar imagens pequenas."""
    img = _flatten(img)
    h, w = img.shape[:2]
    scale = min(1.0, max(THUMB_SIZE[0] / w, THUMB_SIZE[1] / h))
    if scale < 1:
        img = cv2.resize(img, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA)
    _write(out_path, img, "jpg", quality=85)


def image_device_version(src: str, fmt: str, out_dir: str) -> DeviceVersion:
    img = _fit(load_image(src, fmt), DEVICE_MAX_SIDE)
    out = os.path.join(out_dir, f"device.{fmt}")
    _write(out, img, fmt, quality=95)
    h, w = img.shape[:2]
    return DeviceVersion(fmt, out, w, h, os.path.getsize(out), file_sha256(out))


# ---- Vídeos -----------------------------------------------------------------------------------

def ffmpeg_exe() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(args: list[str], timeout: float | None = None, binary: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-nostdin", *args],
        capture_output=True, timeout=timeout, text=not binary, errors=None if binary else "replace",
    )


def parse_probe(text: str) -> MediaInfo | None:
    """Lê o que o `ffmpeg -i` escreve sobre o arquivo: duração, primeiro vídeo e se há áudio."""
    video_line = next((line for line in text.splitlines() if re.search(r"Stream #.*: Video: ", line)), None)
    if video_line is None:
        return None
    # Tira os parênteses, que também têm vírgulas: "yuv420p(tv, bt709, progressive)".
    parts = [p.strip() for p in re.sub(r"\([^()]*\)", "", video_line).split(",")]
    codec = re.search(r"Video: (\w+)", parts[0])
    dims = next((m for p in parts[1:] if (m := re.match(r"(\d+)x(\d+)", p))), None)
    if dims is None:
        return None
    pix_fmt = parts[1] if len(parts) > 1 and re.fullmatch(r"[a-z0-9_]+", parts[1]) else None

    duration = None
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if m:
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    rotation = 0
    m = re.search(r"rotation of (-?\d+(?:\.\d+)?) degrees", text) or re.search(r"rotate\s*:\s*(-?\d+)", text)
    if m:
        rotation = round(float(m.group(1))) % 360
    audio = re.search(r"Stream #.*: Audio: (\w+)", text)

    width, height = int(dims.group(1)), int(dims.group(2))
    if rotation in (90, 270):
        width, height = height, width
    return MediaInfo(
        width=width, height=height, duration=duration, has_audio=audio is not None,
        video_codec=codec.group(1) if codec else None, pix_fmt=pix_fmt,
        audio_codec=audio.group(1) if audio else None, rotation=rotation,
    )


def probe_video(path: str) -> MediaInfo:
    try:
        result = _run(["-i", path], timeout=60)
    except subprocess.TimeoutExpired:
        raise MediaError(UNREADABLE_VIDEO)
    info = parse_probe(result.stderr)
    if info is None or info.width <= 0 or info.height <= 0:
        raise MediaError(UNREADABLE_VIDEO)
    return info


def video_frame(path: str, at_seconds: float) -> np.ndarray:
    """Um quadro do vídeo (já na orientação de exibição), decodificado pelo OpenCV."""
    positions = (at_seconds, 0.0) if at_seconds > 0 else (0.0,)
    for position in positions:
        try:
            result = _run(
                ["-ss", f"{position:.3f}", "-i", path, "-frames:v", "1", "-an", "-c:v", "png", "-f", "image2pipe", "-"],
                timeout=60, binary=True,
            )
        except subprocess.TimeoutExpired:
            continue
        if result.returncode == 0 and result.stdout:
            img = cv2.imdecode(np.frombuffer(result.stdout, np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                return img
    raise MediaError(UNREADABLE_VIDEO)


def thumbnail_time(duration: float | None) -> float:
    """10% do vídeo, até 5 s: foge da tela preta do começo sem demorar para achar o quadro."""
    return min(5.0, (duration or 0) * 0.1)


def _device_compatible(info: MediaInfo) -> bool:
    return (
        info.video_codec == "h264" and info.pix_fmt == "yuv420p" and info.rotation == 0
        and max(info.width, info.height) <= DEVICE_MAX_SIDE and info.audio_codec in (None, "aac")
    )


def video_device_version(src: str, out_dir: str) -> DeviceVersion:
    info = probe_video(src)
    out = os.path.join(out_dir, "device.mp4")
    common = ["-y", "-loglevel", "error", "-i", src, "-map", "0:v:0", "-map", "0:a:0?", "-sn", "-dn",
              "-map_metadata", "-1"]
    if _device_compatible(info):
        codec_args = ["-c", "copy"]
    else:
        side = DEVICE_MAX_SIDE
        scale = (
            f"scale=w='if(gte(iw,ih),trunc(min({side},iw)/2)*2,-2)':h='if(gte(iw,ih),-2,trunc(min({side},ih)/2)*2)'"
        )
        codec_args = ["-vf", scale, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                      "-profile:v", "high", "-c:a", "aac", "-b:a", "160k"]
    result = _run([*common, *codec_args, "-movflags", "+faststart", "-f", "mp4", out])
    if result.returncode != 0 or not os.path.isfile(out) or os.path.getsize(out) == 0:
        detail = (result.stderr or "").strip().splitlines()[-1:] or ["sem detalhes"]
        raise MediaError(f"não foi possível gerar a versão para o óculos ({detail[0][:200]})")
    final = probe_video(out)
    return DeviceVersion("mp4", out, final.width, final.height, os.path.getsize(out), file_sha256(out))

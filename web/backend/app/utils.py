"""Helpers sem dependência do banco: os da ingestão do fluxo antigo (timestamp da pasta e rollups)
e os formatos pt-BR usados nos registros da auditoria ("12/03/1998", "2,4 MB")."""
from datetime import date, datetime, timezone


def parse_captured_at(device_session_id: str):
    """O nome da pasta vem como 'YYYY-MM-DD_HH-MM-SS'. Se não casar, retorna None."""
    try:
        return datetime.strptime(device_session_id, "%Y-%m-%d_%H-%M-%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def compute_rollups(frames: list, samples: list):
    """Retorna (sample_count, valid_sample_count, duration_seconds)."""
    sample_count = len(samples)
    valid = sum(1 for s in samples if s.get("valid"))
    last_frame_t = max((f.get("t", 0.0) for f in frames), default=0.0)
    last_sample_t = max((s.get("t", 0.0) for s in samples), default=0.0)
    duration = max(last_frame_t, last_sample_t)
    return sample_count, valid, duration


def format_date(value: date | None) -> str | None:
    return value.strftime("%d/%m/%Y") if value else None


def format_bytes(size: int) -> str:
    """Como o `formatBytes` do site: "212 KB", "2,4 MB" (uma casa abaixo de 10)."""
    value, unit = float(size), 0
    units = ("B", "KB", "MB", "GB", "TB")
    while unit < len(units) - 1 and round(value) >= 1024:
        value /= 1024
        unit += 1
    if unit == 0:
        return f"{round(value)} B"
    text = f"{value:.1f}" if round(value * 10) / 10 < 10 else f"{value:.0f}"
    return f"{text.replace('.', ',')} {units[unit]}"

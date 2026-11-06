"""Helpers de ingestão: parse do timestamp da pasta e cálculo de rollups."""
from datetime import datetime, timezone


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

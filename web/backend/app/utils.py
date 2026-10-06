"""Helpers sem dependência do banco: os formatos pt-BR usados nos registros da auditoria
("12/03/1998", "2,4 MB")."""
from datetime import date


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


def format_decimal(value: float) -> str:
    """5.0 -> "5", 2.5 -> "2,5" (tempos de tela na auditoria)."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")

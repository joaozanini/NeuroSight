"""Helpers sem dependência do banco: os formatos pt-BR usados nos registros da auditoria e nos CSV
("12/03/1998", "2,4 MB", "5,25")."""
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


def csv_cell(value: str) -> str:
    """Texto para uma célula de CSV: o que começa com = + - @ viraria fórmula ao abrir na planilha."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def csv_number(value: float | int | None, digits: int = 3) -> str:
    """Número com vírgula decimal (o Excel em português lê assim); vazio quando não há valor."""
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    return f"{value:.{digits}f}".replace(".", ",")

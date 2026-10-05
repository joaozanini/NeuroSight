"""Logging da aplicação: um formato só para os módulos `app.*` e para o Alembic.

O uvicorn configura os próprios loggers (`uvicorn`, `uvicorn.access`); eles ficam como estão.
"""
import logging.config


def setup_logging(level: str = "INFO") -> None:
    level = level.upper()
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {"format": "%(asctime)s %(levelname)s [%(name)s] %(message)s"},
        },
        "handlers": {
            "console": {"class": "logging.StreamHandler", "formatter": "default"},
        },
        "loggers": {
            "app": {"handlers": ["console"], "level": level, "propagate": False},
            "alembic": {"handlers": ["console"], "level": "INFO", "propagate": False},
            # O Alembic anuncia cada plugin carregado; só interessam as migrações aplicadas.
            "alembic.runtime.plugins": {"level": "WARNING"},
        },
    })

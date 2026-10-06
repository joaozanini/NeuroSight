"""Regras dos pacientes usadas pelas rotas e pelo `app.seed`: rótulos, código sugerido e os valores
legíveis para o diff da auditoria.
"""
import os
import re
import shutil
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..models import Patient, new_id
from ..utils import format_bytes, format_date
from .storage import storage

SEX_LABELS = {"female": "Feminino", "male": "Masculino", "undisclosed": "Prefiro não informar"}
VISION_LABELS = {"none": "Não", "glasses": "Óculos de grau", "contacts": "Lentes de contato"}
STATUS_LABELS = {"active": "Ativo", "inactive": "Inativo"}
FIELD_LABELS = {
    "code": "Código",
    "name": "Nome",
    "birth_date": "Data de nascimento",
    "sex": "Sexo",
    "vision_correction": "Óculos ou lentes",
    "consent_signed": "Termo assinado",
    "consent_date": "Data da assinatura",
    "consent_file": "Termo (PDF)",
    "notes": "Observações",
    "status": "Situação",
}

SUGGESTED_CODE = re.compile(r"^P-(\d+)$")


def suggest_code(db: DbSession) -> str:
    """Próximo P-NNN livre: um a mais que o maior número em uso (ninguém reaproveita códigos)."""
    numbers = [
        int(m.group(1))
        for code in db.scalars(select(Patient.code).where(Patient.code.startswith("P-")))
        if (m := SUGGESTED_CODE.match(code))
    ]
    return f"P-{max(numbers, default=0) + 1:03d}"


def find_by_code(db: DbSession, code: str) -> Patient | None:
    return db.scalar(select(Patient).where(Patient.code == code.strip().upper()))


def consent_file_label(patient: Patient) -> str | None:
    if not patient.consent_file_name:
        return None
    return f"{patient.consent_file_name} ({format_bytes(patient.consent_file_size or 0)})"


def snapshot(patient: Patient) -> dict[str, object]:
    """Valores legíveis dos campos editáveis, para o diff da auditoria."""
    return {
        "code": patient.code,
        "name": patient.name,
        "birth_date": format_date(patient.birth_date),
        "sex": SEX_LABELS.get(patient.sex, patient.sex),
        "vision_correction": VISION_LABELS.get(patient.vision_correction, patient.vision_correction),
        "consent_signed": bool(patient.consent_signed),
        "consent_date": format_date(patient.consent_date),
        "consent_file": consent_file_label(patient),
        "notes": patient.notes,
        "status": STATUS_LABELS.get(patient.status, patient.status),
    }


def save_consent_file(patient_id: str, fileobj: BinaryIO) -> tuple[str, int]:
    """Grava o PDF do TCLE num arquivo novo da pasta do paciente; devolve (chave, tamanho).

    O arquivo anterior só sai depois do commit, por quem chamou (`storage.delete_file`).
    """
    folder = storage.patient_dir(patient_id)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"tcle-{new_id()[:12]}.pdf")
    with open(path, "wb") as out:
        shutil.copyfileobj(fileobj, out, 1 << 20)
    return storage.key_of(path), os.path.getsize(path)

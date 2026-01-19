"""Persistence helpers for saving/loading application state."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .appointment import Appointment
from .hash_table import HashTable
from .patient import Patient
from .priority_queue import PriorityQueue
from .tree import BST

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "records.json"
CSV_FILE = BASE_DIR / "records.csv"
CSV_FIELDS = ("patient_id", "name", "age", "gender", "phone", "medical_notes")


def _row_to_patient(row):
    if not row:
        return None
    patient_id = (row.get("patient_id") or "").strip()
    name = (row.get("name") or "").strip()
    age_text = (row.get("age") or "").strip()
    gender = (row.get("gender") or "").strip().upper()
    phone = (row.get("phone") or "").strip()
    notes = (row.get("medical_notes") or "").strip()

    if not patient_id or not name or not age_text or not gender or not phone:
        return None

    try:
        age = int(age_text)
    except ValueError:
        return None

    if gender not in ("M", "F", "O"):
        return None

    try:
        return Patient(patient_id, name, age, gender, phone, notes)
    except Exception:
        return None


def _load_csv_patients(path: Path | str):
    path = Path(path)
    if not path.exists():
        return []

    patients = []
    try:
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                patient = _row_to_patient(row)
                if patient is not None:
                    patients.append(patient)
    except Exception:
        return []

    return patients


def load_state(path: Path | str = DATA_FILE, csv_path: Path | str = CSV_FILE):
    """Load persisted records and rebuild in-memory data structures."""
    registry = HashTable()
    triage = PriorityQueue()
    schedule = BST()
    appt_seq = 0

    path = Path(path)
    raw = {}
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except Exception:
            raw = {}

    for pdata in raw.get("patients", []):
        try:
            patient = Patient.from_dict(pdata)
            registry.put(patient.patient_id, patient)
        except Exception:
            continue

    for entry in raw.get("triage", []):
        try:
            triage.enqueue(entry["priority"], entry.get("payload"))
        except Exception:
            continue

    for appt_data in raw.get("appointments", []):
        try:
            dt_value = appt_data.get("datetime") or appt_data.get("dt")
            if not dt_value:
                continue
            appt = Appointment(
                appt_data["patient_id"],
                dt_value,
                code=appt_data.get("code"),
            )
            schedule.insert(appt_data["key"], appt)
        except Exception:
            continue

    saved_seq = raw.get("appt_seq", 0)
    if isinstance(saved_seq, int) and saved_seq >= 0:
        appt_seq = saved_seq

    imported_from_csv = 0
    for patient in _load_csv_patients(csv_path):
        if not registry.contains(patient.patient_id):
            registry.put(patient.patient_id, patient)
            imported_from_csv += 1

    return registry, triage, schedule, appt_seq, imported_from_csv


def save_state(registry: HashTable, triage: PriorityQueue, schedule: BST, appt_seq: int,
               path: Path | str = DATA_FILE, csv_path: Path | str = CSV_FILE):
    """Persist patients, queue, and appointments to disk."""
    path = Path(path)
    data = {
        "patients": [],
        "triage": [],
        "appointments": [],
        "appt_seq": appt_seq,
    }

    for key, patient in registry.items():
        try:
            data["patients"].append(patient.to_dict())
        except Exception:
            continue

    data["patients"].sort(key=lambda item: item["patient_id"])

    for entry in triage.to_list():
        data["triage"].append(entry)

    for key, appt in schedule.items():
        try:
            data["appointments"].append(
                {
                    "key": key,
                    "code": appt.code,
                    "patient_id": appt.patient_id,
                    "datetime": appt.datetime_str(),
                }
            )
        except Exception:
            continue

    try:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
    except Exception:
        # Surface errors is noisy for CLI; best-effort only.
        pass

    _save_csv_patients(registry, csv_path)


def _save_csv_patients(registry: HashTable, path: Path | str):
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = sorted(registry.items(), key=lambda pair: pair[0])
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for _, patient in rows:
                writer.writerow(
                    {
                        "patient_id": patient.patient_id,
                        "name": patient.name,
                        "age": patient.age,
                        "gender": patient.gender,
                        "phone": patient.phone,
                        "medical_notes": patient.medical_notes,
                    }
                )
    except Exception:
        # best effort only
        return

"""Persistence helpers for saving/loading application state."""

from __future__ import annotations

import json
from pathlib import Path

from .appointment import Appointment
from .hash_table import HashTable
from .patient import Patient
from .priority_queue import PriorityQueue
from .tree import BST

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "records.json"


def load_state(path: Path | str = DATA_FILE):
    """Load persisted records and rebuild in-memory data structures."""
    registry = HashTable()
    triage = PriorityQueue()
    schedule = BST()
    appt_seq = 0

    path = Path(path)
    if not path.exists():
        return registry, triage, schedule, appt_seq

    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except Exception:
        # Corrupted file -> start fresh.
        return registry, triage, schedule, appt_seq

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

    return registry, triage, schedule, appt_seq


def save_state(registry: HashTable, triage: PriorityQueue, schedule: BST, appt_seq: int,
               path: Path | str = DATA_FILE):
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

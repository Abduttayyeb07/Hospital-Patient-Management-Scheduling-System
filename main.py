# main.py
# Menu-driven CLI using the mandatory data structures.

from src.patient import Patient
from src.appointment import Appointment
from src.hash_table import HashTable
from src.priority_queue import PriorityQueue
from src.storage import load_state, save_state
from src.tree import BST

APPT_CODE_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def read_int(prompt):
    raw = input(prompt).strip()
    if raw == "":
        raise ValueError("Input cannot be empty.")
    try:
        return int(raw)
    except:
        raise ValueError("Expected an integer.")

def read_nonempty(prompt):
    s = input(prompt).strip()
    if not s:
        raise ValueError("Input cannot be empty.")
    return s

def menu():
    print("\n=== CEP-2 Hospital Patient Management & Scheduling ===")
    print("1) Register Patient")
    print("2) Lookup Patient")
    print("3) Add Visit Record (LinkedList history)")
    print("4) Show Visit History")
    print("5) Admit Emergency (PriorityQueue)")
    print("6) Treat Next Emergency")
    print("7) Schedule Appointment (BST)")
    print("8) Cancel Appointment (BST)")
    print("9) Reschedule Appointment (BST)")
    print("10) List All Appointments (BST in-order)")
    print("0) Exit")


def generate_appt_code(counter):
    """Return a 5-character base36 code derived from the counter."""
    if counter < 0:
        counter = 0
    base = len(APPT_CODE_CHARS)
    if counter == 0:
        code = "0"
    else:
        code = ""
        n = counter
        while n > 0:
            n, rem = divmod(n, base)
            code = APPT_CODE_CHARS[rem] + code
    return code.rjust(5, "0")[-5:]

def main():
    registry, triage, schedule, appt_seq, csv_import_count = load_state()
    if registry is None:
        # fallback if load_state returned None components (defensive)
        registry = HashTable()
    if triage is None:
        triage = PriorityQueue()
    if schedule is None:
        schedule = BST()

    # tie-breaker for appointments at same minute:
    # We avoid Python lists; just increment integer and add small offset.
    if not isinstance(appt_seq, int) or appt_seq < 0:
        appt_seq = 0

    def persist():
        save_state(registry, triage, schedule, appt_seq)

    def register_patient_flow(existing_id=None):
        pid = existing_id or read_nonempty("Patient ID (unique): ")
        if registry.contains(pid):
            print("ERROR: patient_id already exists.")
            return None

        name = read_nonempty("Name: ")
        age = read_int("Age: ")
        gender = read_nonempty("Gender (M/F/O): ").upper()
        phone = read_nonempty("Phone: ")
        notes = input("Medical notes (optional): ").strip()

        patient = Patient(pid, name, age, gender, phone, notes)
        registry.put(pid, patient)
        return patient

    def rebuild_code_index():
        nonlocal appt_seq
        idx = HashTable()
        needs_save = False
        for key, appt in schedule.items():
            code = getattr(appt, "code", None)
            if not code:
                code = generate_appt_code(appt_seq)
                appt_seq += 1
                appt.code = code
                needs_save = True
            idx.put(code, key)
        if needs_save:
            persist()
        return idx

    code_index = rebuild_code_index()

    if csv_import_count:
        print(f"INFO: Imported {csv_import_count} patient(s) from records.csv.")
        persist()

    while True:
        try:
            menu()
            choice = read_int("Select: ")

            if choice == 0:
                persist()
                print("Goodbye.")
                break

            # 1) Register
            if choice == 1:
                p = register_patient_flow()
                if p is None:
                    continue
                print("OK: Registered:", p)
                persist()

            # 2) Lookup
            elif choice == 2:
                pid = read_nonempty("Patient ID: ")
                p = registry.get(pid)
                if p is None:
                    print("NOT FOUND.")
                else:
                    print("FOUND:", p)

            # 3) Add visit record (LinkedList)
            elif choice == 3:
                pid = read_nonempty("Patient ID: ")
                p = registry.get(pid)
                if p is None:
                    print("ERROR: patient not found.")
                    continue
                record = read_nonempty("Visit record text: ")
                p.add_visit(record)
                print("OK: Visit added.")
                persist()

            # 4) Show history
            elif choice == 4:
                pid = read_nonempty("Patient ID: ")
                p = registry.get(pid)
                if p is None:
                    print("ERROR: patient not found.")
                    continue
                print("\n--- Visit History ---")
                print(p.visit_history.to_string())

            # 5) Admit emergency (PriorityQueue)
            elif choice == 5:
                pid = read_nonempty("Patient ID: ")
                p = registry.get(pid)
                if p is None:
                    resp = input("Patient not found. Register now? (Y/N): ").strip().upper()
                    if resp != "Y":
                        print("Canceled.")
                        continue
                    p = register_patient_flow(existing_id=pid)
                    if p is None:
                        continue
                    print("OK: Registered:", p)
                    persist()
                severity = read_int("Severity (1..10): ")
                if severity < 1 or severity > 10:
                    print("ERROR: severity must be 1..10")
                    continue
                complaint = read_nonempty("Emergency complaint: ")
                payload = f"EMERGENCY pid={pid} name={p.name} sev={severity} issue={complaint}"
                triage.enqueue(severity, payload)
                print("OK: added to triage.")
                persist()

            # 6) Treat next emergency
            elif choice == 6:
                nxt = triage.dequeue()
                if nxt is None:
                    print("No emergency patients in queue.")
                else:
                    print("TREAT NOW ->", nxt)
                    persist()

            # 7) Schedule appointment (BST)
            elif choice == 7:
                pid = read_nonempty("Patient ID: ")
                p = registry.get(pid)
                if p is None:
                    print("ERROR: patient not found.")
                    continue

                dt_str = read_nonempty("Appointment Date (YYYY-MM-DD HH:MM): ")
                appt = Appointment(pid, dt_str)
                appt.code = generate_appt_code(appt_seq)
                # handle same-minute collisions by offsetting with sequence
                global_key = appt.key_minutes() * 1000 + appt_seq
                appt_seq += 1

                schedule.insert(global_key, appt)
                code_index.put(appt.code, global_key)
                # also store in patient's visit history as "appointment created"
                p.add_visit(f"APPT SCHEDULED [{appt.code}] -> {appt}")
                print("OK: scheduled:", appt)
                print("Appointment code:", appt.code)
                persist()

            # 8) Cancel appointment
            elif choice == 8:
                code = read_nonempty("Appointment code (5 chars): ").upper()
                key = code_index.get(code)
                if key is None:
                    print("NOT FOUND.")
                    continue

                appt = schedule.find(key)
                if appt is None:
                    code_index.remove(code)
                    print("NOT FOUND.")
                    continue

                ok = schedule.delete(key)
                if ok:
                    code_index.remove(code)
                    p = registry.get(appt.patient_id)
                    if p is not None:
                        p.add_visit(f"APPT CANCELED [{code}] -> {appt}")
                    print("OK: canceled.")
                    persist()
                else:
                    print("ERROR: cancel failed.")

            # 9) Reschedule appointment
            elif choice == 9:
                code = read_nonempty("Existing appointment code (5 chars): ").upper()
                old_key = code_index.get(code)
                if old_key is None:
                    print("NOT FOUND.")
                    continue

                appt = schedule.find(old_key)
                if appt is None:
                    code_index.remove(code)
                    print("NOT FOUND.")
                    continue

                new_dt = read_nonempty("New DateTime (YYYY-MM-DD HH:MM): ")
                # delete old then insert new
                schedule.delete(old_key)

                new_appt = Appointment(appt.patient_id, new_dt)
                new_appt.code = code
                new_key = new_appt.key_minutes() * 1000 + appt_seq
                appt_seq += 1
                schedule.insert(new_key, new_appt)
                code_index.put(code, new_key)

                p = registry.get(appt.patient_id)
                if p is not None:
                    p.add_visit(f"APPT RESCHEDULED [{code}] -> old={appt} new={new_appt}")

                print("OK: rescheduled.")
                print("Appointment code:", code)
                persist()

            # 10) List all appointments (BST in-order)
            elif choice == 10:
                if schedule.size == 0:
                    print("(no appointments)")
                else:
                    print("\n--- Appointments (Chronological) ---")
                    def show(appt):
                        # We print the BST key for cancel/reschedule reference.
                        # But inorder_traverse only gives value; so we add a second method here:
                        # For academic simplicity, we re-traverse with a custom printer below.
                        print(str(appt))

                    # To show keys, we need a key-aware traversal.
                    # We'll implement it inline without lists:
                    def inorder_with_keys(node):
                        if node is None:
                            return
                        inorder_with_keys(node.left)
                        appt = node.value
                        code = appt.code or "-----"
                        print(f"CODE={code}  {appt}")
                        inorder_with_keys(node.right)

                    inorder_with_keys(schedule.root)

            else:
                print("Invalid option.")

        except Exception as e:
            print("ERROR:", str(e))

if __name__ == "__main__":
    main()

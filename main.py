import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from tkcalendar import DateEntry
from datetime import date, datetime
import re
import logging
from contextlib import contextmanager
from typing import Optional, Set

# SQLAlchemy imports
from sqlalchemy import create_engine, Column, Integer, String, Date, Float, ForeignKey, Index
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, joinedload

# ------------------------
# Logging Configuration
# ------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# ------------------------
# Database Models & Setup
# ------------------------
Base = declarative_base()

class Patient(Base):
    __tablename__ = 'patients'
    id = Column(Integer, primary_key=True)
    patient_name = Column(String, nullable=False)
    phone_number = Column(String, unique=True, nullable=False)
    treatment_type = Column(String, nullable=True)
    teeth_location = Column(String, nullable=True)
    # One patient can have multiple appointments
    appointments = relationship("Appointment", back_populates="patient", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Patient(name='{self.patient_name}', phone='{self.phone_number}')>"

class Appointment(Base):
    __tablename__ = 'appointments'
    id = Column(Integer, primary_key=True)
    appointment_date = Column(Date, nullable=False)
    treatment_type = Column(String, nullable=False)
    dentist = Column(String, nullable=False)
    fee = Column(Float, nullable=True)
    notes = Column(String)
    patient_id = Column(Integer, ForeignKey('patients.id'))
    patient = relationship("Patient", back_populates="appointments")

    def __repr__(self) -> str:
        return f"<Appointment(patient='{self.patient.patient_name}', treatment='{self.treatment_type}', date='{self.appointment_date}')>"

# Index for faster phone lookup
Index('idx_phone', Patient.phone_number)

engine = create_engine('sqlite:///dentistry_clinic.db', echo=False)
Session = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

@contextmanager
def session_scope():
    """Provide a transactional scope for database operations."""
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logging.error("Session rollback because of exception: %s", e)
        raise
    finally:
        session.close()

# ------------------------
# Utility Functions
# ------------------------
def validate_phone(phone: str) -> Optional[str]:
    """
    Validate phone number using a regex.
    Accepts an optional '+' at the beginning and 8 to 15 digits.
    """
    pattern = r'^\+?\d{8,15}$'
    if re.match(pattern, phone):
        return phone
    return None

def validate_fee(fee: str) -> Optional[float]:
    try:
        f = float(fee)
        if f >= 0:
            return f
    except ValueError:
        return None
    return None

# ------------------------
# Dentistry Clinic Application Class
# ------------------------
class DentistryClinicApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("🦷 Dentistry Clinic Management System")
        self.geometry("1000x650")
        self.configure(bg="#f4f6f8")
        self.style = ttk.Style()
        self.style.theme_use("default")
        self.style.configure("TLabel", font=("Segoe UI", 10), padding=5)
        self.style.configure("TButton", font=("Segoe UI", 10), padding=5)
        self.style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background="#007acc", foreground="white")
        self.style.configure("Treeview", font=("Segoe UI", 10), rowheight=25)
        self.create_widgets()
        self.show_records()  # Initial load of records
        self.auto_refresh()   # Start auto-refresh

    def create_widgets(self) -> None:
        """Creates main UI widgets including menu, buttons, search, and treeview."""
        # Create Menu
        menu_bar = tk.Menu(self)
        actions_menu = tk.Menu(menu_bar, tearoff=0)
        actions_menu.add_command(label="Add Patient & Appointment", command=self.add_patient_and_appointment_gui)
        actions_menu.add_command(label="Delete Patient", command=self.delete_patient_gui)
        actions_menu.add_command(label="Modify Patient", command=self.modify_patient_gui)
        actions_menu.add_command(label="Appointment Reminders", command=self.appointment_reminders_gui)
        actions_menu.add_separator()
        actions_menu.add_command(label="Exit", command=self.quit)
        menu_bar.add_cascade(label="Actions", menu=actions_menu)
        self.config(menu=menu_bar)

        # Buttons Frame
        btn_frame = tk.Frame(self, bg="#f4f6f8")
        btn_frame.pack(pady=10)
        buttons = [
            ("📝 Add Patient & Appointment", self.add_patient_and_appointment_gui),
            ("🗑 Delete Patient", self.delete_patient_gui),
            ("✏️ Modify Patient", self.modify_patient_gui),
            ("⏰ Appointment Reminders", self.appointment_reminders_gui),
            ("🔁 Refresh Records", self.show_records)
        ]
        for i, (text, cmd) in enumerate(buttons):
            ttk.Button(btn_frame, text=text, width=30, command=cmd).grid(row=0, column=i, padx=5)

        # Search Frame
        search_frame = tk.Frame(self, bg="#f4f6f8")
        search_frame.pack(pady=5)
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=5)
        self.search_entry = tk.Entry(search_frame)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Go", command=self.search_records).pack(side=tk.LEFT, padx=5)

        # Records Treeview with Scrollbar
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("Patient", "Phone", "Patient Treatment", "Teeth Location", "Appointment Date", "Treatment", "Dentist", "Fee", "Notes"),
            show="headings"
        )
        columns = ("Patient", "Phone", "Patient Treatment", "Teeth Location", "Appointment Date", "Treatment", "Dentist", "Fee", "Notes")
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def clear_tree(self) -> None:
        """Clears all entries from the treeview."""
        for item in self.tree.get_children():
            self.tree.delete(item)

    def show_records(self, query: Optional[str] = None) -> None:
        """
        Displays patient and appointment records in the treeview.
        
        Args:
            query: Optional search term to filter records.
        """
        self.clear_tree()
        with session_scope() as session:
            q = session.query(Patient)
            if query:
                q = q.filter(
                    (Patient.patient_name.ilike(f"%{query}%")) |
                    (Patient.phone_number.ilike(f"%{query}%")) |
                    (Patient.treatment_type.ilike(f"%{query}%")) |
                    (Patient.teeth_location.ilike(f"%{query}%")) |
                    (Patient.appointments.any(Appointment.treatment_type.ilike(f"%{query}%")))
                )
            patients = q.all()
            for patient in patients:
                if patient.appointments:
                    appointments_sorted = sorted(patient.appointments, key=lambda a: a.appointment_date)
                    for app in appointments_sorted:
                        self.tree.insert("", "end", values=(
                            patient.patient_name,
                            patient.phone_number,
                            patient.treatment_type if patient.treatment_type else "",
                            patient.teeth_location if patient.teeth_location else "",
                            app.appointment_date.strftime("%Y-%m-%d"),
                            app.treatment_type,
                            app.dentist,
                            f"{app.fee:.2f}" if app.fee is not None else "",
                            app.notes if app.notes else ""
                        ))
                else:
                    self.tree.insert("", "end", values=(
                        patient.patient_name,
                        patient.phone_number,
                        patient.treatment_type if patient.treatment_type else "",
                        patient.teeth_location if patient.teeth_location else "",
                        "", "", "", "", ""
                    ))

    def auto_refresh(self) -> None:
        """
        Automatically refreshes records and checks for today's appointments.
        Schedules itself to run every 60 seconds.
        """
        self.show_records()
        with session_scope() as session:
            today_date = date.today()
            apps_today = session.query(Appointment).filter(Appointment.appointment_date == today_date).all()
            if apps_today:
                logging.info("There are %d appointment(s) scheduled for today.", len(apps_today))
        self.after(60000, self.auto_refresh)  # Refresh every 60 seconds

    def open_teeth_selector(self, parent: tk.Toplevel, initial_selection: str, callback) -> None:
        """
        Opens a teeth selection window arranged in four quadrants:
          - Upper Left and Upper Right in the upper section.
          - Lower Left and Lower Right in the lower section.
        Each quadrant displays its tooth numbers in a 1x8 grid.
          - For left-side quadrants ("Upper Left" and "Lower Left"), the numbers are arranged descending (8 to 1).
          - For right-side quadrants ("Upper Right" and "Lower Right"), the numbers are arranged ascending (1 to 8).
        A prefix is added to each number to differentiate quadrants:
          - Upper Left -> UL, Upper Right -> UR, Lower Left -> LL, Lower Right -> LR.
        Clicking a tooth toggles its selection. On OK, a comma-separated string is returned.
        """
        selector = tk.Toplevel(parent)
        selector.title("Select Teeth")

        # Main container frame
        main_frame = tk.Frame(selector)
        main_frame.pack(padx=10, pady=10)

        # Create separate frames for upper and lower sections
        upper_frame = tk.Frame(main_frame)
        upper_frame.pack(side=tk.TOP, pady=5)
        lower_frame = tk.Frame(main_frame)
        lower_frame.pack(side=tk.TOP, pady=5)

        # In the upper section, pack Upper Left first then Upper Right
        upper_left_frame = tk.LabelFrame(upper_frame, text="Upper Left")
        upper_left_frame.pack(side=tk.LEFT, padx=5)
        upper_right_frame = tk.LabelFrame(upper_frame, text="Upper Right")
        upper_right_frame.pack(side=tk.LEFT, padx=5)

        # In the lower section, pack Lower Left then Lower Right
        lower_left_frame = tk.LabelFrame(lower_frame, text="Lower Left")
        lower_left_frame.pack(side=tk.LEFT, padx=5)
        lower_right_frame = tk.LabelFrame(lower_frame, text="Lower Right")
        lower_right_frame.pack(side=tk.LEFT, padx=5)

        # Define quadrants with their abbreviations and associated frames
        quadrant_info = {
            "Upper Left": ("UL", upper_left_frame),
            "Upper Right": ("UR", upper_right_frame),
            "Lower Left": ("LL", lower_left_frame),
            "Lower Right": ("LR", lower_right_frame)
        }

        # Initialize selection set; selections are stored with quadrant prefix (e.g. "UL3")
        selected_teeth: Set[str] = set()
        if initial_selection:
            for tooth in initial_selection.split(","):
                tooth = tooth.strip()
                if tooth:
                    selected_teeth.add(tooth)

        buttons = {}

        def toggle_tooth(qabbr: str, num: int) -> None:
            tooth_id = f"{qabbr}{num}"
            btn = buttons[tooth_id]
            if tooth_id in selected_teeth:
                selected_teeth.remove(tooth_id)
                btn.config(relief="raised", bg="SystemButtonFace")
            else:
                selected_teeth.add(tooth_id)
                btn.config(relief="sunken", bg="lightblue")

        # Create a 1x8 grid of buttons for each quadrant
        for qname, (qabbr, frame) in quadrant_info.items():
            # For left-side quadrants, arrange numbers descending from 8 to 1;
            # for right-side quadrants, arrange numbers ascending from 1 to 8.
            if "Left" in qname:
                numbers = list(reversed(range(1, 9)))
            else:
                numbers = list(range(1, 9))
            for col, i in enumerate(numbers):
                tooth_id = f"{qabbr}{i}"
                btn = tk.Button(frame, text=str(i), width=4, command=lambda qa=qabbr, num=i: toggle_tooth(qa, num))
                btn.grid(row=0, column=col, padx=2, pady=2)
                buttons[tooth_id] = btn
                if tooth_id in selected_teeth:
                    btn.config(relief="sunken", bg="lightblue")

        # OK and Cancel buttons
        action_frame = tk.Frame(selector)
        action_frame.pack(pady=10)

        def on_ok() -> None:
            selection = ", ".join(sorted(selected_teeth))
            callback(selection)
            selector.destroy()

        def on_cancel() -> None:
            selector.destroy()

        tk.Button(action_frame, text="OK", command=on_ok).grid(row=0, column=0, padx=5)
        tk.Button(action_frame, text="Cancel", command=on_cancel).grid(row=0, column=1, padx=5)

    def add_patient_and_appointment_gui(self) -> None:
        """Combined form to add/update a patient and create an appointment."""
        def save() -> None:
            try:
                # Patient Info
                name = name_entry.get().strip()
                if not name:
                    raise ValueError("Patient name cannot be empty.")
                phone = validate_phone(phone_entry.get().strip())
                if not phone:
                    raise ValueError("Invalid phone number.")
                patient_treatment = patient_treatment_entry.get().strip()
                teeth_location = teeth_var.get()  # from teeth selector

                # Appointment Info
                app_date = date_picker.get_date()
                appointment_treatment = appointment_treatment_combobox.get().strip()
                if not appointment_treatment:
                    raise ValueError("Appointment treatment type is required.")
                dentist = dentist_combobox.get().strip()
                if not dentist:
                    raise ValueError("Dentist name is required.")
                fee_val = validate_fee(fee_entry.get().strip())
                notes_val = notes_entry.get().strip()

                with session_scope() as session:
                    patient = session.query(Patient).filter_by(phone_number=phone).first()
                    if patient is None:
                        # Create new patient
                        patient = Patient(
                            patient_name=name,
                            phone_number=phone,
                            treatment_type=patient_treatment,
                            teeth_location=teeth_location
                        )
                        session.add(patient)
                    else:
                        # Update patient details if desired
                        patient.patient_name = name
                        patient.treatment_type = patient_treatment
                        patient.teeth_location = teeth_location

                    new_app = Appointment(
                        appointment_date=app_date,
                        treatment_type=appointment_treatment,
                        dentist=dentist,
                        fee=fee_val,
                        notes=notes_val,
                        patient=patient
                    )
                    session.add(new_app)
                messagebox.showinfo("Success", f"Patient '{name}' and appointment added successfully.", parent=window)
                window.destroy()
                self.show_records()
            except Exception as e:
                logging.exception("Error saving patient and appointment")
                messagebox.showerror("Error", str(e), parent=window)

        window = tk.Toplevel(self)
        window.title("Add Patient & Appointment")
        window.configure(bg="#f4f6f8")
        window.attributes('-topmost', True)
        window.after_idle(window.attributes, '-topmost', False)

        # Patient Info Frame
        patient_frame = tk.LabelFrame(window, text="Patient Info", padx=10, pady=10, bg="#f4f6f8")
        patient_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        tk.Label(patient_frame, text="Patient Name", bg="#f4f6f8").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        name_entry = tk.Entry(patient_frame)
        name_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(patient_frame, text="Phone Number", bg="#f4f6f8").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        phone_entry = tk.Entry(patient_frame)
        phone_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(patient_frame, text="Patient Treatment", bg="#f4f6f8").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        patient_treatment_entry = tk.Entry(patient_frame)
        patient_treatment_entry.grid(row=2, column=1, padx=5, pady=5)

        tk.Label(patient_frame, text="Teeth Location", bg="#f4f6f8").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        teeth_var = tk.StringVar()
        teeth_entry = tk.Entry(patient_frame, textvariable=teeth_var, state="readonly")
        teeth_entry.grid(row=3, column=1, padx=5, pady=5)
        tk.Button(patient_frame, text="Select Teeth",
                  command=lambda: self.open_teeth_selector(window, teeth_var.get(), lambda selection: teeth_var.set(selection))
                 ).grid(row=3, column=2, padx=5, pady=5)

        # Appointment Info Frame
        appointment_frame = tk.LabelFrame(window, text="Appointment Info", padx=10, pady=10, bg="#f4f6f8")
        appointment_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        tk.Label(appointment_frame, text="Appointment Date", bg="#f4f6f8").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        date_picker = DateEntry(appointment_frame, date_pattern='yyyy-mm-dd')
        date_picker.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(appointment_frame, text="Treatment Type", bg="#f4f6f8").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        # Drop-down menu for treatments
        appointment_treatment_combobox = ttk.Combobox(appointment_frame, 
                                                        values=["Cleaning", "Filling", "Extraction", "Whitening", "Implant", "Root Canal", "Crown", "Other"],
                                                        state="readonly")
        appointment_treatment_combobox.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(appointment_frame, text="Dentist", bg="#f4f6f8").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        # Drop-down menu for doctors
        dentist_combobox = ttk.Combobox(appointment_frame, 
                                        values=["Mohamed", "Essam", "Noha"],
                                        state="readonly")
        dentist_combobox.grid(row=2, column=1, padx=5, pady=5)

        tk.Label(appointment_frame, text="Fee", bg="#f4f6f8").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        fee_entry = tk.Entry(appointment_frame)
        fee_entry.grid(row=3, column=1, padx=5, pady=5)

        tk.Label(appointment_frame, text="Notes", bg="#f4f6f8").grid(row=4, column=0, sticky="e", padx=5, pady=5)
        notes_entry = tk.Entry(appointment_frame)
        notes_entry.grid(row=4, column=1, padx=5, pady=5)

        tk.Button(window, text="Save", command=save).grid(row=2, column=0, pady=10)

    def delete_patient_gui(self) -> None:
        """Prompts for a patient phone number and deletes the patient record after confirmation."""
        try:
            phone = simpledialog.askstring("Phone Number", "Enter Patient Phone Number:", parent=self)
            if phone is None:
                return
            phone = validate_phone(phone.strip())
            if not phone:
                raise ValueError("Invalid phone number.")
            with session_scope() as session:
                patient = session.query(Patient).filter_by(phone_number=phone).first()
                if not patient:
                    raise ValueError("Patient not found.")
                # Confirm deletion
                if not messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete patient '{patient.patient_name}'?", parent=self):
                    return
                session.delete(patient)
            messagebox.showinfo("Deleted", f"Patient with phone '{phone}' deleted.", parent=self)
            self.show_records()
        except Exception as e:
            logging.exception("Error deleting patient")
            messagebox.showerror("Error", str(e), parent=self)

    def modify_patient_gui(self) -> None:
        """Allows modification of patient details by phone number."""
        try:
            phone = simpledialog.askstring("Phone Number", "Enter Patient Phone Number to Modify:", parent=self)
            if phone is None:
                return
            phone = validate_phone(phone.strip())
            if not phone:
                raise ValueError("Invalid phone number.")
            with session_scope() as session:
                patient = session.query(Patient).filter_by(phone_number=phone).first()
                if not patient:
                    raise ValueError("Patient not found.")

                mod_window = tk.Toplevel(self)
                mod_window.title(f"Modify {patient.patient_name}")
                mod_window.configure(bg="#f4f6f8")
                mod_window.attributes('-topmost', True)
                mod_window.after_idle(mod_window.attributes, '-topmost', False)

                ttk.Label(mod_window, text="Patient Name").grid(row=0, column=0, padx=10, pady=5, sticky="e")
                name_entry = tk.Entry(mod_window)
                name_entry.insert(0, patient.patient_name)
                name_entry.grid(row=0, column=1, padx=10, pady=5, sticky="w")

                ttk.Label(mod_window, text="Patient Treatment").grid(row=1, column=0, padx=10, pady=5, sticky="e")
                treatment_entry = tk.Entry(mod_window)
                treatment_entry.insert(0, patient.treatment_type if patient.treatment_type else "")
                treatment_entry.grid(row=1, column=1, padx=10, pady=5, sticky="w")

                ttk.Label(mod_window, text="Teeth Location").grid(row=2, column=0, padx=10, pady=5, sticky="e")
                teeth_var = tk.StringVar(value=patient.teeth_location if patient.teeth_location else "")
                teeth_entry = tk.Entry(mod_window, textvariable=teeth_var, state="readonly")
                teeth_entry.grid(row=2, column=1, padx=10, pady=5, sticky="w")
                ttk.Button(mod_window, text="Select Teeth",
                           command=lambda: self.open_teeth_selector(mod_window, teeth_var.get(), lambda selection: teeth_var.set(selection))
                          ).grid(row=2, column=2, padx=10, pady=5)

                def save_modifications() -> None:
                    try:
                        new_name = name_entry.get().strip()
                        if not new_name:
                            raise ValueError("Patient name cannot be empty.")
                        patient.patient_name = new_name
                        patient.treatment_type = treatment_entry.get().strip()
                        patient.teeth_location = teeth_var.get()
                        messagebox.showinfo("Success", "Patient details updated.", parent=mod_window)
                        mod_window.destroy()
                        self.show_records()
                    except Exception as ex:
                        logging.exception("Error modifying patient")
                        messagebox.showerror("Error", str(ex), parent=mod_window)

                ttk.Button(mod_window, text="Save Changes", command=save_modifications).grid(row=3, column=0, columnspan=3, pady=10)
        except Exception as e:
            logging.exception("Error in modify patient")
            messagebox.showerror("Error", str(e), parent=self)

    def appointment_reminders_gui(self) -> None:
        """Displays appointment reminders for today's appointments."""
        try:
            today_date = date.today()
            with session_scope() as session:
                apps_due = (
                    session.query(Appointment)
                    .options(joinedload(Appointment.patient))
                    .filter(Appointment.appointment_date == today_date)
                    .all()
                )
                if not apps_due:
                    reminders = "✅ No appointments scheduled for today."
                else:
                    reminders_list = []
                    for app in apps_due:
                        reminders_list.append(
                            f"⚠ {app.patient.patient_name} has an appointment for {app.treatment_type} with Dr. {app.dentist} today ({app.appointment_date.strftime('%Y-%m-%d')})."
                        )
                    reminders = "\n".join(reminders_list)
            messagebox.showinfo("Appointment Reminders", reminders, parent=self)
        except Exception as e:
            logging.exception("Error retrieving appointment reminders")
            messagebox.showerror("Error", f"Failed to retrieve reminders: {e}", parent=self)

    def search_records(self) -> None:
        """Searches records based on user input in the search entry."""
        query = self.search_entry.get().strip()
        self.show_records(query=query)

# ------------------------
# Main Execution
# ------------------------
if __name__ == "__main__":
    app = DentistryClinicApp()
    app.mainloop()

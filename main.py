import threading
import time
import random
import tkinter as tk
from tkinter import ttk, messagebox
import csv

# Import librarie graficef
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# Import sunet (Doar Windows)
try:
    import winsound

    SOUND_AVAILABLE = True
except ImportError:
    SOUND_AVAILABLE = False

# --- CONFIGURARE SISTEM ---
N_MAX_MASINI = 12
PRAG_VENTILATIE_ON = 70.0
PRAG_VENTILATIE_OFF = 30.0
PRAG_CRITIC = 90.0

# Culori Cyberpunk / Dark Mode
COLOR_BG = "#1e1e1e"
COLOR_PANEL = "#2d2d2d"
COLOR_TEXT = "#00ff00"  # Verde Neon
COLOR_ALERT = "#ff0055"  # Rosu Neon
COLOR_WARN = "#ffcc00"  # Galben
COLOR_ACCENT = "#00ccff"  # Cyan


# --- BACKEND (MODEL) ---
class MonitorTunel:
    """MODEL (BACKEND): Gestioneaza date, sincronizare si logica."""

    def __init__(self):
        self.lock = threading.Lock()  # Mutex pentru thread-safe
        self.nr_masini = 0
        self.nivel_noxe = 5.0
        self.ventilatoare = False

        # Stari avarie
        self.incendiu = False
        self.panica = False
        self.blocaj_operator = False

        # Simulare Timp
        self.ora_curenta = 6.0

        # Istoric pt grafic
        self.istoric_noxe = [5.0] * 60
        self.log_mesaje = []

    def log(self, mesaj):
        """Adauga mesaj in log cu timestamp."""
        timestamp = f"{int(self.ora_curenta):02d}:{int((self.ora_curenta % 1) * 60):02d}"
        self.log_mesaje.append(f"[{timestamp}] {mesaj}")
        if len(self.log_mesaje) > 15:
            self.log_mesaje.pop(0)

    def salveaza_raport_csv(self):
        """Export loguri in CSV."""
        with self.lock:
            nume_fisier = f"Raport_Tunel_{int(time.time())}.csv"
            try:
                with open(nume_fisier, mode='w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(["TIMESTAMP", "EVENIMENT"])
                    for intrare in self.log_mesaje:
                        parts = intrare.split("] ", 1)
                        if len(parts) == 2:
                            writer.writerow([parts[0].replace("[", ""), parts[1]])
                        else:
                            writer.writerow(["UNKNOWN", intrare])
                return nume_fisier
            except Exception as e:
                return None

    def get_stare_acces(self):
        """Verifica permisiuni acces."""
        if (self.nr_masini >= N_MAX_MASINI or self.incendiu or
                self.panica or self.blocaj_operator or self.nivel_noxe >= PRAG_CRITIC):
            return False
        return True

    def intrare_masina(self, id_senzor):
        with self.lock:
            if self.get_stare_acces():
                self.nr_masini += 1
                self.log(f"Senzor {id_senzor}: Intrare Auto. Total {self.nr_masini}")
                return True
            return False

    def iesire_masina(self, id_senzor):
        with self.lock:
            if self.nr_masini > 0:
                self.nr_masini -= 1
                self.log(f"Senzor {id_senzor}: Iesire Auto. Total {self.nr_masini}")

    def actualizeaza_mediu(self):
        """Motor fizic simulare (Gaz, Ventilatie, Timp)."""
        with self.lock:
            # 1. Avansare Timp
            self.ora_curenta += 0.05
            if self.ora_curenta >= 24.0: self.ora_curenta = 0.0

            # --- FIZICA GAZE ---

            # A. Emisii: 0.3% per masina
            emisii = self.nr_masini * 0.3

            # B. Evacuare
            if self.ventilatoare:
                evacuare = 4.5  # Ventilatie ON (Puternic)
            else:
                # Ventilatie OFF (Natural)
                if self.nr_masini == 0:
                    evacuare = 0.8  # Tunel gol (Curatare rapida)
                else:
                    evacuare = 0.1  # Tunel plin (Blocaj aer)

            # C. Bilant
            self.nivel_noxe = self.nivel_noxe + emisii - evacuare
            self.nivel_noxe = max(0.0, min(100.0, self.nivel_noxe))

            # Update Istoric
            self.istoric_noxe.append(self.nivel_noxe)
            self.istoric_noxe.pop(0)

            # Logica Histerezis
            if not self.ventilatoare and self.nivel_noxe > PRAG_VENTILATIE_ON:
                self.ventilatoare = True
                self.log("AUTOMATIZARE: Ventilatoare PORNITE (>70%)")
            elif self.ventilatoare and self.nivel_noxe < PRAG_VENTILATIE_OFF:
                self.ventilatoare = False
                self.log("AUTOMATIZARE: Ventilatoare OPRITE (<30%)")


# --- WORKERS (Simulare Senzori) ---
def worker_trafic_inteligent(monitor, id_s):
    """Genereaza trafic (Rush Hour)."""
    while True:
        ora = monitor.ora_curenta
        # Ore de varf: 07-10 si 17-19
        if (7 <= ora <= 10) or (17 <= ora <= 19):
            delay = random.uniform(0.5, 1.5)  # Intens
        else:
            delay = random.uniform(2.0, 5.0)  # Lejer
        time.sleep(delay)
        monitor.intrare_masina(id_s)


def worker_iesire(monitor, id_s):
    while True:
        time.sleep(random.uniform(2.0, 4.0))
        monitor.iesire_masina(id_s)


def worker_mediu(monitor):
    while True:
        time.sleep(0.2)  # Refresh fizica 5Hz
        monitor.actualizeaza_mediu()


def worker_incendiu(monitor):
    """Eveniment rar (background)."""
    while True:
        time.sleep(60)
        if random.random() < 0.15:  # 15% sansa
            with monitor.lock:
                if not monitor.incendiu:
                    monitor.incendiu = True
                    monitor.log("ALERTA: INCENDIU DETECTAT (SENZOR)!")
            time.sleep(15)
            with monitor.lock:
                monitor.incendiu = False
                monitor.log("INCENDIU STINS.")


# --- GUI: LOGIN SCREEN ---
class LoginScreen:
    def __init__(self, root):
        self.root = root
        self.root.title("SECURE ACCESS")
        self.root.geometry("400x500")
        self.root.configure(bg="#000000")
        self.success = False
        self.tries = 0

        frame = tk.Frame(root, bg="#000000")
        frame.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(frame, text="LOGIN", font=("Impact", 24), bg="black", fg=COLOR_ACCENT).pack(pady=20)

        tk.Label(frame, text="USERNAME:", font=("Consolas", 10), bg="black", fg="white").pack(anchor="w")
        self.entry_user = tk.Entry(frame, font=("Consolas", 12), bg="#222", fg=COLOR_TEXT, insertbackground="white")
        self.entry_user.pack(fill="x", pady=5)
        self.entry_user.insert(0, "admin")

        tk.Label(frame, text="PASSWORD:", font=("Consolas", 10), bg="black", fg="white").pack(anchor="w")
        self.entry_pass = tk.Entry(frame, font=("Consolas", 12), bg="#222", fg=COLOR_TEXT, insertbackground="white",
                                   show="*")
        self.entry_pass.pack(fill="x", pady=5)

        self.lbl_msg = tk.Label(frame, text="", font=("Arial", 9), bg="black", fg="red")
        self.lbl_msg.pack(pady=10)

        tk.Button(frame, text="AUTHENTICATE", bg=COLOR_ACCENT, fg="black", font=("Arial", 11, "bold"),
                  command=self.check_login).pack(fill="x", pady=20)
        tk.Label(root, text="UNAUTHORIZED ACCESS PROHIBITED", font=("Arial", 7), bg="black", fg="gray").pack(
            side="bottom", pady=10)

    def check_login(self):
        u = self.entry_user.get()
        p = self.entry_pass.get()

        if u == "admin" and p == "admin":
            if SOUND_AVAILABLE: threading.Thread(target=winsound.Beep, args=(2000, 150), daemon=True).start()
            self.success = True
            self.root.destroy()
        else:
            self.tries += 1
            if SOUND_AVAILABLE: threading.Thread(target=winsound.Beep, args=(500, 300), daemon=True).start()
            self.lbl_msg.config(text=f"ACCESS DENIED ({self.tries}/3)")
            if self.tries >= 3:
                messagebox.showerror("SECURITY ALERT", "System Lockdown.")
                self.root.destroy()


# --- GUI: DASHBOARD ---
class DashboardSCADA:
    def __init__(self, root, monitor):
        self.root = root
        self.monitor = monitor
        self.root.title("Tunnel Monitoring System")
        self.root.geometry("950x750")
        self.root.configure(bg=COLOR_BG)

        # Activare God Mode (F)
        self.root.bind('<f>', self.declanseaza_incendiu_manual)
        self.root.bind('<F>', self.declanseaza_incendiu_manual)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Horizontal.TProgressbar", background=COLOR_ACCENT, troughcolor=COLOR_PANEL,
                        bordercolor=COLOR_BG)

        # HEADER
        header = tk.Frame(root, bg=COLOR_PANEL, pady=10)
        header.pack(fill="x")
        self.lbl_title = tk.Label(header, text="TUNNEL CONTROL CENTER", font=("Impact", 24), bg=COLOR_PANEL, fg="white")
        self.lbl_title.pack(side="left", padx=20)
        self.lbl_ceas = tk.Label(header, text="00:00", font=("Consolas", 24, "bold"), bg="black", fg=COLOR_ACCENT,
                                 width=8)
        self.lbl_ceas.pack(side="right", padx=20)

        # MAIN
        main_frame = tk.Frame(root, bg=COLOR_BG)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # STANGA
        left_panel = tk.Frame(main_frame, bg=COLOR_BG, width=300)
        left_panel.pack(side="left", fill="y", padx=5)

        # Status
        f_status = tk.LabelFrame(left_panel, text="SYSTEM STATUS", bg=COLOR_BG, fg="white", font=("Arial", 10, "bold"))
        f_status.pack(fill="x", pady=5)
        self.canvas_led = tk.Canvas(f_status, width=50, height=50, bg=COLOR_BG, highlightthickness=0)
        self.canvas_led.pack(pady=5)
        self.led = self.canvas_led.create_oval(10, 10, 40, 40, fill="green")
        self.lbl_status_txt = tk.Label(f_status, text="NORMAL", font=("Arial", 16, "bold"), bg=COLOR_BG, fg=COLOR_TEXT)
        self.lbl_status_txt.pack(pady=5)

        # Trafic
        f_trafic = tk.LabelFrame(left_panel, text="TRAFIC LIVE", bg=COLOR_BG, fg="white", font=("Arial", 10, "bold"))
        f_trafic.pack(fill="x", pady=5)
        self.lbl_cars = tk.Label(f_trafic, text="0/12", font=("Digital-7", 35), bg="black", fg=COLOR_WARN)
        self.lbl_cars.pack(fill="x", padx=5, pady=5)

        # Butoane
        self.btn_panic = tk.Button(left_panel, text="PANIC LOCK", bg=COLOR_ALERT, fg="white",
                                   font=("Arial", 12, "bold"), command=self.toggle_panica, height=2)
        self.btn_panic.pack(fill="x", pady=10)
        self.btn_block = tk.Button(left_panel, text="BLOCARE OPERATOR", bg=COLOR_PANEL, fg="white", font=("Arial", 10),
                                   command=self.toggle_blocaj)
        self.btn_block.pack(fill="x", pady=2)
        self.btn_export = tk.Button(left_panel, text="EXPORT RAPORT (CSV)", bg="#444", fg="white", font=("Arial", 9),
                                    command=self.export_csv)
        self.btn_export.pack(fill="x", pady=10)

        tk.Label(left_panel, text="[F] - Simulare Incendiu", bg=COLOR_BG, fg="#333", font=("Arial", 8)).pack(
            side="bottom")

        # DREAPTA
        right_panel = tk.Frame(main_frame, bg=COLOR_BG)
        right_panel.pack(side="right", fill="both", expand=True, padx=5)
        tk.Label(right_panel, text="MONITORIZARE CALITATE AER (NOxe %)", bg=COLOR_BG, fg="white",
                 font=("Arial", 12)).pack(anchor="w")

        self.fig = Figure(figsize=(5, 4), dpi=100, facecolor=COLOR_BG)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(COLOR_PANEL)
        self.ax.tick_params(colors='white')
        self.ax.spines['bottom'].set_color('white')
        self.ax.spines['left'].set_color('white')
        self.line, = self.ax.plot([], [], color=COLOR_ACCENT, linewidth=2)
        self.ax.set_ylim(0, 100)
        self.ax.grid(True, color="#444", linestyle='--')
        self.canvas = FigureCanvasTkAgg(self.fig, master=right_panel)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.lbl_vent = tk.Label(right_panel, text="VENTILATIE: OFF", font=("Arial", 12, "bold"), bg=COLOR_BG,
                                 fg="gray")
        self.lbl_vent.pack(anchor="e", pady=5)

        # JOS (LOG)
        f_log = tk.LabelFrame(root, text="EVENT LOG", bg=COLOR_BG, fg="white")
        f_log.pack(fill="x", padx=10, pady=5)
        self.list_log = tk.Listbox(f_log, height=6, bg="black", fg=COLOR_ACCENT, font=("Consolas", 9), borderwidth=0)
        self.list_log.pack(fill="both")

        self.update_ui()

    # --- GOD MODE: INCENDIU MANUAL ---
    def declanseaza_incendiu_manual(self, event):
        threading.Thread(target=self._sim_fire, daemon=True).start()

    def _sim_fire(self):
        with self.monitor.lock:
            if not self.monitor.incendiu:
                self.monitor.incendiu = True
                self.monitor.log("DEMO: INCENDIU FORTAT (MANUAL)!")

        time.sleep(12)

        with self.monitor.lock:
            self.monitor.incendiu = False
            self.monitor.log("DEMO: INCENDIU OPRIT.")

    def toggle_panica(self):
        with self.monitor.lock:
            self.monitor.panica = not self.monitor.panica
            if self.monitor.panica:
                self.monitor.log("BUTON PANICA ACTIONAT!")
            else:
                self.monitor.log("ALARMA RESETATA MANUAL.")

    def toggle_blocaj(self):
        with self.monitor.lock:
            self.monitor.blocaj_operator = not self.monitor.blocaj_operator
            self.monitor.log("COMANDA OPERATOR: Blocaj Acces")

    def export_csv(self):
        f = self.monitor.salveaza_raport_csv()
        if f:
            messagebox.showinfo("Export Reusit", f"Raport salvat in:\n{f}")
        else:
            messagebox.showerror("Eroare", "Nu s-a putut salva fisierul.")

    def update_ui(self):
        with self.monitor.lock:
            ora_int = int(self.monitor.ora_curenta)
            min_int = int((self.monitor.ora_curenta % 1) * 60)
            self.lbl_ceas.config(text=f"{ora_int:02d}:{min_int:02d}")
            self.lbl_cars.config(text=f"{self.monitor.nr_masini}/{N_MAX_MASINI}")

            if self.monitor.incendiu:
                stare, cul = "INCENDIU", COLOR_ALERT
            elif self.monitor.panica:
                stare, cul = "ALARMA", COLOR_ALERT
            elif self.monitor.blocaj_operator:
                stare, cul = "BLOCAT", COLOR_WARN
            elif self.monitor.nivel_noxe >= PRAG_CRITIC:
                stare, cul = "TOXIC", COLOR_ALERT
            elif self.monitor.nr_masini >= N_MAX_MASINI:
                stare, cul = "PLIN", COLOR_WARN
            else:
                stare, cul = "OPTIM", COLOR_TEXT

            self.lbl_status_txt.config(text=stare, fg=cul)
            self.canvas_led.itemconfig(self.led, fill=cul)

            if self.monitor.ventilatoare:
                self.lbl_vent.config(text="VENTILATIE: ON (TURBO)", fg=COLOR_ACCENT)
            else:
                self.lbl_vent.config(text="VENTILATIE: OFF", fg="gray")

            if self.monitor.panica:
                self.btn_panic.config(bg="white", fg="red", text="RESET ALARM")
            else:
                self.btn_panic.config(bg=COLOR_ALERT, fg="white", text="PANIC LOCK")

            self.list_log.delete(0, tk.END)
            for msg in reversed(self.monitor.log_mesaje):
                self.list_log.insert(tk.END, msg)

            data = self.monitor.istoric_noxe
            x_data = range(len(data))
            self.line.set_data(x_data, data)
            self.ax.set_xlim(0, len(data))
            if data[-1] > 70:
                self.line.set_color(COLOR_ALERT)
            elif data[-1] > 50:
                self.line.set_color(COLOR_WARN)
            else:
                self.line.set_color(COLOR_ACCENT)
            self.canvas.draw()

            if SOUND_AVAILABLE:
                if self.monitor.incendiu or self.monitor.panica:
                    threading.Thread(target=winsound.Beep, args=(1000, 100), daemon=True).start()
                elif self.monitor.nivel_noxe >= PRAG_CRITIC:
                    threading.Thread(target=winsound.Beep, args=(500, 100), daemon=True).start()

        self.root.after(100, self.update_ui)


if __name__ == "__main__":
    mon = MonitorTunel()

    # 1. Login
    login_root = tk.Tk()
    login_app = LoginScreen(login_root)
    login_root.mainloop()

    # 2. Dashboard dupa login
    if login_app.success:
        tasks = [
            threading.Thread(target=worker_trafic_inteligent, args=(mon, 1), daemon=True),
            threading.Thread(target=worker_trafic_inteligent, args=(mon, 2), daemon=True),
            threading.Thread(target=worker_iesire, args=(mon, 1), daemon=True),
            threading.Thread(target=worker_iesire, args=(mon, 2), daemon=True),
            threading.Thread(target=worker_mediu, args=(mon,), daemon=True),
            threading.Thread(target=worker_incendiu, args=(mon,), daemon=True)
        ]
        for t in tasks: t.start()

        dash_root = tk.Tk()
        app = DashboardSCADA(dash_root, mon)
        dash_root.mainloop()
    else:
        print("Sistem oprit de utilizator.")
# ======================================================================
#  Pomodoro App v5.7 (Version Finale - Correction Permissions) en Python avec Tkinter
#  Correction : Utilisation du dossier AppData pour les fichiers de données
#  Dépendances : pip install pystray pillow win10toast
# ======================================================================
import tkinter as tk
from tkinter import font, messagebox
import threading
import sys
import os
import json
from datetime import date
from PIL import Image, ImageTk, ImageDraw, ImageFont
import logging

# --- NOUVELLE FONCTION pour gérer le chemin des données utilisateur ---
def get_app_data_path(file_name):
    """ Retourne le chemin complet vers un fichier dans le dossier AppData de l'application. """
    # Le nom du dossier pour votre application dans AppData
    app_name = "FocusPomodoro"
    
    # Obtenir le chemin vers AppData\Roaming
    # Sur Windows: C:\Users\<user>\AppData\Roaming
    # Sur macOS: /Users/<user>/Library/Application Support
    # Sur Linux: /home/<user>/.config ou /home/<user>/.local/share
    if sys.platform == "win32":
        data_dir = os.path.join(os.environ['APPDATA'], app_name)
    elif sys.platform == "darwin":
        data_dir = os.path.join(os.path.expanduser('~/Library/Application Support'), app_name)
    else: # Linux
        data_dir = os.path.join(os.path.expanduser('~/.config'), app_name)
        
    # Créer le dossier s'il n'existe pas
    os.makedirs(data_dir, exist_ok=True)
    
    return os.path.join(data_dir, file_name)

# --- FONCTION pour les ressources internes (icônes, etc.) ---
def resource_path(relative_path):
    """ Obtenir le chemin absolu vers une ressource groupée avec l'app. """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

# --- MODIFICATION : Configuration du logging pour utiliser AppData ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(get_app_data_path("pomodoro.log")), # Utilise le nouveau chemin
        logging.StreamHandler(sys.stdout)
    ]
)

try:
    import pystray
except ImportError:
    messagebox.showerror("Dépendance Manquante", "Veuillez installer 'pystray' avec la commande : pip install pystray")
    sys.exit(1)

try:
    import winsound
    SOUND_ENABLED = True
except ImportError:
    logging.info("Module 'winsound' non trouvé. Les sons seront désactivés.")
    SOUND_ENABLED = False

# --- DÉFINITION DES THÈMES ---
THEMES = {
    "dark": {
        "bg_main": "#1D1D1D", "fg_main": "white",
        "bg_work": "#DB4437", "bg_short_break": "#4285F4", "bg_long_break": "#0F9D58",
        "bg_btn_start": "#4CAF50", "bg_btn_pause": "#ff8800", "bg_btn_neutral": "#6C757D",
        "bg_task": "#2D2D2D", "bg_task_item": "#3D3D3D", "fg_task_done": "#28a745"
    },
    "light": {
        "bg_main": "#F5F5F5", "fg_main": "#3D3D3D",
        "bg_work": "#DB4437", "bg_short_break": "#4285F4", "bg_long_break": "#0F9D58",
        "bg_btn_start": "#4CAF50", "bg_btn_pause": "#ff9800", "bg_btn_neutral": "#9E9E9E",
        "bg_task": "#FFFFFF", "bg_task_item": "#EEEEEE", "fg_task_done": "#28a745"
    }
}

# --- Classes pour la gestion des données ---
class DataManager:
    def __init__(self):
        # --- MODIFICATION : Utilisation de AppData pour les fichiers de données ---
        self.data_file = get_app_data_path("data.json")
        self.stats_file = get_app_data_path("stats.json")
    
    def load_data(self):
        try:
            with open(self.data_file, "r") as f:
                data = json.load(f)
                settings = data.get("settings", {})
                return {
                    "work_time_min": settings.get("work_time_min", 25),
                    "short_break_min": settings.get("short_break_min", 5),
                    "long_break_min": settings.get("long_break_min", 15),
                    "pomodoros_per_cycle": settings.get("pomodoros_per_cycle", 4),
                    "theme": settings.get("theme", "dark"),
                    "auto_transition": settings.get("auto_transition", True),
                    "tasks": data.get("tasks", [])
                }
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "work_time_min": 25,
                "short_break_min": 5,
                "long_break_min": 15,
                "pomodoros_per_cycle": 4,
                "theme": "dark",
                "auto_transition": True,
                "tasks": []
            }
    
    def save_data(self, data):
        try:
            with open(self.data_file, "w") as f:
                json.dump({
                    "settings": {
                        "work_time_min": data["work_time_min"],
                        "short_break_min": data["short_break_min"],
                        "long_break_min": data["long_break_min"],
                        "pomodoros_per_cycle": data["pomodoros_per_cycle"],
                        "theme": data["theme"],
                        "auto_transition": data["auto_transition"]
                    },
                    "tasks": data["tasks"]
                }, f, indent=4)
        except Exception as e:
            logging.error(f"Erreur sauvegarde données: {e}")
            messagebox.showerror("Erreur", f"Échec de sauvegarde: {str(e)}")
    
    def load_stats(self):
        try:
            with open(self.stats_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def save_stats(self, stats):
        try:
            with open(self.stats_file, "w") as f:
                json.dump(stats, f, indent=4)
        except Exception as e:
            logging.error(f"Erreur sauvegarde stats: {e}")
            messagebox.showerror("Erreur", f"Échec de sauvegarde stats: {str(e)}")

# --- Classes pour la logique du minuteur ---
class TimerLogic:
    def __init__(self, work_time_min, short_break_min, long_break_min, pomodoros_per_cycle):
        self.work_time_sec = work_time_min * 60
        self.short_break_time_sec = short_break_min * 60
        self.long_break_time_sec = long_break_min * 60
        self.pomodoros_per_cycle = pomodoros_per_cycle
        self.reset()
    
    def reset(self):
        self.current_time_sec = self.work_time_sec
        self.pomodoro_count = 0
        self.is_running = False
        self.is_paused = False
        self.last_state = "stopped"
    
    def start_session(self, session_type):
        self.last_state = session_type
        self.is_running = True
        self.is_paused = False
        
        if session_type == "work":
            self.current_time_sec = self.work_time_sec
        elif session_type == "short_break":
            self.current_time_sec = self.short_break_time_sec
        elif session_type == "long_break":
            self.current_time_sec = self.long_break_time_sec
    
    def pause(self):
        if self.is_running and not self.is_paused:
            self.is_paused = True
    
    def resume(self):
        if self.is_running and self.is_paused:
            self.is_paused = False
    
    def tick(self):
        if self.is_running and not self.is_paused and self.current_time_sec > 0:
            self.current_time_sec -= 1
            return True
        return False
    
    def get_time_str(self):
        minutes, seconds = divmod(self.current_time_sec, 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    def determine_next_session_type(self):
        if self.last_state == 'work':
            if self.pomodoro_count > 0 and self.pomodoro_count % self.pomodoros_per_cycle == 0:
                return 'long_break'
            else:
                return 'short_break'
        else:
            if self.last_state == 'long_break':
                self.pomodoro_count = 0
            return 'work'

# --- Fenêtre de gestion des tâches ---
class TasksWindow(tk.Toplevel):
    def __init__(self, parent, icon_photo_image=None, close_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.theme = THEMES[parent.current_theme]
        self.close_callback = close_callback
        if icon_photo_image: self.iconphoto(False, icon_photo_image)
        self.title("Tâches de la session")
        self.geometry("420x450")
        self.configure(bg=self.theme["bg_task"])
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close_callback)

        self.task_font = font.Font(family="Segoe UI", size=11)
        self.task_font_strikethrough = font.Font(family="Segoe UI", size=11, overstrike=True)

        add_frame = tk.Frame(self, bg=self.theme["bg_task"])
        add_frame.pack(pady=10, padx=10, fill="x")
        self.task_entry = tk.Entry(add_frame, bg=self.theme["bg_task_item"], fg=self.theme["fg_main"], insertbackground=self.theme["fg_main"], relief="flat")
        self.task_entry.pack(side="left", expand=True, fill="x", ipady=5)
        self.task_entry.bind("<Return>", lambda e: self.add_task())
        add_button = tk.Button(add_frame, text="Ajouter", command=self.add_task, relief="flat", bg="#4CAF50", fg="white")
        add_button.pack(side="left", padx=(5, 0), ipady=1)

        canvas_frame = tk.Frame(self, bg=self.theme["bg_task"])
        canvas_frame.pack(pady=10, padx=10, expand=True, fill="both")
        self.canvas = tk.Canvas(canvas_frame, bg=self.theme["bg_task"], highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=self.theme["bg_task"])

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.task_widgets = []
        self.load_tasks()

    def add_task(self):
        task_text = self.task_entry.get().strip()
        if not task_text: return
        task_data = {'text': task_text, 'done': False}
        self.parent.tasks.append(task_data)
        self.parent.save_data()
        self.task_entry.delete(0, tk.END)
        self.create_task_widget(task_data)

    def create_task_widget(self, task_data):
        task_frame = tk.Frame(self.scrollable_frame, bg=self.theme["bg_task_item"])
        var = tk.BooleanVar(value=task_data['done'])
        label = tk.Label(task_frame, text=task_data['text'], bg=self.theme["bg_task_item"], fg=self.theme["fg_main"], font=self.task_font, padx=5, anchor="w")
        label.pack(side="left", expand=True, fill="x")
        check = tk.Checkbutton(task_frame, variable=var, bg=self.theme["bg_task_item"], activebackground=self.theme["bg_task_item"], relief="flat", highlightthickness=0, borderwidth=0, selectcolor="#fafafa")
        check.pack(side="left")
        delete_btn = tk.Button(task_frame, text="🗑️", bg=self.theme["bg_task_item"], fg="#ff6666", relief="flat", command=lambda d=task_data: self.delete_task(d))
        delete_btn.pack(side="right")

        def toggle_task():
            task_data['done'] = var.get()
            self.update_task_display(label, task_data)
            self.parent.save_data()
        check.config(command=toggle_task)
        self.update_task_display(label, task_data)
        task_frame.pack(fill="x", pady=2, padx=2)
        self.task_widgets.append({'frame': task_frame, 'data': task_data})

    def update_task_display(self, label, task_data):
        if task_data['done']:
            label.config(font=self.task_font_strikethrough, fg=self.theme["fg_task_done"])
        else:
            label.config(font=self.task_font, fg=self.theme["fg_main"])

    def delete_task(self, task_to_delete):
        self.parent.tasks.remove(task_to_delete)
        self.parent.save_data()
        self.redraw_tasks()

    def redraw_tasks(self):
        for widget_info in self.task_widgets: widget_info['frame'].destroy()
        self.task_widgets.clear()
        self.load_tasks()

    def load_tasks(self):
        for task_data in self.parent.tasks: self.create_task_widget(task_data)

# --- FENÊTRE "À PROPOS" ---
class AboutWindow(tk.Toplevel):
    def __init__(self, parent, icon_photo_image=None, close_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.theme = THEMES[parent.current_theme]
        self.close_callback = close_callback
        if icon_photo_image: self.iconphoto(False, icon_photo_image)
        self.title("À Propos de Focus Pomodoro")
        self.geometry("350x220")
        self.configure(bg=self.theme["bg_task"])
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close_callback)

        try:
            logo_image = Image.open(resource_path("logo.png"))
            logo_image = logo_image.resize((250, int(250 * logo_image.height / logo_image.width)), Image.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(logo_image)
            logo_label = tk.Label(self, image=self.logo_photo, bg=self.theme["bg_task"])
            logo_label.pack(pady=1)
        except Exception:
            logo_label = tk.Label(self, text="Logo introuvable", bg=self.theme["bg_task"], fg="#FF6666")
            logo_label.pack(pady=2)

        tk.Label(self, text="Développé par Lokman", bg=self.theme["bg_task"], fg=self.theme["fg_main"], font=("Segoe UI", 12, "bold")).pack()
        tk.Label(self, text="Version 1.2 ", bg=self.theme["bg_task"], fg=self.theme["fg_main"], font=("Segoe UI", 10)).pack()
        tk.Label(self, text="© 2025 - Alger", bg=self.theme["bg_task"], fg=self.theme["fg_main"], font=("Segoe UI", 10)).pack(pady=(0, 2))
        separator = tk.Frame(self, height=1, width=300, bg="#555555")
        separator.pack()
        ok_button = tk.Button(self, text="OK", command=self.close_callback, relief="flat", bg="#0F9D58", fg="white", width=10)
        ok_button.pack(pady=10)

# --- FENÊTRE STATISTIQUES ---
class StatsWindow(tk.Toplevel):
    def __init__(self, parent, icon_photo_image=None, close_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.theme = THEMES[parent.current_theme]
        self.close_callback = close_callback
        if icon_photo_image: self.iconphoto(False, icon_photo_image)
        self.title("Statistiques de Productivité")
        self.geometry("400x450")
        self.configure(bg=self.theme["bg_task"])
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close_callback)
        self._build_ui()

    def _build_ui(self):
        """Construit ou reconstruit l'interface utilisateur de la fenêtre."""
        for widget in self.winfo_children():
            widget.destroy()

        main_frame = tk.Frame(self, bg=self.theme["bg_task"], padx=10, pady=10)
        main_frame.pack(expand=True, fill="both")

        tk.Label(main_frame, text="Statistiques Globales", bg=self.theme["bg_task"], fg=self.theme["fg_main"], font=("Segoe UI", 16, "bold")).pack(pady=(0, 15))

        tasks_stats_frame = tk.Frame(main_frame, bg=self.theme["bg_task_item"], relief="solid", borderwidth=1, bd=1)
        tasks_stats_frame.pack(pady=10, padx=10, fill="x")
        
        completed_tasks = sum(1 for task in self.parent.tasks if task['done'])
        pending_tasks = len(self.parent.tasks) - completed_tasks

        tk.Label(tasks_stats_frame, text=f"Tâches complétées : {completed_tasks}", bg=self.theme["bg_task_item"], fg=self.theme["fg_main"], font=("Segoe UI", 11)).pack(pady=5, padx=10, anchor="w")
        tk.Label(tasks_stats_frame, text=f"Tâches en attente : {pending_tasks}", bg=self.theme["bg_task_item"], fg=self.theme["fg_main"], font=("Segoe UI", 11)).pack(pady=5, padx=10, anchor="w")

        pomodoro_frame = tk.Frame(main_frame, bg=self.theme["bg_task_item"], relief="solid", borderwidth=1, bd=1)
        pomodoro_frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        tk.Label(pomodoro_frame, text="Pomodoros par Jour", bg=self.theme["bg_task_item"], fg=self.theme["fg_main"], font=("Segoe UI", 12, "bold")).pack(pady=(5,0))
        
        stats_text_frame = tk.Frame(pomodoro_frame, bg=self.theme["bg_task_item"])
        stats_text_frame.pack(expand=True, fill="both", padx=10, pady=10)

        stats_text = tk.Text(stats_text_frame, bg=self.theme["bg_task_item"], fg=self.theme["fg_main"], font=("Segoe UI", 11), relief="flat", highlightthickness=0)
        scrollbar = tk.Scrollbar(stats_text_frame, orient="vertical", command=stats_text.yview)
        stats_text.configure(yscrollcommand=scrollbar.set)
        stats_text.pack(side="left", expand=True, fill="both")
        scrollbar.pack(side="right", fill="y")

        stats_data = self.parent.stats
        sorted_dates = sorted(stats_data.keys(), reverse=True)
        
        display_text = ""
        total_pomodoros = 0
        if not stats_data:
            display_text = "Aucun pomodoro complété."
        else:
            for stat_date in sorted_dates:
                count = stats_data[stat_date]
                total_pomodoros += count
                plural = 's' if count > 1 else ''
                display_text += f"{stat_date}: {count} Pomodoro{plural}\n"

        stats_text.insert(tk.END, display_text)
        stats_text.config(state="disabled")

        bottom_frame = tk.Frame(main_frame, bg=self.theme["bg_task"])
        bottom_frame.pack(pady=(10, 0), fill="x")

        tk.Label(bottom_frame, text=f"Total : {total_pomodoros} Pomodoros", bg=self.theme["bg_task"], fg=self.theme["fg_main"], font=("Segoe UI", 12, "italic")).pack(side="left", padx=10)
        
        clear_button = tk.Button(bottom_frame, text="Tout effacer", command=self._confirm_clear_stats, relief="flat", bg="#DB4437", fg="white")
        clear_button.pack(side="right", padx=10)

    def _confirm_clear_stats(self):
        if messagebox.askyesno("Confirmer", "Voulez-vous vraiment effacer toutes les statistiques de pomodoros ? Cette action est irréversible.", parent=self):
            self.parent.clear_stats()
            self._build_ui()

# --- Fenêtre des paramètres ---
class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, icon_photo_image=None, close_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.theme = THEMES[parent.current_theme]
        self.close_callback = close_callback
        if icon_photo_image: self.iconphoto(False, icon_photo_image)
        self.title("Paramètres")
        self.geometry("380x280")
        self.configure(bg=self.theme["bg_task"])
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close_callback)
        
        self.work_var = tk.StringVar(value=str(parent.work_time_min))
        self.short_break_var = tk.StringVar(value=str(parent.short_break_min))
        self.long_break_var = tk.StringVar(value=str(parent.long_break_min))
        self.sessions_var = tk.StringVar(value=str(parent.pomodoros_per_cycle))
        self.theme_var = tk.StringVar(value=parent.current_theme)
        self.auto_transition_var = tk.BooleanVar(value=parent.auto_transition)

        main_frame = tk.Frame(self, bg=self.theme["bg_task"], padx=10, pady=10)
        main_frame.pack(expand=True, fill="both")
        
        tk.Label(main_frame, text="Travail (min):", bg=self.theme["bg_task"], fg=self.theme["fg_main"]).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        work_entry = tk.Entry(main_frame, textvariable=self.work_var)
        work_entry.grid(row=0, column=1, padx=10, pady=5)
        
        tk.Label(main_frame, text="Pause Courte (min):", bg=self.theme["bg_task"], fg=self.theme["fg_main"]).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        short_entry = tk.Entry(main_frame, textvariable=self.short_break_var)
        short_entry.grid(row=1, column=1, padx=10, pady=5)
        
        tk.Label(main_frame, text="Pause Longue (min):", bg=self.theme["bg_task"], fg=self.theme["fg_main"]).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        long_entry = tk.Entry(main_frame, textvariable=self.long_break_var)
        long_entry.grid(row=2, column=1, padx=10, pady=5)
        
        tk.Label(main_frame, text="Sessions par cycle:", bg=self.theme["bg_task"], fg=self.theme["fg_main"]).grid(row=3, column=0, padx=10, pady=5, sticky="w")
        sessions_entry = tk.Entry(main_frame, textvariable=self.sessions_var)
        sessions_entry.grid(row=3, column=1, padx=10, pady=5)

        tk.Label(main_frame, text="Thème:", bg=self.theme["bg_task"], fg=self.theme["fg_main"]).grid(row=4, column=0, padx=10, pady=5, sticky="w")
        theme_frame = tk.Frame(main_frame, bg=self.theme["bg_task"])
        tk.Radiobutton(theme_frame, text="Sombre", variable=self.theme_var, value="dark", bg=self.theme["bg_task"], fg=self.theme["fg_main"], selectcolor=self.theme["bg_task_item"], activebackground=self.theme["bg_task"], activeforeground=self.theme["fg_main"]).pack(side="left")
        tk.Radiobutton(theme_frame, text="Clair", variable=self.theme_var, value="light", bg=self.theme["bg_task"], fg=self.theme["fg_main"], selectcolor=self.theme["bg_task_item"], activebackground=self.theme["bg_task"], activeforeground=self.theme["fg_main"]).pack(side="left")
        theme_frame.grid(row=4, column=1, padx=10, pady=5, sticky="w")

        tk.Label(main_frame, text="Transition auto:", bg=self.theme["bg_task"], fg=self.theme["fg_main"]).grid(row=5, column=0, padx=10, pady=5, sticky="w")
        auto_trans_check = tk.Checkbutton(main_frame, text="Démarrage auto.", variable=self.auto_transition_var, bg=self.theme["bg_task"], fg=self.theme["fg_main"], selectcolor=self.theme["bg_task_item"], activebackground=self.theme["bg_task"], activeforeground=self.theme["fg_main"], relief="flat", highlightthickness=0)
        auto_trans_check.grid(row=5, column=1, padx=10, pady=5, sticky="w")


        button_frame = tk.Frame(main_frame, bg=self.theme["bg_task"])
        button_frame.grid(row=6, columnspan=2, pady=10)
        tk.Button(button_frame, text="Enregistrer", command=self.save_settings).pack(side="left", padx=5)
        tk.Button(button_frame, text="Annuler", command=self.close_callback).pack(side="left", padx=5)

    def save_settings(self):
        try:
            work = int(self.work_var.get())
            short = int(self.short_break_var.get())
            long = int(self.long_break_var.get())
            sessions = int(self.sessions_var.get())
            
            if not (1 <= work <= 60 and 1 <= short <= 30 and 1 <= long <= 60 and 1 <= sessions <= 10):
                raise ValueError("Valeurs hors limites")
                
            self.parent.work_time_min = work
            self.parent.short_break_min = short
            self.parent.long_break_min = long
            self.parent.pomodoros_per_cycle = sessions
            self.parent.auto_transition = self.auto_transition_var.get()
            
            new_theme = self.theme_var.get()
            if self.parent.current_theme != new_theme:
                self.parent.current_theme = new_theme
                self.parent.apply_theme()

            self.parent.save_data()
            self.parent.reset_to_initial_state()
            self.close_callback()
        except ValueError as e:
            logging.error(f"Erreur paramètres: {e}")
            messagebox.showerror("Erreur", "Veuillez entrer des nombres valides. (Travail: 1-60, Pauses: 1-60, Cycle: 1-10)", parent=self)

# --- Application Principale ---
class PomodoroApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Focus Pomodoro")
        self.data_manager = DataManager()
        self.tray_icon_cache = {}
        
        data = self.data_manager.load_data()
        self.work_time_min = data["work_time_min"]
        self.short_break_min = data["short_break_min"]
        self.long_break_min = data["long_break_min"]
        self.pomodoros_per_cycle = data["pomodoros_per_cycle"]
        self.current_theme = data["theme"]
        self.auto_transition = data["auto_transition"]
        self.tasks = data["tasks"]
        self.stats = self.data_manager.load_stats()
        
        self.timer = TimerLogic(
            self.work_time_min,
            self.short_break_min,
            self.long_break_min,
            self.pomodoros_per_cycle
        )
        
        self.theme = THEMES[self.current_theme]

        try:
            # Utilise resource_path pour les icônes qui sont des ressources
            icon_pil_image = Image.open(resource_path('Icon.png'))
            self.icon_photo_image = ImageTk.PhotoImage(icon_pil_image)
            self.iconphoto(False, self.icon_photo_image)
        except Exception as e:
            logging.warning(f"Icon.png non trouvé: {e}")

        self.geometry("560x480")
        self.minsize(550, 400)
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.bind("<Unmap>", self.on_unmap)
        self.hiding_to_tray = False
        self.tasks_window = None
        self.settings_window = None
        self.about_window = None
        self.stats_window = None
        self._timer_job, self.tray_icon = None, None
        self.title_font = font.Font(family="Segoe UI", size=28)
        self.timer_font = font.Font(family="Segoe UI Light", size=110, weight="bold")
        self.button_font = font.Font(family="Segoe UI", size=14)
        self.icon_button_font = font.Font(family="Segoe UI", size=18)
        self._create_widgets()
        self.reset_to_initial_state()

    def _create_widgets(self):
        self.main_frame = tk.Frame(self)
        self.main_frame.pack(expand=True, fill="both", padx=10, pady=5)
        self.top_button_frame = tk.Frame(self.main_frame)
        self.top_button_frame.pack(side="top", anchor="e", pady=(5, 0))
        self.tasks_button = tk.Button(self.top_button_frame, text="📝", font=self.icon_button_font, command=self.open_tasks, relief="flat", borderwidth=0, padx=5)
        self.tasks_button.pack(side="left")
        self.stats_button = tk.Button(self.top_button_frame, text="📊", font=self.icon_button_font, command=self.open_stats, relief="flat", borderwidth=0, padx=5)
        self.stats_button.pack(side="left")
        self.settings_button = tk.Button(self.top_button_frame, text="⚙️", font=self.icon_button_font, command=self.open_settings, relief="flat", borderwidth=0, padx=5)
        self.settings_button.pack(side="left")
        self.about_button = tk.Button(self.top_button_frame, text="ℹ️", font=self.icon_button_font, command=self.open_about, relief="flat", borderwidth=0, padx=5)
        self.about_button.pack(side="left")
        self.session_title_label = tk.Label(self.main_frame, text="Prêt à commencer ?", font=self.title_font)
        self.session_title_label.pack(pady=(0, 10))
        self.timer_label = tk.Label(self.main_frame, text="25:00", font=self.timer_font)
        self.timer_label.pack(expand=True, fill="both")
        self.cycle_indicator_frame = tk.Frame(self.main_frame)
        self.cycle_indicator_frame.pack(pady=10)
        self.button_frame = tk.Frame(self.main_frame)
        self.button_frame.pack(pady=(10, 20))
        self.start_pause_button = tk.Button(self.button_frame, text="Démarrer", font=self.button_font, command=self.start_pause_button_click, relief="flat", borderwidth=0, width=12, height=1)
        self.start_pause_button.pack(side="left", padx=5)
        self.reset_button = tk.Button(self.button_frame, text="Réinitialiser", font=self.button_font, command=self.reset_button_click, relief="flat", borderwidth=0, width=12, height=1)
        self.reset_button.pack(side="left", padx=5)
        self.skip_button = tk.Button(self.button_frame, text="Passer", font=self.button_font, command=self.skip_button_click, relief="flat", borderwidth=0, width=12, height=1)
        self.skip_button.pack(side="left", padx=5)

    def save_data(self):
        data = {
            "work_time_min": self.work_time_min,
            "short_break_min": self.short_break_min,
            "long_break_min": self.long_break_min,
            "pomodoros_per_cycle": self.pomodoros_per_cycle,
            "theme": self.current_theme,
            "auto_transition": self.auto_transition,
            "tasks": self.tasks
        }
        self.data_manager.save_data(data)

    def save_stats(self):
        self.data_manager.save_stats(self.stats)

    def log_completed_pomodoro(self):
        today = str(date.today())
        self.stats[today] = self.stats.get(today, 0) + 1
        self.save_stats()
        
    def clear_stats(self):
        self.stats.clear()
        self.save_stats()
        
    def play_sound(self, sound_type):
        if not SOUND_ENABLED: return
        def _play():
            try:
                if sound_type == "start": winsound.Beep(800, 100)
                elif sound_type == "warning": winsound.Beep(1200, 250)
                elif sound_type == "end_session": winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)
            except Exception as e: logging.error(f"Erreur son: {e}")
        threading.Thread(target=_play, daemon=True).start()

    def start_pause_button_click(self):
        if self.timer.is_paused: 
            self.resume_timer()
        elif self.timer.is_running: 
            self.pause_timer()
        else:
            self.play_sound("start")
            self.hide_to_tray()
            session_to_start = 'work' if self.timer.last_state in ['stopped', 'short_break', 'long_break'] else self.timer.last_state
            self.start_session(session_to_start)

    def reset_button_click(self):
        if self._timer_job: 
            self.after_cancel(self._timer_job)
        self.reset_to_initial_state()

    def skip_button_click(self):
        if self._timer_job: 
            self.after_cancel(self._timer_job)
        self.play_sound("end_session")
        if self.timer.last_state == 'work': 
            self.timer.pomodoro_count += 1
            self.log_completed_pomodoro()
        next_state = self.timer.determine_next_session_type()
        if self.auto_transition:
            self.start_session(next_state)
        else:
            self.prepare_next_session(next_state)

    def handle_session_end(self):
        self.timer.is_running = False
        self.play_sound("end_session")

        if self.timer.last_state == 'work':
            self.timer.pomodoro_count += 1
            self.log_completed_pomodoro()
        
        self.update_cycle_indicator()
        
        if not self.auto_transition and self.state() == 'withdrawn': 
            self.show_window()
            self.lift()

        next_state = self.timer.determine_next_session_type()
        
        message = ""
        if next_state == "work": 
            message = "Pause terminée. Au travail !"
        elif next_state == "short_break": 
            message = "Session de travail terminée. C'est l'heure de la pause courte !"
        else: 
            message = f"Excellent ! Cycle de {self.pomodoros_per_cycle} sessions terminé. Profitez de votre pause longue !"
        
        self.show_notification("Focus Pomodoro - C'est l'heure de changer !", message)
        
        if self.auto_transition:
            self.start_session(next_state)
        else:
            self.prepare_next_session(next_state)

    def prepare_next_session(self, session_type):
        self.timer.last_state = session_type
        self.timer.is_running = True
        self.timer.is_paused = True
        if session_type == "work":
            self.timer.current_time_sec = self.timer.work_time_sec
            title, color_key = "Travail", "bg_work"
        elif session_type == "short_break":
            self.timer.current_time_sec = self.timer.short_break_time_sec
            title, color_key = "Pause Courte", "bg_short_break"
        else:
            self.timer.current_time_sec = self.timer.long_break_time_sec
            title, color_key = "Pause Longue", "bg_long_break"
        
        self.session_title_label.config(text=title + " (en attente)")
        self.apply_theme(color_key)
        self.update_start_pause_button("Reprendre", self.theme["bg_btn_start"])
        self.update_cycle_indicator()
        self.update_timer_display()
        if self.tray_icon and self.tray_icon.visible:
            self.update_tray_display()

    def show_notification(self, title, message):
        try:
            if sys.platform == "win32":
                from win10toast import ToastNotifier
                toaster = ToastNotifier()
                toaster.show_toast(title, message, icon_path=resource_path("Icon.ico"), duration=5, threaded=True)
            else:
                messagebox.showinfo(title, message)
        except ImportError:
            logging.warning("win10toast non trouvé. pip install win10toast")
            messagebox.showinfo(title, message)
        except Exception as e:
            logging.error(f"Erreur de notification: {e}")
            messagebox.showinfo(title, message)

    def start_session(self, session_type):
        self.timer.start_session(session_type)
        if session_type == "work":
            title, color_key = "Travail", "bg_work"
        elif session_type == "short_break":
            title, color_key = "Pause Courte", "bg_short_break"
        else:
            title, color_key = "Pause Longue", "bg_long_break"
        
        self.session_title_label.config(text=title)
        self.apply_theme(color_key)
        self.update_start_pause_button("Pause", self.theme["bg_btn_pause"])
        self.update_cycle_indicator()
        self.timer_tick()

    def pause_timer(self):
        if self.timer.is_running and not self.timer.is_paused:
            self.timer.pause()
            if self._timer_job: 
                self.after_cancel(self._timer_job)
            current_title = self.session_title_label.cget('text')
            if " (en pause)" not in current_title and " (en attente)" not in current_title:
                self.session_title_label.config(text=current_title + " (en pause)")
            self.update_start_pause_button("Reprendre", self.theme["bg_btn_start"])

    def resume_timer(self):
        if self.timer.is_running and self.timer.is_paused:
            self.timer.resume()
            current_title = self.session_title_label.cget('text')
            base_title = current_title.replace(" (en pause)", "").replace(" (en attente)", "")
            self.session_title_label.config(text=base_title)
            self.update_start_pause_button("Pause", self.theme["bg_btn_pause"])
            self.timer_tick()

    def timer_tick(self):
        self.update_timer_display()
        if self.tray_icon and self.tray_icon.visible: 
            self.update_tray_display()
        
        if self.timer.last_state == "work" and self.timer.current_time_sec == 60: 
            self.play_sound("warning")
        
        if self.timer.tick():
            self._timer_job = self.after(1000, self.timer_tick)
        else:
            if self.timer.is_running:
                self.handle_session_end()

    def reset_to_initial_state(self):
        self.timer = TimerLogic(
            self.work_time_min,
            self.short_break_min,
            self.long_break_min,
            self.pomodoros_per_cycle
        )
        self.update_timer_display()
        self.update_cycle_indicator()
        self.session_title_label.config(text="Prêt à commencer ?")
        self.apply_theme()
        self.update_start_pause_button("Démarrer", self.theme["bg_btn_start"])

    def update_timer_display(self):
        self.timer_label.config(text=self.timer.get_time_str())

    def update_start_pause_button(self, text, color):
        self.start_pause_button.config(text=text, bg=color, fg='white')

    def update_cycle_indicator(self):
        for widget in self.cycle_indicator_frame.winfo_children():
            widget.destroy()
        bg_color = self.cget('bg')
        self.cycle_indicator_frame.configure(bg=bg_color)
        for i in range(self.pomodoros_per_cycle):
            fg_color = self.theme["fg_main"] if i < self.timer.pomodoro_count else "#ACACAC"
            tk.Label(self.cycle_indicator_frame, text="🍅", font=("Segoe UI Emoji", 26), fg=fg_color, bg=bg_color).pack(side="left")
    
    def apply_theme(self, state_color_key=None):
        self.theme = THEMES[self.current_theme]
        bg_color = self.theme.get(state_color_key, self.theme["bg_main"])
        fg_color = self.theme["fg_main"]
        self.configure(bg=bg_color)
        bg_widgets = [self.main_frame, self.top_button_frame, self.cycle_indicator_frame, self.button_frame]
        for widget in bg_widgets:
            widget.configure(bg=bg_color)
        text_widgets = [self.session_title_label, self.timer_label, self.tasks_button, self.stats_button, self.settings_button, self.about_button]
        for widget in text_widgets:
            widget.configure(bg=bg_color, fg=fg_color)
        self.reset_button.configure(bg=self.theme["bg_btn_neutral"], fg='white')
        self.skip_button.configure(bg=self.theme["bg_btn_neutral"], fg='white')
        current_start_text = self.start_pause_button.cget('text')
        if current_start_text in ["Démarrer", "Reprendre"]:
            self.update_start_pause_button(current_start_text, self.theme["bg_btn_start"])
        else:
            self.update_start_pause_button(current_start_text, self.theme["bg_btn_pause"])
        for btn in [self.tasks_button, self.stats_button, self.settings_button, self.about_button]:
            btn.configure(activebackground=bg_color, activeforeground="#BBBBBB")
        self.update_cycle_indicator()

    def open_settings(self):
        if not self.settings_window or not self.settings_window.winfo_exists():
            self.settings_window = SettingsWindow(self, self.icon_photo_image, lambda: self.on_window_close('settings'))
            self.settings_window.lift()
        else: self.settings_window.lift()

    def open_tasks(self):
        if not self.tasks_window or not self.tasks_window.winfo_exists():
            self.tasks_window = TasksWindow(self, self.icon_photo_image, lambda: self.on_window_close('tasks'))
            self.tasks_window.lift()
        else: self.tasks_window.lift()

    def open_about(self):
        if not self.about_window or not self.about_window.winfo_exists():
            self.about_window = AboutWindow(self, self.icon_photo_image, lambda: self.on_window_close('about'))
            self.about_window.lift()
        else: self.about_window.lift()

    def open_stats(self):
        if not self.stats_window or not self.stats_window.winfo_exists():
            self.stats_window = StatsWindow(self, self.icon_photo_image, lambda: self.on_window_close('stats'))
            self.stats_window.lift()
        else:
            self.stats_window.lift()

    def on_window_close(self, window_type):
        window_map = {'tasks': 'tasks_window', 'settings': 'settings_window', 'about': 'about_window', 'stats': 'stats_window'}
        window_attribute_name = window_map.get(window_type)
        if window_attribute_name:
            window_instance = getattr(self, window_attribute_name, None)
            if window_instance:
                window_instance.destroy()
            setattr(self, window_attribute_name, None)

    def safe_show_window(self): self.after(0, self.show_window)
    def safe_skip_button_click(self): self.after(0, self.skip_button_click)
    def safe_quit_app(self): self.after(0, self.quit_app)
    def safe_open_tasks(self): self.after(0, self.open_tasks)
    def safe_show_and_open_tasks(self):
        self.safe_show_window()
        self.after(100, self.safe_open_tasks)

    def create_image_with_text(self, color_name, time_text):
        cache_key = (color_name, time_text)
        if cache_key in self.tray_icon_cache:
            return self.tray_icon_cache[cache_key]
        image = Image.new('RGB', (64, 64), color_name)
        draw = ImageDraw.Draw(image)
        try: 
            font = ImageFont.truetype("arial.ttf", 48)
        except IOError: 
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), time_text, font=font)
        text_width = bbox[2] - bbox[0]; text_height = bbox[3] - bbox[1]
        position = ((64 - text_width) / 2, (64 - text_height) / 2 - bbox[1])
        draw.text(position, time_text, font=font, fill="white")
        self.tray_icon_cache[cache_key] = image
        return image

    def run_tray_icon(self):
        try:
            menu = (pystray.MenuItem('Afficher', self.safe_show_window, default=True),
                    pystray.MenuItem('Afficher les tâches', self.safe_show_and_open_tasks),
                    pystray.MenuItem('Passer', self.safe_skip_button_click),
                    pystray.MenuItem('Quitter', self.safe_quit_app))
            self.tray_icon = pystray.Icon("Focus Pomodoro", self.create_image_with_text("black", ""), "Focus Pomodoro", menu)
            self.tray_icon.run()
        except Exception as e: 
            logging.error(f"Erreur création icône barre des tâches: {e}")

    def on_unmap(self, event):
        if self.state() == 'iconic': self.hide_to_tray()

    def hide_to_tray(self):
        if self.hiding_to_tray or (self.tray_icon and self.tray_icon.visible): return
        self.hiding_to_tray = True
        self.withdraw()
        threading.Thread(target=self.run_tray_icon, daemon=True).start()

    def show_window(self):
        if self.tray_icon: 
            self.tray_icon.stop()
            self.tray_icon = None
        self.deiconify()
        self.lift()
        self.hiding_to_tray = False

    def quit_app(self):
        if messagebox.askyesno("Quitter Focus Pomodoro", "Êtes-vous sûr de vouloir quitter ?"):
            self.save_data()
            self.save_stats()
            if self.tray_icon: 
                self.tray_icon.stop()
            self.destroy()
            sys.exit(0)

    def update_tray_display(self):
        if not self.tray_icon or not self.tray_icon.visible: return
        minutes, seconds = divmod(self.timer.current_time_sec, 60)
        time_str = f"{minutes:02d}" if minutes > 0 else f"{seconds:02d}"
        color_map = {"work": self.theme["bg_work"], "short_break": self.theme["bg_short_break"], "long_break": self.theme["bg_long_break"]}
        icon_bg_color = color_map.get(self.timer.last_state, self.theme["bg_main"])
        self.tray_icon.icon = self.create_image_with_text(icon_bg_color, time_str)
        self.tray_icon.title = f"{self.session_title_label.cget('text')} - {self.timer.get_time_str()}"

if __name__ == "__main__":
    app = PomodoroApp()
    app.mainloop()

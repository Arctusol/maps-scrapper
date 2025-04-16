import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading
import logging
import json

# Importer les fonctions nécessaires des autres modules
try:
    from .utils import parse_google_maps_url
    from .core import run_grid_search_and_save
    from .sheets_uploader import upload_csv_to_sheets, validate_gsheet_access
except ImportError:
    from utils import parse_google_maps_url
    from core import run_grid_search_and_save
    from sheets_uploader import upload_csv_to_sheets, validate_gsheet_access

# Configurer le logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s')
logger = logging.getLogger(__name__)

# --- Default Grid Parameters (used if URL mode is selected) ---
DEFAULT_GRID_PARAMS = {
    "sw_lat": 48.81, "sw_lon": 2.22, "ne_lat": 48.90, "ne_lon": 2.47,
    "lat_steps": 10, "lon_steps": 10, "radius": 1500
}

# --- Fonctions pour Sauvegarder/Charger la Configuration ---

def save_configuration():
    """Sauvegarde les paramètres actuels de la GUI dans un fichier JSON."""
    config_data = {
        "input_mode": input_mode_var.get(), # Save selected input mode
        "url": url_entry.get(),
        # Manual Params
        "manual_keyword": manual_keyword_entry.get(),
        "manual_sw_lat": manual_sw_lat_entry.get(),
        "manual_sw_lon": manual_sw_lon_entry.get(),
        "manual_ne_lat": manual_ne_lat_entry.get(),
        "manual_ne_lon": manual_ne_lon_entry.get(),
        "manual_lat_steps": manual_lat_steps_entry.get(),
        "manual_lon_steps": manual_lon_steps_entry.get(),
        "manual_radius": manual_radius_entry.get(),
        # Other Params
        "csv_file": file_entry.get(),
        "csv_mode": mode_var.get(), # CSV mode ('create' or 'append')
        "sheet_id": sheet_id_entry.get(),
        "tab_name": tab_name_entry.get(),
        "key_file": key_file_entry.get(),
    }

    filepath = filedialog.asksaveasfilename(
        parent=root,
        title="Sauvegarder la configuration",
        defaultextension=".json",
        filetypes=[("Fichiers JSON", "*.json"), ("Tous les fichiers", "*.*")]
    )

    if not filepath: return

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
        messagebox.showinfo("Succès", f"Configuration sauvegardée dans\n{filepath}", parent=root)
        logger.info(f"Configuration sauvegardée dans {filepath}")
    except Exception as e:
        messagebox.showerror("Erreur de Sauvegarde", f"Impossible de sauvegarder la configuration:\n{e}", parent=root)
        logger.error(f"Erreur lors de la sauvegarde de la configuration vers {filepath}: {e}", exc_info=True)

def load_configuration():
    """Charge les paramètres depuis un fichier JSON et met à jour la GUI."""
    filepath = filedialog.askopenfilename(
        parent=root,
        title="Charger une configuration",
        filetypes=[("Fichiers JSON", "*.json"), ("Tous les fichiers", "*.*")]
    )

    if not filepath: return

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        # Set input mode first, as it affects UI state
        input_mode_var.set(config_data.get("input_mode", "URL")) # Default to URL

        # Update URL field
        url_entry.delete(0, tk.END)
        url_entry.insert(0, config_data.get("url", ""))

        # Update Manual Param fields
        manual_keyword_entry.delete(0, tk.END)
        manual_keyword_entry.insert(0, config_data.get("manual_keyword", ""))
        manual_sw_lat_entry.delete(0, tk.END)
        manual_sw_lat_entry.insert(0, config_data.get("manual_sw_lat", str(DEFAULT_GRID_PARAMS["sw_lat"])))
        manual_sw_lon_entry.delete(0, tk.END)
        manual_sw_lon_entry.insert(0, config_data.get("manual_sw_lon", str(DEFAULT_GRID_PARAMS["sw_lon"])))
        manual_ne_lat_entry.delete(0, tk.END)
        manual_ne_lat_entry.insert(0, config_data.get("manual_ne_lat", str(DEFAULT_GRID_PARAMS["ne_lat"])))
        manual_ne_lon_entry.delete(0, tk.END)
        manual_ne_lon_entry.insert(0, config_data.get("manual_ne_lon", str(DEFAULT_GRID_PARAMS["ne_lon"])))
        manual_lat_steps_entry.delete(0, tk.END)
        manual_lat_steps_entry.insert(0, config_data.get("manual_lat_steps", str(DEFAULT_GRID_PARAMS["lat_steps"])))
        manual_lon_steps_entry.delete(0, tk.END)
        manual_lon_steps_entry.insert(0, config_data.get("manual_lon_steps", str(DEFAULT_GRID_PARAMS["lon_steps"])))
        manual_radius_entry.delete(0, tk.END)
        manual_radius_entry.insert(0, config_data.get("manual_radius", str(DEFAULT_GRID_PARAMS["radius"])))

        # Update Other fields
        file_entry.delete(0, tk.END)
        file_entry.insert(0, config_data.get("csv_file", "google_maps_results.csv"))
        mode_var.set(config_data.get("csv_mode", "create")) # Load CSV mode
        sheet_id_entry.delete(0, tk.END)
        sheet_id_entry.insert(0, config_data.get("sheet_id", ""))
        tab_name_entry.delete(0, tk.END)
        tab_name_entry.insert(0, config_data.get("tab_name", ""))
        key_file_entry.delete(0, tk.END)
        key_file_entry.insert(0, config_data.get("key_file", ""))

        # Update UI enabled/disabled state AFTER setting the mode
        update_input_mode_ui()

        messagebox.showinfo("Succès", f"Configuration chargée depuis\n{filepath}", parent=root)
        logger.info(f"Configuration chargée depuis {filepath}")

    except FileNotFoundError:
         messagebox.showerror("Erreur de Chargement", f"Fichier de configuration non trouvé:\n{filepath}", parent=root)
         logger.error(f"Fichier de configuration non trouvé: {filepath}")
    except json.JSONDecodeError:
        messagebox.showerror("Erreur de Chargement", f"Fichier de configuration invalide (pas un JSON valide):\n{filepath}", parent=root)
        logger.error(f"Erreur de décodage JSON pour le fichier: {filepath}", exc_info=True)
    except Exception as e:
        messagebox.showerror("Erreur de Chargement", f"Impossible de charger la configuration:\n{e}", parent=root)
        logger.error(f"Erreur lors du chargement de la configuration depuis {filepath}: {e}", exc_info=True)


# --- Fonction du Thread Principal ---
def run_scraping_and_upload_in_thread(
    grid_params, keyword, csv_filename, csv_mode, # Renamed 'mode' to 'csv_mode' for clarity
    sheet_id, tab_name, key_file_path,
    button):
    """Exécute le scraping ET l'upload Google Sheets dans un thread séparé."""
    scraping_success = False
    upload_error_msg = None
    final_message = ""

    try:
        # --- Phase 1: Scraping (core.py now handles append/overwrite logic internally for CSV) ---
        button.config(state=tk.DISABLED, text="Recherche en cours...")
        logger.info("Lancement du thread de scraping...")
        run_grid_search_and_save(
            sw_lat=grid_params['sw_lat'],
            sw_lon=grid_params['sw_lon'],
            ne_lat=grid_params['ne_lat'],
            ne_lon=grid_params['ne_lon'],
            grid_lat_steps=grid_params['lat_steps'],
            grid_lon_steps=grid_params['lon_steps'],
            grid_search_radius=grid_params['radius'],
            keyword=keyword,
            output_filename=csv_filename,
            mode=csv_mode, # Pass the selected CSV mode to core.py
            language='fr'
        )
        logger.info("Thread de scraping terminé avec succès.")
        scraping_success = True
        final_message = f"Recherche terminée. Résultats sauvegardés dans {csv_filename}"

        # --- Phase 2: Upload Google Sheets (si scraping réussi et paramètres fournis) ---
        if scraping_success and sheet_id and tab_name and key_file_path:
            logger.info("Préparation de l'upload vers Google Sheets...")
            button.config(text="Upload en cours...")
            try:
                # Pass the CSV mode ('create' or 'append') to the uploader function
                upload_csv_to_sheets(
                    csv_path=csv_filename,
                    sheet_id=sheet_id,
                    tab_name=tab_name,
                    key_file_path=key_file_path,
                    mode=csv_mode # Pass the mode here
                )
                logger.info(f"Upload vers Google Sheets (mode: {csv_mode}) terminé avec succès.")
                final_message += f"\nDonnées uploadées avec succès vers Google Sheet ID {sheet_id} (Tab: {tab_name}, Mode: {csv_mode})."
            except FileNotFoundError as fnf_err:
                 upload_error_msg = f"Erreur Fichier pendant l'upload: {fnf_err}"
                 logger.error(upload_error_msg)
            except Exception as upload_err:
                upload_error_msg = f"Erreur pendant l'upload vers Google Sheets: {upload_err}"
                logger.error(upload_error_msg, exc_info=True)
                final_message += f"\nÉCHEC de l'upload vers Google Sheets: {upload_error_msg}"
        elif scraping_success:
             logger.info("Paramètres Google Sheets non fournis, upload sauté.")

    except Exception as scrap_err:
        logger.error(f"Erreur dans le thread de scraping: {scrap_err}", exc_info=True)
        final_message = f"Une erreur est survenue pendant la recherche:\n{scrap_err}"

    finally:
        # Determine final message box type based on outcomes
        if not scraping_success:
             messagebox.showerror("Erreur de Recherche", final_message)
        elif upload_error_msg:
             messagebox.showwarning("Terminé (avec erreur d'upload)", final_message)
        else:
             messagebox.showinfo("Terminé", final_message)
        button.config(state=tk.NORMAL, text="Lancer la Recherche et l'Upload")


# --- Fonction de Démarrage ---
def start_scraping_process():
    """Fonction appelée lorsque le bouton 'Lancer' est cliqué."""
    logger.info("Bouton 'Lancer la Recherche et l'Upload' cliqué.")

    # Get common parameters
    csv_filename = file_entry.get()
    csv_mode = mode_var.get() # Get the CSV mode ('create' or 'append')
    sheet_id = sheet_id_entry.get()
    tab_name = tab_name_entry.get()
    key_file_path = key_file_entry.get()

    # --- Validation des entrées communes ---
    if not csv_filename:
        messagebox.showerror("Erreur", "Veuillez spécifier un nom de fichier de sortie CSV.", parent=root)
        return

    upload_intended = bool(sheet_id or tab_name or key_file_path)
    if upload_intended:
        if not sheet_id:
            messagebox.showerror("Erreur", "Veuillez fournir l'ID Google Sheet pour l'upload.", parent=root)
            return
        if not tab_name:
            messagebox.showerror("Erreur", "Veuillez fournir le Nom de l'onglet (Tab) pour l'upload.", parent=root)
            return
        if not key_file_path:
            messagebox.showerror("Erreur", "Veuillez fournir le chemin vers le fichier clé (.json) du compte de service.", parent=root)
            return
        if not os.path.exists(key_file_path):
             messagebox.showerror("Erreur", f"Le fichier clé spécifié n'existe pas:\n{key_file_path}", parent=root)
             return

    # --- Validation et récupération des paramètres spécifiques au mode ---
    selected_input_mode = input_mode_var.get()
    keyword = None
    grid_params = None

    if selected_input_mode == "URL":
        logger.info("Mode d'entrée sélectionné: URL")
        url = url_entry.get()
        if not url:
            messagebox.showerror("Erreur", "Mode URL sélectionné: Veuillez fournir une URL Google Maps.", parent=root)
            return
        logger.info(f"URL fournie: '{url}'")
        parsed_data = parse_google_maps_url(url)
        if parsed_data and parsed_data.get("keyword"):
            keyword = parsed_data["keyword"]
            logger.info(f"Mot-clé extrait de l'URL: '{keyword}'")
        else:
            keyword = "restaurant" # Default
            messagebox.showwarning("Mot-clé manquant", f"Aucun mot-clé détecté dans l'URL. Utilisation du mot-clé par défaut : '{keyword}'", parent=root)
        grid_params = DEFAULT_GRID_PARAMS.copy()
        logger.info(f"Utilisation des paramètres de grille par défaut pour le mode URL: {grid_params}")

    elif selected_input_mode == "Manual":
        logger.info("Mode d'entrée sélectionné: Manuel")
        keyword = manual_keyword_entry.get()
        sw_lat_str = manual_sw_lat_entry.get()
        sw_lon_str = manual_sw_lon_entry.get()
        ne_lat_str = manual_ne_lat_entry.get()
        ne_lon_str = manual_ne_lon_entry.get()
        lat_steps_str = manual_lat_steps_entry.get()
        lon_steps_str = manual_lon_steps_entry.get()
        radius_str = manual_radius_entry.get()

        if not keyword:
            messagebox.showerror("Erreur", "Mode Manuel: Veuillez fournir un Mot-clé.", parent=root)
            return
        try:
            sw_lat = float(sw_lat_str)
            sw_lon = float(sw_lon_str)
            ne_lat = float(ne_lat_str)
            ne_lon = float(ne_lon_str)
            lat_steps = int(lat_steps_str)
            lon_steps = int(lon_steps_str)
            radius = int(radius_str)
            if lat_steps <= 0 or lon_steps <= 0 or radius <= 0:
                raise ValueError("Les pas de grille et le rayon doivent être positifs.")
            grid_params = {
                "sw_lat": sw_lat, "sw_lon": sw_lon, "ne_lat": ne_lat, "ne_lon": ne_lon,
                "lat_steps": lat_steps, "lon_steps": lon_steps, "radius": radius
            }
            logger.info(f"Utilisation des paramètres de grille manuels: {grid_params}")
        except ValueError as ve:
             messagebox.showerror("Erreur de Valeur", f"Mode Manuel: Paramètres de grille invalides.\nAssurez-vous que les latitudes/longitudes sont des nombres, et que les pas/rayon sont des entiers positifs.\n\nErreur: {ve}", parent=root)
             return
        except Exception as e:
             messagebox.showerror("Erreur Inattendue", f"Mode Manuel: Erreur lors de la lecture des paramètres de grille:\n{e}", parent=root)
             return
    else:
        messagebox.showerror("Erreur", f"Mode d'entrée inconnu: {selected_input_mode}", parent=root)
        return

    # --- Pré-validation Google Sheets Access (si upload prévu) ---
    if upload_intended:
        logger.info("Validation de l'accès à Google Sheets avant de démarrer...")
        launch_button.config(state=tk.DISABLED, text="Validation Sheets...")
        root.update_idletasks()
        if not validate_gsheet_access(sheet_id, key_file_path):
             messagebox.showerror(
                 "Erreur d'accès Google Sheets",
                 "Impossible de valider l'accès à Google Sheets.\n\n"
                 "Vérifiez que :\n"
                 "- L'ID Google Sheet est correct.\n"
                 "- Le chemin vers le fichier clé (.json) est correct.\n"
                 "- Le compte de service a les permissions 'Éditeur' sur la feuille.\n"
                 "- L'API Google Sheets est activée dans Google Cloud.\n\n"
                 "Consultez les logs pour plus de détails.",
                 parent=root
             )
             launch_button.config(state=tk.NORMAL, text="Lancer la Recherche et l'Upload")
             return
        else:
            logger.info("Validation de l'accès Google Sheets réussie.")
            launch_button.config(text="Préparation...")
            root.update_idletasks()

    # --- Lancement du Thread ---
    logger.info("Validation(s) terminée(s). Démarrage du thread principal...")
    scraping_thread = threading.Thread(
        target=run_scraping_and_upload_in_thread,
        args=(
            grid_params, keyword, csv_filename, csv_mode, # Pass csv_mode here
            sheet_id, tab_name, key_file_path,
            launch_button
        ),
        daemon=True
    )
    scraping_thread.start()

# --- Fonction pour mettre à jour l'état de l'UI basée sur le mode d'entrée ---
def update_input_mode_ui(*args):
    """Active/désactive les frames URL et Manuelle selon le mode choisi."""
    selected_mode = input_mode_var.get()
    if selected_mode == "URL":
        for child in url_frame.winfo_children():
            child.configure(state='normal')
        url_entry.configure(state='normal')
        for child in manual_params_frame.winfo_children():
             try: child.configure(state='disabled')
             except tk.TclError: pass
    elif selected_mode == "Manual":
        for child in url_frame.winfo_children():
             try: child.configure(state='disabled')
             except tk.TclError: pass
        url_entry.configure(state='disabled')
        for child in manual_params_frame.winfo_children():
             try: child.configure(state='normal')
             except tk.TclError: pass
    else:
         logger.warning(f"Mode d'entrée inconnu sélectionné: {selected_mode}")


# --- Création de la fenêtre principale ---
root = tk.Tk()
root.title("Configuration Scraper Google Maps & Upload Sheets")
root.geometry("750x750")

# Frame principale
main_frame = ttk.Frame(root, padding="20")
main_frame.pack(expand=True, fill=tk.BOTH)

# --- Section Choix Mode d'Entrée ---
input_mode_frame = ttk.LabelFrame(main_frame, text="Mode de Spécification de la Recherche", padding="5")
input_mode_frame.pack(fill=tk.X, pady=(0, 10))
input_mode_var = tk.StringVar(value="URL")
input_mode_var.trace_add("write", update_input_mode_ui)
url_mode_rb = ttk.Radiobutton(input_mode_frame, text="Option 1: Via URL (Extrait mot-clé, utilise zone fixe)", variable=input_mode_var, value="URL")
manual_mode_rb = ttk.Radiobutton(input_mode_frame, text="Option 2: Paramètres Manuels (Mot-clé, Zone, Grille)", variable=input_mode_var, value="Manual")
url_mode_rb.pack(side=tk.LEFT, padx=10, pady=5)
manual_mode_rb.pack(side=tk.LEFT, padx=10, pady=5)

# --- Section URL (Option 1) ---
url_frame = ttk.LabelFrame(main_frame, text="Option 1: Fournir une URL Google Maps", padding="10")
url_frame.pack(fill=tk.X, pady=5)
ttk.Label(url_frame, text="URL:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
url_entry = ttk.Entry(url_frame, width=70)
url_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
url_frame.columnconfigure(1, weight=1)

# --- Section Paramètres Manuels (Option 2) ---
manual_params_frame = ttk.LabelFrame(main_frame, text="Option 2: Paramètres Manuels", padding="10")
manual_params_frame.pack(fill=tk.X, pady=5)
ttk.Label(manual_params_frame, text="Mot-clé:").grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
manual_keyword_entry = ttk.Entry(manual_params_frame, width=40)
manual_keyword_entry.grid(row=0, column=1, columnspan=3, padx=5, pady=2, sticky=tk.EW)
ttk.Label(manual_params_frame, text="Latitude Sud-Ouest:").grid(row=1, column=0, padx=5, pady=2, sticky=tk.W)
manual_sw_lat_entry = ttk.Entry(manual_params_frame, width=15)
manual_sw_lat_entry.grid(row=1, column=1, padx=5, pady=2, sticky=tk.W)
manual_sw_lat_entry.insert(0, str(DEFAULT_GRID_PARAMS["sw_lat"]))
ttk.Label(manual_params_frame, text="Longitude Sud-Ouest:").grid(row=1, column=2, padx=5, pady=2, sticky=tk.W)
manual_sw_lon_entry = ttk.Entry(manual_params_frame, width=15)
manual_sw_lon_entry.grid(row=1, column=3, padx=5, pady=2, sticky=tk.W)
manual_sw_lon_entry.insert(0, str(DEFAULT_GRID_PARAMS["sw_lon"]))
ttk.Label(manual_params_frame, text="Latitude Nord-Est:").grid(row=2, column=0, padx=5, pady=2, sticky=tk.W)
manual_ne_lat_entry = ttk.Entry(manual_params_frame, width=15)
manual_ne_lat_entry.grid(row=2, column=1, padx=5, pady=2, sticky=tk.W)
manual_ne_lat_entry.insert(0, str(DEFAULT_GRID_PARAMS["ne_lat"]))
ttk.Label(manual_params_frame, text="Longitude Nord-Est:").grid(row=2, column=2, padx=5, pady=2, sticky=tk.W)
manual_ne_lon_entry = ttk.Entry(manual_params_frame, width=15)
manual_ne_lon_entry.grid(row=2, column=3, padx=5, pady=2, sticky=tk.W)
manual_ne_lon_entry.insert(0, str(DEFAULT_GRID_PARAMS["ne_lon"]))
ttk.Label(manual_params_frame, text="Pas Latitude (Grille):").grid(row=3, column=0, padx=5, pady=2, sticky=tk.W)
manual_lat_steps_entry = ttk.Entry(manual_params_frame, width=10)
manual_lat_steps_entry.grid(row=3, column=1, padx=5, pady=2, sticky=tk.W)
manual_lat_steps_entry.insert(0, str(DEFAULT_GRID_PARAMS["lat_steps"]))
ttk.Label(manual_params_frame, text="Pas Longitude (Grille):").grid(row=3, column=2, padx=5, pady=2, sticky=tk.W)
manual_lon_steps_entry = ttk.Entry(manual_params_frame, width=10)
manual_lon_steps_entry.grid(row=3, column=3, padx=5, pady=2, sticky=tk.W)
manual_lon_steps_entry.insert(0, str(DEFAULT_GRID_PARAMS["lon_steps"]))
ttk.Label(manual_params_frame, text="Rayon Recherche (m):").grid(row=4, column=0, padx=5, pady=2, sticky=tk.W)
manual_radius_entry = ttk.Entry(manual_params_frame, width=10)
manual_radius_entry.grid(row=4, column=1, padx=5, pady=2, sticky=tk.W)
manual_radius_entry.insert(0, str(DEFAULT_GRID_PARAMS["radius"]))
manual_params_frame.columnconfigure(1, weight=1)
manual_params_frame.columnconfigure(3, weight=1)

# --- Section Fichier de Sortie CSV ---
file_frame = ttk.LabelFrame(main_frame, text="Fichier CSV Intermédiaire", padding="10")
file_frame.pack(fill=tk.X, pady=5)
ttk.Label(file_frame, text="Chemin Fichier CSV:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
file_entry = ttk.Entry(file_frame, width=50)
file_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
file_entry.insert(0, "google_maps_results.csv")
def browse_csv_file():
    initial_dir = os.getcwd()
    current_mode = mode_var.get()
    initial_file = os.path.basename(file_entry.get() or "google_maps_results.csv")
    csv_filter = [("Fichiers CSV", "*.csv"), ("Tous les fichiers", "*.*")]
    if current_mode == 'append':
        filename = filedialog.askopenfilename(parent=root, initialdir=initial_dir, filetypes=csv_filter, initialfile=initial_file, title="Sélectionner le fichier CSV à compléter")
    else:
        filename = filedialog.asksaveasfilename(parent=root, initialdir=initial_dir, defaultextension=".csv", filetypes=csv_filter, initialfile=initial_file, title="Choisir ou créer le fichier CSV de sortie")
    if filename:
        file_entry.delete(0, tk.END)
        file_entry.insert(0, filename)
browse_csv_button = ttk.Button(file_frame, text="Parcourir...", command=browse_csv_file)
browse_csv_button.grid(row=0, column=2, padx=5, pady=5)
file_frame.columnconfigure(1, weight=1)
mode_var = tk.StringVar(value="create")
mode_frame = ttk.Frame(file_frame)
mode_frame.grid(row=1, column=0, columnspan=3, sticky=tk.W, padx=5, pady=(0,5))
ttk.Label(mode_frame, text="Mode d'écriture CSV:").pack(side=tk.LEFT, padx=5)
create_rb = ttk.Radiobutton(mode_frame, text="Créer/Écraser", variable=mode_var, value="create")
append_rb = ttk.Radiobutton(mode_frame, text="Ajouter", variable=mode_var, value="append")
create_rb.pack(side=tk.LEFT, padx=5)
append_rb.pack(side=tk.LEFT, padx=5)

# --- Section Google Sheets (Optionnel) ---
sheets_frame = ttk.LabelFrame(main_frame, text="Upload Google Sheets (Optionnel)", padding="10")
sheets_frame.pack(fill=tk.X, pady=5)
ttk.Label(sheets_frame, text="ID Google Sheet:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
sheet_id_entry = ttk.Entry(sheets_frame, width=50)
sheet_id_entry.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky=tk.EW)
ttk.Label(sheets_frame, text="Nom de l'onglet (Tab):").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
tab_name_entry = ttk.Entry(sheets_frame, width=50)
tab_name_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky=tk.EW)
ttk.Label(sheets_frame, text="Fichier Clé Service Account (.json):").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
key_file_entry = ttk.Entry(sheets_frame, width=50)
key_file_entry.grid(row=2, column=1, padx=5, pady=5, sticky=tk.EW)
def browse_key_file():
    initial_dir = os.path.dirname(key_file_entry.get()) or os.getcwd()
    json_filter = [("Fichiers JSON", "*.json"), ("Tous les fichiers", "*.*")]
    filename = filedialog.askopenfilename(
        parent=root,
        initialdir=initial_dir,
        filetypes=json_filter,
        title="Sélectionner le fichier clé Service Account (.json)"
    )
    if filename:
        key_file_entry.delete(0, tk.END)
        key_file_entry.insert(0, filename)
browse_key_button = ttk.Button(sheets_frame, text="Parcourir...", command=browse_key_file)
browse_key_button.grid(row=2, column=2, padx=5, pady=5)
sheets_frame.columnconfigure(1, weight=1)

# --- Bouton Lancer ---
launch_button = ttk.Button(
    main_frame,
    text="Lancer la Recherche et l'Upload",
    command=start_scraping_process
)
launch_button.pack(pady=10)

# --- Boutons Sauvegarder/Charger Configuration ---
config_button_frame = ttk.Frame(main_frame)
config_button_frame.pack(pady=5)
save_button = ttk.Button(config_button_frame, text="Sauvegarder Configuration", command=save_configuration)
save_button.pack(side=tk.LEFT, padx=10)
load_button = ttk.Button(config_button_frame, text="Charger Configuration", command=load_configuration)
load_button.pack(side=tk.LEFT, padx=10)

# --- Initial UI State ---
update_input_mode_ui()

# --- Fonction principale ---
def main():
     root.mainloop()

if __name__ == "__main__":
    main()
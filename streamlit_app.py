import streamlit as st
import os
import json
import logging
import io # Needed for log capture
import pandas as pd
import csv # Needed for download button quoting
from typing import Optional
import tempfile # For handling credentials from text area
from google.oauth2.service_account import Credentials

# Import project modules
try:
    from src.utils import parse_google_maps_url, calculate_bounding_box # Added calculate_bounding_box
    from src.core import run_grid_search_and_save, CSV_HEADERS_FR
    from src.sheets_uploader import upload_csv_to_sheets, validate_gsheet_access
except ImportError:
    # Add src to path if running streamlit run streamlit_app.py from root
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
    from src.utils import parse_google_maps_url, calculate_bounding_box # Added calculate_bounding_box
    from src.core import run_grid_search_and_save, CSV_HEADERS_FR
    from src.sheets_uploader import upload_csv_to_sheets, validate_gsheet_access


# --- Logging Configuration ---
# Create a logger
logger = logging.getLogger() # Get root logger
logger.setLevel(logging.INFO)

# Create formatter
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s] %(message)s')

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

# Create string buffer handler
log_stream = io.StringIO()
stream_handler = logging.StreamHandler(log_stream)
stream_handler.setFormatter(log_formatter)

# Add handlers only if they haven't been added before to avoid duplicates on rerun
if not logger.handlers:
    logger.addHandler(console_handler)
    logger.addHandler(stream_handler)
else:
    # Ensure our stream handler is present if handlers exist (e.g., after rerun)
    # This is a bit defensive, assuming Streamlit might mess with handlers
    has_stream_handler = any(isinstance(h, logging.StreamHandler) and h.stream == log_stream for h in logger.handlers)
    if not has_stream_handler:
         # Find the existing stream handler pointing to the old buffer and replace its stream
         # or just add our new one if none is found (less ideal but fallback)
         found_and_replaced = False
         for handler in logger.handlers:
             if isinstance(handler, logging.StreamHandler) and isinstance(handler.stream, io.StringIO):
                 handler.stream = log_stream
                 found_and_replaced = True
                 break
         if not found_and_replaced:
              logger.addHandler(stream_handler) # Add if missing, might cause duplicate streams if logic above fails

# --- Default Grid Parameters ---
DEFAULT_GRID_PARAMS = {
    "sw_lat": 48.81, "sw_lon": 2.22, "ne_lat": 48.90, "ne_lon": 2.47,
    "lat_steps": 10, "lon_steps": 10, "radius": 1500
}
# Define the scope for Google Sheets API
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# --- Helper Function to get Credentials from JSON content ---
def get_credentials_from_content(key_content_str: str) -> Optional[Credentials]:
    """Parses JSON string and returns Credentials object or None on error."""
    if not key_content_str:
        return None
    try:
        key_info = json.loads(key_content_str)
        credentials = Credentials.from_service_account_info(key_info, scopes=SCOPES)
        return credentials
    except json.JSONDecodeError:
        st.error("Erreur: Le contenu de la clé Service Account n'est pas un JSON valide.")
        logger.error("Failed to decode service account key JSON.")
        return None
    except Exception as e:
        st.error(f"Erreur lors de la création des identifiants: {e}")
        logger.error(f"Failed to create credentials from service account info: {e}", exc_info=True)
        return None

# --- Page Configuration ---
st.set_page_config(page_title="Google Maps Scraper", layout="wide")

# --- App Title ---
st.title(" scraping Google Maps & Upload Sheets")

# --- Session State Initialization ---
# Use functions for default values to avoid re-running complex logic on each interaction
def get_default_config():
    return {
        "input_mode": "URL", "url": "", "manual_keyword": "",
        "manual_sw_lat": str(DEFAULT_GRID_PARAMS["sw_lat"]),
        "manual_sw_lon": str(DEFAULT_GRID_PARAMS["sw_lon"]),
        "manual_ne_lat": str(DEFAULT_GRID_PARAMS["ne_lat"]),
        "manual_ne_lon": str(DEFAULT_GRID_PARAMS["ne_lon"]),
        "manual_lat_steps": str(DEFAULT_GRID_PARAMS["lat_steps"]),
        "manual_lon_steps": str(DEFAULT_GRID_PARAMS["lon_steps"]),
        "manual_radius": str(DEFAULT_GRID_PARAMS["radius"]),
        "csv_file": "google_maps_results.csv", "csv_mode": "create",
        "sheet_id": "", "tab_name": "", "key_file_content": ""
    }

if 'config' not in st.session_state:
    st.session_state.config = get_default_config()

# --- UI Sections ---

# --- 1. Input Mode Selection ---
st.subheader("1. Mode de Spécification de la Recherche")
input_mode_options = ("URL (Extrait mot-clé, zone fixe)", "Paramètres Manuels (Mot-clé, Zone, Grille)")
current_input_mode_index = 0 if st.session_state.config["input_mode"] == "URL" else 1
selected_input_mode_label = st.radio(
    "Choisissez comment spécifier la recherche:",
    input_mode_options,
    index=current_input_mode_index,
    key="input_mode_radio",
    label_visibility="collapsed"
)
# Update session state based on radio button selection
st.session_state.config["input_mode"] = "URL" if selected_input_mode_label == input_mode_options[0] else "Manual"


# --- 2. Search Parameters (Conditional) ---
st.subheader("2. Paramètres de Recherche")
# Use columns to control layout even when only one section is active
col_url, col_manual = st.columns(2)

with col_url:
    with st.expander("Option 1: Via URL", expanded=(st.session_state.config["input_mode"] == "URL")):
        st.session_state.config["url"] = st.text_input(
            "URL Google Maps:", value=st.session_state.config["url"],
            placeholder="Collez l'URL d'une recherche Google Maps ici...",
            help="Le mot-clé sera extrait de l'URL. La zone de recherche est fixe (Paris par défaut).",
            disabled=(st.session_state.config["input_mode"] != "URL") # Disable if not active
        )
        if st.session_state.config["input_mode"] == "URL":
            st.caption(f"Note: Ce mode utilise une zone de recherche fixe (autour de Paris) et des paramètres de grille par défaut : {DEFAULT_GRID_PARAMS['lat_steps']}x{DEFAULT_GRID_PARAMS['lon_steps']} étapes, rayon {DEFAULT_GRID_PARAMS['radius']}m.")

with col_manual:
     with st.expander("Option 2: Paramètres Manuels", expanded=(st.session_state.config["input_mode"] == "Manual")):
        is_manual_disabled = (st.session_state.config["input_mode"] != "Manual")
        st.session_state.config["manual_keyword"] = st.text_input(
            "Mot-clé:", value=st.session_state.config["manual_keyword"],
            placeholder="Ex: restaurant, plombier, musée", disabled=is_manual_disabled
        )
        st.markdown("---")
        st.markdown("**Zone de Recherche (Bounding Box):**")
        sub_col1, sub_col2 = st.columns(2)
        with sub_col1:
            st.session_state.config["manual_sw_lat"] = st.text_input("Latitude Sud-Ouest:", value=st.session_state.config["manual_sw_lat"], disabled=is_manual_disabled)
            st.session_state.config["manual_ne_lat"] = st.text_input("Latitude Nord-Est:", value=st.session_state.config["manual_ne_lat"], disabled=is_manual_disabled)
        with sub_col2:
            st.session_state.config["manual_sw_lon"] = st.text_input("Longitude Sud-Ouest:", value=st.session_state.config["manual_sw_lon"], disabled=is_manual_disabled)
            st.session_state.config["manual_ne_lon"] = st.text_input("Longitude Nord-Est:", value=st.session_state.config["manual_ne_lon"], disabled=is_manual_disabled)

        st.markdown("---")
        st.markdown("**Paramètres de la Grille:**")
        sub_col3, sub_col4, sub_col5 = st.columns(3)
        with sub_col3:
            st.session_state.config["manual_lat_steps"] = st.text_input("Pas Latitude:", value=st.session_state.config["manual_lat_steps"], disabled=is_manual_disabled)
        with sub_col4:
            st.session_state.config["manual_lon_steps"] = st.text_input("Pas Longitude:", value=st.session_state.config["manual_lon_steps"], disabled=is_manual_disabled)
        with sub_col5:
            st.session_state.config["manual_radius"] = st.text_input("Rayon Recherche (m):", value=st.session_state.config["manual_radius"], disabled=is_manual_disabled)


# --- 3. Configuration CSV ---
st.subheader("3. Fichier CSV Intermédiaire")
col_csv1, col_csv2 = st.columns([3, 1])
with col_csv1:
    st.session_state.config["csv_file"] = st.text_input(
        "Nom du fichier CSV:", value=st.session_state.config["csv_file"],
        help="Le fichier sera sauvegardé sur le serveur où l'application tourne."
    )
with col_csv2:
    csv_mode_options = ("create", "append")
    csv_mode_index = 0 if st.session_state.config["csv_mode"] == "create" else 1
    st.session_state.config["csv_mode"] = st.radio(
        "Mode d'écriture CSV:", csv_mode_options, index=csv_mode_index,
        key="csv_mode_radio", horizontal=True, label_visibility="collapsed"
    )


# --- 4. Configuration Google Sheets (Optionnel) ---
st.subheader("4. Upload Google Sheets (Optionnel)")
with st.expander("Configurer l'upload vers Google Sheets"):
    st.session_state.config["sheet_id"] = st.text_input(
        "ID Google Sheet:", value=st.session_state.config["sheet_id"],
        placeholder="Ex: 1KrxSDiRPh8hwLtlxFgW3vEZ6Lda7TwHSgMtHhK-BBSg"
    )
    st.session_state.config["tab_name"] = st.text_input(
        "Nom de l'onglet (Tab):", value=st.session_state.config["tab_name"],
        placeholder="Ex: Resultats_Paris_Restaurants"
    )
    st.session_state.config["key_file_content"] = st.text_area(
        "Contenu du fichier Clé Service Account (.json):", value=st.session_state.config["key_file_content"],
        placeholder="Collez ici le contenu complet de votre fichier JSON de clé de service.", height=150,
        help="Gardez cette clé sécurisée. Ne la partagez pas publiquement."
    )


# --- 5. Bouton Lancer ---
st.subheader("5. Lancer le Processus")
if st.button("🚀 Lancer la Recherche et l'Upload"):

    # --- Retrieve parameters from session state ---
    config = st.session_state.config
    selected_input_mode = config["input_mode"]
    csv_filename = config["csv_file"]
    csv_mode = config["csv_mode"]
    sheet_id = config["sheet_id"]
    tab_name = config["tab_name"]
    key_content = config["key_file_content"]

    keyword = None
    grid_params = None
    validation_ok = True

    # --- Validate and determine keyword/grid_params ---
    if selected_input_mode == "URL":
        url = config["url"]
        if not url:
            st.error("Mode URL: Veuillez fournir une URL Google Maps.")
            validation_ok = False
        else:
            logger.info(f"Mode URL: URL fournie: '{url}'")
            parsed_data = parse_google_maps_url(url)
            grid_params = DEFAULT_GRID_PARAMS.copy() # Start with defaults

            if parsed_data:
                if parsed_data.get("keyword"):
                    keyword = parsed_data["keyword"]
                    logger.info(f"Mot-clé extrait de l'URL: '{keyword}'")
                else:
                    keyword = "restaurant" # Default keyword if not found
                    st.warning(f"Mode URL: Aucun mot-clé détecté dans l'URL. Utilisation du mot-clé par défaut : '{keyword}'")

                # Attempt to use coordinates and radius from URL
                if parsed_data.get("latitude") is not None and parsed_data.get("longitude") is not None and parsed_data.get("radius_meters") is not None:
                    center_lat = parsed_data["latitude"]
                    center_lon = parsed_data["longitude"]
                    radius = parsed_data["radius_meters"]
                    logger.info(f"Mode URL: Centre extrait: ({center_lat}, {center_lon}), Rayon: {radius}m. Calcul de la bounding box...")
                    bbox = calculate_bounding_box(center_lat, center_lon, radius)
                    if bbox:
                        grid_params.update(bbox) # Update grid_params with calculated box
                        logger.info(f"Mode URL: Utilisation de la bounding box calculée: {bbox}. Les pas et rayons de la grille restent par défaut.")
                    else:
                        logger.warning("Mode URL: Impossible de calculer la bounding box depuis les coordonnées extraites. Utilisation de la zone par défaut.")
                        st.warning("Impossible de calculer la zone de recherche depuis l'URL. Utilisation de la zone par défaut (Paris).")
                else:
                    logger.warning("Mode URL: Coordonnées ou rayon non extraits de l'URL. Utilisation de la zone par défaut.")
                    st.warning("Impossible d'extraire les coordonnées/rayon de l'URL. Utilisation de la zone par défaut (Paris).")

            else: # parsed_data is None
                 keyword = "restaurant" # Default keyword
                 st.error("Mode URL: Impossible d'analyser l'URL fournie. Vérifiez le format.")
                 st.warning(f"Utilisation du mot-clé par défaut '{keyword}' et de la zone par défaut (Paris).")
                 validation_ok = False # Consider stopping if URL parsing fails completely? Or just use defaults? Let's use defaults but warn heavily.

            # Log final grid params being used in URL mode
            logger.info(f"Mode URL: Paramètres de grille finaux utilisés: {grid_params}")

    elif selected_input_mode == "Manual":
        logger.info("Mode Manuel: Validation des paramètres...")
        keyword = config["manual_keyword"]
        sw_lat_str = config["manual_sw_lat"]
        sw_lon_str = config["manual_sw_lon"]
        ne_lat_str = config["manual_ne_lat"]
        ne_lon_str = config["manual_ne_lon"]
        lat_steps_str = config["manual_lat_steps"]
        lon_steps_str = config["manual_lon_steps"]
        radius_str = config["manual_radius"]

        if not keyword:
            st.error("Mode Manuel: Veuillez fournir un Mot-clé.")
            validation_ok = False
        try:
            sw_lat = float(sw_lat_str)
            sw_lon = float(sw_lon_str)
            ne_lat = float(ne_lat_str)
            ne_lon = float(ne_lon_str)
            lat_steps = int(lat_steps_str)
            lon_steps = int(lon_steps_str)
            radius = int(radius_str)
            if lat_steps <= 0 or lon_steps <= 0 or radius <= 0:
                raise ValueError("Les pas de grille et le rayon doivent être des entiers positifs.")
            grid_params = {
                "sw_lat": sw_lat, "sw_lon": sw_lon, "ne_lat": ne_lat, "ne_lon": ne_lon,
                "lat_steps": lat_steps, "lon_steps": lon_steps, "radius": radius
            }
            logger.info(f"Mode Manuel: Utilisation des paramètres de grille: {grid_params}")
        except ValueError as ve:
             st.error(f"Mode Manuel: Paramètres de grille invalides. Vérifiez les nombres et entiers positifs. Erreur: {ve}")
             validation_ok = False
        except Exception as e:
             st.error(f"Mode Manuel: Erreur lors de la lecture des paramètres de grille: {e}")
             validation_ok = False

    # --- Validate common & Sheets parameters ---
    if not csv_filename:
        st.error("Veuillez spécifier un nom de fichier CSV.")
        validation_ok = False

    upload_intended = bool(sheet_id or tab_name or key_content)
    g_credentials = None # Initialize credentials variable
    if upload_intended:
        if not sheet_id:
            st.error("Upload Sheets: Veuillez fournir l'ID Google Sheet.")
            validation_ok = False
        if not tab_name:
            st.error("Upload Sheets: Veuillez fournir le Nom de l'onglet (Tab).")
            validation_ok = False
        if not key_content:
            st.error("Upload Sheets: Veuillez coller le contenu du fichier clé Service Account (.json).")
            validation_ok = False
        else:
            # Try to parse credentials early
            g_credentials = get_credentials_from_content(key_content)
            if not g_credentials:
                validation_ok = False # Error already shown by helper function

    # --- Proceed if validation passed ---
    if validation_ok:
        logger.info("Validation des paramètres réussie.")
        sheets_validation_passed = True # Assume true if not uploading

        # --- Pre-validate Google Sheets Access (if applicable) ---
        if upload_intended and g_credentials:
            with st.spinner("Validation de l'accès à Google Sheets..."):
                logger.info("Validation de l'accès à Google Sheets avant de démarrer...")
                sheets_validation_passed = validate_gsheet_access(sheet_id, g_credentials)
                if not sheets_validation_passed:
                    st.error(
                        "Erreur d'accès Google Sheets. Vérifiez l'ID, les permissions du compte de service (Éditeur), et si l'API Sheets est activée. Voir logs pour détails."
                    )
                else:
                    logger.info("Validation de l'accès Google Sheets réussie.")

        # --- Run main process if Sheets validation (or no upload) passed ---
        if sheets_validation_passed:
            scraping_status = None
            upload_status = None
            error_message = None
            result_df = None

            # Clear log buffer before run
            log_stream.seek(0)
            log_stream.truncate(0)
            try:
                with st.spinner(f"Recherche en cours (Mot-clé: '{keyword}')..."):
                    logger.info("Démarrage du processus principal (scraping)...")
                    # Note: run_grid_search_and_save now always overwrites the CSV
                    run_grid_search_and_save(
                        sw_lat=grid_params['sw_lat'], sw_lon=grid_params['sw_lon'],
                        ne_lat=grid_params['ne_lat'], ne_lon=grid_params['ne_lon'],
                        grid_lat_steps=grid_params['lat_steps'], grid_lon_steps=grid_params['lon_steps'],
                        grid_search_radius=grid_params['radius'],
                        keyword=keyword, output_filename=csv_filename,
                        mode=csv_mode, language='fr'
                    )
                    scraping_status = "Succès"
                    logger.info("Scraping terminé avec succès.")

                # Attempt upload if scraping succeeded and intended
                if upload_intended and g_credentials:
                    with st.spinner(f"Upload vers Google Sheet '{sheet_id}' (Tab: '{tab_name}', Mode: {csv_mode})..."):
                        logger.info("Démarrage de l'upload vers Google Sheets...")
                        upload_csv_to_sheets(
                            csv_path=csv_filename, sheet_id=sheet_id, tab_name=tab_name,
                            credentials=g_credentials, mode=csv_mode
                        )
                        upload_status = "Succès"
                        logger.info("Upload terminé avec succès.")

                # Try to read final CSV for display/download
                try:
                     result_df = pd.read_csv(csv_filename, keep_default_na=False)
                     result_df = result_df.fillna("")
                except Exception as read_err:
                     logger.error(f"Impossible de lire le fichier CSV final pour affichage: {read_err}")
                     st.warning(f"Impossible de lire le fichier CSV final '{csv_filename}' pour affichage.")

            except Exception as proc_err:
                error_message = f"Une erreur est survenue: {proc_err}"
                logger.error(f"Erreur pendant l'exécution: {proc_err}", exc_info=True)
                st.error(error_message)
            finally:
                # Store logs in session state regardless of success/failure
                st.session_state['logs'] = log_stream.getvalue()

            # --- Display Final Status ---
            if scraping_status == "Succès":
                if upload_intended:
                    if upload_status == "Succès":
                        st.success(f"Recherche et Upload (Mode: {csv_mode}) terminés avec succès!")
                    else:
                        st.warning(f"Recherche terminée, mais l'upload a échoué. Vérifiez les logs. Erreur: {error_message or 'Inconnue'}")
                else:
                    st.success("Recherche terminée avec succès!")

                # Display results DataFrame and download button if available
                if result_df is not None:
                    st.subheader("Aperçu des Résultats")
                    st.dataframe(result_df)
                    # Prepare download button
                    csv_data_for_download = result_df.to_csv(index=False, encoding='utf-8', quoting=csv.QUOTE_MINIMAL).encode('utf-8')
                    st.download_button(
                        label="📥 Télécharger le CSV final",
                        data=csv_data_for_download,
                        file_name=os.path.basename(csv_filename), # Use the generated filename
                        mime="text/csv",
                    )

            # No need for else here, error already shown if scraping failed


# --- 6. Sauvegarder/Charger Configuration ---
st.subheader("6. Gestion Configuration (via Fichiers)")
col_save, col_load = st.columns(2)
with col_save:
    config_to_save = json.dumps(st.session_state.config, indent=4)
    st.download_button(
        label="💾 Sauvegarder Configuration Actuelle",
        data=config_to_save,
        file_name="scraper_config.json",
        mime="application/json",
        use_container_width=True
    )
with col_load:
    uploaded_file = st.file_uploader("📂 Charger Configuration", type="json", label_visibility="collapsed")
    if uploaded_file is not None:
        try:
            loaded_config = json.load(uploaded_file)
            # Validate loaded config minimally (e.g., check if it's a dict)
            if isinstance(loaded_config, dict):
                 # Merge loaded config with defaults to handle missing keys gracefully
                 default_conf = get_default_config()
                 default_conf.update(loaded_config) # Overwrite defaults with loaded values
                 st.session_state.config = default_conf
                 st.success(f"Configuration chargée depuis '{uploaded_file.name}'.")
                 # Use rerun for a cleaner update without full reload
                 st.rerun()
            else:
                 st.error("Erreur: Le fichier chargé ne contient pas une configuration valide (objet JSON attendu).")

        except json.JSONDecodeError:
            st.error("Erreur: Le fichier chargé n'est pas un JSON valide.")
        except Exception as e:
            st.error(f"Erreur lors du chargement de la configuration: {e}")


# --- 7. Display Logs ---
st.subheader("7. Logs d'Exécution")
if 'logs' in st.session_state and st.session_state['logs']:
    with st.expander("Voir les logs détaillés", expanded=False):
        st.text_area("Logs", st.session_state['logs'], height=300, disabled=True)
else:
    st.caption("Aucun log à afficher pour le moment. Lancez une recherche pour voir les logs.")
# src/google_maps_scraper/core.py
"""
Core logic for Google Maps scraping, including grid search and CSV writing using pandas.
"""

import csv # Keep for quoting constant
import logging
import time
import os
import datetime
import pandas as pd # Import pandas
from typing import List, Dict, Any, Optional, Tuple, Set

from .api_client import GoogleMapsApiClient, GoogleMapsApiError
from .models import PlaceDetails

logger = logging.getLogger(__name__)

# --- Constantes ---
PLACE_DETAILS_FIELDS = [
    'place_id', 'name', 'user_ratings_total', 'rating', 'website',
    'international_phone_number', 'types', 'opening_hours', 'business_status',
    'formatted_address', 'url',
    'geometry', 'price_level', 'address_components',
    'dine_in', 'takeout', 'delivery', 'curbside_pickup',
    'wheelchair_accessible_entrance'
]

CSV_HEADERS_FR = [
    'ID Place', 'Nom', 'Description', 'Avis (Nombre)', 'Note', 'Site Web', 'Téléphone',
    'Nom Propriétaire', 'Catégorie Principale', 'Catégories', 'Horaires Semaine',
    'Fermé Temporairement', 'Fermé Le', 'Adresse', 'Mots Clés Avis', 'Lien Google Maps',
    'Recherche', 'Latitude', 'Longitude', 'Niveau Prix', 'Numéro Rue', 'Rue', 'Ville',
    'Code Postal', 'Sur Place', 'À Emporter', 'Livraison', 'Retrait Trottoir',
    'Accès Fauteuil Roulant', 'Date de Création'
]
# --- Fin Constantes ---

# --- Fonction generate_grid_points ---
def generate_grid_points(
    sw_lat: float, sw_lon: float, ne_lat: float, ne_lon: float, num_lat_steps: int, num_lon_steps: int
) -> List[Tuple[float, float]]:
    """Generates center points for a grid within a bounding box."""
    points = []
    # Avoid division by zero if steps are 0 or 1
    lat_step = (ne_lat - sw_lat) / num_lat_steps if num_lat_steps > 0 else 0
    lon_step = (ne_lon - sw_lon) / num_lon_steps if num_lon_steps > 0 else 0

    # Handle case where only one step is needed (use center)
    if num_lat_steps <= 1 and num_lon_steps <= 1:
         center_lat = sw_lat + (ne_lat - sw_lat) / 2
         center_lon = sw_lon + (ne_lon - sw_lon) / 2
         points.append((center_lat, center_lon))
         logger.info(f"Généré 1 point de grille (centre) pour la recherche.")
         return points

    for i in range(num_lat_steps):
        # Calculate latitude for the center of the cell
        lat = sw_lat + (i + 0.5) * lat_step
        for j in range(num_lon_steps):
            # Calculate longitude for the center of the cell
            lon = sw_lon + (j + 0.5) * lon_step
            points.append((lat, lon))

    logger.info(f"Généré {len(points)} points de grille pour la recherche.")
    return points
# --- Fin generate_grid_points ---


# --- Fonction format_place_details_for_csv ---
def format_place_details_for_csv(details: PlaceDetails, query: str) -> Dict[str, Any]:
    """Formats the PlaceDetails object into a dictionary suitable for CSV writing."""
    details.query = query
    if details.types:
        details.main_category = details.types[0] if details.types else "N/A"
        details.categories_str = ", ".join(details.types)
    else:
         details.main_category = "N/A"
         details.categories_str = "N/A"

    if details.opening_hours and details.opening_hours.weekday_text:
        details.workday_timing = " | ".join(details.opening_hours.weekday_text)
    else:
        details.workday_timing = "N/A"

    if details.business_status:
        details.is_temporarily_closed = (details.business_status == 'CLOSED_TEMPORARILY')
    else:
        details.is_temporarily_closed = False

    if details.geometry and details.geometry.location:
        details.latitude = details.geometry.location.lat
        details.longitude = details.geometry.location.lng
    else:
        details.latitude = None
        details.longitude = None

    if details.price_level is not None:
         details.price_level_display = '$' * details.price_level if details.price_level > 0 else 'N/A'
    else:
        details.price_level_display = "N/A"

    details.street_number = None
    details.route = None
    details.locality = None
    details.postal_code = None
    if details.address_components:
        for component in details.address_components:
            if 'street_number' in component.types: details.street_number = component.long_name
            elif 'route' in component.types: details.route = component.long_name
            elif 'locality' in component.types: details.locality = component.long_name
            elif 'postal_code' in component.types: details.postal_code = component.long_name

    def format_bool_for_csv(value: Optional[bool]) -> str:
        if value is None: return "N/A"
        return "VRAI" if value else "FAUX"

    details.dine_in_csv = format_bool_for_csv(details.dine_in)
    details.takeout_csv = format_bool_for_csv(details.takeout)
    details.delivery_csv = format_bool_for_csv(details.delivery)
    details.curbside_pickup_csv = format_bool_for_csv(details.curbside_pickup)
    details.wheelchair_accessible_csv = format_bool_for_csv(details.wheelchair_accessible_entrance)

    now = datetime.datetime.now()
    timestamp_str = now.strftime('%Y-%m-%d %H:%M:%S')

    # Ensure all keys match CSV_HEADERS_FR, including 'Date de Création'
    return {
        'ID Place': details.place_id, 'Nom': details.name, 'Description': details.description,
        'Avis (Nombre)': details.user_ratings_total if details.user_ratings_total is not None else "N/A",
        'Note': details.rating if details.rating is not None else "N/A",
        'Site Web': details.website or "", 'Téléphone': details.international_phone_number or "N/A",
        'Nom Propriétaire': details.owner_name, 'Catégorie Principale': details.main_category or "N/A",
        'Catégories': details.categories_str or "N/A", 'Horaires Semaine': details.workday_timing or "N/A",
        'Fermé Temporairement': format_bool_for_csv(details.is_temporarily_closed),
        'Fermé Le': details.closed_on, 'Adresse': details.formatted_address or "N/A",
        'Mots Clés Avis': details.review_keywords, 'Lien Google Maps': details.url,
        'Recherche': details.query or "N/A",
        'Latitude': details.latitude if details.latitude is not None else "N/A",
        'Longitude': details.longitude if details.longitude is not None else "N/A",
        'Niveau Prix': details.price_level_display or "N/A", 'Numéro Rue': details.street_number or "N/A",
        'Rue': details.route or "N/A", 'Ville': details.locality or "N/A",
        'Code Postal': details.postal_code or "N/A", 'Sur Place': details.dine_in_csv,
        'À Emporter': details.takeout_csv, 'Livraison': details.delivery_csv,
        'Retrait Trottoir': details.curbside_pickup_csv,
        'Accès Fauteuil Roulant': details.wheelchair_accessible_csv,
        'Date de Création': timestamp_str
    }
# --- Fin format_place_details_for_csv ---


# --- Nouvelle fonction run_grid_search_and_save utilisant pandas ---
def run_grid_search_and_save(
    sw_lat: float, sw_lon: float, ne_lat: float, ne_lon: float,
    grid_lat_steps: int, grid_lon_steps: int, grid_search_radius: int,
    keyword: str, output_filename: str, mode: str, language: str = 'fr'
    ):
    """
    Exécute la recherche, combine avec les données existantes si mode='append',
    et sauvegarde le résultat complet et dédoublonné dans le CSV (écrase toujours).
    """
    logger.info("--- Démarrage de la Recherche et Sauvegarde Google Maps (v_pandas) ---")
    logger.info(f"Zone: SW({sw_lat},{sw_lon}), NE({ne_lat},{ne_lon})")
    logger.info(f"Grille: {grid_lat_steps}x{grid_lon_steps} étapes, Rayon par point: {grid_search_radius}m")
    logger.info(f"Mot-clé: '{keyword}'")
    logger.info(f"Fichier Sortie: {output_filename}, Mode d'opération interne: {mode}")
    logger.info(f"Langue: {language}")

    if not all([keyword, output_filename, mode]):
         logger.error("Paramètres manquants (mot-clé, fichier sortie ou mode).")
         return

    try:
        client = GoogleMapsApiClient()
    except ValueError as e:
        logger.error(f"Échec initialisation API Client: {e}")
        return

    # --- 1. Charger les données existantes si en mode 'append' ---
    df_old = pd.DataFrame(columns=CSV_HEADERS_FR) # Start with empty df with correct schema
    if mode == 'append' and os.path.exists(output_filename):
        logger.info(f"Mode 'append': Lecture du fichier existant {output_filename}...")
        try:
            # Read existing data, handle potential missing columns later
            # Read all as string initially to avoid type conflicts, keep_default_na=False prevents "NA" strings becoming NaN
            df_old = pd.read_csv(output_filename, keep_default_na=False, dtype=str)
            # Ensure all expected columns are present after reading
            missing_cols = [col for col in CSV_HEADERS_FR if col not in df_old.columns]
            if missing_cols:
                logger.warning(f"Colonnes manquantes dans le CSV existant: {missing_cols}. Ajout avec valeurs vides.")
                for col in missing_cols:
                    df_old[col] = "" # Add missing columns
            # Reindex to ensure correct order and full schema, fill missing with empty string
            df_old = df_old.reindex(columns=CSV_HEADERS_FR, fill_value="")
            logger.info(f"Lu {len(df_old)} lignes depuis le fichier existant.")
        except pd.errors.EmptyDataError:
            logger.warning(f"Le fichier existant {output_filename} est vide ou ne contient que l'en-tête.")
            df_old = pd.DataFrame(columns=CSV_HEADERS_FR) # Ensure schema
        except Exception as e:
            logger.error(f"Erreur lors de la lecture du fichier CSV existant {output_filename}: {e}. L'opération se poursuivra comme si le fichier était vide.", exc_info=True)
            df_old = pd.DataFrame(columns=CSV_HEADERS_FR) # Reset on error
    elif mode == 'append':
         logger.info(f"Mode 'append': Le fichier {output_filename} n'existe pas encore.")
         # df_old remains empty with correct columns


    # --- 2. Effectuer la nouvelle recherche ---
    grid_points = generate_grid_points(sw_lat, sw_lon, ne_lat, ne_lon, grid_lat_steps, grid_lon_steps)
    all_unique_place_ids_this_run: Set[str] = set()
    total_grid_points = len(grid_points)

    logger.info(f"Lancement Nearby Search sur {total_grid_points} points de grille...")
    for i, (lat, lon) in enumerate(grid_points):
        location_str = f"{lat},{lon}"
        logger.debug(f"Recherche point grille {i+1}/{total_grid_points}: {location_str}...")
        try:
            place_ids_for_point = client.nearby_search(
                location=location_str, radius=grid_search_radius, keyword=keyword, language=language
            )
            all_unique_place_ids_this_run.update(place_ids_for_point)
            logger.debug(f"  -> Point {i+1}: Trouvé {len(place_ids_for_point)} IDs. Total unique (run): {len(all_unique_place_ids_this_run)}")
            time.sleep(0.1) # Keep a small delay
        except GoogleMapsApiError as e:
            logger.error(f"  -> Erreur API Nearby Search pour point {i+1} ({location_str}): {e}. Point sauté.")
        except Exception as e:
            logger.error(f"  -> Erreur inattendue Nearby Search pour point {i+1} ({location_str}): {e}. Point sauté.", exc_info=True)

    df_final = pd.DataFrame(columns=CSV_HEADERS_FR) # Initialize df_final with schema

    if not all_unique_place_ids_this_run:
        logger.warning("Aucun ID Place trouvé pendant cette recherche.")
        if df_old.empty:
             logger.info("Aucune donnée ancienne ou nouvelle, écriture d'un fichier vide avec en-têtes.")
             # df_final is already an empty DataFrame with correct columns
        else:
             logger.info("Aucun nouvel ID trouvé, le fichier existant sera réécrit avec le même contenu.")
             df_final = df_old # Use existing data (already has correct schema)
        # Proceed to write df_final (either empty or old data)
    else:
        # --- 3. Récupérer les détails pour TOUS les IDs uniques trouvés cette fois ---
        logger.info(f"Récupération des détails pour {len(all_unique_place_ids_this_run)} Place IDs uniques trouvés...")
        all_processed_details: List[Dict[str, Any]] = []
        ids_to_fetch_list = list(all_unique_place_ids_this_run)

        for i, place_id in enumerate(ids_to_fetch_list):
            logger.debug(f"Traitement Place ID {i+1}/{len(ids_to_fetch_list)}: {place_id}")
            details_dict = client.get_place_details(place_id=place_id, fields=PLACE_DETAILS_FIELDS, language=language)
            if details_dict:
                try:
                    place_details_obj = PlaceDetails.model_validate(details_dict)
                    formatted_row = format_place_details_for_csv(place_details_obj, keyword or "N/A")
                    all_processed_details.append(formatted_row)
                except Exception as e:
                    logger.error(f"Échec traitement/validation détails pour Place ID {place_id}: {e}", exc_info=True)
            else:
                logger.warning(f"Saut Place ID {place_id} (erreur API ou pas de détails).")
            time.sleep(0.05) # Keep small delay

        if not all_processed_details:
             logger.warning("Aucun détail valide n'a pu être récupéré pour les IDs trouvés.")
             if df_old.empty:
                 logger.info("Pas de détails valides et pas de données anciennes. Écriture d'un fichier vide.")
                 # df_final is already an empty DataFrame with correct columns
             else:
                 logger.info("Pas de détails valides. Utilisation des données anciennes uniquement.")
                 df_final = df_old # Use existing data
             # Proceed to write df_final
        else:
            # --- 4. Préparer le DataFrame final ---
            df_new = pd.DataFrame(all_processed_details)
            # Ensure new data also conforms to the full header list before concat
            df_new = df_new.reindex(columns=CSV_HEADERS_FR, fill_value="")
            logger.info(f"Préparé un DataFrame avec {len(df_new)} nouvelles lignes de détails.")

            if not df_old.empty:
                logger.info("Combinaison des anciennes et nouvelles données...")
                # Ensure 'ID Place' columns are of compatible type (string) before concat/dedup
                df_old['ID Place'] = df_old['ID Place'].astype(str)
                df_new['ID Place'] = df_new['ID Place'].astype(str)
                df_combined = pd.concat([df_old, df_new], ignore_index=True)
            else: # Create mode or append to non-existent/empty file
                df_combined = df_new

            # De-duplicate based on 'ID Place', keeping the latest
            initial_rows = len(df_combined)
            # Ensure 'ID Place' is string for reliable deduplication
            df_combined['ID Place'] = df_combined['ID Place'].astype(str)
            df_final = df_combined.drop_duplicates(subset=['ID Place'], keep='last')
            deduplicated_rows = initial_rows - len(df_final)
            if deduplicated_rows > 0:
                logger.info(f"Supprimé {deduplicated_rows} doublons basés sur 'ID Place', gardant les plus récents.")

    # --- 5. Sauvegarder le DataFrame final (toujours écraser) ---
    # Ensure final columns are in the correct order before saving
    try:
        # Make sure df_final exists and is a DataFrame
        if not isinstance(df_final, pd.DataFrame):
             logger.error("Erreur interne: df_final n'a pas été créé correctement. Sauvegarde annulée.")
             return
        df_final = df_final[CSV_HEADERS_FR] # Enforce column order
    except KeyError as e:
        logger.error(f"Erreur: Colonne attendue manquante lors de la finalisation du DataFrame: {e}. Colonnes présentes: {list(df_final.columns)}", exc_info=True)
        logger.error("Sauvegarde annulée en raison d'une incohérence de colonnes.")
        return

    logger.info(f"Écriture de {len(df_final)} lignes finales dans {output_filename} (mode: overwrite)...")
    try:
        # Use pandas to_csv for robust writing, always overwrite
        df_final.to_csv(output_filename, index=False, encoding='utf-8', quoting=csv.QUOTE_MINIMAL)
        logger.info(f"Résultats finaux sauvegardés avec succès dans {output_filename}")
    except IOError as e:
        logger.error(f"Échec écriture fichier CSV final: {e}")
    except Exception as e:
         logger.error(f"Erreur inattendue pendant l'écriture CSV final: {e}", exc_info=True)

    logger.info("--- Recherche et Sauvegarde Terminée ---")
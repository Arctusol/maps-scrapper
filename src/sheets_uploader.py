# src/google_maps_scraper/sheets_uploader.py
"""
Handles uploading CSV data to Google Sheets and validating access.
Supports 'create' (overwrite) and 'append' (merge then overwrite) modes.
Accepts parsed Credentials object for authentication.
"""

import logging
from typing import Optional
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials # Keep this for type hinting
from gspread_dataframe import set_with_dataframe
import os

# Import headers from core module - Needed again for append logic
try:
    from .core import CSV_HEADERS_FR
except ImportError:
    try:
        from core import CSV_HEADERS_FR
    except ImportError:
        logger.warning("Could not import CSV_HEADERS_FR from core. Using fallback list.")
        CSV_HEADERS_FR = [ # Ensure this matches core.py if modified!
            'ID Place', 'Nom', 'Description', 'Avis (Nombre)', 'Note', 'Site Web', 'Téléphone',
            'Nom Propriétaire', 'Catégorie Principale', 'Catégories', 'Horaires Semaine',
            'Fermé Temporairement', 'Fermé Le', 'Adresse', 'Mots Clés Avis', 'Lien Google Maps',
            'Recherche', 'Latitude', 'Longitude', 'Niveau Prix', 'Numéro Rue', 'Rue', 'Ville',
            'Code Postal', 'Sur Place', 'À Emporter', 'Livraison', 'Retrait Trottoir',
            'Accès Fauteuil Roulant', 'Date de Création'
        ]


# Configure logging
logger = logging.getLogger(__name__)

# Define the scope for Google Sheets API
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def validate_gsheet_access(sheet_id: str, credentials: Optional[Credentials]) -> bool:
    """
    Validates access to a Google Sheet using pre-parsed service account credentials.

    Args:
        sheet_id: The ID of the target Google Spreadsheet.
        credentials: The google.oauth2.service_account.Credentials object.

    Returns:
        True if access is successful, False otherwise.
    """
    logger.info(f"Validating access to Google Sheet ID: {sheet_id}")
    if not credentials:
        logger.error("Validation failed: No credentials provided.")
        return False

    try:
        logger.debug("Authorizing gspread client with provided credentials...")
        gc = gspread.authorize(credentials)
        logger.info("Authentication successful for validation.")

        logger.debug(f"Attempting to open Google Sheet with ID: {sheet_id}")
        spreadsheet = gc.open_by_key(sheet_id)
        logger.info(f"Successfully opened spreadsheet '{spreadsheet.title}' for validation.")
        return True
    # No FileNotFoundError needed here as we don't handle the file path
    except gspread.exceptions.APIError as api_error:
        logger.error(f"Validation failed: Google Sheets API error - {api_error}", exc_info=True)
        if "PERMISSION_DENIED" in str(api_error):
            logger.error("Suggestion: Ensure the service account email associated with the credentials has 'Editor' permissions on the target Google Sheet.")
        elif "Not Found" in str(api_error) or "Requested entity was not found" in str(api_error):
             logger.error("Suggestion: Double-check if the provided Google Sheet ID is correct.")
        return False
    except Exception as e:
        logger.error(f"Validation failed: An unexpected error occurred - {e}", exc_info=True)
        return False


def upload_csv_to_sheets(csv_path: str, sheet_id: str, tab_name: str, credentials: Optional[Credentials], mode: str) -> None:
    """
    Uploads data from a CSV file to a Google Sheet tab using parsed credentials.
    - If mode is 'create', overwrites the tab.
    - If mode is 'append', merges CSV data with existing sheet data, de-duplicates, then overwrites tab.
    """
    logger.info(f"Starting upload process for CSV '{csv_path}' to Sheet ID '{sheet_id}', Tab '{tab_name}', Mode: '{mode}'")

    if not credentials:
        logger.error("Upload failed: No credentials provided.")
        raise ValueError("Credentials are required for upload.")

    try:
        # 1. Authenticate using provided credentials
        logger.debug("Authorizing gspread client with provided credentials...")
        gc = gspread.authorize(credentials)
        logger.info("Authentication successful for upload.")

        # 2. Read CSV data (guaranteed clean by core.py)
        logger.debug(f"Reading final CSV file: {csv_path}")
        df_csv = pd.DataFrame(columns=CSV_HEADERS_FR) # Initialize with schema
        try:
            df_csv = pd.read_csv(csv_path, keep_default_na=False, dtype=str)
            df_csv = df_csv.reindex(columns=CSV_HEADERS_FR, fill_value="")
            df_csv = df_csv.fillna("")
            logger.info(f"Successfully read {len(df_csv)} data rows from final CSV.")
        except FileNotFoundError:
            logger.error(f"Final CSV file not found at path: {csv_path}. Cannot upload.")
            raise
        except pd.errors.EmptyDataError:
             logger.warning(f"Final CSV file {csv_path} is empty. Will upload empty data or just headers.")
             # df_csv remains empty with correct columns
        except Exception as e:
            logger.error(f"Error reading final CSV file {csv_path}: {e}", exc_info=True)
            raise

        # 3. Open Google Sheet
        logger.debug(f"Opening Google Sheet with ID: {sheet_id}")
        spreadsheet = gc.open_by_key(sheet_id)
        logger.info(f"Successfully opened spreadsheet: '{spreadsheet.title}'")

        # 4. Handle Worksheet based on mode
        worksheet = None
        df_to_upload = pd.DataFrame(columns=CSV_HEADERS_FR) # Initialize final df

        try:
            worksheet = spreadsheet.worksheet(tab_name)
            logger.info(f"Found existing worksheet '{tab_name}'.")

            if mode == 'append':
                logger.info("Mode 'append': Reading existing data from sheet...")
                sheet_data = worksheet.get_all_values()
                if len(sheet_data) > 1:
                    df_sheet_old = pd.DataFrame(sheet_data[1:], columns=sheet_data[0])
                    df_sheet_old = df_sheet_old.astype(str)
                    df_sheet_old = df_sheet_old.reindex(columns=CSV_HEADERS_FR, fill_value="")
                    df_sheet_old = df_sheet_old.fillna("")
                    logger.info(f"Read {len(df_sheet_old)} rows from existing sheet.")

                    logger.info("Combining sheet data and CSV data...")
                    df_combined = pd.concat([df_sheet_old, df_csv], ignore_index=True)
                    df_combined['ID Place'] = df_combined['ID Place'].astype(str)
                    df_final = df_combined.drop_duplicates(subset=['ID Place'], keep='last')
                    logger.info(f"Combined and de-duplicated data. Final row count: {len(df_final)}")
                    df_to_upload = df_final[CSV_HEADERS_FR]

                else:
                    logger.info("Existing sheet is empty or has only headers. Using only CSV data.")
                    df_to_upload = df_csv[CSV_HEADERS_FR]

            else: # mode == 'create'
                logger.info("Mode 'create': Will overwrite sheet with CSV data.")
                df_to_upload = df_csv[CSV_HEADERS_FR]

            logger.info("Clearing existing worksheet content...")
            worksheet.clear()
            logger.info("Worksheet cleared.")

        except gspread.exceptions.WorksheetNotFound:
            logger.info(f"Worksheet '{tab_name}' not found. Creating new worksheet...")
            worksheet = spreadsheet.add_worksheet(title=tab_name, rows=1, cols=len(CSV_HEADERS_FR))
            logger.info(f"Created new worksheet '{tab_name}'.")
            df_to_upload = df_csv[CSV_HEADERS_FR]

        except Exception as e:
            logger.error(f"Error handling worksheet '{tab_name}': {e}", exc_info=True)
            raise

        # 5. Upload final DataFrame to the worksheet
        if worksheet:
            logger.info(f"Uploading {len(df_to_upload)} rows and {len(df_to_upload.columns)} columns to worksheet '{tab_name}'...")
            set_with_dataframe(worksheet=worksheet, dataframe=df_to_upload, include_index=False, include_column_header=True, resize=True)
            logger.info("DataFrame successfully uploaded.")
        else:
             logger.error("Failed to obtain a valid worksheet object. Upload aborted.")
             raise Exception("Could not get or create the target worksheet.")

        logger.info(f"Successfully processed upload for sheet '{spreadsheet.title}' tab '{tab_name}' (Mode: {mode}).")

    except FileNotFoundError:
        raise
    except gspread.exceptions.APIError as api_error:
        logger.error(f"Google Sheets API Error during upload: {api_error}", exc_info=True)
        if "PERMISSION_DENIED" in str(api_error):
             logger.error("Ensure the service account email associated with the credentials has 'Editor' permissions on the target Google Sheet.")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during the upload process: {e}", exc_info=True)
        raise

# Standalone execution part needs to be adapted or removed if not needed,
# as it currently relies on key_file_path argument.
# For now, let's comment it out as the primary use is via streamlit_app.py
#
# if __name__ == '__main__':
#     import argparse
#     import sys
#
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s')
#
#     parser = argparse.ArgumentParser(description="Upload a CSV file to Google Sheets.")
#     parser.add_argument("--csv-file", required=True, help="Path to the input CSV file.")
#     parser.add_argument("--sheet-id", required=True, help="ID of the target Google Spreadsheet.")
#     parser.add_argument("--tab-name", required=True, help="Name of the target tab.")
#     parser.add_argument("--key-file", required=True, help="Path to the Service Account JSON key file.") # This needs changing
#     parser.add_argument("--mode", required=True, choices=['create', 'append'], help="Upload mode: 'create' (overwrite) or 'append' (merge then overwrite).")
#     parser.add_argument("--validate-only", action='store_true', help="Only validate access, do not upload.")
#
#     args = parser.parse_args()
#
#     # --- Need to load credentials from file here for standalone ---
#     creds = None
#     try:
#          creds = Credentials.from_service_account_file(args.key_file, scopes=SCOPES)
#     except Exception as e:
#          logger.error(f"Failed to load credentials from key file {args.key_file}: {e}")
#          sys.exit(1)
#     # --- End credential loading ---
#
#     validation_passed = False
#     try:
#         logger.info("Running validation check...")
#         validation_passed = validate_gsheet_access(args.sheet_id, creds) # Pass creds object
#         if validation_passed:
#              logger.info("Validation successful.")
#         else:
#              logger.error("Validation failed. See logs for details.")
#              sys.exit(1) # Exit if validation fails
#
#         if args.validate_only:
#             logger.info("Validation only mode finished.")
#             sys.exit(0)
#
#         # Proceed with upload if not validate-only and validation passed
#         upload_csv_to_sheets(
#             csv_path=args.csv_file,
#             sheet_id=args.sheet_id,
#             tab_name=args.tab_name,
#             credentials=creds, # Pass creds object
#             mode=args.mode
#         )
#         logger.info("Standalone script execution completed successfully.")
#         sys.exit(0)
#
#     except Exception as e:
#         logger.error(f"Standalone script execution failed: {e}")
#         sys.exit(1)
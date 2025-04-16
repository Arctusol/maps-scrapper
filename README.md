# Google Maps Scraper (Streamlit Version)
[![Oxylabs promo code](https://raw.githubusercontent.com/oxylabs/how-to-scrape-google-scholar/refs/heads/main/Google-Scraper-API-1090x275.png)](https://oxylabs.go2cloud.org/aff_c?offer_id=7&aff_id=877&url_id=112)

[![](https://dcbadge.vercel.app/api/server/eWsVUJrnG5)](https://discord.com/invite/Pds3gBmKMH)

- [Google Maps Scraper (Streamlit Version)](#google-maps-scraper-streamlit-version)
  * [Overview](#overview)
  * [Prerequisites](#prerequisites)
  * [Installation](#installation)
  * [Google Sheets Setup (Optional Upload Feature)](#google-sheets-setup-optional-upload-feature)
    - [1. Create Service Account & Key File](#1-create-service-account--key-file)
    - [2. Enable APIs](#2-enable-apis)
    - [3. Share Google Sheet](#3-share-google-sheet)
  * [Running the Application](#running-the-application)
  * [Using the Streamlit App](#using-the-streamlit-app)
    - [1. Input Mode Selection](#1-input-mode-selection)
    - [2. Search Parameters](#2-search-parameters)
    - [3. Intermediate CSV File](#3-intermediate-csv-file)
    - [4. Google Sheets Upload (Optional)](#4-google-sheets-upload-optional)
    - [5. Launching the Process](#5-launching-the-process)
    - [6. Saving/Loading Configuration](#6-savingloading-configuration)
  * [Notes](#notes)
  * [Oxylabs Google Maps Scraper](#oxylabs-google-maps-scraper)
  * [How it works](#how-it-works)
    + [Python code example](#python-code-example)
    + [Output Example](#output-example)

## Overview

This tool extracts data from Google Maps using Python and provides a web-based interface built with Streamlit. It allows scraping search results based either on a Google Maps URL or manually specified parameters, and optionally uploading the results directly to a specified Google Sheet.

The second part of the tutorial shows how to use Oxylabs API for more effective, bigger scale scraping (you can get a free trial [here](https://dashboard.oxylabs.io/en/).

## Prerequisites

*   **Python:** Version 3.11 or higher installed.
*   **Google API Key:** You need a Google Cloud API key with the "Places API" enabled. This key should be stored in a `.env` file in the project root directory with the variable name `GOOGLE_MAPS_API_KEY`.
    ```dotenv
    # .env
    GOOGLE_MAPS_API_KEY=YOUR_API_KEY_HERE
    ```
*   **(Optional) Google Cloud Service Account:** Required *only* if you want to use the automatic Google Sheets upload feature. See [Google Sheets Setup](#google-sheets-setup-optional-upload-feature).

## Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/your-username/google-maps-scraper.git # Replace with actual repo URL if different
    cd google-maps-scraper
    ```
2.  **Install Dependencies:** This project uses Poetry for dependency management.
    ```bash
    make install
    # Or directly using poetry:
    # poetry install
    ```
    This will install all necessary libraries, including `streamlit`, `requests`, `pydantic`, `gspread`, `google-auth`, and `pandas`.

## Google Sheets Setup (Optional Upload Feature)

If you want the scraper to automatically upload the results to Google Sheets, follow these steps:

### 1. Create Service Account & Key File

*   Go to the [Google Cloud Console](https://console.cloud.google.com/).
*   Select your project.
*   Navigate to "IAM & Admin" -> "Service Accounts".
*   Click "+ CREATE SERVICE ACCOUNT", give it a name (e.g., `google-sheets-uploader`), and click "CREATE AND CONTINUE".
*   Grant it a role that allows editing Sheets. The "Editor" role is simple, but use with caution. Click "CONTINUE".
*   Skip step 3 (Grant users access) and click "DONE".
*   Find the created service account, click on its email address.
*   Go to the "KEYS" tab.
*   Click "ADD KEY" -> "Create new key".
*   Choose "JSON" and click "CREATE".
*   A JSON key file will be downloaded. **Keep this file secure!** Open the downloaded file and copy its entire content. You will paste this content into the Streamlit app later.

### 2. Enable APIs

*   In the Google Cloud Console, go to "APIs & Services" -> "Library".
*   Search for and enable the **"Google Sheets API"**.
*   Ensure the **"Places API"** (used for scraping) is also enabled.

### 3. Share Google Sheet

*   Open the Google Sheet where you want to upload the data.
*   Click the "Share" button (top right).
*   Enter the email address of the Service Account you created (it looks like `your-service-account-name@your-project-id.iam.gserviceaccount.com`, found in the downloaded JSON key file as `"client_email"`).
*   Give it **"Editor"** permissions.
*   Click "Send" or "Save".

## Running the Application

Once dependencies are installed, launch the Streamlit web application from the project's root directory:

```bash
streamlit run streamlit_app.py
```

This will start a local web server and open the application in your default web browser.

## Using the Streamlit App

The web interface provides fields to configure the scraping and optional upload process:

<img width="700" alt="Streamlit App Screenshot" src="placeholder_streamlit_screenshot.png"> <!-- TODO: Add a screenshot of the Streamlit app -->

### 1. Input Mode Selection

*   Choose how you want to specify the search:
    *   **URL (...):** Extracts the keyword from a Google Maps URL and uses a default search area/grid (currently Paris).
    *   **Paramètres Manuels (...):** Allows you to specify the keyword, search area bounding box, and grid parameters directly.

### 2. Search Parameters

*   Depending on the mode selected in step 1, either the **URL** input or the **Manual Parameters** section will be active.
    *   **URL:** Paste a Google Maps search results URL.
    *   **Manual Parameters:** Fill in the Keyword, SW/NE Latitude/Longitude, Grid Steps, and Search Radius. Ensure numeric fields are valid numbers and steps/radius are positive integers.

### 3. Intermediate CSV File

*   **Nom du fichier CSV:** Specify the base name for the CSV file where results will be saved (e.g., `results.csv`). This file is saved on the server where the Streamlit app is running.
*   **Mode d'écriture CSV:**
    *   `create`: Overwrites the CSV file if it exists.
    *   `append`: Reads the existing CSV, combines with new results, removes duplicates (based on 'ID Place', keeping newest), then overwrites the CSV with the merged data.

### 4. Google Sheets Upload (Optional)

Expand this section and fill in the details *only* if you want to upload results to Google Sheets.

*   **ID Google Sheet:** The unique ID of your target Google Spreadsheet (from its URL).
*   **Nom de l'onglet (Tab):** The exact name of the sheet (tab) for upload. It will be created if it doesn't exist.
*   **Contenu du fichier Clé Service Account (.json):** Paste the *entire content* of the JSON key file you downloaded during setup into this text area.

### 5. Launching the Process

*   Click the **"🚀 Lancer la Recherche et l'Upload"** button.
*   The app will validate inputs. If Sheets upload is configured, it will attempt to validate access using the pasted credentials.
*   A spinner will indicate that the process is running:
    1.  Scraping Google Maps based on the selected parameters.
    2.  Saving/updating the results CSV file on the server.
    3.  If configured and validated, uploading the data to the specified Google Sheet tab (respecting the 'create' or 'append' mode for the *sheet* content).
*   Status messages (success, warnings, errors) will be displayed.
*   If successful, an optional preview of the results DataFrame and a download button for the final CSV file will appear.

### 6. Saving/Loading Configuration

*   **Sauvegarder Configuration:** Click this button to download a `.json` file containing all the current settings from the UI.
*   **Charger Configuration:** Click the "Browse files" button to upload a previously saved `.json` configuration file. The UI fields will update with the loaded settings.

## Notes

*   When using "URL" mode, the search area defaults to Paris. Modify `DEFAULT_GRID_PARAMS` in `streamlit_app.py` if needed.
*   The generated CSV file is saved on the server running the Streamlit app. The download button allows you to get a copy.
*   Ensure your Google Maps API key (`.env`) and Google Sheets setup (pasted key content, sharing, enabled APIs) are correct if using those features. Check server logs (in the terminal where you ran `streamlit run`) for detailed error messages.

## Oxylabs Google Maps Scraper

(Content for Oxylabs remains unchanged...)

## How it works

(Content for Oxylabs remains unchanged...)

### Python code example

(Content for Oxylabs remains unchanged...)

### Output Example

(Content for Oxylabs remains unchanged...)

From local landmarks to various businesses, with Oxylabs’ Google Maps
Scraper you’ll easily access the public data you need. If you have any
questions or need assistance, don’t hesitate to contact our 24/7 support
team via live chat or [<u>email</u>](mailto:support@oxylabs.io).

Read More Google Scraping Related Repositories: [Google Sheets for Basic Web Scraping](https://github.com/oxylabs/web-scraping-google-sheets), [How to Scrape Google Shopping Results](https://github.com/oxylabs/scrape-google-shopping), [Google Play Scraper](https://github.com/oxylabs/google-play-scraper), [How To Scrape Google Jobs](https://github.com/oxylabs/how-to-scrape-google-jobs), [Google News Scrpaer](https://github.com/oxylabs/google-news-scraper), [How to Scrape Google Scholar](https://github.com/oxylabs/how-to-scrape-google-scholar), [How to Scrape Google Flights with Python](https://github.com/oxylabs/how-to-scrape-google-flights), [How To Scrape Google Images](https://github.com/oxylabs/how-to-scrape-google-images), [Scrape Google Search Results](https://github.com/oxylabs/scrape-google-python), [Scrape Google Trends](https://github.com/oxylabs/how-to-scrape-google-trends)

Also, check this tutorial on [pypi](https://pypi.org/project/google-maps-scraper-api/).

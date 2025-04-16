# Plan: Integrate Google Sheets Upload into Scraper GUI

**Goal:** Modify the existing Google Maps scraper application to allow users to specify a target Google Sheet and automatically upload the scraped CSV data to it, overwriting the specified tab if it exists.

**Plan:**

1.  **Add Dependencies:**
    *   Modify `pyproject.toml` to include necessary libraries:
        *   `gspread`: For Google Sheets API interaction.
        *   `google-auth`: For Google Authentication.
        *   `pandas`: (Already included) For reading CSV.
        *   *Optional but recommended for easier DataFrame upload:* `gspread-dataframe`.

2.  **Create Uploader Logic (`src/google_maps_scraper/sheets_uploader.py`):**
    *   Create a new file `src/google_maps_scraper/sheets_uploader.py`.
    *   Define a function `upload_csv_to_sheets(csv_path: str, sheet_id: str, tab_name: str, key_file_path: str) -> None`.
    *   **Inside the function:**
        *   Use `google-auth` and the `key_file_path` to authenticate with Google APIs using defined scopes (`https://www.googleapis.com/auth/spreadsheets`).
        *   Initialize the `gspread` client with the credentials.
        *   Use `pandas.read_csv(csv_path)` to load the CSV data.
        *   Open the Google Spreadsheet using `gspread_client.open_by_key(sheet_id)`.
        *   Try to get the worksheet by `tab_name`.
        *   **If worksheet exists:** Clear it using `worksheet.clear()`.
        *   **If worksheet doesn't exist:** Create it using `spreadsheet.add_worksheet(title=tab_name, rows=1, cols=1)`. (Initial size, gspread handles resizing).
        *   Get a reference to the (now empty or new) worksheet.
        *   Upload the pandas DataFrame content (headers + data) to the worksheet. Use `gspread_dataframe.set_with_dataframe(worksheet, dataframe)` if added, otherwise manually format and use `worksheet.update()`.
        *   Implement `try...except` blocks for file errors, authentication errors, API errors, etc.
        *   Use Python's `logging` module for status updates.

3.  **Modify GUI (`src/google_maps_scraper/gui.py`):**
    *   Add new `ttk.Label` and `ttk.Entry` widgets for:
        *   "Google Sheet ID:"
        *   "Target Tab Name:"
        *   "Service Account Key File:"
    *   Add a `ttk.Button` ("Browse...") next to the key file entry, linked to `filedialog.askopenfilename` to select the `.json` key file.
    *   Modify `start_scraping_process`:
        *   Get the values from the new Sheet ID, Tab Name, and Key File Path entries.
        *   Pass these values as additional arguments when creating the `scraping_thread`.
    *   Modify `run_scraping_in_thread`:
        *   Accept Sheet ID, Tab Name, Key File Path as parameters.
        *   After `run_grid_search_and_save` completes:
            *   Check for errors from scraping. If none:
                *   Update GUI button state/text (e.g., "Uploading...").
                *   `from .sheets_uploader import upload_csv_to_sheets`
                *   Call `upload_csv_to_sheets(csv_path, sheet_id, tab_name, key_file_path)`.
                *   Catch potential exceptions from the upload function.
            *   Update the final `messagebox` to indicate success/failure of both scraping and uploading.
        *   Ensure the button is correctly re-enabled in the `finally` block after all operations.

4.  **Update `core.py`:** No changes currently expected.

5.  **Documentation (`README.md`):**
    *   Add instructions for installing new dependencies (`poetry install`).
    *   Explain how to get a Service Account JSON key file from Google Cloud Console.
    *   Instruct users to share their target Google Sheet with the Service Account email address (giving it Editor permissions).
    *   Describe the new GUI fields for Google Sheets configuration.

**Workflow Diagram:**

```mermaid
graph TD
    subgraph User Interaction in GUI
        A[Enters Scrape Params (URL, CSV File, Mode)] --> B;
        B[Enters Sheets Params (Sheet ID, Tab Name, Key File Path)] --> C;
        C -- Clicks "Start Scrape & Upload" --> D{GUI: start_scraping_process};
    end

    subgraph Background Thread (run_scraping_in_thread)
        D --> E[Get All Params from GUI];
        E --> F(Call core.py: run_grid_search_and_save);
        F -- CSV Path --> G{Scraping Done?};
        G -- Yes --> H[Update GUI Button: "Uploading..."];
        H --> I(Import & Call sheets_uploader.upload_csv_to_sheets);
        I -- Status --> J{Upload Done?};
        J -- Yes/Error --> K[Update GUI Button: "Done" / Re-enable];
        K --> L[Show Final Status Messagebox];
        G -- Error --> K; # Scraping Error
        J -- Error --> K; # Upload Error
    end

    subgraph Prerequisites
        M[Service Account Key File] --> B;
        N[Sheet Shared with Service Account] --> I;
        O[Dependencies Installed] --> I;
    end
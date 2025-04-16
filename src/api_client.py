"""
Client for interacting with the Google Maps Places API.
"""

import os
import time
import logging
import requests
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from .models import PlaceDetails # Assuming models.py is in the same directory

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GoogleMapsApiError(Exception):
    """Custom exception for API errors."""
    pass

class GoogleMapsApiClient:
    """Handles requests to the Google Maps Places API."""

    BASE_URL = "https://maps.googleapis.com/maps/api/place"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initializes the client.

        Args:
            api_key: Google Maps API Key. If None, attempts to read from
                     the GOOGLE_MAPS_API_KEY environment variable.

        Raises:
            ValueError: If the API key is not provided and cannot be found
                        in the environment variables.
        """
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY")
        if not self.api_key:
            raise ValueError("Google Maps API key not provided or found in environment variable GOOGLE_MAPS_API_KEY.")
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        logger.info("GoogleMapsApiClient initialized.")

    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Makes a request to a specified API endpoint."""
        params['key'] = self.api_key
        url = f"{self.BASE_URL}/{endpoint}/json"
        logger.debug(f"Requesting URL: {url} with params: {params}")

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            data = response.json()
            status = data.get('status')

            if status not in ['OK', 'ZERO_RESULTS']:
                 error_message = data.get('error_message', 'Unknown API error')
                 logger.error(f"API Error ({status}): {error_message}")
                 # Specific handling for common errors
                 if status == 'REQUEST_DENIED':
                     raise GoogleMapsApiError(f"API request denied. Check your API key, billing status, and API enablement. Status: {status}, Message: {error_message}")
                 elif status == 'INVALID_REQUEST':
                     raise GoogleMapsApiError(f"Invalid request. Check parameters. Status: {status}, Message: {error_message}")
                 elif status == 'OVER_QUERY_LIMIT':
                      raise GoogleMapsApiError(f"Query limit exceeded. Status: {status}, Message: {error_message}")
                 else:
                     raise GoogleMapsApiError(f"API returned status '{status}': {error_message}")

            if status == 'ZERO_RESULTS':
                logger.warning(f"API returned ZERO_RESULTS for endpoint {endpoint} with params: {params}")
                return data # Return the data even if zero results

            logger.debug(f"API Response Status: {status}")
            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP Request failed: {e}")
            raise GoogleMapsApiError(f"HTTP Request failed: {e}") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred during API request: {e}")
            raise # Re-raise unexpected errors

    def nearby_search(
        self,
        location: str,
        radius: int,
        keyword: Optional[str] = None,
        place_type: Optional[str] = None,
        language: str = 'en' # Default to English if not specified
        ) -> List[str]:
        """
        Performs a Nearby Search request and handles pagination.

        Args:
            location: Latitude,Longitude string (e.g., "48.8584,2.2945").
            radius: Search radius in meters.
            keyword: Search term (e.g., "restaurant").
            place_type: Restricts results to places matching the specified type (e.g., "cafe").
                        See https://developers.google.com/maps/documentation/places/web-service/supported_types
            language: The language code (e.g., 'fr', 'en') for results.

        Returns:
            A list of unique Place IDs found.

        Raises:
            GoogleMapsApiError: If the API request fails or returns an error status.
        """
        endpoint = "nearbysearch"
        params = {
            "location": location,
            "radius": radius,
            "language": language,
        }
        if keyword:
            params["keyword"] = keyword
        if place_type:
             params["type"] = place_type # Note: 'type' is deprecated but still works for some cases. Consider alternatives if needed.

        all_place_ids = set()
        page_count = 0
        max_pages = 3 # Google typically returns max 60 results (3 pages of 20)

        logger.info(f"Starting Nearby Search: location={location}, radius={radius}, keyword='{keyword}', type='{place_type}'")

        while page_count < max_pages:
            page_count += 1
            logger.info(f"Requesting Nearby Search page {page_count}...")
            try:
                data = self._make_request(endpoint, params)
            except GoogleMapsApiError as e:
                 logger.error(f"Nearby Search failed on page {page_count}: {e}")
                 # Decide if we should return partial results or raise fully
                 if page_count > 1:
                     logger.warning("Returning partial results due to error on subsequent page.")
                     break
                 else:
                     raise # Reraise if error on the first page

            results = data.get('results', [])
            current_page_ids = {place['place_id'] for place in results if 'place_id' in place}
            new_ids_count = len(current_page_ids - all_place_ids)
            all_place_ids.update(current_page_ids)
            logger.info(f"Page {page_count}: Found {len(results)} results, {new_ids_count} new unique Place IDs. Total unique: {len(all_place_ids)}")


            next_page_token = data.get('next_page_token')
            if not next_page_token:
                logger.info("No more pages available.")
                break

            # IMPORTANT: Wait before requesting the next page token
            logger.info("Waiting before requesting next page...")
            time.sleep(2) # Google requires a short delay before using the next_page_token
            # Language parameter is not needed for next page requests, only pagetoken
            params = {"pagetoken": next_page_token}

        logger.info(f"Nearby Search finished. Found {len(all_place_ids)} unique Place IDs in {page_count} pages.")
        return list(all_place_ids)


    def get_place_details(
        self,
        place_id: str,
        fields: List[str],
        language: str = 'en' # Default to English if not specified
        ) -> Optional[Dict[str, Any]]:
        """
        Retrieves details for a specific Place ID.

        Args:
            place_id: The Place ID to query.
            fields: A list of fields to retrieve (e.g., ['name', 'rating', 'formatted_phone_number']).
                    See https://developers.google.com/maps/documentation/places/web-service/place-details#fields
            language: The language code (e.g., 'fr', 'en') for results.

        Returns:
            A dictionary containing the requested place details, or None if an error occurs
            or ZERO_RESULTS is returned for this specific place_id.

        Raises:
            GoogleMapsApiError: If the API request fails or returns an error status other than ZERO_RESULTS.
        """
        endpoint = "details"
        params = {
            "place_id": place_id,
            "fields": ",".join(fields),
            "language": language,
        }
        logger.info(f"Requesting Place Details for Place ID: {place_id}")
        try:
            data = self._make_request(endpoint, params)
            if data.get('status') == 'OK':
                return data.get('result')
            elif data.get('status') == 'ZERO_RESULTS':
                 logger.warning(f"Place Details returned ZERO_RESULTS for Place ID: {place_id}")
                 return None # Indicate that this specific place ID yielded no results
            else:
                # Should have been caught by _make_request, but double-check
                raise GoogleMapsApiError(f"Unexpected status in Place Details response: {data.get('status')}")
        except GoogleMapsApiError as e:
            logger.error(f"Failed to get Place Details for {place_id}: {e}")
            # Decide whether to return None or re-raise. Returning None might be
            # preferable in a batch process to avoid stopping the whole run.
            return None
        except Exception as e:
             logger.error(f"Unexpected error getting Place Details for {place_id}: {e}")
             return None # Or re-raise depending on desired behavior
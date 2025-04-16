"""
Pydantic models for Google Maps API data.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PlaceOpeningHoursPeriodDetail(BaseModel):
    day: int # 0-6, Sunday to Saturday
    time: str # "HHMM"

class PlaceOpeningHoursPeriod(BaseModel):
    open: PlaceOpeningHoursPeriodDetail
    close: Optional[PlaceOpeningHoursPeriodDetail] = None # May be missing for 24h places

class PlaceOpeningHours(BaseModel):
    open_now: Optional[bool] = None
    periods: Optional[List[PlaceOpeningHoursPeriod]] = None
    weekday_text: Optional[List[str]] = None

# --- New Models for Added Fields ---
class PlaceGeometryLocation(BaseModel):
    lat: float
    lng: float

class PlaceGeometry(BaseModel):
    location: PlaceGeometryLocation
    # viewport: Optional[Dict[str, Any]] = None # Add if needed

class PlaceAddressComponent(BaseModel):
    long_name: str
    short_name: str
    types: List[str]
# --- End New Models ---


class PlaceDetails(BaseModel):
    # --- Fields directly from API ---
    place_id: str = Field(..., alias='Place Id')
    name: str = Field(..., alias='Name')
    user_ratings_total: Optional[int] = Field(None, alias='Reviews')
    rating: Optional[float] = Field(None, alias='Rating')
    website: Optional[str] = Field(None, alias='Website')
    international_phone_number: Optional[str] = Field(None, alias='Phone')
    types: Optional[List[str]] = None # Raw types list
    opening_hours: Optional[PlaceOpeningHours] = None # Raw opening hours
    business_status: Optional[str] = None # e.g., OPERATIONAL, CLOSED_TEMPORARILY
    formatted_address: Optional[str] = Field(None, alias='Address')
    url: str = Field(..., alias='Link') # Google Maps URL

    # --- New fields from API ---
    geometry: Optional[PlaceGeometry] = None
    price_level: Optional[int] = None
    address_components: Optional[List[PlaceAddressComponent]] = None
    dine_in: Optional[bool] = None
    takeout: Optional[bool] = None
    delivery: Optional[bool] = None
    curbside_pickup: Optional[bool] = None
    wheelchair_accessible_entrance: Optional[bool] = None
    # --- End New fields from API ---


    # --- Derived/Formatted fields for CSV output (matching PLAN.md + New) ---
    query: Optional[str] = Field(None, alias='Query')
    description: str = Field("N/A", alias='Description') # Placeholder
    owner_name: str = Field("N/A", alias='Owner Name') # Placeholder
    main_category: Optional[str] = Field(None, alias='Main Category')
    categories_str: Optional[str] = Field(None, alias='Categories') # Comma-separated types
    workday_timing: Optional[str] = Field(None, alias='Workday Timing') # Formatted weekday_text
    is_temporarily_closed: Optional[bool] = Field(None, alias='Is Temporarily Closed') # Derived from business_status
    closed_on: str = Field("N/A", alias='Closed On') # Placeholder
    review_keywords: str = Field("N/A", alias='Review Keywords') # Placeholder

    # --- New derived/formatted fields for CSV ---
    latitude: Optional[float] = Field(None, alias='Latitude')
    longitude: Optional[float] = Field(None, alias='Longitude')
    price_level_display: Optional[str] = Field(None, alias='Price Level') # e.g., "$$"
    street_number: Optional[str] = Field(None, alias='Street Number')
    route: Optional[str] = Field(None, alias='Route') # Street name
    locality: Optional[str] = Field(None, alias='Locality') # City
    postal_code: Optional[str] = Field(None, alias='Postal Code')
    dine_in_csv: Optional[str] = Field(None, alias='Dine In') # TRUE/FALSE/N/A
    takeout_csv: Optional[str] = Field(None, alias='Takeout') # TRUE/FALSE/N/A
    delivery_csv: Optional[str] = Field(None, alias='Delivery') # TRUE/FALSE/N/A
    curbside_pickup_csv: Optional[str] = Field(None, alias='Curbside Pickup') # TRUE/FALSE/N/A
    wheelchair_accessible_csv: Optional[str] = Field(None, alias='Wheelchair Accessible') # TRUE/FALSE/N/A
    # --- End New derived/formatted fields ---


    class Config:
        populate_by_name = True # Allows using aliases during instantiation (Pydantic V2+)
        # If you need to handle extra fields from API response gracefully:
        # extra = 'ignore'

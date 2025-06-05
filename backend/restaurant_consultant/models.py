from pydantic import BaseModel, Field, HttpUrl, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import logging
from pydantic import field_validator

logger = logging.getLogger(__name__)

# Custom URL type that allows S3 URLs for testing
class FlexibleUrl(str):
    """Custom URL type that accepts HTTP, HTTPS, and S3 schemes"""
    
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema
        return core_schema.no_info_after_validator_function(cls.validate, core_schema.str_schema())
    
    @classmethod
    def validate(cls, v):
        if isinstance(v, str):
            if v.startswith(('http://', 'https://', 's3://')):
                return cls(v)
            else:
                # Try to validate as HTTP URL for other cases
                from pydantic import HttpUrl
                return str(HttpUrl(v))
        return str(v)

class ScreenshotInfo(BaseModel):
    s3_url: FlexibleUrl  # Allow S3 URLs for testing
    caption: Optional[str] = None
    source_phase: Optional[int] = None # e.g., 2 for DOM crawler, 4 for Stagehand
    taken_at: Optional[datetime] = None

class MenuItem(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_original: Optional[str] = None
    price_cleaned: Optional[float] = None
    ai_categories: Optional[List[str]] = None
    # a_la_carte: Optional[bool] = False # Example, if we need more granularity later
    # combos_available: Optional[bool] = False # Example

class SocialMediaProfile(BaseModel):
    platform_name: str # e.g., "Facebook", "Instagram", "Yelp"
    url: HttpUrl
    username: Optional[str] = None
    followers: Optional[int] = None
    bio: Optional[str] = None

class GoogleMyBusinessData(BaseModel):
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    place_id: Optional[str] = None
    cid: Optional[str] = None # Customer ID, sometimes useful
    # Potentially add a list of recent review snippets later

class OperatingHours(BaseModel):
    day_of_week: str # e.g., "Monday", "Tuesday"
    open_time: Optional[str] = None # e.g., "09:00 AM"
    close_time: Optional[str] = None # e.g., "10:00 PM"
    raw_string: Optional[str] = None # Original hours string for this day

class CompetitorSummary(BaseModel):
    name: Optional[str] = None
    url: Optional[HttpUrl] = None
    # Basic contact info from initial lightweight scrape
    phone: Optional[str] = None
    email: Optional[str] = None
    # Placeholder for more detailed analysis if needed later
    # strengths: Optional[List[str]] = None
    # weaknesses: Optional[List[str]] = None
    # menu_highlights_s3_url: Optional[HttpUrl] = None

class LLMStrategicAnalysisOutput(BaseModel):
    # Executive Hook - Compelling opening for the report
    executive_hook: Optional[Dict[str, Any]] = Field(None, description="Executive hook with growth potential and urgency")
    
    # Competitive positioning analysis
    competitive_positioning: Optional[Dict[str, Any]] = Field(None, description="Market position and competitive analysis")
    
    # Top strategic opportunities with enhanced data support
    top_3_opportunities: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Prioritized opportunities with implementation details and data supporting evidence")
    
    # NEW: Cross-platform strategy recommendations
    cross_platform_strategy: Optional[Dict[str, Any]] = Field(None, description="Integrated strategy across delivery platforms, social media, and website")
    
    # Analysis metadata with enhanced tracking
    analysis_metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata about the analysis generation including data sources and platforms analyzed")
    
    # Legacy fields for backward compatibility
    competitive_landscape_summary: Optional[str] = Field(None, description="Overview of how the target restaurant stacks up.")
    prioritized_opportunities: List[Dict[str, Any]] = Field(default_factory=list, description="List of opportunities, each with a title, description, and ai_solution_pitch.")
    further_insights_teaser: Optional[str] = Field(None, description="Hint at deeper insights available in a paid service.")
    generic_success_tips: List[str] = Field(default_factory=list, description="Actionable, generic advice.")
    follow_up_engagement_questions: List[str] = Field(default_factory=list, description="Questions to encourage user to engage further.")

class ExtractionMetadata(BaseModel):
    extraction_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_duration_seconds: Optional[float] = None
    total_cost_usd: Optional[float] = 0.0
    phases_completed: List[int] = Field(default_factory=list)
    final_quality_score: Optional[float] = None
    overall_status: Optional[str] = Field(None, description="Overall extraction status: 'success', 'error', 'partial'")
    error_message: Optional[str] = None # Added to capture critical errors during extraction
    # Can add per-phase duration/cost details here later if needed

class StructuredAddress(BaseModel):
    street_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    full_address_text: Optional[str] = None # Original full address text

class SocialMediaLinks(BaseModel):
    facebook: Optional[HttpUrl] = None
    instagram: Optional[HttpUrl] = None
    twitter: Optional[HttpUrl] = None
    tiktok: Optional[HttpUrl] = None
    youtube: Optional[HttpUrl] = None
    linkedin: Optional[HttpUrl] = None
    yelp: Optional[HttpUrl] = None
    tripadvisor: Optional[HttpUrl] = None
    other_platforms: Optional[Dict[str, HttpUrl]] = None # For flexibility

class FinalRestaurantOutput(BaseModel):
    # Basic Info
    restaurant_name: Optional[str] = None
    website_url: HttpUrl
    canonical_url: Optional[HttpUrl] = Field(None, description="Canonical/final URL after redirects")
    description_short: Optional[str] = None # Short tagline or summary
    description_long_ai_generated: Optional[str] = None # AI-generated detailed description
    year_established: Optional[int] = None
    specialties: Optional[List[str]] = None
    primary_cuisine_type_ai: Optional[str] = None # e.g., "Italian", "Mexican", "Fine Dining"
    secondary_cuisine_types_ai: Optional[List[str]] = None
    cuisine_types: Optional[List[str]] = Field(default_factory=list, description="All cuisine types identified")
    price_range_ai: Optional[str] = None # e.g., "$", "$$", "$$$", "$$$$"
    price_range: Optional[str] = Field(None, description="Price range identifier")

    # Contact & Location - Raw and Canonical versions
    address_raw: Optional[str] = Field(None, description="Raw address as found on website")
    address_canonical: Optional[str] = Field(None, description="Cleaned/standardized address")
    structured_address: Optional[StructuredAddress] = None
    phone_raw: Optional[str] = Field(None, description="Raw phone number as found")
    phone_canonical: Optional[str] = Field(None, description="Cleaned/standardized phone number")
    canonical_phone_number: Optional[str] = None # Standardized format
    raw_phone_numbers: Optional[List[str]] = None # All found phone numbers
    canonical_email: Optional[str] = None
    raw_emails: Optional[List[str]] = None

    # Menu
    menu_items: Optional[List[MenuItem]] = Field(default_factory=list)
    full_menu_text_raw: Optional[str] = None # Concatenated raw text from all menu sources
    menu_pdf_s3_urls: Optional[List[FlexibleUrl]] = Field(default_factory=list)

    # Online Presence
    social_media_links: Optional[SocialMediaLinks] = None
    social_media_profiles: Optional[List[SocialMediaProfile]] = Field(default_factory=list)
    
    # Google Places Integration - Dedicated fields for better structure
    google_rating: Optional[float] = Field(None, description="Google Places rating (1-5 stars)")
    google_review_count: Optional[int] = Field(None, description="Total number of Google reviews")
    google_place_id: Optional[str] = Field(None, description="Google Places unique identifier")
    google_maps_url: Optional[HttpUrl] = Field(None, description="Google Maps URL for the restaurant")
    google_recent_reviews: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Recent Google reviews with author, rating, text")
    google_my_business: Optional[GoogleMyBusinessData] = Field(None, description="Google My Business data")
    
    # Legacy Google Places summary (for backward compatibility)
    google_places_summary: Optional[Dict[str, Any]] = None # Key info from Google Places API
    # e.g. rating, review_count, opening_hours, etc.
    # Potentially add specific fields from Google Places like:
    # google_rating: Optional[float] = None
    # google_review_count: Optional[int] = None
    # google_place_id: Optional[str] = None

    # Operating Hours
    operating_hours: Optional[List[OperatingHours]] = Field(default_factory=list)

    # Website Content & Structure
    extracted_text_blocks: Optional[Dict[str, str]] = None # e.g., {"about_us": "...", "our_story": "..."}
    sitemap_urls: Optional[List[HttpUrl]] = Field(default_factory=list)
    key_pages_found: Optional[List[str]] = Field(default_factory=list) # e.g. ['menu', 'contact', 'about']

    # Media
    screenshots: Optional[List[ScreenshotInfo]] = Field(default_factory=list, description="All screenshots captured")
    website_screenshots_s3_urls: Optional[List[ScreenshotInfo]] = Field(default_factory=list) # Comprehensive screenshots

    # Competitive Landscape
    competitors: Optional[List[CompetitorSummary]] = Field(default_factory=list, description="Identified competitors")
    identified_competitors_basic: Optional[List[CompetitorSummary]] = Field(default_factory=list)

    # LLM Analysis (to be populated later)
    llm_strategic_analysis: Optional[Dict[str, Any]] = None # Placeholder for rich analysis output

    # PDF Generation Info (Phase C results)
    pdf_generation_info: Optional[Dict[str, Any]] = Field(None, description="Results from PDF report generation")

    # Extraction Metadata
    extraction_metadata: Optional[ExtractionMetadata] = None

    # Data Provenance & Quality (Optional, for debugging and improvement)
    # data_sources: Optional[List[str]] = None # e.g. ["google_places", "dom_crawler_homepage", "ai_vision_menu_pdf"]
    # missing_critical_fields: Optional[List[str]] = None
    # overall_data_quality_score: Optional[float] = None # 0.0 to 1.0

    # Raw data for reprocessing if necessary
    # raw_html_content: Optional[Dict[str, str]] = None #  e.g. {"homepage_html": "<html>..."}

    class Config:
        validate_assignment = True
        # For HttpUrl and other complex types
        # json_encoders = {
        # HttpUrl: lambda v: str(v) if v else None,
        # }

    def __init__(self, **data: Any):
        super().__init__(**data)
        logger.info(f"FinalRestaurantOutput initialized for {data.get('restaurant_name', 'Unknown Restaurant')}")

    def log_completeness(self):
        # Basic logging of filled fields, can be expanded
        filled_fields = {k: v for k, v in self.dict().items() if v is not None and v != [] and v != {}}
        logger.info(f"FinalRestaurantOutput for {self.restaurant_name} has {len(filled_fields)} fields populated.")
        if self.menu_items:
            logger.info(f"Found {len(self.menu_items)} menu items.")
        if self.website_screenshots_s3_urls:
            logger.info(f"Found {len(self.website_screenshots_s3_urls)} screenshots.")

# Example Usage (can be removed or moved to a test file)
if __name__ == "__main__":
    example_restaurant_data = {
        "restaurant_name": "The Gourmet Place",
        "website_url": "http://example.com",
        "structured_address": {
            "street_address": "123 Main St",
            "city": "Anytown",
            "state": "CA",
            "zip_code": "90210",
            "country": "USA",
            "full_address_text": "123 Main St, Anytown, CA 90210"
        },
        "canonical_phone_number": "+15551234567",
        "menu_items": [
            {"name": "Spaghetti Carbonara", "price_original": "$15.99", "price_cleaned": 15.99, "ai_categories": ["Italian", "Pasta"]},
            {"name": "Margherita Pizza", "description": "Classic tomato, mozzarella, basil", "price_original": "12.50 EUR", "price_cleaned": 12.50, "ai_categories": ["Italian", "Pizza"]}
        ],
        "website_screenshots_s3_urls": [
            {"s3_url": "http://s3.example.com/screenshot1.png", "page_type": "homepage", "source_phase": "phase_2_dom_crawler"}
        ],
        "llm_strategic_analysis": {"key_finding": "Menu is well-priced for the area."}
    }
    try:
        restaurant_instance = FinalRestaurantOutput(**example_restaurant_data)
        print("Successfully created FinalRestaurantOutput instance:")
        print(restaurant_instance.json(indent=2))
        restaurant_instance.log_completeness()
    except Exception as e:
        print(f"Error creating instance: {e}")

    # Example of updating a field (if validate_assignment = True)
    # try:
    #     restaurant_instance.restaurant_name = "The New Gourmet Place"
    #     print(f"\nUpdated restaurant name: {restaurant_instance.restaurant_name}")
    # except ValidationError as e:
    #     print(f"Validation error on update: {e}")

    logger.info("Logging from models.py example execution.") 
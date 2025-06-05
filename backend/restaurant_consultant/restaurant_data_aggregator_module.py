import asyncio
import os
import json
import time
import uuid
from urllib.parse import urlparse
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, TypedDict, Union

# Async HTTP and file handling
import httpx
import aiofiles

# Existing imports
from bs4 import BeautifulSoup
import googlemaps
from textblob import TextBlob
import logging
from dotenv import load_dotenv

# Local imports
from restaurant_consultant.llm_analyzer_module import extract_menu_with_gemini
from restaurant_consultant.stagehand_integration import stagehand_scraper
from playwright.async_api import async_playwright
import openai

# Load environment variables
load_dotenv()

# Set up comprehensive logging with security considerations
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Log successful imports without exposing sensitive info
logger.info("Successfully imported all required packages")
logger.debug("googlemaps package imported successfully")
logger.debug("Enhanced async HTTP and file handling imported")

# Configuration with secure logging
BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Safe environment variable logging
def _log_env_status(var_name: str, value: Optional[str]) -> None:
    """Safely log environment variable status without exposing secrets."""
    if value:
        if var_name.endswith('_KEY') or var_name.endswith('_SECRET'):
            logger.info(f"Environment variable {var_name}: ✓ (configured)")
        else:
            logger.info(f"Environment variable {var_name}: ✓")
    else:
        logger.warning(f"Environment variable {var_name}: ✗ (missing)")

_log_env_status("GOOGLE_API_KEY", GOOGLE_API_KEY)
_log_env_status("OPENAI_API_KEY", OPENAI_API_KEY)
_log_env_status("BROWSERBASE_API_KEY", BROWSERBASE_API_KEY)

# Base directory for file operations
BASE_DIR = Path(__file__).parent.parent
MENUS_DIR = BASE_DIR / "menus"
ANALYSIS_DIR = BASE_DIR / "analysis_data"

# Ensure directories exist
MENUS_DIR.mkdir(exist_ok=True)
ANALYSIS_DIR.mkdir(exist_ok=True)
logger.info(f"Created directories - Menus: {MENUS_DIR}, Analysis: {ANALYSIS_DIR}")

# Enhanced type safety with Pydantic models
from pydantic import BaseModel, Field, HttpUrl
import textwrap

# Type definitions for better type safety
class RestaurantData(TypedDict, total=False):
    name: Optional[str]
    url: str
    html_content: str
    menu_screenshot: Optional[str]
    contact: Dict[str, Optional[str]]
    address: Optional[str]
    social_links: List[str]
    scraper_used: str

class CompetitorData(TypedDict, total=False):
    name: Optional[str]
    address: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    rating: Optional[float]
    review_count: int
    price_level: Optional[int]
    competitor_type: str

# Enhanced type definitions with Pydantic for better validation
class ContactInfo(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None

class MenuItems(BaseModel):
    name: str
    description: Optional[str] = None
    price: Optional[str] = None
    category: Optional[str] = None
    source: str = "unknown"

class RestaurantDataEnhanced(BaseModel):
    name: Optional[str] = None
    url: HttpUrl
    html_content: str = ""
    menu_screenshot: Optional[str] = None
    contact: ContactInfo = Field(default_factory=ContactInfo)
    address: Optional[str] = None
    social_links: List[str] = Field(default_factory=list)
    scraper_used: str = "unknown"
    menu_items: List[MenuItems] = Field(default_factory=list)

class GoogleReviewData(BaseModel):
    rating: Optional[float] = None
    total_reviews: int = 0
    avg_sentiment: float = 0.0
    reviews: List[Dict] = Field(default_factory=list)
    place_details: Dict = Field(default_factory=dict)
    opening_hours: Dict = Field(default_factory=dict)
    photos: Dict = Field(default_factory=dict)
    geometry: Dict = Field(default_factory=dict)
    data_quality: Dict = Field(default_factory=dict)

class CompetitorDataEnhanced(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    review_count: int = 0
    price_level: Optional[int] = Field(None, ge=0, le=4)  # Google's 0-4 scale
    competitor_type: str = "unknown"
    distance_km: Optional[float] = None

# Global browser instance for reuse
_playwright_browser = None
_browser_lock = asyncio.Lock()

async def get_shared_browser():
    """Get a shared Playwright browser instance for performance."""
    global _playwright_browser
    
    async with _browser_lock:
        if _playwright_browser is None:
            from playwright.async_api import async_playwright
            playwright = await async_playwright().start()
            _playwright_browser = await playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            logger.info("✅ Shared Playwright browser instance created")
        
        return _playwright_browser

async def cleanup_shared_browser():
    """Cleanup shared browser resources."""
    global _playwright_browser
    
    async with _browser_lock:
        if _playwright_browser:
            await _playwright_browser.close()
            _playwright_browser = None
            logger.info("🧹 Shared Playwright browser cleaned up")

# Google Maps client with connection reuse
_gmaps_client = None

def get_gmaps_client():
    """Get a reused Google Maps client for better performance."""
    global _gmaps_client
    if _gmaps_client is None and GOOGLE_API_KEY:
        _gmaps_client = googlemaps.Client(key=GOOGLE_API_KEY)
        logger.info("✅ Google Maps client initialized with connection reuse")
    return _gmaps_client

# Initialize OpenAI client safely - only when API key is available
def get_openai_client():
    """Get OpenAI client, initializing only when needed and API key is available."""
    if not OPENAI_API_KEY:
        logger.warning("OpenAI API key not found")
        return None
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        logger.debug("OpenAI client initialized successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {str(e)}")
        return None

async def get_website_data(url: str) -> Union[RestaurantDataEnhanced, Dict[str, str]]:
    """Scrape website using Stagehand first, then fallback to other methods."""
    logger.info(f"Starting website data extraction for {url}")
    
    # Try Stagehand first if available
    if stagehand_scraper.is_available():
        try:
            logger.info("Attempting to scrape with Stagehand")
            stagehand_result = await stagehand_scraper.scrape_restaurant(url)
            if stagehand_result and "error" not in stagehand_result:
                logger.info("Successfully extracted data using Stagehand")
                return stagehand_result
        except Exception as e:
            logger.warning(f"Stagehand scraping failed: {str(e)}, falling back to other methods")
    else:
        logger.info("Stagehand not available, using fallback methods")
    
    # Fallback to enhanced async requests approach (removing playwright call that was causing errors)
    logger.info("Falling back to enhanced async requests approach")
    return await get_website_data_fallback_async(url)

async def get_website_data_fallback_async(url: str) -> Union[RestaurantDataEnhanced, Dict[str, str]]:
    """Enhanced async fallback method using httpx instead of requests."""
    try:
        # Use async HTTP client with proper timeout and error handling
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=300.0,
            headers={"User-Agent": USER_AGENT}
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html_content = response.text
        
        soup = BeautifulSoup(html_content, "html.parser")

        # Extract contact info safely
        email = None
        phone = None
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        phone_pattern = r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
        
        # Safely get page text
        try:
            page_text = soup.get_text()
        except Exception as text_error:
            logger.warning(f"Error extracting text from soup: {text_error}")
            page_text = str(soup)
        
        email_match = re.search(email_pattern, page_text, re.I)
        phone_match = re.search(phone_pattern, page_text)

        if email_match:
            email = email_match.group(0)
        if phone_match:
            phone = phone_match.group(0)

        # Extract address safely
        address = None
        address_pattern = r"\d{1,5}\s+(?:[A-Z][a-zA-Z]+\s){1,2}(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Boulevard|Blvd\.?|Lane|Ln\.?|Drive|Dr\.?|Court|Ct\.?|Place|Pl\.?|Square|Sq\.?|Parkway|Pkwy\.?|Circle|Cir\.?)\b(?:,?\s*(?:Apt\.?|Suite|Ste\.?|Flat|Fl\.?)\s*\d+[A-Za-z]?)?,?\s*(?:[A-Z][a-zA-Z]+|[A-Z]{2,})\s*,?\s*[A-Z]{2}\s*\d{5}(?:[-\s]?\d{4})?\b"
        address_matches = re.finditer(address_pattern, page_text)
        for match in address_matches:
            address = match.group(0).strip()
            if address:
                break
        
        # Enhanced restaurant name extraction
        restaurant_name = None
        try:
            # Multiple strategies to extract restaurant name
            restaurant_name_tag = soup.find("h1")
            if restaurant_name_tag:
                potential_name = restaurant_name_tag.get_text().strip()
                if potential_name and not any(word in potential_name.lower() for word in ['home', 'homepage', 'home page', 'welcome']):
                    restaurant_name = potential_name
            
            if not restaurant_name and soup.title and soup.title.string:
                title_text = str(soup.title.string).strip()
                # Remove common suffixes from title
                for suffix in [' | Home', ' - Home', ' Home', ' | Official Site', ' - Official Site', 
                              ' | Menu', ' - Menu', ' | Restaurant', ' - Restaurant', ' | Delivery', ' - Delivery']:
                    if title_text.endswith(suffix):
                        title_text = title_text[:-len(suffix)].strip()
                        break
                
                if title_text and not any(word in title_text.lower() for word in ['home page', 'homepage']):
                    restaurant_name = title_text
            
            # Look for meta property og:site_name or og:title
            if not restaurant_name:
                og_site_name = soup.find("meta", property="og:site_name")
                if og_site_name and og_site_name.get("content"):
                    restaurant_name = og_site_name.get("content").strip()
                
                if not restaurant_name:
                    og_title = soup.find("meta", property="og:title")
                    if og_title and og_title.get("content"):
                        restaurant_name = og_title.get("content").strip()
            
            logger.info(f"Extracted restaurant name: '{restaurant_name}' using enhanced async fallback method")
                        
        except Exception as name_error:
            logger.warning(f"Error extracting restaurant name: {name_error}")
            restaurant_name = None

        # Create a placeholder screenshot path
        screenshot_path = MENUS_DIR / f"screenshot_{uuid.uuid4().hex}.png"

        # Extract social media links safely
        social_links = []
        try:
            for a in soup.find_all("a", href=True):
                href = a.get("href", "").lower()
                if any(platform in href for platform in ["facebook", "instagram", "twitter", "linkedin"]):
                    social_links.append(href)
        except Exception as social_error:
            logger.warning(f"Error extracting social links: {social_error}")

        logger.info(f"Successfully scraped website data for {restaurant_name or 'Unknown'} using async fallback method")
        return RestaurantDataEnhanced(
            name=restaurant_name,
            url=url,
            html_content=html_content,
            menu_screenshot=str(screenshot_path),
            contact=ContactInfo(
                email=email,
                phone=phone
            ),
            address=address,
            social_links=social_links,
            scraper_used="async_requests_fallback",
            menu_items=[]
        )
    except httpx.TimeoutException:
        logger.error(f"Timeout error accessing {url}")
        return {"error": "Request timeout"}
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code} for {url}")
        return {"error": f"HTTP {e.response.status_code}"}
    except Exception as e:
        logger.error(f"Error in async fallback website scraping for {url}: {str(e)}")
        return {"error": str(e)}

async def get_google_reviews(place_name: str, address: str) -> GoogleReviewData:
    """Fetch comprehensive Google Places data with improved rate limiting and error handling."""
    try:
        gmaps = get_gmaps_client()  # Use shared client
        if not gmaps:
            logger.error("Google Maps client not available")
            return GoogleReviewData()
        
        logger.info(f"🔍 Searching Google Places for: '{place_name}' at '{address}'")
        
        # Enhanced search query with fallback strategies
        search_queries = [
            f"{place_name} {address}",
            f"{place_name}",
            f"restaurant {place_name} {address}"
        ]
        
        places = None
        for query in search_queries:
            try:
                logger.info(f"📍 Trying search query: '{query}'")
                places = gmaps.places(query=query)
                if places["results"]:
                    logger.info(f"✅ Found {len(places['results'])} places with query: '{query}'")
                    break
                # Add small delay between queries to be respectful
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.warning(f"❌ Search query failed: '{query}' - {str(e)}")
                continue
        
        if not places or not places["results"]:
            logger.warning(f"🚫 No Google Places data found for '{place_name}' at '{address}'")
            return GoogleReviewData()
        
        # Get the best match (first result)
        place = places["results"][0]
        place_id = place["place_id"]
        logger.info(f"🎯 Using place: '{place.get('name')}' with ID: {place_id}")
        
        # Get comprehensive place details with proper field selection
        fields = [
            "rating", "user_ratings_total", "reviews", "formatted_address",
            "formatted_phone_number", "international_phone_number", "website",
            "opening_hours", "price_level", "photo", "geometry",
            "business_status", "editorial_summary", "vicinity", "place_id"
        ]
        
        logger.info(f"📊 Fetching detailed place information with {len(fields)} fields")
        details = gmaps.place(place_id=place_id, fields=fields)
        result = details["result"]
        
        # Extract comprehensive data with proper type conversion
        rating = result.get("rating", 0.0)
        total_reviews = result.get("user_ratings_total", 0)
        reviews = result.get("reviews", [])
        
        logger.info(f"⭐ Found rating: {rating}/5 with {total_reviews} total reviews")
        logger.info(f"📝 Retrieved {len(reviews)} recent reviews")
        
        # Get opening hours information
        opening_hours = result.get("opening_hours", {})
        hours_info = {
            "weekday_text": opening_hours.get("weekday_text", []),
            "open_now": opening_hours.get("open_now"),
            "periods": opening_hours.get("periods", [])
        }
        
        # Get photos information
        photos = result.get("photo", [])
        if not isinstance(photos, list):
            photos = [photos] if photos else []
        photo_references = [photo.get("photo_reference") for photo in photos[:10] if photo.get("photo_reference")]
        logger.info(f"📸 Found {len(photo_references)} photos")
        
        # Enhanced review analysis with proper rate limiting
        all_reviews = reviews.copy()
        next_page_token = details.get("next_page_token")
        page_count = 1
        
        while next_page_token and page_count < 3:  # Limit to 3 pages to avoid rate limits
            try:
                logger.info(f"📄 Fetching review page {page_count + 1}")
                # Google requires 2-second delay for next page token
                await asyncio.sleep(2.0)  # Proper rate limiting
                
                more_reviews = gmaps.place(place_id=place_id, fields=["reviews"], page_token=next_page_token)
                new_reviews = more_reviews["result"].get("reviews", [])
                all_reviews.extend(new_reviews)
                next_page_token = more_reviews.get("next_page_token")
                page_count += 1
                logger.info(f"📝 Added {len(new_reviews)} more reviews (total: {len(all_reviews)})")
            except Exception as e:
                logger.exception(f"❌ Failed to fetch review page {page_count + 1}: {str(e)}")
                break
        
        # Enhanced sentiment analysis with better error handling
        sentiments = []
        for review in all_reviews:
            try:
                # Consider using vaderSentiment for better results as suggested
                sentiment = TextBlob(review["text"]).sentiment.polarity
                sentiments.append(sentiment)
            except Exception as e:
                logger.debug(f"Sentiment analysis failed for review: {str(e)}")
        
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
        logger.info(f"🎭 Sentiment analysis: {avg_sentiment:.2f} average (from {len(sentiments)} reviews)")
        
        # Enhanced review data with proper validation
        processed_reviews = []
        for review in all_reviews:
            processed_reviews.append({
                "text": review.get("text", ""),
                "rating": review.get("rating"),
                "time": review.get("time"),
                "author_name": review.get("author_name"),
                "profile_photo_url": review.get("profile_photo_url"),
                "relative_time_description": review.get("relative_time_description")
            })
        
        # Safely handle price_level (0-4 scale)
        price_level = result.get("price_level")
        if price_level is not None:
            price_level = max(0, min(4, int(price_level)))  # Clamp to 0-4 range
        
        return GoogleReviewData(
            rating=float(rating) if rating else None,
            total_reviews=int(total_reviews),
            avg_sentiment=float(avg_sentiment),
            reviews=processed_reviews,
            place_details={
                "place_id": place_id,
                "formatted_address": result.get("formatted_address"),
                "phone": result.get("formatted_phone_number"),
                "international_phone": result.get("international_phone_number"),
                "website": result.get("website"),
                "price_level": price_level,
                "business_status": result.get("business_status"),
                "types": place.get("types", []),
                "vicinity": result.get("vicinity"),
                "editorial_summary": result.get("editorial_summary")
            },
            opening_hours=hours_info,
            photos={
                "count": len(photo_references),
                "references": photo_references
            },
            geometry=result.get("geometry", {}),
            data_quality={
                "has_reviews": len(all_reviews) > 0,
                "has_hours": bool(hours_info.get("weekday_text")),
                "has_photos": len(photo_references) > 0,
                "has_phone": bool(result.get("formatted_phone_number")),
                "has_website": bool(result.get("website"))
            }
        )
        
    except Exception as e:
        logger.exception(f"❌ Google API error for '{place_name}': {str(e)}")
        return GoogleReviewData()

async def get_competitor_data(search_query: str) -> List[Dict]:
    """Find nearby competitors with comprehensive data using Google Places - optimized for local restaurants."""
    try:
        gmaps = googlemaps.Client(key=GOOGLE_API_KEY)
        logger.info(f"🏪 Searching for LOCAL competitors using query: '{search_query}'")
        
        competitors = []
        
        if not search_query:
            logger.warning("🚫 No valid search query provided for competitor search")
            return competitors
        
        # NEW STRATEGY: First geocode the location, then search nearby
        # This is much more reliable for finding local competitors
        try:
            # Geocode the search query to get coordinates
            logger.info(f"📍 Geocoding location: '{search_query}'")
            geocode_result = gmaps.geocode(search_query)
            
            if not geocode_result:
                logger.warning(f"❌ Could not geocode location: '{search_query}'")
                # Fallback to text search
                return await get_competitors_by_text_search(gmaps, search_query)
            
            # Get the coordinates
            location = geocode_result[0]['geometry']['location']
            lat = location['lat']
            lng = location['lng']
            address = geocode_result[0]['formatted_address']
            
            logger.info(f"✅ Geocoded '{search_query}' to: {lat}, {lng} ({address})")
            
            # Now search for nearby restaurants using coordinates
            search_strategies = [
                {
                    "location": (lat, lng),
                    "radius": 1500,  # 1.5km - focus on very local competitors
                    "type": "restaurant"
                },
                {
                    "location": (lat, lng),
                    "radius": 3000,  # 3km - broader local area
                    "type": "restaurant"
                },
                {
                    "location": (lat, lng),
                    "radius": 1500,  # Also search for general food establishments
                    "type": "food"
                }
            ]
            
            all_places = []
            
            for strategy in search_strategies:
                try:
                    logger.info(f"🔍 Searching radius {strategy['radius']}m for {strategy['type']} near {lat}, {lng}")
                    
                    results = gmaps.places_nearby(
                        location=strategy['location'],
                        radius=strategy['radius'],
                        type=strategy['type']
                    )
                    
                    places = results.get("results", [])
                    logger.info(f"📍 Found {len(places)} places with {strategy['radius']}m radius")
                    
                    # Filter out duplicates and add to all_places
                    for place in places:
                        place_id = place.get("place_id")
                        if place_id and not any(p.get("place_id") == place_id for p in all_places):
                            # Filter out chains and focus on local restaurants
                            place_name = place.get("name", "").lower()
                            place_types = place.get("types", [])
                            
                            # Skip obvious chains (you can expand this list)
                            chain_keywords = ['mcdonald', 'burger king', 'subway', 'starbucks', 'kfc', 'taco bell', 'domino', 'pizza hut', 'wendy', 'chipotle', 'sweetgreen']
                            is_chain = any(chain in place_name for chain in chain_keywords)
                            
                            # Focus on actual restaurants (not just food/grocery)
                            is_restaurant = any(t in place_types for t in ['restaurant', 'food', 'meal_takeaway', 'meal_delivery'])
                            
                            if is_restaurant and not is_chain:
                                all_places.append(place)
                                logger.info(f"✅ Added LOCAL restaurant: {place.get('name')}")
                            else:
                                logger.info(f"⏭️ Skipped (chain/non-restaurant): {place.get('name')}")
                            
                    # Stop if we have enough local competitors
                    if len(all_places) >= 15:
                        logger.info(f"🎯 Found enough local competitors ({len(all_places)}), stopping search")
                        break
                        
                except Exception as e:
                    logger.warning(f"❌ Nearby search failed for radius {strategy.get('radius', 'unknown')}m: {str(e)}")
                    continue
            
        except Exception as geocode_error:
            logger.warning(f"❌ Geocoding failed: {str(geocode_error)}, falling back to text search")
            return await get_competitors_by_text_search(gmaps, search_query)
        
        logger.info(f"🎯 Total LOCAL competitors found: {len(all_places)}")
        
        # Sort by rating and review count (indicators of established local businesses)
        sorted_places = sorted(
            all_places, 
            key=lambda x: (x.get("rating", 0), x.get("user_ratings_total", 0)), 
            reverse=True
        )[:8]  # Top 8 local competitors
        
        logger.info(f"🏆 Processing top {len(sorted_places)} LOCAL competitors")
        
        # CONCURRENCY OPTIMIZATION: Process competitors in parallel batches
        max_concurrent_competitors = 3  # Process 3 competitors simultaneously
        competitor_batches = [sorted_places[i:i + max_concurrent_competitors] 
                            for i in range(0, len(sorted_places), max_concurrent_competitors)]
        
        for batch_num, batch in enumerate(competitor_batches):
            logger.info(f"🚀 Processing competitor batch {batch_num + 1}/{len(competitor_batches)} ({len(batch)} competitors)")
            
            # Create tasks for parallel processing
            competitor_tasks = []
            for i, place in enumerate(batch):
                task = process_single_competitor(place, i + 1 + (batch_num * max_concurrent_competitors), lat, lng, gmaps)
                competitor_tasks.append(task)
            
            # Execute batch in parallel
            batch_results = await asyncio.gather(*competitor_tasks, return_exceptions=True)
            
            # Collect successful results and log exceptions
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"❌ Competitor processing failed: {str(result)}")
                elif result:
                    competitors.append(result)
        
        logger.info(f"🎉 Successfully found {len(competitors)} LOCAL competitors with digital strategy analysis")
        return competitors
        
    except Exception as e:
        logger.error(f"❌ Error fetching local competitor data for '{search_query}': {str(e)}")
        return []

async def process_single_competitor(place: Dict, competitor_num: int, target_lat: float, target_lng: float, gmaps) -> Dict:
    """Process a single competitor in parallel - extracted from main competitor loop."""
    try:
        logger.info(f"📊 Processing local competitor {competitor_num}: '{place.get('name')}'")
        
        # Get comprehensive details for each competitor
        fields = [
            "name", "formatted_address", "formatted_phone_number", 
            "international_phone_number", "website", "rating", 
            "user_ratings_total", "price_level", "photo",
            "opening_hours", "business_status", "vicinity", "geometry"
        ]
        
        details = gmaps.place(place_id=place["place_id"], fields=fields)
        result = details["result"]
        
        # Get opening hours
        opening_hours = result.get("opening_hours", {})
        hours_info = {
            "weekday_text": opening_hours.get("weekday_text", []),
            "open_now": opening_hours.get("open_now")
        }
        
        # Get photos
        photos = result.get("photo", [])
        if not isinstance(photos, list):
            photos = [photos] if photos else []
        photo_count = len(photos)
        
        # Calculate distance from target location
        distance_info = None
        geometry = result.get("geometry", {})
        if geometry and "location" in geometry:
            location = geometry["location"]
            distance_info = {
                "lat": location.get("lat"),
                "lng": location.get("lng")
            }
            
            # Calculate actual distance
            try:
                import math
                def haversine_distance(lat1, lng1, lat2, lng2):
                    R = 6371  # Earth radius in km
                    dlat = math.radians(lat2 - lat1)
                    dlng = math.radians(lng2 - lng1)
                    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
                    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                    return R * c
                
                distance_km = haversine_distance(target_lat, target_lng, location.get("lat"), location.get("lng"))
                distance_info["distance_km"] = round(distance_km, 2)
                logger.info(f"📏 Distance to {result.get('name')}: {distance_km:.2f}km")
            except:
                pass
        
        competitor_data = {
            "name": result.get("name"),
            "address": result.get("formatted_address"),
            "vicinity": result.get("vicinity"),
            "phone": result.get("formatted_phone_number"),
            "international_phone": result.get("international_phone_number"),
            "website": result.get("website"),
            "rating": result.get("rating"),
            "review_count": result.get("user_ratings_total", 0),
            "price_level": result.get("price_level"),
            "categories": place.get("types", []),
            "business_status": result.get("business_status"),
            "opening_hours": hours_info,
            "photos": {
                "count": photo_count,
                "available": photo_count > 0
            },
            "location": distance_info,
            "place_id": place["place_id"],
            "competitor_type": "local_restaurant",  # Mark as local
            "data_quality": {
                "has_rating": bool(result.get("rating")),
                "has_reviews": bool(result.get("user_ratings_total", 0) > 0),
                "has_phone": bool(result.get("formatted_phone_number")),
                "has_website": bool(result.get("website")),
                "has_hours": bool(hours_info.get("weekday_text")),
                "has_photos": photo_count > 0
            }
        }
        
        # Enhanced competitor intelligence - scrape their website for digital strategy insights
        competitor_website = result.get("website")
        if competitor_website:
            logger.info(f"🕷️ Analyzing competitor's digital presence: {competitor_website}")
            try:
                # Get website URL with better filtering
                website_url = competitor_website
                
                # Filter out low-quality URLs
                excluded_domains = ['facebook.com', 'yelp.com', 'doordash.com', 'ubereats.com', 'grubhub.com', 'postmates.com', 'instagram.com', 'twitter.com', 'foursquare.com']
                
                if website_url and not any(domain in website_url.lower() for domain in excluded_domains):
                    logger.info(f"🕷️ Analyzing competitor's digital presence: {website_url}")
                    # CONCURRENCY OPTIMIZATION: Use full Stagehand with improved concurrent processing
                    competitor_website_data = await get_website_data(website_url)
                    
                    # Enhanced conversion - handle all possible types
                    competitor_website_dict = {}
                    
                    if hasattr(competitor_website_data, 'model_dump'):
                        # New Pydantic v2 method
                        competitor_website_dict = competitor_website_data.model_dump()
                    elif hasattr(competitor_website_data, 'dict'):
                        # Old Pydantic v1 method
                        competitor_website_dict = competitor_website_data.dict()
                    elif isinstance(competitor_website_data, dict):
                        # Already a dictionary
                        competitor_website_dict = competitor_website_data
                    else:
                        # Convert to dict manually if all else fails
                        competitor_website_dict = {
                            'name': getattr(competitor_website_data, 'name', None),
                            'contact': getattr(competitor_website_data, 'contact', {}),
                            'social_links': getattr(competitor_website_data, 'social_links', []),
                            'menu': getattr(competitor_website_data, 'menu', {}),
                            'address': getattr(competitor_website_data, 'address', None),
                            'scraper_used': getattr(competitor_website_data, 'scraper_used', 'unknown')
                        }
                    
                    # Ensure the dictionary has the required structure for analyze_digital_strategy
                    if not isinstance(competitor_website_dict, dict):
                        logger.error(f"Failed to convert competitor website data to dict: {type(competitor_website_data)}")
                        competitor_website_dict = {}
                    
                    digital_analysis = analyze_digital_strategy(competitor_website_dict)
                    
                    competitor_data["digital_strategy"] = digital_analysis
                    competitor_data["contact_info"] = competitor_website_dict.get("contact", {})
                    competitor_data["social_presence"] = competitor_website_dict.get("social_links", [])
                    
                    logger.info(f"✅ Digital strategy analysis for '{result.get('name')}': email={digital_analysis.get('email_capture', False)}, social={len(digital_analysis.get('social_links', []))}, online_menu={digital_analysis.get('online_menu', False)}")
                else:
                    if website_url:
                        logger.info(f"⏭️ Skipping low-quality URL for '{result.get('name')}': {website_url}")
                    else:
                        logger.info(f"⏭️ No website URL available for '{result.get('name')}'")
                    competitor_website_data = {}
                    digital_analysis = {}
                    competitor_data["digital_strategy"] = digital_analysis
                    competitor_data["contact_info"] = {}
                    competitor_data["social_presence"] = []
            except Exception as analysis_error:
                logger.error(f"❌ Error analyzing competitor digital strategy: {str(analysis_error)}")
                competitor_data["digital_strategy"] = {"error": str(analysis_error)}
                competitor_data["contact_info"] = {}
                competitor_data["social_presence"] = []
        else:
            logger.info(f"⚠️ No website found for '{result.get('name')}' - opportunity for growth hacking!")
            competitor_data["digital_strategy"] = {"has_website": False}
            competitor_data["contact_info"] = {}
            competitor_data["social_presence"] = []
        
        logger.info(f"✅ Processed LOCAL competitor '{result.get('name')}': "
                  f"{result.get('rating', 'N/A')}⭐ ({result.get('user_ratings_total', 0)} reviews), "
                  f"{distance_info.get('distance_km', 'unknown') if distance_info else 'unknown'}km away")
        
        return competitor_data
    except Exception as e:
        logger.warning(f"❌ Failed to process competitor {competitor_num}: {str(e)}")
        return None

async def get_competitors_by_text_search(gmaps, search_query: str) -> List[Dict]:
    """Fallback method using text search when geocoding fails."""
    logger.info(f"🔍 Using text search fallback for: '{search_query}'")
    
    competitors = []
    search_queries = [
        f"restaurants near {search_query}",
        f"local restaurants {search_query}",
        f"food {search_query}"
    ]
    
    for query in search_queries:
        try:
            logger.info(f"🔍 Text search: '{query}'")
            results = gmaps.places(query=query, type="restaurant")
            places = results.get("results", [])
            
            for place in places[:5]:  # Limit results
                place_id = place.get("place_id")
                if place_id and not any(c.get("place_id") == place_id for c in competitors):
                    # Basic competitor data without website analysis to save time
                    competitor_data = {
                        "name": place.get("name"),
                        "place_id": place_id,
                        "rating": place.get("rating"),
                        "review_count": place.get("user_ratings_total", 0),
                        "address": place.get("formatted_address"),
                        "competitor_type": "text_search_fallback"
                    }
                    competitors.append(competitor_data)
                    
            if competitors:
                break  # Found some results, stop searching
                
        except Exception as e:
            logger.warning(f"❌ Text search failed for '{query}': {str(e)}")
            continue
    
    logger.info(f"📋 Text search fallback found {len(competitors)} competitors")
    return competitors

async def aggregate_data(url: str, email: Optional[str] = None, name: Optional[str] = None, address: Optional[str] = None) -> Dict:
    """
    Compatibility wrapper for ProgressiveDataExtractor.
    This function maintains backward compatibility with the old API.
    """
    logger.info(f"🔄 aggregate_data compatibility wrapper called for: {url}")
    
    try:
        from .progressive_data_extractor import ProgressiveDataExtractor
        
        # Initialize the progressive extractor
        extractor = ProgressiveDataExtractor()
        
        # Extract restaurant data using the new progressive system
        final_restaurant_output = await extractor.extract_restaurant_data(
            url=url,
            restaurant_name=name,
            address=address
        )
        
        if not final_restaurant_output:
            return {"error": "Progressive extraction failed - no data returned"}
        
        # Convert to the old format expected by the API
        restaurant_data = {
            "restaurant_name": final_restaurant_output.restaurant_name,
            "address_raw": final_restaurant_output.address_raw,
            "phone_raw": final_restaurant_output.phone_raw,
            "website_data": {
                "menu": {
                    "items": [
                        {
                            "name": item.name,
                            "description": item.description or "",
                            "price": item.price or "",
                            "category": item.category or ""
                        } 
                        for item in final_restaurant_output.menu_items
                    ]
                }
            },
            "competitors": {
                "competitors": [
                    {
                        "name": comp.name,
                        "rating": comp.rating,
                        "address": comp.address_raw,
                        "website": comp.url
                    } 
                    for comp in (final_restaurant_output.competitors or [])
                ]
            },
            "reviews": {
                "google": {
                    "rating": final_restaurant_output.google_rating,
                    "total_reviews": final_restaurant_output.google_review_count
                }
            },
            "scraper_used": "progressive_extractor",
            "data_quality_metrics": {
                "quality_score": final_restaurant_output.extraction_metadata.final_quality_score if final_restaurant_output.extraction_metadata else None,
                "phases_completed": final_restaurant_output.extraction_metadata.phases_completed if final_restaurant_output.extraction_metadata else 0
            }
        }
        
        logger.info(f"✅ aggregate_data compatibility wrapper completed for: {final_restaurant_output.restaurant_name}")
        return restaurant_data
        
    except Exception as e:
        logger.error(f"❌ aggregate_data compatibility wrapper failed: {str(e)}")
        return {"error": f"Aggregation failed: {str(e)}"}


async def get_website_data(url: str) -> Dict:
    """
    Compatibility wrapper to get website data.
    """
    logger.info(f"🔄 get_website_data compatibility wrapper called for: {url}")
    
    try:
        # Use aggregate_data and extract just the website portion
        full_data = await aggregate_data(url)
        
        if "error" in full_data:
            return full_data
            
        return full_data.get("website_data", {})
        
    except Exception as e:
        logger.error(f"❌ get_website_data failed: {str(e)}")
        return {"error": f"Website data extraction failed: {str(e)}"}


async def get_competitor_insights(restaurant_name: str, location: str = None) -> Dict:
    """
    Compatibility wrapper to get competitor insights.
    """
    logger.info(f"🔄 get_competitor_insights compatibility wrapper called for: {restaurant_name}")
    
    try:
        from .google_places_extractor import GooglePlacesExtractor
        
        # Initialize Google Places extractor
        places_extractor = GooglePlacesExtractor()
        
        # Search for competitors
        competitors_data = await places_extractor.find_competitors(
            restaurant_name=restaurant_name,
            location=location or "United States"
        )
        
        return {
            "competitors": competitors_data.get("competitors", []),
            "analysis": {
                "total_found": len(competitors_data.get("competitors", [])),
                "data_source": "google_places_api"
            }
        }
            
    except Exception as e:
        logger.error(f"❌ get_competitor_insights failed: {str(e)}")
        return {"error": f"Competitor insights extraction failed: {str(e)}"}

def analyze_social_performance(review_platforms: Dict) -> Dict:
    """Analyze social media and review platform performance - updated for local restaurants."""
    performance = {
        "platforms_found": len(review_platforms),
        "total_reviews": 0,
        "average_rating": 0,
        "platform_breakdown": {},
        "google_presence": False,
        "facebook_presence": False
    }
    
    ratings = []
    total_reviews = 0
    
    for platform, data in review_platforms.items():
        if not data.get('error'):
            platform_info = {
                "found": data.get('found', False),
                "rating": data.get('rating'),
                "review_count": data.get('reviewCount')
            }
            
            # Extract numeric rating
            if data.get('rating'):
                try:
                    rating_text = data['rating']
                    # Handle different rating formats
                    if '/' in rating_text:
                        rating = float(rating_text.split('/')[0])
                    else:
                        rating = float(re.sub(r'[^\d.]', '', rating_text))
                    
                    if 0 <= rating <= 5:  # Valid rating range
                        ratings.append(rating)
                        platform_info["numeric_rating"] = rating
                except:
                    pass
            
            # Extract review count
            if data.get('reviewCount'):
                try:
                    count_text = data['reviewCount']
                    count = int(re.sub(r'[^\d]', '', count_text))
                    total_reviews += count
                    platform_info["numeric_review_count"] = count
                except:
                    pass
            
            # Track key platform presence
            if platform == 'google':
                performance["google_presence"] = platform_info["found"]
            elif platform == 'facebook':
                performance["facebook_presence"] = platform_info["found"]
            
            performance["platform_breakdown"][platform] = platform_info
    
    if ratings:
        performance["average_rating"] = round(sum(ratings) / len(ratings), 2)
    performance["total_reviews"] = total_reviews
    
    # Competitive intelligence insights
    performance["competitive_insights"] = {
        "strong_online_presence": performance["google_presence"] and performance["facebook_presence"],
        "review_volume": "high" if total_reviews > 100 else "medium" if total_reviews > 20 else "low",
        "rating_quality": "excellent" if performance["average_rating"] > 4.5 else "good" if performance["average_rating"] > 4.0 else "needs_improvement"
    }
    
    return performance

def compile_review_ratings(review_platforms: Dict) -> Dict:
    """Compile ratings from accessible review platforms for local restaurants."""
    ratings = {}
    
    for platform, data in review_platforms.items():
        if data.get('rating') and not data.get('error'):
            try:
                rating_text = data['rating']
                # Handle different rating formats
                if '/' in rating_text:
                    rating = float(rating_text.split('/')[0])
                else:
                    rating = float(re.sub(r'[^\d.]', '', rating_text))
                
                if 0 <= rating <= 5:  # Valid rating range
                    ratings[platform] = {
                        "rating": rating,
                        "review_count": data.get('reviewCount'),
                        "found": data.get('found', False),
                        "business_status": data.get('businessStatus') if platform == 'google' else None,
                        "verified": data.get('verified') if platform == 'facebook' else None
                    }
            except:
                ratings[platform] = {"error": "Could not parse rating"}
    
    # Add summary insights for competitive analysis
    if ratings:
        all_ratings = [r["rating"] for r in ratings.values() if isinstance(r.get("rating"), (int, float))]
        ratings["summary"] = {
            "platforms_with_ratings": len(all_ratings),
            "average_across_platforms": round(sum(all_ratings) / len(all_ratings), 2) if all_ratings else 0,
            "consistent_rating": max(all_ratings) - min(all_ratings) < 0.5 if len(all_ratings) > 1 else True
        }
    
    return ratings

def analyze_pricing_strategy(menu_items: List[Dict]) -> Dict:
    """Analyze competitor pricing strategy from menu items with enhanced logging."""
    logger.info(f"🔍 Analyzing pricing strategy for {len(menu_items)} menu items")
    
    if not menu_items:
        logger.warning("❌ No menu items provided for pricing analysis")
        return {"error": "No menu items to analyze"}
    
    prices = []
    categories = {}
    
    for item in menu_items:
        if item.get('price'):
            try:
                # Extract numeric price (remove $ and other characters)
                price_str = re.sub(r'[^\d.]', '', item['price'])
                if price_str:
                    price = float(price_str)
                    prices.append(price)
                    
                    category = item.get('category', 'Other')
                    if category not in categories:
                        categories[category] = []
                    categories[category].append(price)
                    
                    logger.debug(f"💰 Parsed price: {item.get('name', 'Unknown')} - ${price} ({category})")
            except Exception as parse_error:
                logger.warning(f"⚠️ Could not parse price '{item.get('price')}' for item '{item.get('name')}'")
                continue
    
    if not prices:
        logger.warning("❌ No valid prices found in menu items")
        return {"error": "No valid prices found"}
    
    pricing_analysis = {
        "average_price": round(sum(prices) / len(prices), 2),
        "price_range": {"min": min(prices), "max": max(prices)},
        "total_items": len(menu_items),
        "priced_items": len(prices),
        "category_averages": {cat: round(sum(cat_prices) / len(cat_prices), 2) 
                            for cat, cat_prices in categories.items() if cat_prices},
        "pricing_insights": {
            "price_spread": round(max(prices) - min(prices), 2),
            "most_expensive_category": max(categories.keys(), key=lambda k: sum(categories[k])/len(categories[k])) if categories else None,
            "cheapest_category": min(categories.keys(), key=lambda k: sum(categories[k])/len(categories[k])) if categories else None,
            "price_tier": "premium" if sum(prices)/len(prices) > 20 else "mid-range" if sum(prices)/len(prices) > 12 else "budget"
        }
    }
    
    logger.info(f"✅ Pricing analysis complete: avg=${pricing_analysis['average_price']}, "
              f"range=${pricing_analysis['price_range']['min']}-${pricing_analysis['price_range']['max']}, "
              f"tier={pricing_analysis['pricing_insights']['price_tier']}")
    
    return pricing_analysis

def analyze_digital_strategy(website_data: Dict) -> Dict:
    """
    Analyze a restaurant's digital strategy based on website data.
    
    Args:
        website_data: Extracted website data dictionary
        
    Returns:
        Dictionary with digital strategy analysis
    """
    if not website_data or website_data.get("error"):
        return {}
    
    # Check for email capture capabilities
    email_capture = bool(website_data.get("contact", {}).get("email"))
    
    # Count social media presence
    social_links = website_data.get("social_links", [])
    
    # Check for online menu
    online_menu = len(website_data.get("menu", {}).get("items", [])) > 0
    
    # Check for online ordering
    online_ordering = bool(website_data.get("online_ordering_url"))
    
    # Assess website quality
    has_seo_title = bool(website_data.get("seo_title"))
    has_meta_description = bool(website_data.get("meta_description"))
    
    website_quality = "high" if (has_seo_title and has_meta_description) else "basic"
    
    return {
        "email_capture": email_capture,
        "social_links": social_links,
        "social_count": len(social_links),
        "online_menu": online_menu,
        "online_ordering": online_ordering,
        "website_quality": website_quality,
        "seo_optimized": has_seo_title and has_meta_description,
        "digital_maturity": "advanced" if (online_ordering and email_capture and len(social_links) > 2) else "developing"
    }
"""
Google Places API Extractor for Restaurant Data
Part of the Progressive Data Extraction System (Phase 1)
"""

import logging
import googlemaps
from typing import Dict, List, Optional, Any
import os
from datetime import datetime
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class GooglePlacesExtractor:
    """
    Extract restaurant data from Google Places API
    Provides high-quality, structured data as the foundation for Phase 1
    """
    
    def __init__(self):
        # Check for API key in multiple possible environment variables
        self.api_key = os.getenv('GOOGLE_MAPS_API_KEY') or os.getenv('GOOGLE_API_KEY')
        self.client = None
        
        if self.api_key:
            try:
                self.client = googlemaps.Client(key=self.api_key)
                logger.info(f"✅ Google Places API client initialized with key: {self.api_key[:10]}...")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Google Places client: {str(e)}")
                self.client = None
        else:
            logger.warning("⚠️ GOOGLE_MAPS_API_KEY or GOOGLE_API_KEY not found - Google Places extraction disabled")
            logger.info("💡 Make sure to set GOOGLE_MAPS_API_KEY in your environment variables")
    
    async def extract_places_data(self, restaurant_name: str = None, 
                                address: str = None) -> Optional[Dict[str, Any]]:
        """
        Extract restaurant data from Google Places API
        
        Args:
            restaurant_name: Name of the restaurant
            address: Address of the restaurant
            
        Returns:
            Dictionary with standardized restaurant data
        """
        if not self.client:
            logger.warning("❌ Google Places API not available")
            return None
        
        try:
            # Construct search query
            query_parts = []
            if restaurant_name:
                query_parts.append(restaurant_name)
            if address:
                query_parts.append(address)
            
            if not query_parts:
                logger.warning("❌ No search criteria provided for Google Places")
                return None
            
            search_query = " ".join(query_parts)
            logger.info(f"🔍 Searching Google Places for: {search_query}")
            
            # Search for the place
            places_result = self.client.places(query=search_query, type='restaurant')
            
            if not places_result.get('results'):
                logger.warning(f"❌ No results found in Google Places for: {search_query}")
                return None
            
            # Get the first (most relevant) result
            place = places_result['results'][0]
            place_id = place.get('place_id')
            
            if not place_id:
                logger.warning("❌ No place_id found in Google Places result")
                return None
            
            # Get detailed place information
            logger.info(f"📍 Fetching detailed info for place_id: {place_id}")
            place_details = self.client.place(
                place_id=place_id,
                fields=[
                    'name', 'formatted_address', 'formatted_phone_number',
                    'international_phone_number', 'website', 'url',
                    'rating', 'user_ratings_total', 'price_level',
                    'opening_hours', 'geometry', 'business_status', 'reviews'
                ]
            )
            
            place_info = place_details.get('result', {})
            
            # Transform to our standard format
            restaurant_data = self._transform_places_data(place_info)
            
            logger.info(f"✅ Google Places: Extracted {len(restaurant_data)} fields")
            return restaurant_data
            
        except googlemaps.exceptions.ApiError as e:
            logger.error(f"❌ Google Places API error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"❌ Google Places extraction failed: {str(e)}")
            return None
    
    def _transform_places_data(self, place_info: Dict) -> Dict[str, Any]:
        """
        Transform Google Places API response to our standard format
        """
        restaurant_data = {}
        
        # Basic Information
        if place_info.get('name'):
            restaurant_data['name'] = place_info['name']
        
        if place_info.get('formatted_address'):
            restaurant_data['address'] = place_info['formatted_address']
        
        if place_info.get('formatted_phone_number'):
            restaurant_data['phone'] = place_info['formatted_phone_number']
        
        if place_info.get('website'):
            restaurant_data['website'] = place_info['website']
        
        # Ratings and Reviews
        if place_info.get('rating'):
            restaurant_data['google_rating'] = place_info['rating']
        
        if place_info.get('user_ratings_total'):
            restaurant_data['google_review_count'] = place_info['user_ratings_total']
        
        if place_info.get('price_level') is not None:
            restaurant_data['price_level'] = place_info['price_level']
        
        # Operating Hours
        opening_hours = place_info.get('opening_hours', {})
        if opening_hours.get('weekday_text'):
            restaurant_data['hours'] = opening_hours['weekday_text']
        
        # Location
        geometry = place_info.get('geometry', {})
        if geometry.get('location'):
            location = geometry['location']
            restaurant_data['coordinates'] = {
                'latitude': location.get('lat'),
                'longitude': location.get('lng')
            }
        
        # Business Type - Note: types field not included in API request due to validation issues
        # if place_info.get('types'):
        #     restaurant_data['business_types'] = place_info['types']
        
        # Business Status
        if place_info.get('business_status'):
            restaurant_data['business_status'] = place_info['business_status']
        
        # Photos - Note: photos field not included in API request due to validation issues
        # if place_info.get('photos'):
        #     photo_references = [photo.get('photo_reference') for photo in place_info['photos'][:5]]
        #     restaurant_data['google_photos'] = photo_references
        
        # Recent Reviews
        if place_info.get('reviews'):
            reviews = []
            for review in place_info['reviews'][:3]:  # Get top 3 reviews
                review_data = {
                    'author': review.get('author_name'),
                    'rating': review.get('rating'),
                    'text': review.get('text'),
                    'time': review.get('time')
                }
                reviews.append(review_data)
            restaurant_data['google_reviews'] = reviews
        
        # Google URL
        if place_info.get('url'):
            restaurant_data['google_maps_url'] = place_info['url']
        
        # Add metadata
        restaurant_data['data_source'] = 'google_places_api'
        restaurant_data['extraction_timestamp'] = datetime.now().isoformat()
        
        logger.info(f"📊 Google Places data transformed: {list(restaurant_data.keys())}")
        return restaurant_data

    async def find_local_competitors(self, latitude: float, longitude: float, 
                                     radius: int = 5000, # 5km radius
                                     target_cuisine_types: Optional[List[str]] = None,
                                     max_competitors: int = 5) -> List[Dict[str, Any]]:
        """
        Find local competitors using Google Places API Nearby Search.

        Args:
            latitude: Latitude of the target restaurant.
            longitude: Longitude of the target restaurant.
            radius: Search radius in meters.
            target_cuisine_types: Optional list of cuisine types to refine search.
            max_competitors: Maximum number of competitors to return.

        Returns:
            A list of competitor data dictionaries.
        """
        if not self.client:
            logger.warning("❌ Google Places API not available for competitor search")
            return []

        if not latitude or not longitude:
            logger.warning("❌ Missing latitude/longitude for competitor search")
            return []

        try:
            location = (latitude, longitude)
            keyword = "restaurant"
            if target_cuisine_types:
                # Pick the first cuisine type as a primary keyword if available
                keyword = f"{target_cuisine_types[0]} restaurant"
            
            logger.info(f"🔍 Searching for competitors near ({latitude},{longitude}) with keyword '{keyword}' within {radius}m")

            nearby_results = self.client.places_nearby(
                location=location,
                radius=radius,
                keyword=keyword,
                type='restaurant' # Ensure we only get restaurants
            )

            competitors = []
            if nearby_results.get('results'):
                logger.info(f"Found {len(nearby_results['results'])} potential competitors initially.")
                for place in nearby_results['results'][:max_competitors]: # Limit results
                    place_id = place.get('place_id')
                    if not place_id:
                        continue
                    
                    # Fetch basic details for each competitor
                    # We can expand fields later if needed, keeping it minimal for now
                    comp_details = self.client.place(
                        place_id=place_id,
                        fields=['name', 'formatted_address', 'website', 'rating', 'user_ratings_total', 'url']
                    )
                    
                    if comp_details.get('result'):
                        res = comp_details['result']
                        competitor_data = {
                            "name": res.get('name'),
                            "address_raw": res.get('formatted_address'),
                            "url": res.get('website'), # This is the business's website
                            "google_maps_url": res.get('url'), # This is the Google Maps URL for the place
                            "rating": res.get('rating'),
                            "review_count": res.get('user_ratings_total'),
                            # "cuisine_types": [t for t in res.get('types', []) if t not in ['food', 'point_of_interest', 'establishment']],
                            "source": "google_places_api"
                        }
                        # Ensure essential fields are present
                        if competitor_data["name"] and competitor_data["address_raw"]:
                            competitors.append(competitor_data)
                            if len(competitors) >= max_competitors:
                                break
            
            logger.info(f"✅ Found {len(competitors)} relevant competitors after filtering.")
            return competitors

        except googlemaps.exceptions.ApiError as e:
            logger.error(f"❌ Google Places API error during competitor search: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"❌ Competitor search failed: {str(e)}")
            return []

    async def get_place_details_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract place details based on website URL (full implementation)"""
        logger.info(f"🔍 Attempting to find Google Places data for URL: {url}")
        
        if not self.client:
            logger.warning("❌ Google Places API not available")
            return None
        
        try:
            # Extract domain name for search
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            
            # Try different search queries
            search_queries = [
                f"site:{domain}",
                f"{domain} restaurant",
                f"{domain.replace('www.', '').replace('.com', '').replace('.', ' ')}"
            ]
            
            for query in search_queries:
                try:
                    logger.debug(f"🔍 Searching Google Places with query: {query}")
                    
                    # Use text search to find places
                    places_result = self.client.places(query=query, type='restaurant')
                    
                    if places_result.get('results'):
                        # Check each result to see if the website matches
                        for place in places_result['results']:
                            place_id = place.get('place_id')
                            if not place_id:
                                continue
                            
                            # Get detailed place information including website
                            place_details = self.client.place(
                                place_id=place_id,
                                fields=[
                                    'name', 'formatted_address', 'formatted_phone_number',
                                    'international_phone_number', 'website', 'url',
                                    'rating', 'user_ratings_total', 'price_level',
                                    'opening_hours', 'geometry', 'business_status', 'reviews'
                                ]
                            )
                            
                            place_info = place_details.get('result', {})
                            place_website = place_info.get('website', '')
                            
                            # Check if websites match (handle various URL formats)
                            if place_website:
                                place_domain = urlparse(place_website).netloc.lower()
                                if domain in place_domain or place_domain in domain:
                                    logger.info(f"✅ Found matching place: {place_info.get('name')} - {place_website}")
                                    return self._transform_places_data(place_info)
                
                except googlemaps.exceptions.ApiError as e:
                    logger.debug(f"❌ Google Places API error for query '{query}': {str(e)}")
                    continue
                except Exception as e:
                    logger.debug(f"❌ Error searching for query '{query}': {str(e)}")
                    continue
            
            logger.warning(f"⚠️ No matching Google Places entry found for URL: {url}")
            return None
            
        except Exception as e:
            logger.error(f"❌ URL-based place lookup failed for {url}: {str(e)}")
            return None
    
    async def get_place_details_by_query(self, query: str, fields: List[str] = None) -> Optional[Dict[str, Any]]:
        """Extract place details based on search query (full implementation)"""
        logger.info(f"🔍 Searching Google Places for: {query}")
        
        if not self.client:
            logger.warning("❌ Google Places API not available")
            return None
        
        try:
            # Default fields if none provided
            if fields is None:
                fields = [
                    'name', 'formatted_address', 'formatted_phone_number',
                    'international_phone_number', 'website', 'url',
                    'rating', 'user_ratings_total', 'price_level',
                    'opening_hours', 'geometry', 'business_status', 'reviews'
                ]
            
            # Search for the place
            places_result = self.client.places(query=query, type='restaurant')
            
            if not places_result.get('results'):
                logger.warning(f"❌ No results found in Google Places for: {query}")
                return None
            
            # Get the first (most relevant) result
            place = places_result['results'][0]
            place_id = place.get('place_id')
            
            if not place_id:
                logger.warning("❌ No place_id found in Google Places result")
                return None
            
            # Get detailed place information
            logger.info(f"📍 Fetching detailed info for place_id: {place_id}")
            place_details = self.client.place(place_id=place_id, fields=fields)
            
            place_info = place_details.get('result', {})
            
            if place_info:
                # Transform to our standard format and add cost estimation
                restaurant_data = self._transform_places_data(place_info)
                restaurant_data['cost'] = 0.02  # Estimated cost for Places API calls
                
                logger.info(f"✅ Google Places: Found {place_info.get('name')} via query")
                return restaurant_data
            else:
                logger.warning(f"❌ No place details found for query: {query}")
                return None
                
        except googlemaps.exceptions.ApiError as e:
            logger.error(f"❌ Google Places API error for query '{query}': {str(e)}")
            return None
        except Exception as e:
            logger.error(f"❌ Query-based place lookup failed for '{query}': {str(e)}")
            return None
    
    async def find_local_competitors(self, place_id: str = None, radius: int = 5000, keyword: str = "restaurant") -> Optional[Dict[str, Any]]:
        """Find local competitors near a place (full implementation)"""
        logger.info(f"🏢 Searching for competitors near place_id: {place_id}")
        
        if not self.client:
            logger.warning("❌ Google Places API not available")
            return None
        
        if not place_id:
            logger.warning("❌ No place_id provided for competitor search")
            return None
        
        try:
            # First, get the location of the target place
            target_place = self.client.place(
                place_id=place_id,
                fields=['name', 'geometry']
            )
            
            target_info = target_place.get('result', {})
            geometry = target_info.get('geometry', {})
            location_data = geometry.get('location', {})
            
            if not location_data:
                logger.warning(f"❌ Could not get location for place_id: {place_id}")
                return None
            
            latitude = location_data.get('lat')
            longitude = location_data.get('lng')
            
            if not latitude or not longitude:
                logger.warning(f"❌ Invalid coordinates for place_id: {place_id}")
                return None
            
            # Search for nearby restaurants
            logger.info(f"🔍 Searching for competitors near ({latitude}, {longitude}) within {radius}m")
            
            location = (latitude, longitude)
            nearby_results = self.client.places_nearby(
                location=location,
                radius=radius,
                keyword=keyword,
                type='restaurant'
            )
            
            competitors = []
            if nearby_results.get('results'):
                logger.info(f"Found {len(nearby_results['results'])} potential competitors")
                
                for place in nearby_results['results'][:10]:  # Limit to top 10
                    comp_place_id = place.get('place_id')
                    if comp_place_id == place_id:  # Skip the target restaurant itself
                        continue
                    
                    if comp_place_id:
                        try:
                            # Get detailed info for each competitor
                            comp_details = self.client.place(
                                place_id=comp_place_id,
                                fields=['name', 'formatted_address', 'website', 'rating', 'user_ratings_total', 'url']
                            )
                            
                            if comp_details.get('result'):
                                comp_info = comp_details['result']
                                competitor_data = {
                                    "name": comp_info.get('name'),
                                    "address": comp_info.get('formatted_address'),
                                    "website": comp_info.get('website'),
                                    "phone": comp_info.get('formatted_phone_number'),
                                    "google_rating": comp_info.get('rating'),
                                    "google_review_count": comp_info.get('user_ratings_total'),
                                    "google_maps_url": comp_info.get('url'),
                                    "price_level": comp_info.get('price_level'),
                                    "business_types": comp_info.get('types', []),
                                    "place_id": comp_place_id,
                                    "source": "google_places_api"
                                }
                                
                                # Only include if we have essential info
                                if competitor_data["name"] and competitor_data["address"]:
                                    competitors.append(competitor_data)
                                    
                        except googlemaps.exceptions.ApiError as e:
                            logger.debug(f"❌ Could not get details for competitor {comp_place_id}: {str(e)}")
                            continue
                        except Exception as e:
                            logger.debug(f"❌ Error processing competitor {comp_place_id}: {str(e)}")
                            continue
            
            result = {
                "results": competitors,
                "total_found": len(competitors),
                "search_location": {"latitude": latitude, "longitude": longitude},
                "search_radius": radius,
                "cost": len(competitors) * 0.02,  # Estimated API cost
                "extraction_timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"✅ Found {len(competitors)} competitors for place_id: {place_id}")
            return result
            
        except googlemaps.exceptions.ApiError as e:
            logger.error(f"❌ Google Places API error during competitor search: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"❌ Competitor search failed for place_id {place_id}: {str(e)}")
            return None 
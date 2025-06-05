"""
Gemini-Powered Data Cleaner for Restaurant Data
Handles complex normalization tasks that rule-based systems struggle with
"""

import logging
import json
import re
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import google.generativeai as genai
import os
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .json_parser_utils import (
    parse_llm_json_output, 
    validate_json_structure, 
    safe_get_nested_value,
    log_json_parsing_attempt
)

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

class GeminiDataCleaner:
    """
    Gemini-powered restaurant data cleaning and normalization
    Cost-optimized for production use with batching capabilities
    """
    
    def __init__(self):
        # Initialize Gemini API
        self.enabled = self._initialize_gemini()
        
        # Cost tracking
        self.cost_per_request = 0.001  # Gemini 1.5 Flash pricing
        self.requests_made = 0
        self.total_cost = 0.0
        
        # Batch processing optimization
        self.batch_size = 5  # Process up to 5 items per batch
        self.max_concurrent_requests = 3  # Limit concurrent API calls
        
        # Standard categories for menu items
        self.standard_categories = [
            'Appetizer', 'Main Course', 'Dessert', 'Beverage (Non-Alcoholic)',
            'Beverage (Alcoholic)', 'Side Dish', 'Soup/Salad', 'Breakfast', 'Other'
        ]
        
        # Cache for repeated operations
        self._categorization_cache = {}
        
        logger.info(f"🤖 Gemini Data Cleaner initialized - Enabled: {self.enabled}")
        if self.enabled:
            logger.info(f"💰 Cost tracking: ${self.cost_per_request:.4f} per request, batch size: {self.batch_size}")
    
    def get_cost_projection(self, num_restaurants: int) -> Dict[str, float]:
        """
        Calculate cost projection for scaling
        
        Args:
            num_restaurants: Number of restaurants to process
            
        Returns:
            Cost breakdown and projections
        """
        # Estimated API calls per restaurant based on test data
        avg_calls_per_restaurant = 50  # From our test: 52 calls for comprehensive cleaning
        
        total_calls = num_restaurants * avg_calls_per_restaurant
        total_cost = total_calls * self.cost_per_request
        
        return {
            'restaurants': num_restaurants,
            'estimated_api_calls': total_calls,
            'estimated_cost_usd': total_cost,
            'cost_per_restaurant': avg_calls_per_restaurant * self.cost_per_request,
            'cost_per_1000_restaurants': 1000 * avg_calls_per_restaurant * self.cost_per_request,
            'monthly_cost_1000_sites': 1000 * avg_calls_per_restaurant * self.cost_per_request * 1,  # Assuming once per month
            'recommendations': {
                'batch_processing': total_calls > 1000,
                'rate_limiting': total_calls > 10000,
                'cost_alerts': total_cost > 100  # Alert if over $100
            }
        }
    
    def _initialize_gemini(self) -> bool:
        """Initialize Gemini API with proper error handling"""
        try:
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                logger.warning("⚠️ GEMINI_API_KEY not found - Gemini cleaning disabled")
                return False
            
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('Gemini-2.0-flash')
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini: {str(e)}")
            return False
    
    async def clean_restaurant_data(self, restaurant_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for cleaning restaurant data with Gemini
        
        Args:
            restaurant_data: Raw restaurant data from extraction phases
            
        Returns:
            Cleaned and normalized restaurant data
        """
        if not self.enabled:
            logger.warning("⚠️ Gemini cleaning disabled - performing basic cleaning only")
            return await self._basic_rule_based_cleaning(restaurant_data)
        
        logger.info("🧹 Starting Gemini-powered data cleaning...")
        start_time = datetime.now()
        
        # Step 1: Basic rule-based cleaning first (fast and cheap)
        cleaned_data = await self._basic_rule_based_cleaning(restaurant_data)
        
        # Step 2: Gemini-powered advanced cleaning
        cleaned_data = await self._gemini_advanced_cleaning(cleaned_data)
        
        # Step 3: Final validation and consistency checks
        cleaned_data = await self._final_validation(cleaned_data)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Add cleaning metadata
        cleaned_data['data_cleaning'] = {
            'cleaned_at': datetime.now().isoformat(),
            'duration_seconds': duration,
            'gemini_requests_made': self.requests_made,
            'gemini_cost': self.total_cost,
            'cleaning_method': 'gemini_enhanced'
        }
        
        logger.info(f"✅ Gemini cleaning complete: {duration:.2f}s, {self.requests_made} API calls, ${self.total_cost:.4f}")
        return cleaned_data
    
    async def _basic_rule_based_cleaning(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Basic rule-based cleaning - the 'low hanging fruit'"""
        logger.info("🔧 Step 1: Basic rule-based cleaning...")
        
        cleaned = data.copy()
        
        # Whitespace trimming for all string fields
        for key, value in cleaned.items():
            if isinstance(value, str):
                cleaned[key] = value.strip()
            elif isinstance(value, list):
                cleaned[key] = [item.strip() if isinstance(item, str) else item for item in value]
        
        # Phone number basic cleaning
        if cleaned.get('phone'):
            phone = cleaned['phone']
            # Remove common formatting characters
            phone_cleaned = re.sub(r'[^\d\+]', '', phone)
            if len(phone_cleaned) >= 10:
                cleaned['phone_raw'] = cleaned['phone']  # Keep original
                cleaned['phone'] = phone_cleaned
        
        # Email normalization
        if cleaned.get('email'):
            cleaned['email'] = cleaned['email'].lower().strip()
        
        # URL normalization
        if cleaned.get('website'):
            website = cleaned['website']
            if not website.startswith(('http://', 'https://')):
                cleaned['website'] = f"https://{website}"
        
        # Social media link deduplication
        if cleaned.get('social_media'):
            social_links = []
            seen = set()
            for link in cleaned['social_media']:
                link_clean = link.lower().strip()
                if link_clean not in seen:
                    seen.add(link_clean)
                    social_links.append(link)
            cleaned['social_media'] = social_links
        
        # Menu items deduplication (exact matches)
        if cleaned.get('menu_items'):
            menu_items = []
            seen_names = set()
            for item in cleaned['menu_items']:
                if isinstance(item, dict) and item.get('name'):
                    name_key = item['name'].lower().strip()
                    if name_key not in seen_names:
                        seen_names.add(name_key)
                        # Basic price cleaning
                        if item.get('price'):
                            price_match = re.search(r'[\d,]+\.?\d*', str(item['price']))
                            if price_match:
                                item['price_raw'] = item['price']
                                item['price'] = price_match.group()
                        menu_items.append(item)
            cleaned['menu_items'] = menu_items
        
        logger.info(f"📊 Basic cleaning: {len(cleaned)} fields processed")
        return cleaned
    
    async def _gemini_advanced_cleaning(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Advanced cleaning using Gemini for complex tasks"""
        logger.info("🤖 Step 2: Gemini advanced cleaning...")
        
        cleaned = data.copy()
        
        # Task 1: Address parsing and canonicalization
        if cleaned.get('address'):
            parsed_address = await self._clean_address_with_gemini(cleaned['address'])
            if parsed_address:
                cleaned['address_structured'] = parsed_address
                cleaned['address_canonical'] = self._format_canonical_address(parsed_address)
        
        # Task 2: Phone number canonicalization
        if cleaned.get('phone'):
            canonical_phone = await self._clean_phone_with_gemini(cleaned['phone'])
            if canonical_phone:
                cleaned.update(canonical_phone)
        
        # Task 3: Menu item category standardization
        if cleaned.get('menu_items'):
            categorized_items = []
            for item in cleaned['menu_items']:
                if isinstance(item, dict):
                    categorized_item = await self._categorize_menu_item_with_gemini(item['name'], item.get('description', ''))
                    categorized_items.append(categorized_item or item)
            cleaned['menu_items'] = categorized_items
        
        # Task 4: Restaurant name canonicalization (if multiple variations)
        if cleaned.get('name_variations'):
            canonical_name = await self._canonicalize_name_with_gemini(cleaned['name_variations'])
            if canonical_name:
                cleaned['name_canonical'] = canonical_name
        
        # Task 5: Extract details from about/description text
        if cleaned.get('description') or cleaned.get('about_text'):
            text = cleaned.get('description') or cleaned.get('about_text')
            extracted_details = await self._extract_details_from_text_with_gemini(text)
            if extracted_details:
                cleaned.update(extracted_details)
        
        return cleaned
    
    async def _clean_address_with_gemini(self, address: str) -> Optional[Dict[str, Optional[str]]]:
        """
        Enhanced address cleaning with robust JSON parsing and explicit schema.
        
        Args:
            address: Raw address string to clean and parse
            
        Returns:
            Dictionary with parsed address components or None if failed
        """
        function_name = "_clean_address_with_gemini"
        logger.info(f"🧹 [{function_name}] Cleaning address: {repr(address)}")
        
        # Enhanced prompt with explicit JSON schema and examples
        prompt = f"""
Parse the following restaurant address into its components.

Address: "{address.strip()}"

Return ONLY a valid JSON object strictly adhering to the following structure. Use null for any missing or unclear components. DO NOT include any explanatory text before or after the JSON object.

Required JSON Structure:
{{
  "street_address": "Street number and name (e.g., '123 Main St, Suite 4') or null",
  "city": "City name (e.g., 'San Francisco') or null", 
  "state": "State abbreviation (e.g., 'CA') or null",
  "postal_code": "ZIP or postal code (e.g., '90210') or null",
  "country": "Country name (e.g., 'United States') or null"
}}

Examples:
Input: "123 Main St, Suite 4, San Francisco, CA 90210"
Output: {{"street_address": "123 Main St, Suite 4", "city": "San Francisco", "state": "CA", "postal_code": "90210", "country": "United States"}}

Input: "456 Oak Ave, New York, NY"  
Output: {{"street_address": "456 Oak Ave", "city": "New York", "state": "NY", "postal_code": null, "country": "United States"}}

Input: "Downtown Restaurant Area"
Output: {{"street_address": null, "city": null, "state": null, "postal_code": null, "country": null}}
"""
        
        try:
            # Get raw response from Gemini
            raw_response = await self._call_gemini(prompt, max_tokens=300, function_name=function_name)
            
            if not raw_response:
                logger.error(f"❌ [{function_name}] No response from Gemini")
                log_json_parsing_attempt(function_name, prompt, 0, False, "No response from Gemini")
                return None
            
            # Parse JSON using robust utility
            expected_keys = ["street_address", "city", "state", "postal_code", "country"]
            parsed_result = parse_llm_json_output(
                raw_response, 
                function_name=function_name,
                expected_keys=expected_keys
            )
            
            if not parsed_result:
                logger.error(f"❌ [{function_name}] Failed to parse JSON response")
                log_json_parsing_attempt(function_name, prompt, len(raw_response), False, "JSON parsing failed")
                return None
            
            # Validate structure
            if not validate_json_structure(parsed_result, expected_keys, function_name):
                logger.error(f"❌ [{function_name}] Invalid JSON structure")
                log_json_parsing_attempt(function_name, prompt, len(raw_response), False, "Invalid structure")
            return None
            
            # Log successful parsing
            log_json_parsing_attempt(function_name, prompt, len(raw_response), True)
            
            # Track API usage
            self.requests_made += 1
            self.total_cost += self.cost_per_request
            logger.info(f"📊 [{function_name}] API usage: {self.requests_made} requests, ${self.total_cost:.4f} total cost")
            
            logger.info(f"✅ [{function_name}] Successfully parsed address components")
            return parsed_result
            
        except Exception as e:
            logger.error(f"❌ [{function_name}] Exception during address cleaning: {str(e)}")
            log_json_parsing_attempt(function_name, prompt, 0, False, str(e))
            return None
    
    async def _clean_phone_with_gemini(self, phone: str) -> Optional[Dict[str, Optional[str]]]:
        """
        Enhanced phone number cleaning with robust JSON parsing and explicit schema.
        
        Args:
            phone: Raw phone string to clean and standardize
            
        Returns:
            Dictionary with parsed phone components or None if failed
        """
        function_name = "_clean_phone_with_gemini"
        logger.info(f"🧹 [{function_name}] Cleaning phone: {repr(phone)}")
        
        # Enhanced prompt with explicit JSON schema and examples
        prompt = f"""
Parse and standardize the following phone number for a restaurant.

Phone Number: "{phone.strip()}"

Return ONLY a valid JSON object strictly adhering to the following structure. Use null for any missing components. DO NOT include any explanatory text before or after the JSON object.

Required JSON Structure:
{{
  "canonical": "E.164 format (+1234567890) or null if invalid",
  "display": "Human-readable format ((123) 456-7890) or null if invalid",
  "country_code": "Country code (e.g., '+1') or null",
  "area_code": "Area code (e.g., '123') or null",
  "number": "Local number (e.g., '4567890') or null",
  "extension": "Extension number or null if none"
}}

Examples:
Input: "(555) 123-4567 ext 123"
Output: {{"canonical": "+15551234567", "display": "(555) 123-4567", "country_code": "+1", "area_code": "555", "number": "1234567", "extension": "123"}}

Input: "555-123-4567"
Output: {{"canonical": "+15551234567", "display": "(555) 123-4567", "country_code": "+1", "area_code": "555", "number": "1234567", "extension": null}}

Input: "call us"
Output: {{"canonical": null, "display": null, "country_code": null, "area_code": null, "number": null, "extension": null}}
"""
        
        try:
            # Get raw response from Gemini
            raw_response = await self._call_gemini(prompt, max_tokens=250, function_name=function_name)
            
            if not raw_response:
                logger.error(f"❌ [{function_name}] No response from Gemini")
                log_json_parsing_attempt(function_name, prompt, 0, False, "No response from Gemini")
                return None
            
            # Parse JSON using robust utility
            expected_keys = ["canonical", "display", "country_code", "area_code", "number", "extension"]
            parsed_result = parse_llm_json_output(
                raw_response, 
                function_name=function_name,
                expected_keys=expected_keys
            )
            
            if not parsed_result:
                logger.error(f"❌ [{function_name}] Failed to parse JSON response")
                log_json_parsing_attempt(function_name, prompt, len(raw_response), False, "JSON parsing failed")
                return None
            
            # Validate structure
            if not validate_json_structure(parsed_result, expected_keys, function_name):
                logger.error(f"❌ [{function_name}] Invalid JSON structure")
                log_json_parsing_attempt(function_name, prompt, len(raw_response), False, "Invalid structure")
            return None
            
            # Log successful parsing
            log_json_parsing_attempt(function_name, prompt, len(raw_response), True)
            
            # Track API usage
            self.requests_made += 1
            self.total_cost += self.cost_per_request
            logger.info(f"📊 [{function_name}] API usage: {self.requests_made} requests, ${self.total_cost:.4f} total cost")
            
            logger.info(f"✅ [{function_name}] Successfully parsed phone components")
            return parsed_result
            
        except Exception as e:
            logger.error(f"❌ [{function_name}] Exception during phone cleaning: {str(e)}")
            log_json_parsing_attempt(function_name, prompt, 0, False, str(e))
            return None
    
    async def _categorize_menu_item_with_gemini(self, item_name: str, description: str = "") -> Optional[str]:
        """
        Enhanced menu item categorization with robust JSON parsing and explicit schema.
        
        Args:
            item_name: Name of the menu item
            description: Optional description of the menu item
            
        Returns:
            Standardized category string or None if failed
        """
        function_name = "_categorize_menu_item_with_gemini"
        logger.info(f"🧹 [{function_name}] Categorizing menu item: {repr(item_name)}")
        
        # Enhanced prompt with explicit JSON schema and examples
        prompt = f"""
Categorize the following restaurant menu item into one of the standard categories.

Item Name: "{item_name.strip()}"
Description: "{description.strip() if description else 'No description provided'}"

Return ONLY a valid JSON object strictly adhering to the following structure. DO NOT include any explanatory text before or after the JSON object.

Required JSON Structure:
{{
  "category": "One of the standard categories below",
  "confidence": "High, Medium, or Low based on certainty"
}}

Standard Categories (choose exactly one):
- "Appetizers" - Starters, small plates, finger foods
- "Main Courses" - Entrees, large plates, main dishes  
- "Soups & Salads" - Soups, salads, lighter dishes
- "Desserts" - Sweet items, cakes, ice cream
- "Beverages" - Drinks, cocktails, coffee, tea
- "Pizza" - Pizza items and flatbreads
- "Pasta" - Pasta dishes and noodles
- "Sandwiches" - Burgers, wraps, subs, sandwiches
- "Seafood" - Fish and seafood specialties
- "Sides" - Side dishes, add-ons, extras
- "Breakfast" - Breakfast items, brunch dishes
- "Other" - Items that don't fit standard categories

Examples:
Input: "Caesar Salad", "Fresh romaine lettuce with croutons"
Output: {{"category": "Soups & Salads", "confidence": "High"}}

Input: "Margherita Pizza", "Wood-fired pizza with mozzarella"  
Output: {{"category": "Pizza", "confidence": "High"}}

Input: "Mystery Special", ""
Output: {{"category": "Other", "confidence": "Low"}}
"""
        
        try:
            # Get raw response from Gemini
            raw_response = await self._call_gemini(prompt, max_tokens=150, function_name=function_name)
            
            if not raw_response:
                logger.error(f"❌ [{function_name}] No response from Gemini")
                log_json_parsing_attempt(function_name, prompt, 0, False, "No response from Gemini")
                return None
            
            # Parse JSON using robust utility
            expected_keys = ["category", "confidence"]
            parsed_result = parse_llm_json_output(
                raw_response, 
                function_name=function_name,
                expected_keys=expected_keys
            )
            
            if not parsed_result:
                logger.error(f"❌ [{function_name}] Failed to parse JSON response")
                log_json_parsing_attempt(function_name, prompt, len(raw_response), False, "JSON parsing failed")
                return None
            
            # Validate structure
            if not validate_json_structure(parsed_result, expected_keys, function_name):
                logger.error(f"❌ [{function_name}] Invalid JSON structure")
                log_json_parsing_attempt(function_name, prompt, len(raw_response), False, "Invalid structure")
                return None
            
            # Extract category
            category = safe_get_nested_value(parsed_result, "category", "Other", function_name)
            confidence = safe_get_nested_value(parsed_result, "confidence", "Low", function_name)
            
            # Log successful parsing
            log_json_parsing_attempt(function_name, prompt, len(raw_response), True)
            
            # Track API usage
            self.requests_made += 1
            self.total_cost += self.cost_per_request
            logger.info(f"📊 [{function_name}] API usage: {self.requests_made} requests, ${self.total_cost:.4f} total cost")
            
            logger.info(f"✅ [{function_name}] Successfully categorized: '{item_name}' -> '{category}' ({confidence} confidence)")
            return category

        except Exception as e:
            logger.error(f"❌ [{function_name}] Exception during menu categorization: {str(e)}")
            log_json_parsing_attempt(function_name, prompt, 0, False, str(e))
            return None
    
    async def _canonicalize_name_with_gemini(self, name_variations: List[str]) -> Optional[str]:
        """Pick the most canonical restaurant name from variations"""
        if not name_variations or len(name_variations) < 2:
            return None
        
        names_str = '", "'.join(name_variations)
        
        prompt = f"""
        From these restaurant name variations, identify the most official/canonical version:
        ["{names_str}"]
        
        Return ONLY valid JSON: {{"canonical_name": "..."}}
        """
        
        try:
            response = await self._call_gemini(prompt, max_tokens=100)
            if response:
                json_data = self._extract_json_from_response(response)
                if json_data and json_data.get('canonical_name'):
                    return json_data['canonical_name']
        except Exception as e:
            logger.error(f"❌ Name canonicalization failed: {str(e)}")
        
        return None
    
    async def _extract_details_from_text_with_gemini(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract structured details from unstructured about/description text"""
        if not text or len(text.strip()) < 20:
            return None
        
        # Limit text length to avoid token limits
        text_limited = text[:1000] + "..." if len(text) > 1000 else text
        
        prompt = f"""
        Extract the following details from this restaurant description text:
        - year_established (number or null)
        - cuisine_type (string or null) 
        - specialty_items (array of strings, max 3 items)
        - mission_summary (1-2 sentences or null)
        
        Text: "{text_limited}"
        
        Return ONLY valid JSON with these exact keys.
        """
        
        try:
            response = await self._call_gemini(prompt, max_tokens=200)
            if response:
                json_data = self._extract_json_from_response(response)
                if json_data:
                    # Clean up the extracted data
                    cleaned_extracted = {}
                    if json_data.get('year_established'):
                        try:
                            year = int(json_data['year_established'])
                            if 1800 <= year <= datetime.now().year:
                                cleaned_extracted['year_established'] = year
                        except (ValueError, TypeError):
                            pass
                    
                    if json_data.get('cuisine_type'):
                        cleaned_extracted['cuisine_type'] = json_data['cuisine_type']
                    
                    if json_data.get('specialty_items') and isinstance(json_data['specialty_items'], list):
                        cleaned_extracted['specialty_items'] = json_data['specialty_items'][:3]
                    
                    if json_data.get('mission_summary'):
                        cleaned_extracted['mission_summary'] = json_data['mission_summary'][:200]
                    
                    return cleaned_extracted
        except Exception as e:
            logger.error(f"❌ Text extraction failed: {str(e)}")
        
        return None
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), retry=retry_if_exception_type(Exception))
    async def _call_gemini(self, prompt: str, max_tokens: int = 200, function_name: str = "unknown") -> Optional[str]:
        """
        Enhanced Gemini API call with robust JSON parsing and comprehensive logging.
        
        Args:
            prompt: The prompt to send to Gemini
            max_tokens: Maximum tokens to generate
            function_name: Name of calling function for logging context
            
        Returns:
            Raw response text or None if failed
        """
        if not self.model:
            logger.error(f"❌ [{function_name}] Gemini model not initialized")
            return None
        
        try:
            logger.info(f"📤 [{function_name}] Sending prompt to Gemini ({len(prompt)} chars, max_tokens={max_tokens})")
            logger.debug(f"📤 [{function_name}] Prompt preview: {repr(prompt[:200])}")
            
            # Enhanced generation config with JSON MIME type
            generation_config = genai.types.GenerationConfig(
                temperature=0.1,  # Low temperature for consistent structured output
                    max_output_tokens=max_tokens,
                response_mime_type="application/json"  # Force JSON output
            )
            
            response = await self.model.generate_content_async(
                prompt,
                generation_config=generation_config
            )
            
            if not response or not response.text:
                logger.error(f"❌ [{function_name}] Empty response from Gemini")
                return None
                
            raw_response = response.text.strip()
            logger.info(f"📥 [{function_name}] Received Gemini response ({len(raw_response)} chars)")
            logger.debug(f"📥 [{function_name}] Response preview: {repr(raw_response[:200])}")
            
            return raw_response
            
        except Exception as e:
            logger.error(f"❌ [{function_name}] Gemini API call failed: {str(e)}")
            return None
    
    def _extract_json_from_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from Gemini response (handles markdown code blocks)"""
        if not response_text:
            return None
        
        # Try to find JSON in markdown code blocks first
        json_match = re.search(r'```json\s*([\s\S]+?)\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Fallback: assume the whole response is JSON
            json_str = response_text.strip()
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning(f"⚠️ Failed to parse JSON from Gemini response: {json_str[:100]}...")
            return None
    
    def _format_canonical_address(self, address_components: Dict[str, str]) -> str:
        """Format structured address components into canonical string"""
        parts = []
        
        if address_components.get('street_address'):
            parts.append(address_components['street_address'])
        
        if address_components.get('city'):
            parts.append(address_components['city'])
        
        state_zip = []
        if address_components.get('state'):
            state_zip.append(address_components['state'])
        if address_components.get('postal_code'):
            state_zip.append(address_components['postal_code'])
        
        if state_zip:
            parts.append(' '.join(state_zip))
        
        return ', '.join(parts)
    
    async def _final_validation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Final validation and consistency checks"""
        logger.info("✅ Step 3: Final validation...")
        
        validated = data.copy()
        
        # Cross-validate related fields
        if validated.get('menu_items'):
            alcohol_items = [
                item for item in validated['menu_items'] 
                if isinstance(item, dict) and 
                item.get('category_standardized') == 'Beverage (Alcoholic)'
            ]
            if alcohol_items:
                validated['serves_alcohol'] = True
        
        # Ensure required fields are present
        required_fields = ['name', 'address', 'phone']
        validated['data_completeness_score'] = sum(
            1 for field in required_fields if validated.get(field)
        ) / len(required_fields)
        
        # Add data quality metadata
        validated['data_quality'] = {
            'fields_present': len([k for k, v in validated.items() if v]),
            'address_structured': bool(validated.get('address_structured')),
            'phone_canonicalized': bool(validated.get('phone_canonical')),
            'menu_items_categorized': bool(
                validated.get('menu_items') and 
                any(item.get('category_standardized') for item in validated['menu_items'] if isinstance(item, dict))
            ),
            'completeness_score': validated.get('data_completeness_score', 0)
        }
        
        return validated

    async def extract_menu_items_from_text(self, menu_text: str) -> Optional[List[Dict[str, Any]]]:
        """
        Extract structured menu items from raw menu text using Gemini AI
        
        Args:
            menu_text: Raw menu text from DOM crawler or other sources
            
        Returns:
            List of menu item dictionaries with name, price, description, category
        """
        if not self.enabled or not menu_text or len(menu_text.strip()) < 20:
            return None
            
        logger.info("🍽️ Extracting menu items from raw text using Gemini...")
        
        prompt = f"""
        Extract menu items from this restaurant menu text. Return a JSON array of menu items.
        
        Each menu item should have:
        - name: The dish name (required)
        - price: Price as a string (e.g., "$12.99", "12.99", etc.) or null if not found
        - description: Brief description or null if not found
        - category: One of these categories: {', '.join(self.standard_categories)}
        
        Menu Text:
        {menu_text[:2000]}  # Limit to first 2000 chars
        
        Return ONLY a valid JSON array like:
        [
            {{"name": "Grilled Salmon", "price": "$24.99", "description": "Fresh Atlantic salmon with herbs", "category": "Main Course"}},
            {{"name": "Caesar Salad", "price": "$12.99", "description": "Romaine lettuce with parmesan", "category": "Soup/Salad"}}
        ]
        
        If no clear menu items found, return: []
        """
        
        try:
            response = await self._call_gemini(prompt, max_tokens=1000, function_name="extract_menu_items")
            if not response:
                return None
            
            # Parse JSON response
            menu_items_data = self._extract_json_from_response(response)
            if not menu_items_data or not isinstance(menu_items_data, list):
                # Try to parse as direct JSON array
                try:
                    import json
                    menu_items_data = json.loads(response.strip())
                except:
                    logger.warning("⚠️ Could not parse menu items JSON from Gemini response")
                    return None
            
            # Validate and clean the extracted items
            valid_items = []
            for item in menu_items_data:
                if isinstance(item, dict) and item.get('name'):
                    # Clean up the item
                    clean_item = {
                        'name': str(item['name']).strip(),
                        'price': str(item.get('price', '')).strip() if item.get('price') else None,
                        'description': str(item.get('description', '')).strip() if item.get('description') else None,
                        'category': str(item.get('category', 'Other')).strip()
                    }
                    
                    # Validate category
                    if clean_item['category'] not in self.standard_categories:
                        clean_item['category'] = 'Other'
                    
                    # Remove empty descriptions
                    if not clean_item['description'] or clean_item['description'] in ['', 'null', 'None']:
                        clean_item['description'] = None
                        
                    # Remove empty prices
                    if not clean_item['price'] or clean_item['price'] in ['', 'null', 'None', '$']:
                        clean_item['price'] = None
                    
                    valid_items.append(clean_item)
            
            logger.info(f"✅ Extracted {len(valid_items)} menu items from raw text")
            return valid_items if valid_items else None
            
        except Exception as e:
            logger.error(f"❌ Error extracting menu items with Gemini: {str(e)}")
            return None 
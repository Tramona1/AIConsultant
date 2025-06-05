import json
import asyncio
import aiohttp
from typing import Dict, Tuple, List, Any, Optional, Union
import os
from dotenv import load_dotenv
import logging
import re
from bs4 import BeautifulSoup
import base64
from pathlib import Path
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
import orjson
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from pydantic import HttpUrl
import httpx
from pydantic import BaseModel, Field
from .models import (
    FinalRestaurantOutput, 
    CompetitorSummary, 
    LLMStrategicAnalysisOutput,
    MenuItem,
    ScreenshotInfo
)
from .json_parser_utils import parse_llm_json_output, validate_json_structure, safe_get_nested_value
import uuid
from datetime import datetime
import time
from collections import defaultdict
from urllib.parse import unquote

load_dotenv()

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Use the correct Google Gemini API base URL
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
# FIXED: Use correct current model names from official Google docs
GEMINI_MODEL_TEXT = "gemini-2.0-flash"  # Stable model for text
GEMINI_MODEL_VISION = "gemini-2.0-flash"  # Supports vision

# Set up module-level logging with proper configuration
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False  # Prevent duplicate logs

# Add RichHandler if available, otherwise use StreamHandler
try:
    from rich.logging import RichHandler
    if not logger.handlers:
        handler = RichHandler(rich_tracebacks=True)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
except ImportError:
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)

@retry(
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3)
)
async def make_gemini_request(session: aiohttp.ClientSession, model: str, payload: dict, timeout: int = 300) -> dict:
    """Make a robust API request to Gemini with retries and proper error handling."""
    url = f"{GEMINI_API_BASE_URL}/{model}:generateContent?key={GEMINI_API_KEY}"
    
    # Add security check: never log API keys
    safe_payload = {k: v for k, v in payload.items() if k != 'key'}
    logger.debug(f"Making Gemini API request to {model}")
    
    async with session.post(
        url, 
        json=payload, 
        timeout=aiohttp.ClientTimeout(total=timeout),
        headers={"Content-Type": "application/json"}
    ) as response:
        response.raise_for_status()
        return await response.json()

def clean_and_parse_json(raw_text: str) -> dict:
    """Robustly clean and parse JSON from Gemini responses."""
    # Strip whitespace
    cleaned_text = raw_text.strip()
    
    # Enhanced markdown fence removal - handle more patterns
    fence_patterns = [
        r'^```json\s*\n?',  # ```json at start
        r'^```\s*\n?',      # ``` at start  
        r'\n?```\s*$',      # ``` at end
        r'```$',            # ``` at very end
        r'^```json\s*',     # ```json without newline
        r'```\s*$',         # ``` at end without newline
    ]
    
    for pattern in fence_patterns:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.MULTILINE)
    
    cleaned_text = cleaned_text.strip()
    
    # Handle cases where there might be extra text before/after JSON
    # Look for the first '{' and last '}' to extract just the JSON part
    if cleaned_text:
        # Find the first '{' character (start of JSON object)
        start_idx = cleaned_text.find('{')
        if start_idx == -1:
            # Try looking for '[' for JSON arrays
            start_idx = cleaned_text.find('[')
        
        if start_idx != -1:
            # Find the matching closing brace/bracket
            if cleaned_text[start_idx] == '{':
                # For objects, find the last '}'
                end_idx = cleaned_text.rfind('}')
                if end_idx != -1 and end_idx > start_idx:
                    cleaned_text = cleaned_text[start_idx:end_idx + 1]
            elif cleaned_text[start_idx] == '[':
                # For arrays, find the last ']'
                end_idx = cleaned_text.rfind(']')
                if end_idx != -1 and end_idx > start_idx:
                    cleaned_text = cleaned_text[start_idx:end_idx + 1]
    
    cleaned_text = cleaned_text.strip()
    
    if not cleaned_text:
        raise json.JSONDecodeError("Empty JSON string after cleaning", "", 0)
    
    try:
        # Try orjson first for better handling of trailing commas
        return orjson.loads(cleaned_text)
    except orjson.JSONDecodeError:
        try:
            # Fallback to standard json
            return json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {str(e)}")
            logger.error(f"Cleaned text (first 500 chars): {cleaned_text[:500]}")
            logger.error(f"Raw text (first 500 chars): {raw_text[:500]}")
            
            # Try one more time with aggressive cleaning
            try:
                # Remove any remaining non-JSON characters at start/end
                cleaned_text = re.sub(r'^[^{\[]*', '', cleaned_text)  # Remove everything before { or [
                cleaned_text = re.sub(r'[^}\]]*$', '', cleaned_text)  # Remove everything after } or ]
                cleaned_text = cleaned_text.strip()
                
                if cleaned_text:
                    return json.loads(cleaned_text)
            except json.JSONDecodeError:
                pass
            
            raise e

def check_image_size_limits(image_data: bytes) -> bool:
    """Check if image meets size requirements for Gemini Vision API."""
    # FIXED: Add 20MB limit check before base64 encoding
    size_mb = len(image_data) / (1024 * 1024)
    if size_mb > 20:
        logger.warning(f"Image size {size_mb:.1f}MB exceeds 20MB limit")
        return False
    return True

async def extract_menu_with_gemini(html_content: str) -> List[Dict]:
    """Extracts menu items, descriptions, and prices from HTML content using Gemini."""
    logger.info("Attempting to extract menu with Gemini.")
    
    # Preprocess HTML to reduce token count and focus on menu-relevant content
    def preprocess_html_for_menu(html: str) -> str:
        """Enhanced preprocessing to find menu-specific content"""
        logger.info("🔍 Enhanced menu content preprocessing starting")
        
        # Remove script and style tags first
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Look for menu-specific indicators with broader patterns
        menu_indicators = [
            r'<[^>]*(?:class|id)[^>]*["\'].*?(?:menu|food|dish|item|price|cuisine|appetizer|entree|dessert|drink|beverage).*?["\'][^>]*>.*?</[^>]+>',
            r'<[^>]*(?:menu|food|dining|restaurant).*?>.*?</[^>]+>',
            r'\$\d+(?:\.\d{2})?.*?(?:</[^>]+>|<br|<p)',  # Price patterns
            r'(?:appetizer|entree|main|dessert|drink|wine|beer|cocktail|pasta|pizza|burger|salad|soup).*?\$\d+',
        ]
        
        menu_content = []
        for pattern in menu_indicators:
            matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
            menu_content.extend(matches[:10])  # Limit to avoid too much content
        
        if menu_content:
            logger.info(f"✅ Found {len(menu_content)} menu-specific content blocks")
            combined_content = '\n'.join(menu_content)
            if len(combined_content) > 30000:
                combined_content = combined_content[:30000] + "... [truncated]"
            return combined_content
        
        # Fallback: Look for content with dollar signs and common food words
        logger.info("🔄 Falling back to price-based content detection")
        soup = BeautifulSoup(html, 'html.parser')
            
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer']):
            element.decompose()
        
        text_content = soup.get_text()
        
        # Split into lines and find lines with prices and food terms
        lines = text_content.split('\n')
        menu_lines = []
        
        for line in lines:
            line = line.strip()
            if len(line) > 10 and '$' in line:
                # Check if line contains food-related terms
                food_terms = ['chicken', 'beef', 'pork', 'fish', 'salmon', 'pasta', 'pizza', 'salad', 'soup', 'burger', 'sandwich', 'rice', 'noodles', 'bread', 'cheese', 'sauce', 'grilled', 'fried', 'roasted', 'fresh', 'organic', 'wine', 'beer', 'cocktail', 'coffee', 'tea']
                if any(term in line.lower() for term in food_terms):
                    menu_lines.append(line)
        
        if menu_lines:
            logger.info(f"✅ Found {len(menu_lines)} potential menu lines with prices")
            return '\n'.join(menu_lines[:50])  # Limit to 50 lines
        
        # Final fallback: use main content but truncated
        logger.info("⚠️ No specific menu content found, using main content")
        main_content = soup.get_text()
        if len(main_content) > 50000:
            main_content = main_content[:50000]
        
        return main_content
    
    # Preprocess the HTML to reduce size and focus on menu content
    processed_html = preprocess_html_for_menu(html_content)
    logger.info(f"Preprocessed HTML from {len(html_content)} to {len(processed_html)} characters")
    
    prompt = f"""
    <instructions>You are an expert at extracting structured data from HTML. 
    Your task is to parse the provided HTML content of a restaurant website 
    and extract all individual menu items, their descriptions (if available), 
    and their prices (if available). 
    
    If a price is not explicitly mentioned next to an item, you can leave it null. 
    Do not include non-menu items, headers, footers, or navigation elements. 
    Focus only on actual food and drink items with their prices. 
    </instructions>
    <input_html>
    {processed_html}
    </input_html>
    <output_format>
    Return ONLY a JSON array of objects. Each object should have the following keys:
    "name": string (name of the menu item)
    "description": string | null (description of the menu item, null if not found)
    "price": string | null (price of the menu item, null if not found. Keep as string to preserve currency symbols.)
    </output_format>
    """

    # FIXED: Use correct payload structure for current Gemini API
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048  # FIXED: Respect token limits
        }
    }
    
    try:
        # Use async HTTP client with proper session management
        async with aiohttp.ClientSession() as session:
            logger.info(f"🔗 Making Gemini API request for menu extraction")
            
            response_data = await make_gemini_request(session, GEMINI_MODEL_TEXT, payload)
            
            logger.info(f"📊 Gemini response status: success")
            logger.debug(f"🔍 Response structure: {list(response_data.keys()) if isinstance(response_data, dict) else 'Not a dict'}")
            
            # Extract text from Google Gemini API response format
            if 'candidates' in response_data and len(response_data['candidates']) > 0:
                logger.info(f"✅ Found {len(response_data['candidates'])} candidates in response")
                candidate = response_data['candidates'][0]
                
                if 'content' in candidate and 'parts' in candidate['content']:
                    raw_text = candidate['content']['parts'][0]['text']
                    logger.info(f"📄 Raw text from Gemini: {raw_text[:200]}...")
                    logger.info(f"📏 Raw text length: {len(raw_text)}")
                    
                    # Clean and validate JSON
                    menu_data = clean_and_parse_json(raw_text)
                    logger.info(f"✅ Successfully extracted {len(menu_data)} menu items with Gemini.")
                    return menu_data
                else:
                    logger.error(f"❌ Missing 'content' or 'parts' in candidate: {candidate}")
            else:
                logger.error(f"❌ No candidates found in response: {response_data}")
        
        logger.error("❌ Unexpected response format from Gemini API")
        return []
        
    except Exception as e:
        logger.error(f"❌ Gemini API request failed during menu extraction: {e}")
        return []

async def analyze_with_gemini(data: Dict) -> str:
    """Analyze restaurant data using Gemini and return XML-formatted results."""
    
    # Convert GoogleReviewData to dict if it's a Pydantic object
    google_reviews_data = data.get('reviews', {}).get('google', {})
    if hasattr(google_reviews_data, 'model_dump'):
        google_reviews_dict = google_reviews_data.model_dump()
    elif hasattr(google_reviews_data, 'dict'):
        google_reviews_dict = google_reviews_data.dict()
    elif isinstance(google_reviews_data, dict):
        google_reviews_dict = google_reviews_data
    else:
        google_reviews_dict = {}
    
    prompt = f"""
            You are a restaurant business consultant providing comprehensive analysis for decision makers.
            
            Context: {data['restaurant_name']} is seeking to understand their competitive position and growth opportunities.
            
            <analysis_data>
            Restaurant: {data['restaurant_name']}
            Website: {data.get('website_data', {}).get('url', 'Not provided')}
            Contact: {data.get('website_data', {}).get('contact', {}).get('email', 'Not provided')}
            
            Menu Analysis:
            - Items found: {len(data.get('website_data', {}).get('menu', {}).get('items', []))}
            - Sample items: {str(data.get('website_data', {}).get('menu', {}).get('items', [])[:3])}
            
            Customer Reviews:
            - Google Rating: {google_reviews_dict.get('rating', 'N/A')} ({google_reviews_dict.get('total_reviews', 0)} reviews)
            - Sentiment Score: {google_reviews_dict.get('avg_sentiment', 'N/A')}
            
            Competitive Landscape:
            {chr(10).join([f"- {comp['name']}: {comp.get('rating', 'N/A')} stars ({comp.get('review_count', 0)} reviews)" 
                          for comp in data.get('competitors', {}).get('competitors', [])[:5]])}
            </analysis_data>
            
            Provide strategic recommendations in this XML format:
            
            <analysis>
                <competitive_landscape>
                    <item>Key insight about competitive positioning</item>
                    <item>Market differentiation opportunities</item>
                    <item>Competitive advantages or disadvantages</item>
                </competitive_landscape>
                
                <opportunity_gaps>
                    <item>Specific improvement opportunity with rationale</item>
                    <item>Revenue growth potential area</item>
                    <item>Operational efficiency opportunity</item>
                </opportunity_gaps>
                
                <prioritized_actions>
                    <action_item>
                        <action>Specific actionable recommendation</action>
                        <impact>Expected business impact (High/Medium/Low)</impact>
                        <feasibility>Implementation difficulty (Easy/Medium/Hard)</feasibility>
                        <rationale>Why this action will drive results</rationale>
                    </action_item>
                    <action_item>
                        <action>Second priority recommendation</action>
                        <impact>Expected business impact</impact>
                        <feasibility>Implementation difficulty</feasibility>
                        <rationale>Strategic reasoning</rationale>
                    </action_item>
                    <action_item>
                        <action>Third priority recommendation</action>
                        <impact>Expected business impact</impact>
                        <feasibility>Implementation difficulty</feasibility>
                        <rationale>Business justification</rationale>
                    </action_item>
                </prioritized_actions>
            </analysis>
            """
    
    # FIXED: Use correct payload structure
    payload = {
        "contents": [
            {
                "role": "user", 
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            response_data = await make_gemini_request(session, GEMINI_MODEL_TEXT, payload)
            
            # Extract text from Google Gemini API response format
            if 'candidates' in response_data and len(response_data['candidates']) > 0:
                candidate = response_data['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    return candidate['content']['parts'][0]['text']
    except Exception as e:
        logger.error(f"❌ Analysis failed: {str(e)}")
        raise Exception(f"Gemini analysis failed: {str(e)}")
    
    raise Exception("Unexpected response format from Gemini API")

async def analyze_target_restaurant(restaurant_data: Dict) -> Dict:
    """
    Stage 1: In-depth analysis of the target restaurant.
    
    Args:
        restaurant_data: Comprehensive data about the target restaurant
    
    Returns:
        Structured analysis with strengths, weaknesses, and opportunities
    """
    logger.info(f"🎯 Analyzing target restaurant: {restaurant_data.get('restaurant_name', 'Unknown')}")
    
    # Prepare comprehensive data summary
    website_data = restaurant_data.get('website_data', {})
    reviews_data = restaurant_data.get('reviews', {}).get('google', {})
    business_info = restaurant_data.get('business_info', {})
    
    # Extract key metrics
    menu_items_count = len(website_data.get('menu', {}).get('items', []))
    products_count = len(website_data.get('products', []))
    services_count = len(website_data.get('services', []))
    social_links_count = len(website_data.get('social_links', []))
    
    # Get reviews data and convert GoogleReviewData to dict if it's a Pydantic object
    reviews_data = restaurant_data.get('reviews', {}).get('google', {})
    if hasattr(reviews_data, 'model_dump'):
        reviews_data = reviews_data.model_dump()
    elif hasattr(reviews_data, 'dict'):
        reviews_data = reviews_data.dict()
    elif not isinstance(reviews_data, dict):
        reviews_data = {}
    
    google_rating = reviews_data.get('rating', 0)
    google_reviews_count = reviews_data.get('total_reviews', 0)
    
    prompt = f"""
    <instructions>
    You are a top-tier restaurant business consultant analyzing a target restaurant's complete online presence.
    Based on the comprehensive data provided, identify specific strengths, weaknesses, and opportunities.
    Be precise, actionable, and focus on digital marketing and operational improvements.
    </instructions>
    
    <target_restaurant_data>
    <basic_info>
        <name>{restaurant_data.get('restaurant_name', 'Unknown')}</name>
        <website>{website_data.get('url', 'Not provided')}</website>
        <email>{website_data.get('contact', {}).get('email', 'Not provided')}</email>
        <phone>{website_data.get('contact', {}).get('phone', 'Not provided')}</phone>
        <address>{website_data.get('address', 'Not provided')}</address>
    </basic_info>
    
    <digital_presence>
        <menu_items_online>{menu_items_count}</menu_items_online>
        <products_catalog>{products_count}</products_catalog>
        <services_offered>{services_count}</services_offered>
        <social_media_platforms>{social_links_count}</social_media_platforms>
        <scraper_used>{website_data.get('scraper_used', 'unknown')}</scraper_used>
        <menu_extraction_source>{restaurant_data.get('menu_extraction_source', 'unknown')}</menu_extraction_source>
    </digital_presence>
    
    <google_presence>
        <rating>{google_rating}</rating>
        <total_reviews>{google_reviews_count}</total_reviews>
        <avg_sentiment>{reviews_data.get('avg_sentiment', 'N/A')}</avg_sentiment>
        <has_hours>{bool(reviews_data.get('opening_hours', {}).get('weekday_text'))}</has_hours>
        <has_photos>{reviews_data.get('photos', {}).get('count', 0) > 0}</has_photos>
        <verified_listing>{reviews_data.get('place_details', {}).get('business_status') == 'OPERATIONAL'}</verified_listing>
    </google_presence>
    
    <enhanced_business_intelligence>
        <revenue_streams>{business_info.get('revenue_streams', [])}</revenue_streams>
        <competitive_advantages>{business_info.get('competitive_advantages', [])}</competitive_advantages>
        <pages_analyzed>{business_info.get('pages_analyzed', 0)}</pages_analyzed>
        <navigation_elements>{business_info.get('navigation_analysis', {}).get('totalNavigationElements', 0)}</navigation_elements>
    </enhanced_business_intelligence>
    
    <data_quality_assessment>
        <stagehand_quality>{restaurant_data.get('data_quality_metrics', {})}</stagehand_quality>
        <screenshots_captured>{len(website_data.get('all_screenshots', []))}</screenshots_captured>
    </data_quality_assessment>
    </target_restaurant_data>
    
    <task>
    Analyze this restaurant's online presence comprehensively and provide:
    
    1. **3-5 Key Strengths**: What is this restaurant doing well online? Consider website quality, Google presence, social media, menu accessibility, business intelligence gathered.
    
    2. **3-5 Key Weaknesses**: What are the major gaps or problems? Consider missing contact info, poor Google presence, limited menu online, weak social media, technical issues.
    
    3. **3-5 Distinct Opportunities**: Specific, actionable improvements that could drive revenue. Include estimated impact level (high/medium/low) and suggest first actionable steps.
    
    For each item, be specific and reference the actual data provided. Focus on opportunities that directly impact customer acquisition and revenue.
    </task>
    
    <output_format>
    Return ONLY a JSON object with this exact structure:
    {{
        "strengths": [
            {{
                "title": "Strength title",
                "description": "Detailed explanation with specific data references",
                "evidence": "Specific metrics or data points supporting this"
            }}
        ],
        "weaknesses": [
            {{
                "title": "Weakness title", 
                "description": "Detailed explanation of the problem",
                "impact": "Why this matters for the business"
            }}
        ],
        "opportunities": [
            {{
                "title": "Opportunity title",
                "description": "Detailed explanation of the opportunity", 
                "impact_level": "high|medium|low",
                "first_step": "Specific actionable first step",
                "estimated_impact": "Estimated business impact"
            }}
        ]
    }}
    </output_format>
    """
    
    try:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 2048
            }
        }
        
        logger.info(f"🔗 Making target analysis API request")
        
        async with aiohttp.ClientSession() as session:
            response_data = await make_gemini_request(session, GEMINI_MODEL_TEXT, payload, timeout=300)
            
            if response_data.get("error"):
                logger.error(f"❌ Target analysis API error: {response_data['error']}")
                return {
                    "error": f"AI analysis failed: {response_data['error']}",
                    "restaurant_name": restaurant_data.get('restaurant_name', 'Unknown')
                }
            
            # Parse response
            analysis_content = response_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if not analysis_content:
                logger.error("❌ Empty response from target analysis API")
                return {
                    "error": "Empty response from AI analysis",
                    "restaurant_name": restaurant_data.get('restaurant_name', 'Unknown')
                }
            
            # Log the raw response for debugging
            logger.debug(f"📝 Raw analysis content length: {len(analysis_content)}")
            logger.debug(f"📝 Raw analysis content (first 100 chars): {analysis_content[:100]}")
            
            # Parse JSON from response
            try:
                analysis_result = clean_and_parse_json(analysis_content)
                logger.info(f"✅ Target analysis complete: {len(analysis_result.get('strengths', []))} strengths, {len(analysis_result.get('weaknesses', []))} weaknesses, {len(analysis_result.get('opportunities', []))} opportunities")
                return {
                    "target_restaurant_analysis": analysis_result,
                    "restaurant_name": restaurant_data.get('restaurant_name', 'Unknown')
                }
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse target analysis JSON: {str(e)}")
                logger.error(f"Raw response: {analysis_content[:500]}...")
                
                # Attempt to gracefully handle by creating a fallback response
                logger.warning("🔄 Creating fallback response structure for broken JSON")
                return {
                    "target_restaurant_analysis": {
                        "strengths": [{"title": "Data Available", "description": "Restaurant data was collected but AI analysis needs debugging", "estimated_impact": "Analysis in progress"}],
                        "weaknesses": [{"title": "Analysis Processing", "description": "JSON parsing error in AI response - technical issue", "estimated_impact": "Temporary"}],
                        "opportunities": [{"title": "System Optimization", "description": "API response format needs improvement", "estimated_impact": "Resolving"}]
                    },
                    "restaurant_name": restaurant_data.get('restaurant_name', 'Unknown'),
                    "parsing_error": str(e),
                    "raw_response_preview": analysis_content[:200]
                }
        
    except Exception as e:
        logger.error(f"❌ Target restaurant analysis failed: {str(e)}")
        return {
            "error": f"Analysis failed: {str(e)}",
            "strengths": [],
            "weaknesses": [],
            "opportunities": []
        }

async def analyze_competitor_snapshot(competitor_data: Dict) -> str:
    """
    Stage 2: Concise analysis of a single competitor.
    
    Args:
        competitor_data: Data about a single competitor
    
    Returns:
        Brief textual summary of the competitor's positioning
    """
    competitor_name = competitor_data.get('name', 'Unknown Competitor')
    logger.info(f"📊 Creating competitor snapshot: {competitor_name}")
    
    prompt = f"""
    <instructions>
    Provide a concise 2-3 sentence competitive intelligence summary for this local restaurant competitor.
    Focus on their apparent online positioning, key strengths, and any notable digital strategy elements.
    </instructions>
    
    <competitor_data>
    <name>{competitor_name}</name>
    <google_rating>{competitor_data.get('rating', 'N/A')}</google_rating>
    <review_count>{competitor_data.get('review_count', 0)}</review_count>
    <address>{competitor_data.get('address', 'Not provided')}</address>
    <phone>{competitor_data.get('phone', 'Not provided')}</phone>
    <website>{competitor_data.get('website', 'No website')}</website>
    <price_level>{competitor_data.get('price_level', 'Unknown')}</price_level>
    <categories>{competitor_data.get('categories', [])}</categories>
    <distance>{competitor_data.get('location', {}).get('distance_km', 'Unknown')} km</distance>
    
    <digital_strategy>
    {competitor_data.get('digital_strategy', {})}
    </digital_strategy>
    
    <social_presence>
    {competitor_data.get('social_presence', [])}
    </social_presence>
    </competitor_data>
    
    <task>
    Create a brief competitive intelligence summary. Example format:
    "[Competitor Name] appears to have [key strength] with [rating] stars from [count] reviews. 
    Their digital presence shows [notable strengths/weaknesses]. 
    Located [distance] away, they seem positioned as [market positioning]."
    
    Focus on what makes them competitive or what gaps they have that represent opportunities.
    </task>
    
    Return only the summary text, no JSON or extra formatting.
    """
    
    try:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 300
            }
        }
        
        async with aiohttp.ClientSession() as session:
            response_data = await make_gemini_request(session, GEMINI_MODEL_TEXT, payload, timeout=300)
            
            if 'candidates' in response_data and len(response_data['candidates']) > 0:
                candidate = response_data['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    summary = candidate['content']['parts'][0]['text'].strip()
                    logger.info(f"✅ Competitor snapshot created for {competitor_name}")
                    return summary
                    
    except Exception as e:
        logger.error(f"❌ Competitor snapshot failed for {competitor_name}: {str(e)}")
        return f"{competitor_name} - Analysis unavailable due to processing error."

async def generate_strategic_recommendations(
    target_analysis: Dict,
    competitor_summaries: List[str],
    restaurant_name: str,
    supporting_screenshots: List[Dict] = None
) -> Dict:
    """
    Stage 3: Main strategic recommendation engine - the "consultant" prompt.
    
    Args:
        target_analysis: Results from analyze_target_restaurant
        competitor_summaries: List of competitor summary strings
        restaurant_name: Name of the target restaurant
        supporting_screenshots: List of relevant screenshot data with S3 URLs
    
    Returns:
        Comprehensive strategic recommendations JSON
    """
    logger.info(f"🧠 Generating strategic recommendations for {restaurant_name}")
    
    # Format competitor information
    competitor_text = "\n".join([f"- {summary}" for summary in competitor_summaries[:5]])
    
    # Format screenshot evidence
    screenshot_evidence = ""
    if supporting_screenshots:
        screenshot_evidence = "\n<supporting_visual_evidence>\n"
        for i, screenshot in enumerate(supporting_screenshots[:3]):  # Limit to 3 most relevant
            screenshot_evidence += f'<screenshot_{i+1} url="{screenshot.get("s3_url", "")}" caption="{screenshot.get("caption", "")}" analysis_focus="{screenshot.get("analysis_focus", "")}"/>\n'
        screenshot_evidence += "</supporting_visual_evidence>\n"
    
    prompt = f"""
    <instructions>
    You are a top-tier strategy consultant specializing in local restaurant digital transformation.
    Your analysis will be used to create a compelling business report that demonstrates clear ROI and competitive advantages.
    Focus on specific competitive gaps and provide actionable recommendations with realistic revenue estimates.
    </instructions>
    
    <context>
    <target_restaurant_analysis>
    {json.dumps(target_analysis, indent=2)}
    </target_restaurant_analysis>
    
    <competitive_intelligence>
    {competitor_text}
    </competitive_intelligence>
    {screenshot_evidence}
    </context>
    
    <task>
    Generate a sales-focused strategic analysis for {restaurant_name} with these components:
    
    1. **Executive Hook:** Create a compelling 1-2 sentence hook that quantifies potential revenue increase (10-40% range) by addressing the most critical competitive gap. Be specific about timeframe (6-12 months) and cite competitor advantages.
    
    2. **Competitive Landscape Summary:** Compare {restaurant_name} directly to its top 3 competitors in these areas:
       - Google review volume and ratings advantage/disadvantage
       - Online ordering and digital presence gaps
       - Social media engagement and follower disparities
       - Website quality and menu accessibility issues
       Identify the 1-2 areas where {restaurant_name} is losing customers to competitors.
    
    3. **Top 3 Prioritized Opportunities:** Rank by revenue impact potential. For each:
       - Opportunity title (specific and actionable)
       - Problem description citing specific competitor advantages
       - Detailed recommendation with implementation steps
       - Revenue impact estimate with reasoning ("competitors see X% more orders due to Y")
       - AI solution pitch explaining exactly how our platform automates this solution
       - Timeline and difficulty level
    
    4. **Premium Analysis Teasers:** Create 3 premium content areas that would make restaurant owners pay:
       - "Competitor Customer Acquisition Analysis" 
       - "Automated Review Response Strategy"
       - "Dynamic Pricing Optimization Report"
       Each with a compelling one-sentence teaser.
    
    5. **Immediate Action Items:** 3 tips they can implement today (builds trust).
    
    6. **Engagement Questions:** 3 questions about their current challenges with POS systems, online ordering, and marketing that lead to consultation booking.
    </task>
    
    <output_format>
    Return ONLY a JSON object with this exact structure:
    {{
        "executive_hook": "Specific revenue estimate with competitive reasoning and timeframe",
        "competitive_landscape_summary": "Direct comparison highlighting 1-2 key areas where target is losing to competitors",
        "prioritized_opportunities": [
            {{
                "opportunity_title": "Specific actionable title",
                "problem_description": "Problem with specific competitor references and lost revenue estimates",
                "recommendation": "Step-by-step implementation advice",
                "revenue_impact_estimate": "Percentage increase with reasoning based on competitor data",
                "our_ai_solution_pitch": "Exact explanation of how our platform automates/implements this",
                "implementation_timeline": "2-4 weeks | 1-2 months | 3-6 months",
                "difficulty_level": "Easy | Medium | Advanced",
                "supporting_screenshot_caption": "Caption for relevant screenshot if available"
            }}
        ],
        "premium_insights_teasers": [
            {{
                "title": "Premium analysis title",
                "teaser": "Compelling one-sentence hook that makes them want to upgrade",
                "value_proposition": "What specific ROI they'll get from this analysis"
            }}
        ],
        "immediate_action_items": [
            "Specific actionable tip they can do today",
            "Second actionable tip with expected impact",
            "Third tip that builds credibility"
        ],
        "consultation_questions": [
            "Question about POS/ordering system challenges",
            "Question about current marketing/review management",
            "Question about biggest restaurant growth obstacle"
        ]
    }}
    </output_format>
    """
    
    try:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 3000
            }
        }
        
        logger.info(f"🔗 Making strategic recommendations API request")
        
        async with aiohttp.ClientSession() as session:
            response_data = await make_gemini_request(session, GEMINI_MODEL_TEXT, payload, timeout=300)
            
            if 'candidates' in response_data and len(response_data['candidates']) > 0:
                candidate = response_data['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    raw_text = candidate['content']['parts'][0]['text']
                    
                    # Clean and parse JSON
                    recommendations = clean_and_parse_json(raw_text)
                    logger.info(f"✅ Strategic recommendations generated: {len(recommendations.get('prioritized_opportunities', []))} opportunities identified")
                    
                    return recommendations
            
    except Exception as e:
        logger.error(f"❌ Strategic recommendations failed: {str(e)}")
        return {
            "error": f"Recommendations failed: {str(e)}",
            "executive_hook": f"Our AI analysis identifies growth opportunities for {restaurant_name}.",
            "competitive_landscape_summary": "Analysis unavailable due to processing error.",
            "prioritized_opportunities": [],
            "premium_insights_teasers": [],
            "immediate_action_items": [],
            "consultation_questions": []
        }

async def quality_check_analysis(analysis_content: Dict) -> Dict:
    """
    Stage 4: Optional QA check to polish the analysis content.
    
    Args:
        analysis_content: JSON content from strategic recommendations
    
    Returns:
        Polished and validated JSON content
    """
    logger.info("🔍 Performing quality check on analysis content")
    
    prompt = f"""
    <instructions>
    Review the provided restaurant analysis content for a small business owner audience.
    Check for clarity, professional tone, realistic claims, and coherence.
    Ensure revenue estimates are plausible and recommendations are actionable.
    Make minor improvements for impact while maintaining the exact JSON structure.
    </instructions>
    
    <content_to_review>
    {json.dumps(analysis_content, indent=2)}
    </content_to_review>
    
    <task>
    1. Verify that revenue claims in the executive hook are realistic (typically 10-40% for digital improvements)
    2. Ensure recommendations are specific and actionable
    3. Check that competitor references make sense
    4. Improve clarity and impact where needed
    5. Maintain professional, consultative tone
    
    Return the improved content in the EXACT same JSON structure.
    </task>
    """
    
    try:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 3000
            }
        }
        
        async with aiohttp.ClientSession() as session:
            response_data = await make_gemini_request(session, GEMINI_MODEL_TEXT, payload, timeout=300)
            
            if 'candidates' in response_data and len(response_data['candidates']) > 0:
                candidate = response_data['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    raw_text = candidate['content']['parts'][0]['text']
                    
                    # Clean and parse JSON
                    polished_content = clean_and_parse_json(raw_text)
                    logger.info("✅ Quality check completed - content polished")
                    
                    return polished_content
            
    except Exception as e:
        logger.error(f"❌ Quality check failed, using original content: {str(e)}")
        return analysis_content  # Return original if QA fails

async def evaluate_screenshot_quality(image_s3_url: str, page_type: str, restaurant_name: str) -> Dict[str, Any]:
    """
    Evaluate screenshot quality and relevance before including in reports.
    
    Args:
        image_s3_url: S3 URL of the screenshot
        page_type: Type of page (homepage, menu, about, contact, etc.)
        restaurant_name: Name of restaurant for context
    
    Returns:
        Quality assessment with score and recommendations
    """
    logger.info(f"🔍 Evaluating screenshot quality: {page_type} for {restaurant_name}")
    
    quality_prompt = f"""
    <instructions>
    You are evaluating a screenshot from {restaurant_name}'s website for inclusion in a professional business analysis report.
    Assess the technical quality, content relevance, and suitability for client presentation.
    </instructions>
    
    <evaluation_criteria>
    Page Type: {page_type}
    Restaurant: {restaurant_name}
    
    Rate the screenshot on these factors (1-5 scale each):
    1. Technical Quality: Is the image clear, properly loaded, no broken elements?
    2. Content Relevance: Does it show relevant {page_type} content clearly?
    3. Professional Appearance: Would this look good in a client report?
    4. Information Value: Does it provide useful insights for analysis?
    5. Completeness: Is the important content fully visible (not cut off)?
    
    Special considerations for {page_type}:
    - Homepage: Should show branding, navigation, key info clearly
    - Menu: Should show actual menu items with prices if possible
    - About: Should show restaurant story, team, or location info
    - Contact: Should show contact information, hours, location
    </evaluation_criteria>
    
    <task>
    Provide a detailed assessment including:
    1. Overall suitability score (1-5, where 5 = excellent for report, 1 = unusable)
    2. Individual factor scores
    3. Key insights visible in the screenshot
    4. Issues or problems noted
    5. Recommendation (include/exclude/retry)
    6. Suggested caption if including
    </task>
    
    <output_format>
    Return ONLY a JSON object:
    {{
        "overall_score": 4.2,
        "technical_quality": 5,
        "content_relevance": 4,
        "professional_appearance": 4,
        "information_value": 4,
        "completeness": 4,
        "key_insights": ["Insight 1", "Insight 2"],
        "issues_noted": ["Issue 1 if any"],
        "recommendation": "include|exclude|retry",
        "suggested_caption": "Caption for report if including",
        "rationale": "Brief explanation of scoring and recommendation"
    }}
    </output_format>
    """
    
    try:
        # First check if we can access the image
        async with aiohttp.ClientSession() as session:
            try:
                async with session.head(image_s3_url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status == 200:
                        logger.info(f"✅ Image accessible at {image_s3_url}")
                    else:
                        logger.warning(f"⚠️ Image not accessible (status {response.status}): {image_s3_url}")
                        return None
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ Image accessibility check timed out: {image_s3_url}")
                return None
            except Exception as e:
                logger.warning(f"⚠️ Image accessibility check failed: {str(e)}")
                return None
            
            # Download image for analysis
            try:
                async with session.get(image_s3_url, timeout=aiohttp.ClientTimeout(total=120)) as response:
                    response.raise_for_status()
                    image_data = await response.read()
                    
                    if not check_image_size_limits(image_data):
                        return {"overall_score": 1, "recommendation": "exclude", "rationale": "Image too large for processing"}
                    
                    image_base64 = base64.b64encode(image_data).decode()
            except Exception as e:
                logger.error(f"❌ Failed to download image: {str(e)}")
                return {"overall_score": 1, "recommendation": "exclude", "rationale": f"Image download failed: {str(e)}"}
        
        # Use Gemini Vision for quality assessment
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": quality_prompt},
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": image_base64
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 800
            }
        }
        
        async with aiohttp.ClientSession() as session:
            response_data = await make_gemini_request(session, GEMINI_MODEL_VISION, payload, timeout=300)
            
            # Extract text from response
            if 'candidates' in response_data and len(response_data['candidates']) > 0:
                candidate = response_data['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    raw_text = candidate['content']['parts'][0]['text']
                    
                    # Clean and parse JSON
                    quality_assessment = clean_and_parse_json(raw_text)
                    
                    logger.info(f"✅ Screenshot quality assessment: {quality_assessment.get('overall_score', 0)}/5 "
                              f"({quality_assessment.get('recommendation', 'unknown')})")
                    
                    return quality_assessment
        
        logger.error("❌ Invalid response structure from quality assessment")
        return {"overall_score": 1, "recommendation": "exclude", "rationale": "Assessment failed"}
        
    except Exception as e:
        logger.error(f"❌ Screenshot quality assessment failed: {str(e)}")
        return {"overall_score": 1, "recommendation": "exclude", "rationale": f"Quality check failed: {str(e)}"}

async def orchestrate_comprehensive_analysis(report_dict: Dict) -> Dict:
    """
    Orchestrate a comprehensive analysis pipeline for restaurant data.
    
    This function coordinates multiple analysis stages:
    1. Target restaurant analysis
    2. Competitor analysis summaries  
    3. Strategic recommendations generation
    4. Quality assurance check
    
    Args:
        report_dict: Complete restaurant data from aggregator
        
    Returns:
        Comprehensive analysis results with all insights
    """
    logger.info(f"🚀 Starting comprehensive analysis orchestration for {report_dict.get('restaurant_name', 'Unknown Restaurant')}")
    
    try:
        # Stage 1: Analyze target restaurant in detail
        logger.info("📊 Stage 1: Analyzing target restaurant")
        target_analysis = await analyze_target_restaurant(report_dict)
        logger.info("✅ Target restaurant analysis completed")
        
        # Stage 2: Generate competitor analysis summaries
        logger.info("🔍 Stage 2: Processing competitor data")
        competitor_summaries = []
        
        # Fix: Access competitors from the correct path in report_dict
        competitors_section = report_dict.get('competitors', {})
        competitors_list = competitors_section.get('competitors', [])
        
        if competitors_list:
            logger.info(f"Found {len(competitors_list)} competitors to analyze")
            # Process each competitor (competitors is a list, not a dict)
            for i, competitor_data in enumerate(competitors_list):
                if competitor_data and isinstance(competitor_data, dict):
                    competitor_name = competitor_data.get('name', f'Competitor {i+1}')
                    logger.info(f"  Analyzing competitor: {competitor_name}")
                    try:
                        competitor_summary = await analyze_competitor_snapshot(competitor_data)
                        competitor_summaries.append(competitor_summary)
                        logger.info(f"  ✅ Completed analysis for {competitor_name}")
                    except Exception as comp_error:
                        logger.error(f"  ❌ Failed to analyze {competitor_name}: {str(comp_error)}")
                        # Continue with other competitors
                        continue
        else:
            logger.info("No competitors found in report data")
        
        logger.info(f"✅ Processed {len(competitor_summaries)} competitor analyses")
        
        # Stage 3: Generate strategic recommendations
        logger.info("🎯 Stage 3: Generating strategic recommendations")
        restaurant_name = report_dict.get('restaurant_name', 'Target Restaurant')
        
        # Extract screenshots for context if available
        supporting_screenshots = []
        screenshots = report_dict.get('screenshots', {})
        if screenshots:
            for page_type, screenshot_data in screenshots.items():
                if screenshot_data and isinstance(screenshot_data, dict):
                    supporting_screenshots.append({
                        'page_type': page_type,
                        'data': screenshot_data
                    })
        
        strategic_recommendations = await generate_strategic_recommendations(
            target_analysis=target_analysis,
            competitor_summaries=competitor_summaries,
            restaurant_name=restaurant_name,
            supporting_screenshots=supporting_screenshots if supporting_screenshots else None
        )
        logger.info("✅ Strategic recommendations generated")
        
        # Stage 4: Quality assurance check
        logger.info("🔍 Stage 4: Performing quality assurance")
        polished_recommendations = await quality_check_analysis(strategic_recommendations)
        logger.info("✅ Quality assurance completed")
        
        # Compile comprehensive results
        comprehensive_analysis = {
            'status': 'success',
            'restaurant_name': restaurant_name,
            'analysis_timestamp': report_dict.get('analysis_timestamp'),
            'target_analysis': target_analysis,
            'competitor_summaries': competitor_summaries,
            'strategic_recommendations': polished_recommendations,
            'metadata': {
                'total_competitors_analyzed': len(competitor_summaries),
                'analysis_stages_completed': 4,
                'supporting_screenshots_count': len(supporting_screenshots)
            }
        }
        
        logger.info(f"🎉 Comprehensive analysis orchestration completed successfully for {restaurant_name}")
        logger.info(f"📈 Results: {len(competitor_summaries)} competitors analyzed, {len(supporting_screenshots)} screenshots processed")
        
        return comprehensive_analysis
        
    except Exception as e:
        logger.error(f"❌ Comprehensive analysis orchestration failed: {str(e)}")
        
        # Return error response with partial data if available
        error_response = {
            'status': 'error',
            'error': str(e),
            'restaurant_name': report_dict.get('restaurant_name', 'Unknown'),
            'analysis_timestamp': report_dict.get('analysis_timestamp'),
            'partial_data': {}
        }
        
        # Include any partial results that were successful
        if 'target_analysis' in locals():
            error_response['partial_data']['target_analysis'] = target_analysis
        if 'competitor_summaries' in locals():
            error_response['partial_data']['competitor_summaries'] = competitor_summaries
            
        return error_response

class LLMAnalyzer:
    """
    Handles the generation of strategic report content and screenshot analysis using LLM prompts.
    """
    def __init__(self):
        self.enabled = self._initialize_gemini()
        if self.enabled:
            # Using Gemini 1.5 Flash for potentially faster/cheaper structured output generation and vision tasks.
            self.vision_model = genai.GenerativeModel('gemini-1.5-flash-latest')
            self.text_model = genai.GenerativeModel('gemini-1.5-flash-latest') # Can be same or different
            logger.info("🤖 LLMAnalyzer initialized with Gemini models (flash for text and vision).")
        else:
            logger.warning("⚠️ LLMAnalyzer initialized but Gemini is not available. Strategic analysis and screenshot analysis will be skipped.")

    def _initialize_gemini(self) -> bool:
        try:
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                logger.warning("GEMINI_API_KEY not found. LLMAnalyzer will be disabled.")
                return False
            genai.configure(api_key=api_key)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini for LLMAnalyzer: {str(e)}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
    async def _call_gemini_text_json_mode(self, prompt: str, max_tokens: int = 2048) -> Optional[Dict[str, Any]]:
        """Helper to call Gemini text model and expect a JSON string which is then parsed."""
        if not self.enabled:
            logger.warning("Gemini disabled, skipping LLM text call.")
            return None
        try:
            logger.debug(f"Submitting TEXT prompt to Gemini (JSON mode, max_tokens={max_tokens}):\n{prompt[:300]}...")
            
            response = await self.text_model.generate_content_async(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    # response_mime_type="application/json", # Use if model/SDK version fully supports clean JSON output
                    max_output_tokens=max_tokens,
                    temperature=0.1 # Low temp for factual/structured output
                ),
                safety_settings={ # Added basic safety settings
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                }
            )
            
            response_text = response.text.strip()
            logger.debug(f"Gemini TEXT response: {response_text[:300]}...")
            
            match = re.search(r"```json\n(.*?)\n```", response_text, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                # If no markdown block, try to find JSON directly.
                # Look for the first '{' and last '}' or first '[' and last ']'
                first_brace = response_text.find('{')
                first_bracket = response_text.find('[')

                if first_brace == -1 and first_bracket == -1: # No JSON object or array start found
                    logger.error(f"No JSON object/array found in Gemini response: {response_text}")
                    raise json.JSONDecodeError("No JSON object/array found", response_text, 0)

                if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
                    # JSON object seems to be first
                    last_brace = response_text.rfind('}')
                    if last_brace != -1:
                        json_str = response_text[first_brace : last_brace+1]
                    else: # No closing brace for object
                        raise json.JSONDecodeError("Mismatched braces for JSON object", response_text, 0)
                elif first_bracket != -1:
                     # JSON array seems to be first or only
                    last_bracket = response_text.rfind(']')
                    if last_bracket != -1:
                        json_str = response_text[first_bracket : last_bracket+1]
                    else: # No closing bracket for array
                        raise json.JSONDecodeError("Mismatched brackets for JSON array", response_text, 0)
                else: # Should not happen due to earlier check
                     raise json.JSONDecodeError("Could not determine JSON start in vision response", response_text, 0)
            
            parsed_json = json.loads(json_str)
            logger.info(f"Successfully parsed JSON from Gemini TEXT response.")
            return parsed_json
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from Gemini TEXT response: {e}. Response text: {response_text}")
            raise 
        except Exception as e:
            logger.error(f"Error calling Gemini TEXT model or processing response: {e}")
            raise

    async def _fetch_image_data(self, image_url: HttpUrl) -> Optional[bytes]:
        """
        Fetch image data from URL or local file path.
        Enhanced to handle both real S3 URLs and local file paths.
        """
        url_str = str(image_url)
        logger.info(f"📸 Fetching image data from: {url_str}")
        
        # Check if it's a local file path
        if url_str.startswith("file://"):
            # Extract the local path from file:// URL and URL decode it
            local_path = url_str.replace("file://", "")
            # URL decode the path to handle %20 and other encoded characters
            local_path = unquote(local_path)
            logger.info(f"📂 Decoded local path: {local_path}")
            
            try:
                path_obj = Path(local_path)
                if path_obj.exists() and path_obj.is_file():
                    logger.info(f"📁 Reading local screenshot: {local_path}")
                    with open(path_obj, 'rb') as f:
                        return f.read()
                else:
                    logger.warning(f"⚠️ Local screenshot not found: {local_path}")
                    return None
            except Exception as e:
                logger.error(f"❌ Error reading local screenshot {local_path}: {e}")
                return None
        
        # Check for mock/invalid URLs and skip them
        if any(mock_indicator in url_str.lower() for mock_indicator in 
               ["mock-restaurant-bucket", "example.com", "placeholder", "test-bucket", "fake-"]):
            logger.warning(f"⚠️ Skipping mock/invalid URL: {url_str}")
            return None
            
        # Handle real S3 or HTTP URLs
        if url_str.startswith(("http://", "https://")):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    logger.info(f"🌐 Fetching remote image: {url_str}")
                    response = await client.get(url_str)
                    response.raise_for_status()
                    
                    # Check content type
                    content_type = response.headers.get('content-type', '').lower()
                    if not content_type.startswith('image/'):
                        logger.warning(f"⚠️ URL returned non-image content: {content_type}")
                        return None
                    
                    image_data = response.content
                    logger.info(f"✅ Successfully fetched {len(image_data)} bytes from {url_str}")
                    return image_data
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"❌ HTTP error fetching image {url_str}: {e.response.status_code} - {e.response.text}")
                return None
            except httpx.RequestError as e:
                logger.error(f"❌ Request error fetching image {url_str}: {e}")
                return None
            except Exception as e:
                logger.error(f"❌ Unexpected error fetching image {url_str}: {e}")
                return None
        
        logger.error(f"❌ Unsupported URL format: {url_str}")
        return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
    async def analyze_screenshot_with_gemini(
        self, 
        image_s3_url: HttpUrl, 
        analysis_focus: str, # e.g., "menu_impression", "social_profile_check"
        additional_context: Optional[str] = None # Optional text context for the image
    ) -> Optional[Dict[str, Any]]:
        """
        Analyzes a screenshot using Gemini Vision based on the S3 URL and analysis focus.
        Returns a JSON summary.
        """
        if not self.enabled:
            logger.warning("Gemini disabled, skipping screenshot analysis.")
            return None

        logger.info(f"📸 Starting screenshot analysis for: {image_s3_url} (Focus: {analysis_focus})")

        image_bytes = await self._fetch_image_data(image_s3_url)
        if not image_bytes:
            return None # Error already logged by _fetch_image_data

        image_part = {
            "mime_type": "image/png", # Assuming PNG, could try to infer or require it
            "data": base64.b64encode(image_bytes).decode()
        }

        # Define prompts based on analysis_focus
        prompt_text = ""
        if analysis_focus == "menu_impression":
            prompt_text = f"""
            Analyze the provided restaurant menu screenshot.
            Focus on:
            1.  Overall visual impression and aesthetics (e.g., cluttered, clean, modern, dated).
            2.  Readability of text (font choices, size, contrast).
            3.  Any obvious design flaws or strengths.
            4.  Presence of key information like prices, item names, descriptions.
            {f"Additional context: {additional_context}" if additional_context else ""}
            Return a JSON object with keys: "visual_impression", "readability_assessment", "design_notes", "information_clarity", "overall_summary".
            """
        elif analysis_focus == "social_profile_check":
            prompt_text = f"""
            This screenshot is from a Google Search result, likely showing a social media profile (e.g., Instagram, Facebook, Yelp).
            Analyze the screenshot to:
            1.  Identify the social media platform if visible.
            2.  Extract the username/profile name.
            3.  Extract follower count if visible.
            4.  Extract a snippet of the bio or description if visible.
            5.  Note if the profile seems official or verified.
            {f"Additional context: {additional_context}" if additional_context else ""}
            Return a JSON object with keys: "platform_identified", "profile_name", "follower_count", "bio_snippet", "verification_status", "confidence_score" (0-1 on how confident you are about the extracted info).
            """
        else:
            logger.warning(f"Unknown analysis_focus for screenshot: {analysis_focus}. Using generic prompt.")
            prompt_text = f"""
            Analyze the provided image. 
            {f"Additional context: {additional_context}" if additional_context else ""}
            Describe its content and any notable features. Return a JSON object with a "summary" key.
            """
        
        try:
            logger.debug(f"Submitting VISION prompt to Gemini (Focus: {analysis_focus}):\n{prompt_text[:300]}...")
            response = await self.vision_model.generate_content_async(
                [prompt_text, image_part], # Multimodal content: text prompt + image
                generation_config=genai.types.GenerationConfig(
                    # response_mime_type="application/json", # Not always reliable for vision with all SDK versions/models
                    max_output_tokens=1024,
                    temperature=0.2 # Slightly higher temp for descriptive tasks if needed, but keep low for JSON
                ),
                 safety_settings={
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                }
            )
            response_text = response.text.strip()
            logger.debug(f"Gemini VISION response: {response_text[:300]}...")

            # JSON parsing logic similar to _call_gemini_text_json_mode
            match = re.search(r"```json\n(.*?)\n```", response_text, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                first_brace = response_text.find('{')
                first_bracket = response_text.find('[')
                if first_brace == -1 and first_bracket == -1:
                    logger.error(f"No JSON object/array found in Gemini VISION response: {response_text}")
                    return {"error": "No JSON found in vision response", "raw_output": response_text}
                if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
                    last_brace = response_text.rfind('}')
                    if last_brace != -1: json_str = response_text[first_brace : last_brace+1]
                    else: raise json.JSONDecodeError("Mismatched braces for JSON object in vision response", response_text, 0)
                elif first_bracket != -1:
                    last_bracket = response_text.rfind(']')
                    if last_bracket != -1: json_str = response_text[first_bracket : last_bracket+1]
                    else: raise json.JSONDecodeError("Mismatched brackets for JSON array in vision response", response_text, 0)
                else: raise json.JSONDecodeError("Could not determine JSON start in vision response", response_text, 0)

            parsed_json = json.loads(json_str)
            logger.info(f"✅ Successfully parsed JSON from Gemini VISION response for focus '{analysis_focus}'.")
            return parsed_json

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from Gemini VISION response (Focus: {analysis_focus}): {e}. Response text: {response_text}")
            return {"error": f"JSON decode error: {e}", "raw_output": response_text}
        except Exception as e:
            # Catching specific Google API errors if possible, e.g., response.prompt_feedback
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                 logger.error(f"Gemini VISION call blocked. Reason: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}")
                 return {"error": "Content blocked by API", "block_reason": str(response.prompt_feedback.block_reason)}

            logger.error(f"Error calling Gemini VISION model (Focus: {analysis_focus}): {e}")
            # Attempt to log parts of the exception that might be Google API specific errors
            if hasattr(e, 'message'): logger.error(f"  Error details: {e.message}")

            raise # Re-raise for tenacity to catch if it's a transient error

    async def _generate_target_restaurant_deep_dive(self, restaurant_data: FinalRestaurantOutput) -> Optional[Dict[str, Any]]:
        """Generate deep dive analysis for the target restaurant"""
        logger.info(f"🧠 Generating Target Restaurant Deep Dive for: {restaurant_data.restaurant_name}")
        
        # Extract delivery platform analysis
        delivery_platform_data = {}
        if hasattr(restaurant_data, 'misc_structured_data') and restaurant_data.misc_structured_data:
            delivery_platform_data = restaurant_data.misc_structured_data.get('delivery_platform_analysis', {})
            
        # Extract social media analysis
        social_media_data = {}
        if hasattr(restaurant_data, 'misc_structured_data') and restaurant_data.misc_structured_data:
            social_media_data = restaurant_data.misc_structured_data.get('social_media_analysis', {})
            
        # Extract Stagehand comprehensive analysis
        stagehand_data = {}
        if hasattr(restaurant_data, 'misc_structured_data') and restaurant_data.misc_structured_data:
            stagehand_data = restaurant_data.misc_structured_data.get('stagehand_comprehensive', {})
            
        # Extract technical health data
        technical_health = {}
        if hasattr(restaurant_data, 'misc_structured_data') and restaurant_data.misc_structured_data:
            technical_health = restaurant_data.misc_structured_data.get('technical_health', {})
        
        restaurant_context = {
            "basic_info": {
                "name": restaurant_data.restaurant_name,
                "description": restaurant_data.description_short or restaurant_data.description_long_ai_generated,
                "cuisine_type": restaurant_data.primary_cuisine_type_ai,
                "price_range": restaurant_data.price_range_ai,
                "website_url": str(restaurant_data.website_url),
                "menu_items_count": len(restaurant_data.menu_items) if restaurant_data.menu_items else 0,
                "actual_menu_items": [{"name": item.name, "price": item.price, "description": item.description} for item in restaurant_data.menu_items[:10]] if restaurant_data.menu_items else []
            },
            "google_presence": {
                "rating": restaurant_data.google_places_summary.get("rating") if restaurant_data.google_places_summary else None,
                "reviews_count": restaurant_data.google_places_summary.get("reviews_count") if restaurant_data.google_places_summary else None,
                "place_id": restaurant_data.google_places_summary.get("place_id") if restaurant_data.google_places_summary else None
            },
            "delivery_platform_analysis": delivery_platform_data,
            "social_media_analysis": social_media_data,
            "comprehensive_stagehand_data": stagehand_data,
            "technical_health": technical_health,
            "social_media_links": restaurant_data.social_media_links or {},
            "competitive_data": {
                "identified_competitors": [{"name": comp.name, "url": str(comp.url) if comp.url else None} for comp in restaurant_data.identified_competitors_basic] if restaurant_data.identified_competitors_basic else [],
                "delivery_platform_competitors": restaurant_data.misc_structured_data.get('identified_competitors_delivery', []) if restaurant_data.misc_structured_data else []
            }
        }
        
        prompt = f"""
        Analyze the provided comprehensive restaurant data and generate a strategic deep dive analysis.
        This data includes delivery platform presence, social media analysis, competitive intelligence, and technical insights.

        Comprehensive Restaurant Data:
        {json.dumps(restaurant_context, indent=2)}
        
        Generate a detailed strategic analysis incorporating ALL available data, focusing on:
        
        1. **Digital Presence Assessment**: Website, social media, delivery platforms
        2. **Competitive Market Position**: Based on delivery platform rankings and competitor analysis  
        3. **Operational Strengths**: Menu variety, pricing strategy, customer engagement
        4. **Growth Opportunities**: Gaps in delivery platforms, social media potential, technical improvements
        5. **Strategic Recommendations**: Data-driven insights for expansion and optimization
        
        Pay special attention to:
        - Delivery platform performance (DoorDash, Uber Eats, Grubhub rankings and product listings)
        - Social media engagement metrics and follower analysis
        - Competitive positioning on delivery platforms
        - Technical website health and optimization opportunities
        - Cross-platform consistency and brand presence
        
        Return a comprehensive JSON analysis:
        {{
            "digital_presence_score": {{
                "overall_score": "1-10 rating",
                "website_quality": "assessment of technical health and user experience",
                "social_media_strength": "analysis of social media presence and engagement",
                "delivery_platform_presence": "assessment of delivery platform coverage and performance"
            }},
            "competitive_positioning": {{
                "market_position": "strong/moderate/weak with justification",
                "delivery_platform_rankings": "summary of rankings across platforms",
                "unique_differentiators": ["diff1", "diff2", "diff3"],
                "competitive_gaps": ["gap1", "gap2", "gap3"]
            }},
            "key_strengths": ["strength1", "strength2", "strength3"],
            "critical_weaknesses": ["weakness1", "weakness2", "weakness3"],
            "growth_opportunities": {{
                "high_impact": ["opportunity1", "opportunity2"],
                "quick_wins": ["quick1", "quick2"],
                "long_term": ["longterm1", "longterm2"]
            }},
            "strategic_priorities": {{
                "immediate_actions": ["action1", "action2"],
                "6_month_goals": ["goal1", "goal2"],
                "12_month_vision": "long-term strategic direction"
            }},
            "data_insights": {{
                "delivery_platform_summary": "key insights from platform analysis",
                "social_media_summary": "key insights from social analysis", 
                "technical_summary": "key insights from technical health analysis",
                "competitive_summary": "key insights from competitor analysis"
            }},
            "overall_assessment": "comprehensive strategic summary incorporating all data sources"
        }}
        """
        
        return await self._call_gemini_text_json_mode(prompt, max_tokens=2048)

    async def _generate_competitor_snapshot(self, competitor_data: CompetitorSummary, target_restaurant_name: str) -> Optional[Dict[str, Any]]:
        """Prompt 2.2: Analyze each competitor in FinalRestaurantOutput.competitors."""
        logger.info(f"🧠 Generating Competitor Snapshot for: {competitor_data.name} (vs {target_restaurant_name})")
        
        prompt_data = competitor_data.dict() # Pydantic model to dict

        prompt = f"""
        Analyze the provided data for "{competitor_data.name}", a competitor to "{target_restaurant_name}".
        Based *only* on this information, identify its apparent key strengths and key weaknesses relative to a typical restaurant or from the perspective of a customer choosing between options.

        Competitor Data:
        {json.dumps(prompt_data, indent=2)}

        Return a JSON object with the following keys:
        - "competitor_name": "{competitor_data.name}"
        - "key_strengths": [list of strings]
        - "key_weaknesses": [list of strings]
        """
        analysis_result = await self._call_gemini_text_json_mode(prompt, max_tokens=512)
        if analysis_result and "key_strengths" in analysis_result and "key_weaknesses" in analysis_result:
            # Update the Pydantic model passed by reference (if it is) or return for caller to update
            # For safety, let's assume the caller will handle updating the original competitor_data model
            # The returned dict here will be used by the caller.
            return {
                "competitor_name": competitor_data.name, # ensure name is part of the returned dict
                "key_strengths": analysis_result["key_strengths"],
                "key_weaknesses": analysis_result["key_weaknesses"],
            }
        logger.warning(f"Could not fully analyze competitor {competitor_data.name}. Result: {analysis_result}")
        return None


    async def _generate_main_strategic_recommendations(
        self, 
        target_analysis: Dict[str, Any], 
        competitor_analyses: List[Dict[str, Any]], 
        restaurant_data: FinalRestaurantOutput, 
        screenshot_analysis_results: Dict[HttpUrl, Dict[str, Any]] # Changed key from str to HttpUrl
    ) -> Optional[LLMStrategicAnalysisOutput]:
        """Generate strategic recommendations based on all analysis"""
        logger.info(f"🧠 Generating Main Strategic Recommendations for: {restaurant_data.restaurant_name}")
        
        # Extract all the rich data sources
        delivery_platform_data = {}
        social_media_data = {}
        stagehand_data = {}
        technical_health = {}
        delivery_competitors = []
        
        if hasattr(restaurant_data, 'misc_structured_data') and restaurant_data.misc_structured_data:
            delivery_platform_data = restaurant_data.misc_structured_data.get('delivery_platform_analysis', {})
            social_media_data = restaurant_data.misc_structured_data.get('social_media_analysis', {})
            stagehand_data = restaurant_data.misc_structured_data.get('stagehand_comprehensive', {})
            technical_health = restaurant_data.misc_structured_data.get('technical_health', {})
            delivery_competitors = restaurant_data.misc_structured_data.get('identified_competitors_delivery', [])
        
        # Prepare comprehensive data for analysis
        analysis_context = {
            "target_restaurant": {
                "name": restaurant_data.restaurant_name,
                "description": restaurant_data.description_short or restaurant_data.description_long_ai_generated,
                "cuisine_type": restaurant_data.primary_cuisine_type_ai,
                "price_range": restaurant_data.price_range_ai,
                "website_url": str(restaurant_data.website_url),
                "google_rating": restaurant_data.google_places_summary.get("rating") if restaurant_data.google_places_summary else None,
                "google_review_count": restaurant_data.google_places_summary.get("reviews_count") if restaurant_data.google_places_summary else None,
                "menu_items": [{"name": item.name, "price": item.price, "description": item.description} for item in restaurant_data.menu_items[:15]] if restaurant_data.menu_items else [],
                "social_media_links": restaurant_data.social_media_links or {},
                "deep_dive_analysis": target_analysis
            },
            "delivery_platform_intelligence": {
                "platforms_analyzed": delivery_platform_data,
                "competitive_rankings": delivery_competitors,
                "market_presence_summary": "Based on DoorDash, Uber Eats, Grubhub analysis"
            },
            "social_media_intelligence": {
                "platform_analysis": social_media_data,
                "engagement_metrics": "Extracted from social media analysis",
                "competitive_social_positioning": "Based on follower counts and engagement"
            },
            "technical_intelligence": {
                "website_health": technical_health,
                "performance_metrics": technical_health.get('performance', {}),
                "seo_optimization": technical_health.get('seoOptimized', False),
                "mobile_responsiveness": technical_health.get('mobileResponsive', False)
            },
            "comprehensive_competitor_data": {
                "local_competitors": competitor_analyses,
                "delivery_platform_competitors": delivery_competitors,
                "total_competitors_analyzed": len(competitor_analyses) + len(delivery_competitors)
            },
            "screenshot_insights": screenshot_analysis_results,
            "data_completeness": {
                "has_menu": bool(restaurant_data.menu_items and len(restaurant_data.menu_items) > 0),
                "has_social_media": bool(restaurant_data.social_media_links),
                "has_google_presence": bool(restaurant_data.google_places_summary),
                "has_delivery_platform_data": bool(delivery_platform_data),
                "has_technical_analysis": bool(technical_health),
                "has_screenshots": bool(restaurant_data.website_screenshots_s3_urls)
            }
        }

        prompt = f"""
        Generate strategic recommendations for {restaurant_data.restaurant_name} based on comprehensive multi-source analysis.
        
        You have access to rich data including:
        - Delivery platform performance (DoorDash, Uber Eats, Grubhub rankings, product listings, competitor analysis)
        - Social media analysis (follower counts, engagement metrics, competitive positioning)
        - Technical website health (performance, SEO, mobile responsiveness)
        - Local and delivery platform competitor intelligence
        - Screenshot analysis and visual brand assessment
        
        Comprehensive Analysis Data:
        {json.dumps(analysis_context, indent=2)}
        
        Create data-driven strategic recommendations that leverage ALL available intelligence sources.
        Focus on actionable opportunities with clear revenue impact estimates.
        
        Generate recommendations in this format:
        
        {{
            "executive_hook": {{
                "growth_potential_statement": "Compelling growth statement based on delivery platform gaps, social media opportunities, and competitive analysis",
                "timeframe": "3-12 months based on data insights",
                "key_metrics": ["delivery platform market share", "social media engagement rate", "website conversion rate"],
                "urgency_factor": "Data-driven reason why they should act now (e.g., competitor gaps, seasonal opportunities)"
            }},
            "competitive_positioning": {{
                "market_position_summary": "Position based on delivery platform rankings and local competitor analysis",
                "key_differentiators": ["unique strengths found in analysis"],
                "competitive_gaps": ["specific gaps identified from delivery platform and social media analysis"],
                "market_opportunity": "Specific opportunity based on competitor weaknesses and platform gaps"
            }},
            "top_3_opportunities": [
                {{
                    "priority_rank": 1,
                    "opportunity_title": "Delivery Platform Optimization" (or other data-driven opportunity),
                    "problem_statement": "Specific problem identified from delivery platform analysis",
                    "recommendation": "Specific action based on platform ranking data and competitor gaps",
                    "revenue_impact_estimate": "X% increase based on delivery platform market expansion",
                    "ai_solution_angle": "How AI can optimize delivery platform presence, social media, or technical performance",
                    "implementation_timeline": "Timeline based on technical complexity and competitive urgency",
                    "difficulty_level": "Assessment based on technical requirements and competitive landscape", 
                    "success_metrics": ["platform-specific KPIs", "social media engagement rates", "website performance metrics"],
                    "data_supporting_evidence": "Specific data points from analysis that support this recommendation"
                }},
                {{
                    "priority_rank": 2,
                    "opportunity_title": "Social Media Competitive Advantage",
                    "problem_statement": "Gap identified from social media analysis",
                    "recommendation": "Strategy based on competitor social media weaknesses",
                    "revenue_impact_estimate": "Impact based on social media engagement correlation",
                    "ai_solution_angle": "AI-powered social media optimization and content strategy",
                    "implementation_timeline": "Based on platform-specific requirements",
                    "difficulty_level": "Assessment based on current social media presence",
                    "success_metrics": ["follower growth", "engagement rate", "conversion tracking"],
                    "data_supporting_evidence": "Social media analysis findings"
                }},
                {{
                    "priority_rank": 3,
                    "opportunity_title": "Technical Performance Optimization",
                    "problem_statement": "Issue identified from technical health analysis",
                    "recommendation": "Specific technical improvements based on performance data",
                    "revenue_impact_estimate": "Revenue impact from improved conversion rates",
                    "ai_solution_angle": "AI-powered website optimization and user experience enhancement",
                    "implementation_timeline": "Development timeline based on technical complexity",
                    "difficulty_level": "Assessment based on current technical infrastructure",
                    "success_metrics": ["page load speed", "mobile responsiveness score", "conversion rate"],
                    "data_supporting_evidence": "Technical health analysis findings"
                }}
            ],
            "cross_platform_strategy": {{
                "delivery_platform_recommendations": "Specific actions for DoorDash, Uber Eats, Grubhub based on analysis",
                "social_media_strategy": "Platform-specific recommendations based on competitor analysis",
                "website_optimization_priority": "Technical improvements based on performance analysis",
                "brand_consistency_actions": "Recommendations for unified presence across all platforms"
            }},
            "analysis_metadata": {{
                "generated_at": "{datetime.now().isoformat()}",
                "analysis_duration_seconds": 0,
                "estimated_cost_usd": 0.08,
                "screenshots_analyzed": {len(screenshot_analysis_results)},
                "competitors_analyzed": {len(competitor_analyses) + len(delivery_competitors)},
                "data_sources_used": ["delivery_platforms", "social_media", "technical_health", "competitor_intelligence", "screenshot_analysis"],
                "delivery_platforms_analyzed": {list(delivery_platform_data.keys()) if delivery_platform_data else []},
                "social_platforms_analyzed": {list(social_media_data.keys()) if social_media_data else []}
            }}
        }}
        """
        
        strategic_analysis_dict = await self._call_gemini_text_json_mode(prompt, max_tokens=3072)
        
        if strategic_analysis_dict:
            try:
                return LLMStrategicAnalysisOutput(**strategic_analysis_dict)
            except Exception as e: 
                logger.error(f"Failed to create LLMStrategicAnalysisOutput: {e}")
                return None 
        
        return None

    async def generate_strategic_report_content(
        self, 
        final_restaurant_data: FinalRestaurantOutput, 
        # screenshot_analysis_results: Dict[HttpUrl, Dict[str, Any]] # Keyed by S3 URL (HttpUrl)
        # This now will be populated by calling analyze_screenshot_with_gemini internally if screenshots exist
    ) -> Optional[LLMStrategicAnalysisOutput]:
        """
        Phase B: LLM Strategic Analysis
        Main orchestration method for generating strategic analysis
        """
        if not self.enabled:
            logger.warning("🤖 LLM Analyzer is disabled (no API key)")
            return None

        logger.info(f"📝 Starting strategic report content generation for {final_restaurant_data.restaurant_name}")
        start_time = datetime.now()
        
        try:
            # Phase B1: Screenshot Analysis (if available)
            screenshot_analyses: Dict[HttpUrl, Dict[str, Any]] = {}
            screenshots_analyzed = 0
            
            if final_restaurant_data.website_screenshots_s3_urls:
                logger.info(f"📸 Analyzing {len(final_restaurant_data.website_screenshots_s3_urls)} screenshots...")
                
                for screenshot_info in final_restaurant_data.website_screenshots_s3_urls:
                    try:
                        # Determine analysis focus based on caption/metadata
                        analysis_focus = "homepage_impression"  # Default
                        if screenshot_info.caption:
                            if "menu" in screenshot_info.caption.lower():
                                analysis_focus = "menu_impression"
                            elif "contact" in screenshot_info.caption.lower():
                                analysis_focus = "contact_page_analysis"
                        
                        context_for_vision = f"This is for the restaurant: {final_restaurant_data.restaurant_name}."
                        
                        screenshot_analysis = await self.analyze_screenshot_with_gemini(
                            screenshot_info.s3_url,
                            analysis_focus,
                            context_for_vision
                        )
                        
                        if screenshot_analysis:
                            screenshot_analyses[screenshot_info.s3_url] = screenshot_analysis
                            screenshots_analyzed += 1
                            logger.info(f"✅ Analyzed screenshot: {screenshot_info.s3_url}")
                        else:
                            logger.warning(f"⚠️ Failed to analyze screenshot: {screenshot_info.s3_url}")
                            
                    except Exception as e_screenshot:
                        logger.error(f"❌ Error analyzing screenshot {screenshot_info.s3_url}: {str(e_screenshot)}")
                        continue
            
            # Phase B2: Target Restaurant Deep Dive
            logger.info("🧠 Generating target restaurant deep dive...")
            target_deep_dive = await self._generate_target_restaurant_deep_dive(final_restaurant_data)
            
            if not target_deep_dive:
                logger.warning("⚠️ Target restaurant deep dive failed")
                target_deep_dive = {"analysis": "Basic analysis could not be generated"}
            
            # Phase B3: Competitor Analysis
            competitor_snapshots = []
            competitors_analyzed = 0
            
            if final_restaurant_data.identified_competitors_basic:
                logger.info(f"🏢 Analyzing {len(final_restaurant_data.identified_competitors_basic)} competitors...")
                
                for competitor in final_restaurant_data.identified_competitors_basic:
                    try:
                        competitor_analysis = await self._generate_competitor_snapshot(competitor, final_restaurant_data.restaurant_name)
                        
                        if competitor_analysis:
                            competitor_snapshots.append(competitor_analysis)
                            competitors_analyzed += 1
                            logger.info(f"✅ Analyzed competitor: {competitor.name}")
                        else:
                            logger.warning(f"⚠️ Failed to analyze competitor: {competitor.name}")
                            
                    except Exception as e_competitor:
                        logger.error(f"❌ Error analyzing competitor {competitor.name}: {str(e_competitor)}")
                        continue
            
            # Phase B4: Generate Main Strategic Recommendations
            logger.info("🎯 Generating main strategic recommendations...")
            llm_strategic_output = await self._generate_main_strategic_recommendations(
                target_analysis=target_deep_dive,
                competitor_analyses=competitor_snapshots,
                restaurant_data=final_restaurant_data,
                screenshot_analysis_results=screenshot_analyses
            )
            
            if not llm_strategic_output:
                logger.warning("⚠️ Main strategic recommendations failed to generate")
                return None
            
            logger.info("✅ Main strategic recommendations generated successfully")
            return llm_strategic_output
        
        except Exception as e:
            logger.error(f"❌ Exception in strategic report content generation: {str(e)}")
            return None

    async def generate_main_strategic_recommendations(
        self, 
        target_deep_dive: Dict[str, Any],
        competitor_snapshots: List[Dict[str, Any]], 
        screenshot_analyses: Dict[str, Any],
        target_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        LLMA-6: Main Comparative & Strategic Recommendation Engine (THE GRAND SUMMARY)
        
        This is the ultimate synthesis prompt that creates the final strategic report
        combining all previous analyses into actionable business intelligence.
        """
        logger.info("🎯 Generating main strategic recommendations (LLMA-6: Grand Summary)")
        
        # LLMA-6: The "Holy Grail" - Main Comparative & Strategic Recommendation Engine
        LLMA_6_MAIN_STRATEGIC_PROMPT_TEMPLATE = """You are an exceptionally insightful, empathetic, and data-driven Restaurant Growth Strategist, a true "McKinsey for Main Street Restaurants."
Your primary objective is to analyze the comprehensive multi-source data provided for {target_restaurant_name_placeholder} and craft a compelling, actionable, 5-7 page strategic report.
This report must empower the owner to understand their current standing, identify clear growth paths, and feel motivated to take decisive action.
Your analysis should make the owner feel clearly understood, see achievable paths to improvement, and be compelled by the opportunities.
The tone must be professional, supportive, factual, solutions-oriented, and empathetic. Avoid harsh criticism; frame all challenges as clear, addressable opportunities.

**COMPREHENSIVE MULTI-SOURCE DATA PROVIDED TO YOU:**

**🚚 DELIVERY PLATFORM INTELLIGENCE (New Enhanced Data):**
You now have access to comprehensive delivery platform analysis including:
- DoorDash, Uber Eats, and Grubhub presence and rankings
- Product listings and menu optimization on delivery platforms  
- Delivery platform competitor analysis with specific rankings
- Cross-platform performance metrics and opportunities
- Revenue potential from improved delivery platform presence

**📱 SOCIAL MEDIA COMPETITIVE INTELLIGENCE (New Enhanced Data):**
You now have access to detailed social media analysis including:
- Platform-specific follower counts and engagement metrics
- Competitive social media positioning analysis
- Content strategy gaps and opportunities
- Cross-platform brand consistency assessment
- Social media-driven customer acquisition potential

**🏢 COMPETITIVE DELIVERY PLATFORM DATA (New Enhanced Data):**
You now have access to competitor performance on delivery platforms:
- Specific competitor rankings on DoorDash, Uber Eats, Grubhub
- Competitor product offerings and pricing strategies on delivery platforms
- Market share analysis across delivery platforms
- Competitive gaps and opportunities in delivery space

**⚙️ TECHNICAL WEBSITE HEALTH ANALYSIS (New Enhanced Data):**
You now have access to comprehensive technical analysis including:
- Website performance metrics and optimization opportunities  
- SEO health and local search optimization status
- Mobile responsiveness and user experience assessment
- Technical barriers to customer conversion

**📊 COMPREHENSIVE STAGEHAND INTELLIGENCE (New Enhanced Data):**
You now have access to advanced competitive intelligence including:
- Deep competitor analysis across multiple platforms
- Market positioning insights from comprehensive data scraping
- Business intelligence gathered from advanced web analysis
- Strategic opportunities identified through data synthesis

1. **Target Restaurant Deep Dive Analysis (Enhanced with All Data Sources):**
   {target_deep_dive_json_placeholder}

2. **Competitor Snapshot Analyses (Enhanced with Multi-Platform Data):**
   {competitor_snapshots_json_array_placeholder}

3. **Screenshot Interpretation Summaries (Visual Evidence):**
   {screenshot_interpretation_summaries_json_placeholder}

4. **Industry Benchmarks and Facts (Enhanced with Platform-Specific Data):**
   • Restaurants with optimized delivery platform presence see 25-40% increase in off-premise revenue
   • Restaurants ranking in top 3 on DoorDash/Uber Eats for their category see 2-3x more orders
   • Consistent cross-platform branding increases customer recognition by 35-50%
   • Restaurants with active social media (1000+ engaged followers) see 15-30% higher customer retention
   • Technical website optimizations can improve conversion rates by 20-45%
   • Restaurants responding to delivery platform reviews within 24 hours see 15% higher ratings
   • Optimized delivery platform menu photos increase item selection by 20-30%
   • Restaurants with consistent hours/contact info across all platforms see 25% more direct bookings
   • Social media-driven promotions can increase foot traffic by 10-25% during slow periods
   • Delivery platform exclusive items can increase average order value by 15-20%
   • Mobile-optimized websites convert 40% better than non-optimized sites
   • Local SEO optimization can increase Google Maps visibility by 60-80%

5. **Key Target Restaurant Data Points (Multi-Platform Enhanced):**
   {key_target_restaurant_data_points_placeholder}

**YOUR ENHANCED TASK: Generate Content for a 5-7 Page Strategic Report Leveraging ALL Data Sources**

Based on ALL the comprehensive multi-source data provided (delivery platforms, social media intelligence, competitive delivery data, technical analysis, and Stagehand intelligence), generate the content for the report. 

**CRITICAL: You must specifically reference and leverage the delivery platform analysis, social media competitive intelligence, delivery platform competitor data, technical health insights, and comprehensive Stagehand data in your recommendations. These are not optional - they are core data sources that must drive your strategic insights.**

Pay special attention to:
- **Cross-Platform Revenue Opportunities**: Identify gaps in delivery platform presence that competitors are exploiting
- **Social Media Competitive Advantages**: Leverage social media analysis to identify engagement and follower opportunities  
- **Technical Conversion Optimization**: Use technical health data to identify website improvements that drive revenue
- **Delivery Platform Market Share**: Use competitor delivery platform rankings to identify market capture opportunities
- **Integrated Marketing Strategy**: Create recommendations that leverage all platforms synergistically

Adhere strictly to the JSON output format defined below. Each section requires thorough elaboration to ensure substantial content.

Return ONLY a valid JSON object with this exact structure:

{{
  "executive_hook": {{
    "hook_statement": "Craft a compelling 2-3 sentence opening for the report. Start by identifying the single largest quantifiable gap between [This Restaurant] and its best-performing competitor based on delivery platform rankings, social media engagement, or technical performance. Calculate the potential daily revenue impact or opportunity cost with your reasoning. Then state an overall potential revenue increase percentage (e.g., '25-45%') achievable in 60-90 days by addressing the top cross-platform opportunities. Mention the number of key opportunities found across all data sources. Make it feel urgent but solvable.",
    "biggest_opportunity_teaser": "A one-sentence teaser of the single most impactful cross-platform opportunity that will be detailed later in the report. This should create curiosity and reference specific data findings."
  }},
  "competitive_landscape_summary": {{
    "introduction": "Start with a brief (1-2 sentence) confidence-building statement acknowledging any clear strengths or positive aspects of [This Restaurant] found in the multi-source analysis before discussing competitive aspects.",
    "detailed_comparison_text": "Provide a detailed narrative (target 400-600 words). Compare [This Restaurant] to its top 2-3 anonymous local competitors across delivery platform presence (DoorDash/Uber Eats/Grubhub rankings), social media engagement metrics, website technical performance, Google Review presence, and unique market positioning. Use specific data from the delivery platform analysis, social media intelligence, and technical health assessment. Conclude by identifying 1-2 primary areas where [This Restaurant] is being clearly outperformed OR has a significant unexploited advantage based on the comprehensive data analysis.",
    "key_takeaway_for_owner": "A 1-2 sentence summary of the most critical competitive insight the owner needs to grasp from this cross-platform analysis, emphasizing an actionable perspective with specific data support."
  }},
  "top_3_prioritized_opportunities": [
    {{
      "priority_rank": 1,
      "opportunity_title": "Specific, actionable title using strong verbs that references the data source (e.g., 'Capture 40% More Orders Through DoorDash Optimization Based on Competitor Gap Analysis' or 'Launch Social Media Engagement Strategy to Match Top Competitor's 300% Higher Follower Count').",
      "current_situation_and_problem": "Detailed explanation (target 200-300 words) of the current situation at [This Restaurant] related to this opportunity. Clearly explain the problem or gap using specific data from delivery platform analysis, social media intelligence, technical health assessment, or competitive analysis. Reference competitor performance metrics and quantify the problem using the enhanced data sources.",
      "detailed_recommendation": "Outline clear, step-by-step actions (target 250-350 words) [This Restaurant] can take to seize this opportunity. Be practical, specific, and break it down into manageable phases. Reference how competitors are succeeding in this area and how to replicate/exceed their performance using the data insights.",
      "estimated_revenue_or_profit_impact": "Provide a quantifiable impact estimate using the enhanced data sources. Reference specific delivery platform market share data, social media engagement correlation with revenue, technical conversion improvements, or competitive performance gaps. Show your reasoning using the comprehensive data available.",
      "ai_solution_pitch": "Explain (target 100-200 words) how technology automation could significantly reduce the time, complexity, or cost of implementing this recommendation. Reference specific data insights that AI can leverage (delivery platform optimization algorithms, social media automation based on competitor analysis, technical performance monitoring). Mention which AI platform tools can specifically address the data-driven insights.",
      "implementation_timeline": "Select one: '2-4 Weeks', '1-2 Months', '3-6 Months'",
      "difficulty_level": "Select one: 'Easy (Quick Wins)', 'Medium (Requires Focused Effort)', 'Hard (Strategic Shift, High Reward)'",
      "data_sources_supporting_evidence": "List the specific data sources that support this recommendation (e.g., 'delivery_platform_analysis', 'social_media_intelligence', 'technical_health_assessment', 'competitor_delivery_rankings')",
      "visual_evidence_suggestion": {{
          "idea_for_visual": "Describe a type of visual that would effectively illustrate this opportunity or problem using the data sources.",
          "relevant_screenshot_s3_url_from_input": "If a specific screenshot S3 URL from the input is highly relevant, state it here, otherwise null."
      }}
    }},
    {{
      "priority_rank": 2,
      "opportunity_title": "Second opportunity title incorporating data source insights",
      "current_situation_and_problem": "Detailed explanation for opportunity 2 using enhanced data sources...",
      "detailed_recommendation": "Step-by-step actions for opportunity 2 based on comprehensive analysis...",
      "estimated_revenue_or_profit_impact": "Quantifiable impact estimate for opportunity 2 using specific data metrics...",
      "ai_solution_pitch": "AI technology solution for opportunity 2 leveraging data insights...",
      "implementation_timeline": "Timeline for opportunity 2",
      "difficulty_level": "Difficulty level for opportunity 2",
      "data_sources_supporting_evidence": "Specific data sources supporting opportunity 2",
      "visual_evidence_suggestion": {{
          "idea_for_visual": "Visual concept for opportunity 2...",
          "relevant_screenshot_s3_url_from_input": "S3 URL or null"
      }}
    }},
    {{
      "priority_rank": 3,
      "opportunity_title": "Third opportunity title with data-driven insights",
      "current_situation_and_problem": "Detailed explanation for opportunity 3 using multi-source data...",
      "detailed_recommendation": "Step-by-step actions for opportunity 3 based on comprehensive intelligence...",
      "estimated_revenue_or_profit_impact": "Quantifiable impact estimate for opportunity 3 with data support...",
      "ai_solution_pitch": "AI technology solution for opportunity 3 incorporating data analysis...",
      "implementation_timeline": "Timeline for opportunity 3",
      "difficulty_level": "Difficulty level for opportunity 3", 
      "data_sources_supporting_evidence": "Specific data sources supporting opportunity 3",
      "visual_evidence_suggestion": {{
          "idea_for_visual": "Visual concept for opportunity 3...",
          "relevant_screenshot_s3_url_from_input": "S3 URL or null"
      }}
    }}
  ],
  "cross_platform_integration_strategy": {{
    "delivery_platform_optimization": "Specific recommendations based on delivery platform analysis and competitor rankings",
    "social_media_competitive_strategy": "Strategy based on social media intelligence and engagement gap analysis", 
    "technical_performance_enhancement": "Recommendations based on technical health assessment and conversion optimization",
    "unified_brand_presence": "Cross-platform consistency recommendations based on comprehensive analysis",
    "revenue_synergy_opportunities": "How optimizing across all platforms creates multiplicative revenue effects"
  }},
  "premium_analysis_teasers": [
    {{
      "premium_feature_title": "Select from: Advanced Delivery Platform Revenue Optimization Engine, AI-Powered Social Media Competitive Intelligence Dashboard, Cross-Platform Customer Journey Optimization Blueprint, Dynamic Pricing Strategy Based on Delivery Platform Analytics, Automated Review Response & Reputation Management Across All Platforms, Technical Performance Monitoring & Conversion Rate Optimization, Comprehensive Competitor Intelligence & Market Share Analysis",
      "compelling_teaser_hook": "Tailor this hook to [This Restaurant]'s specific competitive situation using the enhanced data sources. Identify a question or curiosity the main analysis likely raised that this premium feature directly answers using the comprehensive data available.",
      "value_proposition": "What specific, high-value outcome, data, or actionable strategy will this premium analysis deliver that leverages the enhanced data sources and provides deeper insights than this current freemium report?"
    }},
    {{
      "premium_feature_title": "Second premium feature based on data insights...",
      "compelling_teaser_hook": "Hook for second premium feature using enhanced data...",
      "value_proposition": "Value proposition for second premium feature incorporating comprehensive analysis..."
    }},
    {{
      "premium_feature_title": "Third premium feature leveraging multi-source data...",
      "compelling_teaser_hook": "Hook for third premium feature with data-driven insights...",
      "value_proposition": "Value proposition for third premium feature based on comprehensive intelligence..."
    }}
  ],
  "immediate_action_items_quick_wins": [
    {{
      "action_item": "Specific, easy action requiring no budget, completable in under 2 hours, addressing a fixable issue identified in the enhanced data analysis. Include exact location/platform where change needs to be made and reference the specific data insight that supports this action.",
      "rationale_and_benefit": "Why it's important and the quick, tangible benefit based on data findings and competitive analysis."
    }},
    {{
      "action_item": "Second quick win action item based on data insights...",
      "rationale_and_benefit": "Rationale for second action item using enhanced data analysis..."
    }},
    {{
      "action_item": "Third quick win action item incorporating multi-source findings...",
      "rationale_and_benefit": "Rationale for third action item with comprehensive data support..."
    }}
  ],
  "engagement_and_consultation_questions": [
    "Question 1: Tailored to their specific situation and top weaknesses/opportunities identified in the enhanced data analysis",
    "Question 2: Related to another key opportunity or pain point discovered through comprehensive multi-source analysis", 
    "Question 3: More general about their current systems or biggest goals, incorporating insights from delivery platform, social media, and technical analysis"
  ],
  "forward_thinking_strategic_insights": {{
    "introduction": "A brief (1-2 sentence) transition: 'Beyond these immediate opportunities identified through our comprehensive analysis, successful restaurants continuously adapt across all platforms. Here are a few forward-thinking considerations for [This Restaurant] based on the enhanced data intelligence:'",
    "untapped_potential_and_innovation_ideas": [
        {{
            "idea_title": "Innovative Idea 1 Title based on data insights (e.g., 'Launch Cross-Platform Loyalty Program Leveraging Social Media Engagement Data')", 
            "description_and_rationale": "Detailed explanation (200-300 words) of the concept, why it's relevant and uniquely suited for [This Restaurant] given their profile revealed in the enhanced data analysis, competitive gaps identified in delivery platform and social media intelligence, and potential first steps for exploration using the comprehensive data insights."
        }},
        {{
            "idea_title": "Innovative Idea 2 Title incorporating multi-source analysis (e.g., 'Develop AI-Powered Menu Optimization Based on Delivery Platform Performance Data')", 
            "description_and_rationale": "Detailed explanation (200-300 words) of second innovative concept leveraging enhanced data sources..."
        }}
    ],
    "long_term_vision_alignment_thoughts": [
        {{
            "strategic_thought_title": "Long-Term Consideration 1 Title using comprehensive analysis (e.g., 'Building a Data-Driven Multi-Platform Restaurant Ecosystem')", 
            "elaboration": "Detailed discussion (200-300 words) on a broader strategic consideration for sustained growth over 1-3 years, incorporating insights from all enhanced data sources and competitive intelligence."
        }}
    ],
    "consultants_core_empowerment_message": "Craft an impactful concluding paragraph (target 100-150 words) that motivates the owner of [This Restaurant] to take action on the identified opportunities. Reference the comprehensive data analysis that supports the recommendations, emphasize that growth is achievable with focused effort across all platforms, and subtly reinforce the value of ongoing partnership or premium tools that can leverage the enhanced data intelligence for continuous optimization."
  }},
  "data_synthesis_summary": {{
    "total_data_sources_analyzed": "Number and list of all data sources used in this analysis",
    "key_platforms_analyzed": "List of platforms analyzed (delivery platforms, social media platforms, technical systems, etc.)",
    "competitive_intelligence_depth": "Summary of the depth and breadth of competitive analysis performed",
    "data_confidence_score": "Assessment of data quality and confidence level (High/Medium/Low) with brief explanation"
  }}
}}

**Instructions for Enhanced Content Generation:**
- **MANDATORY**: Reference and leverage ALL enhanced data sources in your analysis
- **MANDATORY**: Use specific metrics and findings from delivery platform analysis, social media intelligence, technical health assessment, and competitive data
- Adhere STRICTLY to the JSON output structure above
- Provide detailed, elaborate content for each narrative section as indicated by word count targets
- Ground all analysis, comparisons, and recommendations in the comprehensive multi-source data provided
- When referencing competitors, use specific performance metrics from the enhanced data analysis
- Maintain a professional, supportive, empathetic, and highly expert tone throughout
- Ensure all recommendations are actionable and supported by specific data insights
- The "AI Solution Pitch" for each opportunity must clearly link to how AI can leverage the enhanced data sources
- Make the "Premium Teasers" genuinely enticing by connecting them to specific data insights and competitive gaps identified
- The "Forward-Thinking Strategic Insights" should offer genuine consultant-level advice that builds upon the comprehensive data analysis
- **Critical**: More information, well-reasoned opinions using the enhanced data, and detailed explanations are better than brief or superficial statements. Depth and breadth leveraging all data sources are highly valued for making this a world-class output.
"""

        # Extract restaurant name for placeholder
        target_restaurant_name_placeholder = target_summary.get('name', '[This Restaurant]')
        
        # Prepare JSON string inputs for the prompt
        target_deep_dive_json_str = json.dumps(target_deep_dive, indent=2)
        competitor_snapshots_json_array_str = json.dumps(competitor_snapshots, indent=2)
        
        # Prepare screenshot summaries
        screenshot_summaries_json_str = "{}"
        if screenshot_analyses:
            screenshot_summaries_json_str = json.dumps(screenshot_analyses, indent=2)
        
        # Prepare key target restaurant data
        key_target_data = {
            "name": target_summary.get('name', 'Unknown Restaurant'),
            "url": target_summary.get('website', 'Not available'),
            "menu_item_count": len(target_summary.get('menu_items', [])),
            "google_rating": target_summary.get('google_rating', 'Not available'),
            "google_review_count": target_summary.get('total_reviews', 'Not available'),
            "primary_cuisine_types": target_summary.get('cuisine_types', ['Not specified']),
            "screenshots_available_count": len(screenshot_analyses) if screenshot_analyses else 0
        }
        key_target_restaurant_data_points_json_str = json.dumps(key_target_data, indent=2)
        
        # Populate the main prompt template
        prompt = LLMA_6_MAIN_STRATEGIC_PROMPT_TEMPLATE.format(
            target_restaurant_name_placeholder=target_restaurant_name_placeholder,
            target_deep_dive_json_placeholder=target_deep_dive_json_str,
            competitor_snapshots_json_array_placeholder=competitor_snapshots_json_array_str,
            screenshot_interpretation_summaries_json_placeholder=screenshot_summaries_json_str,
            key_target_restaurant_data_points_placeholder=key_target_restaurant_data_points_json_str
        )
        
        try:
            # Call Gemini with enhanced generation config for strategic analysis
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,  # Slightly higher for creative strategic thinking
                    "maxOutputTokens": 8192,  # High token limit for comprehensive analysis
                    "response_mime_type": "application/json"  # Request JSON output format
                },
                "safetySettings": [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH", 
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    }
                ]
            }
            
            logger.info(f"🔗 Making LLMA-6 strategic recommendations API request")
            
            async with aiohttp.ClientSession() as session:
                response_data = await make_gemini_request(session, GEMINI_MODEL_TEXT, payload, timeout=300)
                
                if response_data.get("error"):
                    logger.error(f"❌ LLMA-6 API error: {response_data['error']}")
                    return self._create_fallback_strategic_analysis()
                
                # Extract and parse response using robust JSON parsing
                if 'candidates' in response_data and len(response_data['candidates']) > 0:
                    candidate = response_data['candidates'][0]
                    if 'content' in candidate and 'parts' in candidate['content']:
                        raw_text = candidate['content']['parts'][0]['text']
                        
                        # Use robust JSON parsing utilities
                        expected_keys = [
                            "executive_hook", "competitive_landscape_summary", "top_3_prioritized_opportunities",
                            "premium_analysis_teasers", "immediate_action_items_quick_wins", 
                            "engagement_and_consultation_questions", "forward_thinking_strategic_insights"
                        ]
                        
                        parsed_result = parse_llm_json_output(
                            raw_text,
                            function_name="generate_main_strategic_recommendations",
                            expected_keys=expected_keys
                        )
                        
                        if not parsed_result:
                            logger.error("❌ Failed to parse LLMA-6 strategic recommendations JSON")
                            return self._create_fallback_strategic_analysis()
                        
                        # Validate structure
                        if not validate_json_structure(parsed_result, expected_keys, "generate_main_strategic_recommendations"):
                            logger.warning("⚠️ LLMA-6 strategic recommendations missing some expected keys, proceeding with available data")
                        
                        # Log successful generation
                        logger.info("✅ Successfully generated main strategic recommendations")
                        logger.info(f"📊 Generated {len(parsed_result.get('top_3_prioritized_opportunities', []))} growth opportunities")
                        logger.info(f"📊 Generated {len(parsed_result.get('immediate_action_items_quick_wins', []))} immediate action items")
                        
                        return parsed_result
                
        except Exception as e:
            logger.error(f"❌ Exception in LLMA-6 main strategic recommendations generation: {str(e)}")
            return self._create_fallback_strategic_analysis()

    def _create_fallback_strategic_analysis(self) -> Dict[str, Any]:
        """Create fallback strategic analysis if main generation fails"""
        return {
            "executive_hook": {
                "hook_statement": "While our AI analysis encountered technical difficulties, preliminary data suggests significant growth opportunities exist for this restaurant through improved digital presence and strategic positioning.",
                "biggest_opportunity_teaser": "The most significant opportunity lies in optimizing the restaurant's online presence to capture untapped digital revenue streams."
            },
            "competitive_landscape_summary": {
                "introduction": "Based on available data, this restaurant shows potential for strategic improvements in several key areas.",
                "detailed_comparison_text": "Local market analysis indicates opportunities for differentiation and improved customer engagement through enhanced online presence and strategic messaging. While a comprehensive competitive comparison requires additional data processing, initial indicators suggest that focusing on digital optimization and customer experience enhancement could yield significant competitive advantages.",
                "key_takeaway_for_owner": "The primary focus should be on strengthening digital presence and customer engagement capabilities to capture market opportunities."
            },
            "top_3_prioritized_opportunities": [
                {
                    "priority_rank": 1,
                    "opportunity_title": "Digital Presence Enhancement",
                    "current_situation_and_problem": "Based on extracted data patterns, improving online visibility could drive significant customer acquisition.",
                    "detailed_recommendation": "1. Audit current online presence, 2. Optimize Google My Business profile, 3. Enhance website user experience",
                    "estimated_revenue_or_profit_impact": "Potential 15-25% increase in online-driven traffic within 3-6 months",
                    "ai_solution_pitch": "Our AI OrderFlow Manager and Social Spark Bot can automate online presence optimization and customer engagement.",
                    "implementation_timeline": "1-2 Months",
                    "difficulty_level": "Medium (Requires Focused Effort)",
                    "visual_evidence_suggestion": {
                        "idea_for_visual": "Before/after comparison of online presence optimization",
                        "relevant_screenshot_s3_url_from_input": None
                    }
                },
                {
                    "priority_rank": 2,
                    "opportunity_title": "Menu Strategy Optimization",
                    "current_situation_and_problem": "Menu presentation and pricing strategy appear to have room for optimization based on available data.",
                    "detailed_recommendation": "1. Analyze current menu performance, 2. Test pricing strategies, 3. Improve menu descriptions",
                    "estimated_revenue_or_profit_impact": "Potential 10-20% increase in average order value through strategic menu optimization",
                    "ai_solution_pitch": "Menu Optimizer Pro can analyze pricing patterns and suggest optimal menu structure and pricing.",
                    "implementation_timeline": "2-4 Weeks",
                    "difficulty_level": "Easy (Quick Wins)",
                    "visual_evidence_suggestion": {
                        "idea_for_visual": "Menu analytics dashboard showing optimization opportunities",
                        "relevant_screenshot_s3_url_from_input": None
                    }
                },
                {
                    "priority_rank": 3,
                    "opportunity_title": "Customer Engagement Enhancement",
                    "current_situation_and_problem": "Opportunities exist to improve customer retention and word-of-mouth marketing through enhanced engagement.",
                    "detailed_recommendation": "1. Implement customer feedback system, 2. Develop loyalty program, 3. Enhance social media presence",
                    "estimated_revenue_or_profit_impact": "Potential 20-30% improvement in customer retention and referral rates",
                    "ai_solution_pitch": "Customer Loyalty AI and Review Amplify AI can automate customer engagement and reputation management.",
                    "implementation_timeline": "1-2 Months",
                    "difficulty_level": "Medium (Requires Focused Effort)",
                    "visual_evidence_suggestion": {
                        "idea_for_visual": "Customer engagement funnel showing improvement opportunities",
                        "relevant_screenshot_s3_url_from_input": None
                    }
                }
            ],
            "premium_analysis_teasers": [
                {
                    "premium_feature_title": "Deep Dive Competitor Customer Acquisition Funnels",
                    "compelling_teaser_hook": "Discover exactly how your top competitors are attracting customers and how you can capture that same traffic.",
                    "value_proposition": "Detailed competitive intelligence that reveals specific marketing strategies and customer acquisition tactics your competitors use."
                },
                {
                    "premium_feature_title": "Dynamic Menu Pricing & Profitability Optimization Engine",
                    "compelling_teaser_hook": "What if you could optimize your menu pricing to maximize profit margins while maintaining customer satisfaction?",
                    "value_proposition": "AI-driven pricing analysis that identifies optimal price points for each menu item based on cost analysis and local market data."
                },
                {
                    "premium_feature_title": "Automated AI-Powered Review Response & Reputation Management Strategy",
                    "compelling_teaser_hook": "Never miss a customer review again and turn every piece of feedback into a business growth opportunity.",
                    "value_proposition": "Comprehensive reputation management system that monitors, responds to, and leverages customer feedback for continuous improvement."
                }
            ],
            "immediate_action_items_quick_wins": [
                {
                    "action_item": "Complete Google My Business profile optimization with current photos and information",
                    "rationale_and_benefit": "Improves local search visibility and provides customers with accurate, up-to-date information."
                },
                {
                    "action_item": "Implement basic website improvements for mobile responsiveness and contact clarity",
                    "rationale_and_benefit": "Ensures customers can easily find and contact the restaurant from any device."
                },
                {
                    "action_item": "Establish customer review response protocol and respond to recent reviews",
                    "rationale_and_benefit": "Shows commitment to customer service and can improve online reputation and search rankings."
                }
            ],
            "engagement_and_consultation_questions": [
                "What are your primary business goals for the next 12 months?",
                "Which competitors do you consider your biggest threats and why?",
                "What unique aspects of your restaurant do customers mention most often?"
            ],
            "forward_thinking_strategic_insights": {
                "introduction": "Beyond these immediate opportunities, successful restaurants continuously adapt. Here are a few forward-thinking considerations for this restaurant:",
                "untapped_potential_and_innovation_ideas": [
                    {
                        "idea_title": "Catering and Off-Premise Expansion",
                        "description_and_rationale": "Catering and off-premise dining opportunities may be underexplored. Many successful restaurants find that expanding into catering services can provide a significant additional revenue stream with relatively low additional overhead. This could involve developing catering packages, partnering with local businesses for corporate catering, or offering family-style take-home meal options that leverage existing kitchen capabilities while reaching new customer segments."
                    },
                    {
                        "idea_title": "Strategic Local Business Partnerships",
                        "description_and_rationale": "Strategic partnerships with local businesses could drive consistent traffic and create mutually beneficial relationships. This might include cross-promotional opportunities with nearby businesses, collaborative events, or loyalty program partnerships that help build a stronger local community presence while providing customers with added value and convenience."
                    }
                ],
                "long_term_vision_alignment_thoughts": [
                    {
                        "strategic_thought_title": "Building Sustainable Competitive Advantages",
                        "elaboration": "Focus on building sustainable competitive advantages through operational excellence and customer experience differentiation rather than competing solely on price. This involves developing systems and processes that consistently deliver exceptional value to customers while maintaining healthy profit margins. Consider investing in staff training, technology integration, and customer relationship management to create lasting competitive moats."
                    }
                ],
                "consultants_core_empowerment_message": "The opportunities identified in this analysis represent clear, actionable paths to meaningful business growth. With focused effort and strategic implementation, this restaurant can achieve significant improvements in revenue, customer satisfaction, and market position. Success lies in prioritizing the highest-impact opportunities while maintaining operational excellence in daily service delivery."
            }
        }

    async def analyze_operational_intelligence(self, restaurant_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLMA-8: Contact & Hours Intelligence Analysis
        
        Analyzes business hours, contact methods, and accessibility patterns
        for operational optimization insights.
        """
        logger.info("🕒 Analyzing operational intelligence (LLMA-8)")
        
        # Extract relevant operational data
        hours = restaurant_data.get('hours', {})
        phone = restaurant_data.get('phone')
        email = restaurant_data.get('email')
        website = restaurant_data.get('website')
        social_media = restaurant_data.get('social_media', [])
        address = restaurant_data.get('address')
        
        prompt = f"""You are an expert Restaurant Operations and Customer Access Strategist. Your goal is to help a restaurant owner optimize their operational setup for maximum customer convenience and revenue generation.

Analyze the provided contact information, business hours, and accessibility data for [This Restaurant].

<operational_data>
Business Hours: {json.dumps(hours, indent=2) if hours else 'Not available'}
Phone Number: {phone or 'Not available'}
Email: {email or 'Not available'}  
Website: {website or 'Not available'}
Social Media: {social_media if social_media else 'Not available'}
Address: {address or 'Not available'}
</operational_data>

Based SOLELY on the operational data provided, provide a detailed analysis focusing on:

1. **Hours Strategy Assessment (Detailed):**
   - Are their operating hours optimized for their likely customer base and market segment?
   - Do they appear to be missing potential revenue opportunities during specific time periods?
   - How do their hours compare to typical patterns for their restaurant type?
   - Are there any accessibility or convenience issues with their current schedule?

2. **Contact Method Effectiveness (Detailed):**
   - How easy is it for customers to reach them through multiple channels?
   - Are there gaps in their contact options that could frustrate potential customers?
   - Is their contact information professional and complete?
   - What contact methods might they be missing that competitors likely have?

3. **Customer Accessibility & Convenience (Detailed):**
   - Based on available information, what barriers might exist for customers trying to engage?
   - Are there convenience factors that could be improved to reduce customer friction?
   - How does their accessibility compare to modern customer expectations?

4. **Missed Revenue Opportunities (Detailed):**
   - Based on hours and contact patterns, what revenue opportunities might they be missing?
   - Are there operational adjustments that could capture more business?
   - What specific improvements could increase customer conversion and retention?

5. **Overall Assessment & Improvement Opinions:**
   - What is your overall professional assessment of their operational accessibility and customer convenience?
   - Provide 3-4 specific, actionable recommendations to improve their operational setup for better customer experience and revenue generation.

6. **Anything Else an Operations Consultant Would Tell the Owner?**
   - Based on this operational data, are there any other critical insights or advice a professional operations consultant would offer?

Return your analysis ONLY as a valid JSON object with the following exact structure:

{{
  "overall_operational_assessment": "Your concise professional judgment of their operational setup.",
  "hours_strategy_analysis": {{
    "hours_optimization_assessment": "Analysis of current hours vs. optimal strategy",
    "potential_missed_revenue_periods": "Time periods where they might be missing business",
    "hours_vs_market_comparison": "How their hours compare to restaurant type standards",
    "accessibility_convenience_issues": "Any scheduling barriers for customers"
  }},
  "contact_effectiveness_analysis": {{
    "multi_channel_accessibility": "Assessment of how easy they are to reach",
    "contact_gaps_identified": "Missing contact options that could frustrate customers", 
    "professionalism_completeness": "Quality of their contact information presentation",
    "missing_contact_methods": "Contact options they should consider adding"
  }},
  "customer_accessibility_assessment": {{
    "engagement_barriers": "Obstacles customers might face when trying to connect",
    "convenience_improvement_areas": "Friction points that could be reduced",
    "modern_expectations_gap": "How they compare to current customer expectations"
  }},
  "missed_revenue_opportunities": {{
    "operational_revenue_gaps": "Revenue opportunities based on hours/contact analysis",
    "conversion_improvement_potential": "Operational changes that could increase conversions",
    "customer_retention_operational_factors": "How operations impact customer loyalty"
  }},
  "operational_improvement_recommendations": [
    {{"area": "Specific operational area", "recommendation": "Detailed actionable suggestion"}},
    {{"area": "Specific operational area", "recommendation": "Detailed actionable suggestion"}},
    {{"area": "Specific operational area", "recommendation": "Detailed actionable suggestion"}}
  ],
  "additional_operations_consultant_advice": "Any other critical operational insights or advice."
}}"""

        try:
            raw_response = await self._call_gemini_async(
                prompt,
                max_tokens=2048,
                temperature=0.1,
                function_name="analyze_operational_intelligence"
            )
            
            if not raw_response:
                logger.error("❌ No response from Gemini for operational intelligence analysis")
                return {}
            
            # Parse using robust JSON utilities
            expected_keys = [
                "overall_operational_assessment", "hours_strategy_analysis", 
                "contact_effectiveness_analysis", "customer_accessibility_assessment",
                "missed_revenue_opportunities", "operational_improvement_recommendations"
            ]
            
            parsed_result = parse_llm_json_output(
                raw_response,
                function_name="analyze_operational_intelligence",
                expected_keys=expected_keys
            )
            
            if parsed_result:
                logger.info("✅ Successfully analyzed operational intelligence")
                return parsed_result
            else:
                logger.error("❌ Failed to parse operational intelligence JSON")
                return {}
                
        except Exception as e:
            logger.error(f"❌ Exception in operational intelligence analysis: {str(e)}")
            return {}

    async def analyze_content_and_seo_strategy(self, restaurant_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLMA-9: Content Quality & SEO Analysis
        
        Analyzes website content, descriptions, and online presence for SEO
        and content marketing optimization insights.
        """
        logger.info("📝 Analyzing content and SEO strategy (LLMA-9)")
        
        # Extract relevant content data
        website = restaurant_data.get('website')
        description = restaurant_data.get('description', '')
        about_text = restaurant_data.get('about_text', '')
        tagline = restaurant_data.get('tagline', '')
        menu_items = restaurant_data.get('menu_items', [])
        social_media = restaurant_data.get('social_media', [])
        seo_data = restaurant_data.get('seo_data', {})
        
        # Prepare content summary
        content_summary = {
            'website_url': website,
            'description_text': description[:500] + '...' if len(description) > 500 else description,
            'about_text': about_text[:500] + '...' if len(about_text) > 500 else about_text,
            'tagline': tagline,
            'menu_items_count': len(menu_items),
            'social_media_presence': len(social_media),
            'seo_elements': seo_data
        }

        prompt = f"""You are an expert Restaurant Digital Marketing and Content Strategist specializing in SEO optimization and compelling brand storytelling. Your goal is to help a restaurant owner enhance their online content strategy for better discoverability and customer engagement.

Analyze the provided website content, descriptions, and online presence for [This Restaurant].

<content_data>
{json.dumps(content_summary, indent=2)}
</content_data>

Based SOLELY on the content and SEO data provided, provide a detailed analysis focusing on:

1. **Content Quality Assessment (Detailed):**
   - Is their messaging compelling, clear, and differentiated?
   - How effectively do they communicate their unique value proposition?
   - Are their descriptions engaging and likely to convert visitors to customers?
   - What content strengths can they leverage further?

2. **SEO Optimization Level (Detailed):**
   - Based on available data, how discoverable do they appear to be online?
   - Are there obvious SEO gaps or opportunities for improved search visibility?
   - How well do they utilize keywords and local SEO principles?
   - What SEO improvements could drive more organic traffic?

3. **Brand Story Effectiveness (Detailed):**
   - Does their content tell a compelling restaurant story that builds emotional connection?
   - Are they effectively communicating their brand personality and values?
   - How memorable and distinctive is their brand narrative?
   - What story elements could be strengthened or better highlighted?

4. **Content Gaps & Marketing Opportunities (Detailed):**
   - What types of content could better showcase their offerings and attract customers?
   - Are there content marketing opportunities they're missing?
   - How could they better leverage their menu, location, or unique features in content?
   - What content could improve customer engagement and loyalty?

5. **Overall Assessment & Content Strategy Recommendations:**
   - What is your overall professional assessment of their content and SEO strategy?
   - Provide 3-4 specific, actionable recommendations to improve their content quality, SEO performance, and brand storytelling.

6. **Anything Else a Digital Marketing Consultant Would Tell the Owner?**
   - Based on this content analysis, are there any other critical insights or advanced strategies a professional digital marketing consultant would recommend?

Return your analysis ONLY as a valid JSON object with the following exact structure:

{{
  "overall_content_seo_assessment": "Your concise professional judgment of their content and SEO strategy.",
  "content_quality_analysis": {{
    "messaging_effectiveness": "Assessment of how compelling and clear their messaging is",
    "value_proposition_communication": "How well they communicate their unique advantages",
    "content_engagement_potential": "Likelihood their content converts visitors to customers",
    "leverageable_content_strengths": "Existing content assets they should amplify"
  }},
  "seo_optimization_analysis": {{
    "online_discoverability_assessment": "How easily customers can find them online",
    "seo_gaps_and_opportunities": "Specific SEO improvements needed",
    "keyword_local_seo_utilization": "How well they use SEO best practices",
    "organic_traffic_improvement_potential": "SEO changes that could drive more traffic"
  }},
  "brand_story_analysis": {{
    "story_compelling_factor": "How engaging and memorable their brand narrative is",
    "brand_personality_communication": "How well they express their restaurant's character",
    "emotional_connection_potential": "Their ability to build customer relationships through content",
    "story_strengthening_opportunities": "Narrative elements that could be enhanced"
  }},
  "content_marketing_opportunities": {{
    "missing_content_types": "Content formats they should consider creating",
    "underutilized_marketing_channels": "Platforms or methods they could leverage better",
    "menu_location_feature_optimization": "How to better showcase their unique assets",
    "engagement_loyalty_content_ideas": "Content strategies for customer retention"
  }},
  "content_strategy_recommendations": [
    {{"focus_area": "Specific content area", "recommendation": "Detailed actionable suggestion"}},
    {{"focus_area": "Specific content area", "recommendation": "Detailed actionable suggestion"}},
    {{"focus_area": "Specific content area", "recommendation": "Detailed actionable suggestion"}}
  ],
  "additional_digital_marketing_advice": "Any other critical content or digital marketing insights."
}}"""

        try:
            raw_response = await self._call_gemini_async(
                prompt,
                max_tokens=2048,
                temperature=0.1,
                function_name="analyze_content_and_seo_strategy"
            )
            
            if not raw_response:
                logger.error("❌ No response from Gemini for content and SEO analysis")
                return {}
            
            # Parse using robust JSON utilities
            expected_keys = [
                "overall_content_seo_assessment", "content_quality_analysis",
                "seo_optimization_analysis", "brand_story_analysis", 
                "content_marketing_opportunities", "content_strategy_recommendations"
            ]
            
            parsed_result = parse_llm_json_output(
                raw_response,
                function_name="analyze_content_and_seo_strategy",
                expected_keys=expected_keys
            )
            
            if parsed_result:
                logger.info("✅ Successfully analyzed content and SEO strategy")
                return parsed_result
            else:
                logger.error("❌ Failed to parse content and SEO analysis JSON")
                return {}
                
        except Exception as e:
            logger.error(f"❌ Exception in content and SEO analysis: {str(e)}")
            return {}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
    async def _call_gemini_async(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.1,
        function_name: str = "llm_call"
    ) -> Optional[str]:
        """
        Helper method to call Gemini with standardized configuration and robust error handling.
        
        Args:
            prompt: The prompt text to send to Gemini
            max_tokens: Maximum output tokens
            temperature: Temperature for response generation
            function_name: Name of calling function for logging
            
        Returns:
            Raw text response from Gemini or None if failed
        """
        if not self.enabled:
            logger.warning(f"Gemini disabled, skipping {function_name}")
            return None
            
        try:
            logger.info(f"🔗 Making Gemini API call for {function_name}")
            logger.debug(f"📝 Prompt length: {len(prompt)} characters")
            
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                    "response_mime_type": "application/json"
                },
                "safetySettings": [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                response_data = await make_gemini_request(session, GEMINI_MODEL_TEXT, payload, timeout=300)
                
                if response_data.get("error"):
                    logger.error(f"❌ {function_name} API error: {response_data['error']}")
                    return None
                
                # Extract response text
                if 'candidates' in response_data and len(response_data['candidates']) > 0:
                    candidate = response_data['candidates'][0]
                    if 'content' in candidate and 'parts' in candidate['content']:
                        raw_text = candidate['content']['parts'][0]['text']
                        logger.info(f"✅ {function_name} API call successful")
                        logger.debug(f"📄 Response length: {len(raw_text)} characters")
                        return raw_text
                
                logger.error(f"❌ Invalid response structure from {function_name}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Exception in {function_name}: {str(e)}")
            raise

# Example Usage (for testing this module directly):
# async def test_llm_analyzer():
#     # This requires a populated FinalRestaurantOutput object and screenshot_analysis_results
#     # For now, this is a placeholder for direct testing.
#     logger.info("Testing LLMAnalyzer...")
#     analyzer = LLMAnalyzer()
#     if not analyzer.enabled:
#         logger.error("Cannot run test, Gemini is not enabled.")
#         return

#     # Create a mock FinalRestaurantOutput object
#     # ... (populate with some data) ...
#     mock_data = FinalRestaurantOutput(
#         restaurant_id="test_001", 
#         canonical_url="http://example.com", 
#         name="Testaurant",
#         name_canonical="The Testaurant Supreme",
#         cuisine_types=["Test Food", "Mock Cuisine"],
#         extraction_metadata=ExtractionMetadata(extraction_id="mock_ext_id", started_at=datetime.now()),
#         # ... other fields ...
#         competitors=[
#             CompetitorSummary(name="Competitor Alpha", url="http://compalpha.com"),
#             CompetitorSummary(name="Competitor Beta", url="http://compbeta.com")
#         ]
#     )
#     mock_screenshot_results = {}

#     strategic_content = await analyzer.generate_strategic_report_content(mock_data, mock_screenshot_results)
    
#     if strategic_content:
#         logger.info("Strategic Content Generated:")
#         logger.info(json.dumps(strategic_content.dict(), indent=2))
#     else:
#         logger.error("Failed to generate strategic content in test.")

# if __name__ == '__main__':
#     # Remember to have GEMINI_API_KEY in your .env for this test to run properly
#     from dotenv import load_dotenv
#     load_dotenv(Path(__file__).parent.parent / '.env') # Adjust path to your .env
#     asyncio.run(test_llm_analyzer())

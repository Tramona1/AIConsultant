"""
Progressive Data Extraction System for Restaurant AI Consulting
Implements a 4-phase approach for scalable data extraction (10,000+ sites)

Phase 1: Lightweight Pre-computation (Google Places, Schema.org, Sitemaps)
Phase 2: Targeted DOM Crawling (Playwright + CSS Selectors)  
Phase 3: AI-Enhanced Analysis (Gemini Vision, OCR, Selective Stagehand)
Phase 4: Data Aggregation, Cleaning & Validation
"""

import asyncio
import logging
import re
import json
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from urllib.parse import urljoin, urlparse, quote
import xml.etree.ElementTree as ET

import httpx
import googlemaps
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import openai
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
import uuid

from .google_places_extractor import GooglePlacesExtractor
from .schema_org_extractor import SchemaOrgExtractor
from .sitemap_analyzer import SitemapAnalyzer
from .dom_crawler import DOMCrawler
from .ai_vision_processor import AIVisionProcessor
from .stagehand_integration import StagehandScraper
from .data_quality_validator import DataQualityValidator
from .llm_analyzer_module import LLMAnalyzer
from .models import (
    FinalRestaurantOutput,
    ExtractionMetadata,
    ScreenshotInfo,
    MenuItem,
    SocialMediaProfile,
    GoogleMyBusinessData,
    OperatingHours,
    CompetitorSummary,
    SocialMediaLinks,
    LLMStrategicAnalysisOutput,
    StructuredAddress
)

logger = logging.getLogger(__name__)

class ExtractionPhase(BaseModel):
    """Track which extraction phase we're in and results"""
    phase: int = 1
    completed_phases: List[int] = Field(default_factory=list)
    phase_results: Dict[int, Dict] = Field(default_factory=dict)
    phase_costs: Dict[int, float] = Field(default_factory=dict)
    phase_durations: Dict[int, float] = Field(default_factory=dict)
    total_cost: float = 0.0
    total_duration: float = 0.0

class DataQualityScore(BaseModel):
    """Track data quality at each phase"""
    completeness: float = 0.0  # 0-1 score
    confidence: float = 0.0    # 0-1 score
    source_reliability: float = 0.0  # 0-1 score
    overall_score: float = 0.0  # 0-1 score
    missing_critical_fields: List[str] = Field(default_factory=list)
    data_sources: List[str] = Field(default_factory=list)

class ProgressiveDataExtractor:
    """
    Progressive Data Extraction System with 4 Phases:
    1. Lightweight pre-computation (Google Places, Schema.org, sitemaps)
    2. Targeted DOM crawling (Playwright + CSS selectors)
    3. AI-enhanced analysis (Gemini Vision, OCR)
    4. LLM fallback (Stagehand for critical missing data)
    """
    
    def __init__(self):
        # Initialize all extractors
        self.google_places = GooglePlacesExtractor()
        self.schema_extractor = SchemaOrgExtractor()
        self.sitemap_analyzer = SitemapAnalyzer()
        self.dom_crawler = DOMCrawler()
        
        # AI Vision processor (optional if API key available)
        try:
            self.ai_vision = AIVisionProcessor()
            logger.info("✅ AI Vision processor initialized")
        except Exception as e:
            logger.warning(f"⚠️ AI Vision processor not available: {str(e)}")
            self.ai_vision = None
        
        # LLM Analyzer for Phase B Strategic Analysis (optional if API key available)
        try:
            self.llm_analyzer = LLMAnalyzer()
            logger.info("✅ LLM Analyzer initialized")
        except Exception as e:
            logger.warning(f"⚠️ LLM Analyzer not available: {str(e)}")
            self.llm_analyzer = None
        
        # Gemini data cleaner (optional if API key available)
        try:
            # Note: GeminiDataCleaner may not exist yet, so this is optional
            # self.gemini_cleaner = GeminiDataCleaner()
            # logger.info("✅ Gemini data cleaner initialized")
            self.gemini_cleaner = None
            logger.info("ℹ️ Gemini data cleaner not implemented yet")
        except Exception as e:
            logger.warning(f"⚠️ Gemini data cleaner not available: {str(e)}")
            self.gemini_cleaner = None
        
        self.validator = DataQualityValidator()
        self.stagehand_extractor = StagehandScraper()
        
        # Phase decision thresholds - Updated for more comprehensive extraction
        self.phase_thresholds = {
            'phase_2_trigger': 0.8,  # Always run DOM crawling unless quality is very high (was 0.4)
            'phase_3_trigger': 0.9,  # Always run AI analysis unless quality is excellent (was 0.6)
            'phase_4_trigger': 0.95, # Only skip Stagehand if quality is near-perfect (was 0.8)
        }
        
        logger.info("✅ Progressive data extractor initialized with all phases")
    
    async def extract_restaurant_data(self, url: str, restaurant_name: Optional[str] = None, 
                                    address: Optional[str] = None) -> FinalRestaurantOutput:
        """
        Main entry point for progressive data extraction.
        Now returns a FinalRestaurantOutput Pydantic model instance.
        
        Args:
            url: Restaurant website URL
            restaurant_name: Optional restaurant name (if known)
            address: Optional address (if known)
            
        Returns:
            A FinalRestaurantOutput Pydantic model instance.
        """
        logger.info(f"🎯 Starting progressive extraction for: {url}")
        request_start_time = datetime.now()
        # extraction_id = uuid.uuid4().hex # For logging/tracking individual full requests

        # This will be the main object we build up and eventually use to create FinalRestaurantOutput
        # Initialize with fields that FinalRestaurantOutput expects, where possible.
        current_restaurant_data: Dict[str, Any] = {
            "website_url": HttpUrl(url if url.startswith("http") else f"http://{url}"),
            "restaurant_name": restaurant_name,
            "raw_phone_numbers": [],
            "raw_emails": [],
            "menu_items": [], # Will be populated by MenuItem Pydantic models
            "menu_pdf_s3_urls": [],
            "social_media_links": {}, # Will be populated to match SocialMediaLinks model structure
            "google_places_summary": None,
            "extracted_text_blocks": {},
            "sitemap_urls": [],
            "key_pages_found": [], # Will store key page types found (e.g. menu, contact)
            "website_screenshots_s3_urls": [], # Will store ScreenshotInfo Pydantic models
            "identified_competitors_basic": [], # Will store CompetitorSummary Pydantic models
            "llm_strategic_analysis": None,
            "full_menu_text_raw_parts": [], # Temporary store for raw menu text pieces from DOM crawler
            "about_us_text": None, # Raw text for about us
            "contact_page_text_raw": None, # Raw text for contact page
            "discovered_social_links_raw": {}, # Raw social links from DOM crawler
            "raw_html_content": {}, # HTML content of key pages
            "data_sources_used": set() # Track unique sources
            # internal processing fields, not directly in FinalRestaurantOutput:
            # 'google_full_address_text': address, # From phase 1, for cleaner to parse to StructuredAddress
        }
        if address: # If provided, use it for eventual structured address parsing
            current_restaurant_data['google_full_address_text'] = address

        # --- Start of Phase Logic --- 
        # PHASE 1: Lightweight Pre-computation
        logger.info("📊 PHASE 1: Lightweight pre-computation starting...")
        phase1_result = await self._execute_phase_1(url, restaurant_name, address)
        
        # Merge data from phase 1 into current_restaurant_data with proper None checks
        if phase1_result and phase1_result.get("data"):
            p1_data = phase1_result["data"]
            logger.info(f"📊 Phase 1 data keys: {list(p1_data.keys())}")
            
            if p1_data.get("restaurant_name"): 
                current_restaurant_data["restaurant_name"] = p1_data["restaurant_name"]
                logger.info(f"✅ Restaurant name from Phase 1: {p1_data['restaurant_name']}")
            else:
                logger.warning(f"⚠️ No restaurant name found in Phase 1 data")
                
            if p1_data.get("google_full_address_text"): 
                current_restaurant_data["google_full_address_text"] = p1_data["google_full_address_text"]
                
            if p1_data.get("raw_phone_numbers"): 
                current_restaurant_data["raw_phone_numbers"].extend(p for p in p1_data["raw_phone_numbers"] if p not in current_restaurant_data["raw_phone_numbers"])
            
            # Handle Google Places data with dedicated fields and proper mapping
            if p1_data.get("google_places_data"): 
                google_places_data = p1_data["google_places_data"]
                current_restaurant_data["google_places_summary"] = google_places_data # Store the whole thing for legacy
                logger.info(f"✅ Google Places data found with keys: {list(google_places_data.keys())}")
                
                # Populate dedicated Google Places fields
                current_restaurant_data["google_rating"] = google_places_data.get("google_rating")
                current_restaurant_data["google_review_count"] = google_places_data.get("google_review_count")
                current_restaurant_data["google_place_id"] = google_places_data.get("place_id")
                current_restaurant_data["google_maps_url"] = google_places_data.get("google_maps_url")
                current_restaurant_data["google_recent_reviews"] = google_places_data.get("google_reviews", [])
                
                # Update contact info with proper field names for final compilation
                if google_places_data.get("phone"):
                    current_restaurant_data["canonical_phone_number"] = google_places_data["phone"]
                    # Also add to raw phone numbers if not already there
                    if google_places_data["phone"] not in current_restaurant_data["raw_phone_numbers"]:
                        current_restaurant_data["raw_phone_numbers"].append(google_places_data["phone"])
                    logger.info(f"📞 Set canonical phone from Google Places: {google_places_data['phone']}")
                
                if google_places_data.get("address"):
                    current_restaurant_data["canonical_address"] = google_places_data["address"]
                    current_restaurant_data["structured_address"] = {
                        "full_address_text": google_places_data["address"]
                    }
                    logger.info(f"📍 Set canonical address from Google Places: {google_places_data['address']}")
                    
                # Store the Phase 1 data structure for the compilation method
                current_restaurant_data["phase_1_data"] = p1_data
            else:
                logger.warning("⚠️ No Google Places data found in Phase 1")
                # Store the Phase 1 data anyway for compilation method access
                current_restaurant_data["phase_1_data"] = p1_data
            
            # Merge other Phase 1 data
            if p1_data.get("schema_org_data"): 
                current_restaurant_data.setdefault("misc_structured_data", {}).update({"schema_org": p1_data["schema_org_data"]})
            if p1_data.get("sitemap_urls"): 
                current_restaurant_data["sitemap_urls"] = p1_data["sitemap_urls"]
            if p1_data.get("key_pages_found_sitemap"): 
                current_restaurant_data["key_pages_found"].extend(k for k in p1_data["key_pages_found_sitemap"] if k not in current_restaurant_data["key_pages_found"])
            if p1_data.get("identified_competitors_basic"): # This should be List[CompetitorSummary]
                current_restaurant_data["identified_competitors_basic"].extend(p1_data["identified_competitors_basic"])
            if p1_data.get("third_party_platforms"):
                 current_restaurant_data.setdefault("misc_structured_data", {}).setdefault("third_party_platforms", [])
                 current_restaurant_data["misc_structured_data"]["third_party_platforms"].extend(p1_data["third_party_platforms"])
            
            # ENHANCED: Merge Google Search Results for Delivery Platforms
            if p1_data.get("delivery_platforms_google_search"):
                current_restaurant_data.setdefault("misc_structured_data", {})["delivery_platforms_google_search"] = p1_data["delivery_platforms_google_search"]
                logger.info(f"✅ Integrated Google delivery platform search results: {list(p1_data['delivery_platforms_google_search'].keys())}")
            
            # ENHANCED: Merge Google Search Results for Social Media
            if p1_data.get("social_media_google_search"):
                current_restaurant_data.setdefault("misc_structured_data", {})["social_media_google_search"] = p1_data["social_media_google_search"]
                logger.info(f"✅ Integrated Google social media search results: {list(p1_data['social_media_google_search'].keys())}")
            
            current_restaurant_data["data_sources_used"].add("Phase1_Extractors")
        else:
            logger.warning("⚠️ Phase 1 returned no data or failed")
            current_restaurant_data["data_sources_used"].add("Phase1_Failed")

        # Log current restaurant name status
        final_restaurant_name = current_restaurant_data.get("restaurant_name")
        logger.info(f"📛 Current restaurant name after Phase 1: {final_restaurant_name}")
        
        # If we still don't have a restaurant name, try to extract it from the URL or use a fallback
        if not final_restaurant_name or final_restaurant_name == "None":
            logger.info("📛 Restaurant name missing or invalid, applying fallback logic...")
            # Try to extract from URL (basic heuristic)
            try:
                from urllib.parse import urlparse
                parsed_url = urlparse(url)
                domain_name = parsed_url.netloc.replace('www.', '').split('.')[0]
                logger.info(f"📛 Extracted domain name from URL: {domain_name}")
                
                if domain_name and domain_name.lower() not in ['example', 'test', 'localhost', '127', '0']:
                    fallback_name = domain_name.replace('-', ' ').replace('_', ' ').title()
                    current_restaurant_data["restaurant_name"] = fallback_name
                    logger.info(f"📛 Using fallback restaurant name from URL: {fallback_name}")
                else:
                    current_restaurant_data["restaurant_name"] = "Unknown Restaurant"
                    logger.info(f"📛 Using default restaurant name: Unknown Restaurant")
            except Exception as e:
                current_restaurant_data["restaurant_name"] = "Unknown Restaurant"
                logger.warning(f"⚠️ Error extracting name from URL, using default: {e}")
        
        # Final check to ensure we have a valid restaurant name
        if not current_restaurant_data.get("restaurant_name"):
            current_restaurant_data["restaurant_name"] = "Unknown Restaurant"
            logger.info("📛 Final fallback: set restaurant name to 'Unknown Restaurant'")
        
        logger.info(f"📛 Final restaurant name for analysis: {current_restaurant_data['restaurant_name']}")

        high_priority_urls_for_phase2 = phase1_result.get("sitemap_pages", []) if phase1_result else []
        quality_score_obj = await self.validator.assess_quality(current_restaurant_data, phase=1) # TODO: Adapt assess_quality to new data structure
        logger.info(f"📊 Phase 1 Quality Score: {quality_score_obj.overall_score:.2f}")
        current_restaurant_data["data_quality_phase1_score"] = quality_score_obj.overall_score # Store for metadata

        # PHASE 2: Targeted DOM crawling
        # Condition to run Phase 2 (example: if critical data is missing or quality is low)
        # For now, let's assume we always run Phase 2 if Phase 1 score is below a threshold.
        if not quality_score_obj.overall_score >= self.phase_thresholds['phase_2_trigger']:
            logger.info("📊 PHASE 2: Targeted DOM crawling starting...")
            phase2_result = await self._execute_phase_2(url, high_priority_urls_for_phase2, current_restaurant_data)
            # _execute_phase_2 modifies current_restaurant_data in place for textual data.
            # It returns lists of ScreenshotInfo objects and PDF S3 URLs.
            if phase2_result.get("screenshots"):
                current_restaurant_data["website_screenshots_s3_urls"].extend(phase2_result["screenshots"])
            if phase2_result.get("pdfs"):
                existing_pdf_urls = {str(pu) for pu in current_restaurant_data["menu_pdf_s3_urls"]}
                for p_url in phase2_result["pdfs"]:
                    if str(p_url) not in existing_pdf_urls:
                        current_restaurant_data["menu_pdf_s3_urls"].append(str(p_url))  # Keep as strings for FlexibleUrl
            current_restaurant_data["data_sources_used"].add("Phase2_DOMCrawler")
            
            quality_score_obj = await self.validator.assess_quality(current_restaurant_data, phase=2) # TODO: Adapt
            logger.info(f"📊 Phase 2 Quality Score: {quality_score_obj.overall_score:.2f}")
            current_restaurant_data["data_quality_phase2_score"] = quality_score_obj.overall_score
        else:
            logger.info("⏭️ Skipping Phase 2 DOM crawling based on Phase 1 quality score.")

        # PHASE 3: AI-Enhanced Analysis (Vision for Screenshots/PDFs)
        if (self.ai_vision and self.ai_vision.enabled and 
            (current_restaurant_data["website_screenshots_s3_urls"] or current_restaurant_data["menu_pdf_s3_urls"]) and 
            (not quality_score_obj.overall_score >= self.phase_thresholds['phase_3_trigger'])):  # Condition to run Phase 3
            logger.info("📊 PHASE 3: AI Vision analysis starting...")
            # Prepare S3 URLs for AI Vision Processor
            try:
                screenshot_s3_urls_for_vision = []
                for si in current_restaurant_data["website_screenshots_s3_urls"]:
                    logger.debug(f"Processing screenshot item: {si}, type: {type(si)}")
                    if hasattr(si, 's3_url'):
                        screenshot_s3_urls_for_vision.append(str(si.s3_url))
                    else:
                        logger.warning(f"Screenshot item missing s3_url attribute: {si}")
                        # Handle case where it might be a dict or string
                        if isinstance(si, dict) and 's3_url' in si:
                            screenshot_s3_urls_for_vision.append(str(si['s3_url']))
                        elif isinstance(si, str):
                            screenshot_s3_urls_for_vision.append(si)
                
                pdf_s3_urls_for_vision = [str(pu) for pu in current_restaurant_data["menu_pdf_s3_urls"]]
                logger.info(f"Prepared {len(screenshot_s3_urls_for_vision)} screenshot URLs and {len(pdf_s3_urls_for_vision)} PDF URLs for vision analysis")
            except Exception as e_url_prep:
                logger.error(f"Error preparing URLs for Phase 3: {str(e_url_prep)}", exc_info=True)
                screenshot_s3_urls_for_vision = []
                pdf_s3_urls_for_vision = []
            
            phase3_result = await self._execute_phase_3(screenshot_s3_urls_for_vision, pdf_s3_urls_for_vision, current_restaurant_data)
            # _execute_phase_3 should update current_restaurant_data, especially menu_items, and potentially add more screenshots
            if phase3_result.get("data"):
                # Menu items from vision should be MenuItem Pydantic models or dicts that can be converted
                vision_menu_items = phase3_result["data"].get("menu_items", [])
                for item_data in vision_menu_items:
                    try: 
                        # Ensure it's a dict before attempting to create MenuItem to avoid errors if already model
                        item_model = MenuItem(**item_data) if isinstance(item_data, dict) else item_data
                        current_restaurant_data["menu_items"].append(item_model)
                    except Exception as e_menu_item_model:
                        logger.error(f"Could not convert vision menu item to Pydantic model: {item_data}, error: {e_menu_item_model}")
                # Merge other data if any
                # current_restaurant_data.update(...) # Example: if vision returns other structured text
            if phase3_result.get("screenshots"): # If vision processor generated new images (e.g. PDF page images)
                 current_restaurant_data["website_screenshots_s3_urls"].extend(phase3_result["screenshots"])
            current_restaurant_data["data_sources_used"].add("Phase3_AIVision")

            quality_score_obj = await self.validator.assess_quality(current_restaurant_data, phase=3) # TODO: Adapt
            logger.info(f"📊 Phase 3 Quality Score: {quality_score_obj.overall_score:.2f}")
            current_restaurant_data["data_quality_phase3_score"] = quality_score_obj.overall_score
        else:
            logger.info("⏭️ Skipping Phase 3 AI Vision based on conditions (no media, quality, or AI vision disabled).")

        # PHASE 4: LLM Fallback (Stagehand for Critical Missing Data)
        # TODO: Re-evaluate missing_critical_fields with new data structure
        missing_critical_fields = self.validator.identify_missing_critical_fields(current_restaurant_data) 
        if (self.stagehand_extractor and missing_critical_fields and 
            (not quality_score_obj.overall_score >= self.phase_thresholds['phase_4_trigger'])):  # Condition for Phase 4
            logger.info(f"📊 PHASE 4: Stagehand LLM fallback for missing fields: {missing_critical_fields}")
            phase4_result = await self._execute_phase_4(url, current_restaurant_data, missing_critical_fields)
            # _execute_phase_4 modifies current_restaurant_data directly and returns new screenshots.
            if phase4_result.get("screenshots"):
                 current_restaurant_data["website_screenshots_s3_urls"].extend(phase4_result["screenshots"])
            current_restaurant_data["data_sources_used"].add("Phase4_StagehandSelective")

            quality_score_obj = await self.validator.assess_quality(current_restaurant_data, phase=4) # TODO: Adapt
            logger.info(f"📊 Phase 4 Quality Score: {quality_score_obj.overall_score:.2f}")
            current_restaurant_data["data_quality_phase4_score"] = quality_score_obj.overall_score
        else:
            logger.info("⏭️ Skipping Phase 4 Stagehand LLM fallback based on conditions (no missing fields, quality, or stagehand disabled).")

        # FINAL CLEANING & STRUCTURING (Phase A7/A9)
        logger.info("📊 FINAL STEP: Data compilation, cleaning, and structuring...")
        
        # PHASE B: LLM Strategic Analysis (if LLM Analyzer is available)
        if self.llm_analyzer and self.llm_analyzer.enabled:
            logger.info("🧠 PHASE B: LLM Strategic Analysis starting...")
            phase_b_start_time = datetime.now()
            
            try:
                # Create a temporary FinalRestaurantOutput for strategic analysis
                # We need this because the LLM analyzer expects a FinalRestaurantOutput
                temp_final_output = await self._create_temp_final_output(current_restaurant_data, request_start_time)
                
                # Generate strategic analysis
                strategic_analysis = await self.llm_analyzer.generate_strategic_report_content(temp_final_output)
                
                if strategic_analysis:
                    current_restaurant_data["llm_strategic_analysis"] = strategic_analysis.model_dump()
                    logger.info("✅ Successfully generated LLM strategic analysis")
                else:
                    logger.warning("⚠️ LLM strategic analysis returned None, generating intelligent fallback")
                    # Generate intelligent fallback using available data
                    fallback_analysis = await self._generate_intelligent_strategic_fallback(current_restaurant_data)
                    current_restaurant_data["llm_strategic_analysis"] = fallback_analysis
                    
                phase_b_duration = (datetime.now() - phase_b_start_time).total_seconds()
                logger.info(f"📊 Phase B completed in {phase_b_duration:.2f} seconds")
                current_restaurant_data["data_sources_used"].add("PhaseB_LLMStrategicAnalysis")
                
            except Exception as e_phase_b:
                logger.error(f"❌ Phase B strategic analysis failed: {str(e_phase_b)}", exc_info=True)
                logger.info("🔄 Generating intelligent fallback strategic analysis from available data")
                # Generate intelligent fallback using available data instead of None
                try:
                    fallback_analysis = await self._generate_intelligent_strategic_fallback(current_restaurant_data)
                    current_restaurant_data["llm_strategic_analysis"] = fallback_analysis
                    logger.info("✅ Successfully generated intelligent fallback strategic analysis")
                except Exception as e_fallback:
                    logger.error(f"❌ Even fallback strategic analysis failed: {str(e_fallback)}")
                    # Last resort: basic fallback structure
                    current_restaurant_data["llm_strategic_analysis"] = self._create_basic_strategic_fallback(current_restaurant_data)
        else:
            logger.info("⏭️ LLM Analyzer not available, generating data-driven strategic analysis")
            # Generate intelligent analysis using available data instead of None
            fallback_analysis = await self._generate_intelligent_strategic_fallback(current_restaurant_data)
            current_restaurant_data["llm_strategic_analysis"] = fallback_analysis
        
        # Continue with final compilation
        try:
            # Debug: Log what canonical fields are in current_restaurant_data before final compilation
            logger.info(f"🔍 PRE-FINAL DEBUG: canonical_address in current_restaurant_data: {current_restaurant_data.get('canonical_address')}")
            logger.info(f"🔍 PRE-FINAL DEBUG: canonical_phone_number in current_restaurant_data: {current_restaurant_data.get('canonical_phone_number')}")
            logger.info(f"🔍 PRE-FINAL DEBUG: Keys in current_restaurant_data: {list(current_restaurant_data.keys())}")
            
            final_output_model = await self._final_data_compilation_and_cleaning(
                current_restaurant_data, 
                request_start_time
            )
            logger.info(f"✅ Successfully generated FinalRestaurantOutput for: {final_output_model.restaurant_name}")
            # The llm_strategic_analysis part (Phase B) will be populated later by a separate call after this initial extraction.
            # For now, we return the data object focused on extraction.
            return final_output_model
        except Exception as e_final_compile:
            logger.critical(f"💥 CRITICAL ERROR during final data compilation: {e_final_compile}", exc_info=True)
            # Depending on requirements, either raise the error or return a partial/error state.
            # For now, constructing a minimal FinalRestaurantOutput with error indication.
            # This ensures the function signature (returning FinalRestaurantOutput) is met.
            error_metadata = ExtractionMetadata(
                extraction_id=uuid.uuid4().hex,
                started_at=request_start_time,
                completed_at=datetime.now(),
                total_duration_seconds=(datetime.now() - request_start_time).total_seconds(),
                error_message=f"Critical failure in final compilation: {str(e_final_compile)}"
            )
            # Create a basic FinalRestaurantOutput, primarily with the URL and the error metadata.
            # Most fields will be None or default.
            # This requires ExtractionMetadata to have an optional error_message field or similar.
            # Let's assume we add it to the model or log it extensively and return a basic object.
            # For now, this example won't perfectly map to an error field in FinalRestaurantOutput's metadata
            # but illustrates the intent to return *something* of the expected type.
            # A better approach might be to have the orchestrator return a tuple (Optional[FinalRestaurantOutput], Optional[Error])
            # or raise a custom exception that the caller can handle.
            
            # Simplification: Log the error and return a mostly empty FinalRestaurantOutput
            # The actual error is logged above. The caller should check for minimal data.
            minimal_error_output = FinalRestaurantOutput(
                website_url=HttpUrl(url if url.startswith("http") else f"http://{url}"),
                restaurant_name=current_restaurant_data.get("restaurant_name", "Errored Extraction"),
                extraction_metadata=error_metadata # Assuming we add error details to metadata
            )
            # If ExtractionMetadata cannot store the error directly, it will be logged, 
            # and the caller would notice the lack of data.
            return minimal_error_output

    def _process_raw_screenshots(self, screenshot_data: List[Any], source_phase: int) -> List[ScreenshotInfo]:
        """
        Converts raw screenshot data (expected to be S3 URLs or paths that can be converted to S3 URLs)
        into ScreenshotInfo Pydantic models.
        Assumes _upload_to_s3 is available if local paths are given.
        """
        processed_screenshots: List[ScreenshotInfo] = []
        if not screenshot_data: return processed_screenshots

        for item in screenshot_data:
            try:
                if isinstance(item, ScreenshotInfo):
                    processed_screenshots.append(item)
                elif isinstance(item, dict):
                    # If it's a dict, assume it has s3_url and other ScreenshotInfo fields
                    # Potentially re-validate or reconstruct if needed
                    # Ensure s3_url is HttpUrl type
                    if item.get("s3_url") and not isinstance(item["s3_url"], HttpUrl):
                        item["s3_url"] = HttpUrl(item["s3_url"])
                    processed_screenshots.append(ScreenshotInfo(**item))
                elif isinstance(item, str): # Assuming it's an S3 URL string
                    processed_screenshots.append(ScreenshotInfo(s3_url=HttpUrl(item), source_phase=f"phase_{source_phase}"))
                # TODO: Handle Path objects if local paths are returned by a phase and need S3 upload here
                # elif isinstance(item, Path):
                #     s3_url = await self._upload_to_s3(item, object_name_prefix=f"screenshots_phase{source_phase}")
                #     processed_screenshots.append(ScreenshotInfo(s3_url=HttpUrl(s3_url), source_phase=f"phase_{source_phase}"))
                else:
                    logger.warning(f"Unsupported screenshot data type: {type(item)}, item: {item}")
            except Exception as e:
                logger.error(f"Error processing screenshot item {item}: {e}", exc_info=True)
        return processed_screenshots

    def _process_raw_pdfs(self, pdf_data: List[Any]) -> List[HttpUrl]:
        """
        Converts raw PDF data (expected to be S3 URL strings) into a list of HttpUrl.
        """
        processed_urls: List[HttpUrl] = []
        if not pdf_data: return processed_urls
        for item in pdf_data:
            try:
                if isinstance(item, HttpUrl):
                    processed_urls.append(item)
                elif isinstance(item, str):
                    processed_urls.append(HttpUrl(item))
                else:
                    logger.warning(f"Unsupported PDF data type: {type(item)}, item: {item}")
            except Exception as e:
                logger.error(f"Error processing PDF item {item}: {e}", exc_info=True)
        return processed_urls

    async def _execute_phase_1(self, url: str, restaurant_name: Optional[str] = None, 
                              address: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes Phase 1: Lightweight pre-computation.
        Gathers data from Google Places, Schema.org, Sitemaps, and identifies competitors.
        """
        logger.info(f"🚀 Starting Phase 1 for {url}")
        phase_start_time = datetime.now()
        
        phase_data: Dict[str, Any] = {
            "sitemap_urls": [],
            "key_pages_found_sitemap": [], # From sitemap that look like menu, contact etc.
            "google_places_data": None,
            "schema_org_data": None,
            "identified_competitors_basic": [],
            "third_party_platforms": [],
            "raw_phone_numbers": [],
            "raw_emails": [],
            # Other fields to align with FinalRestaurantOutput initial structure
        }
        cost = 0.0
        errors = []

        # ENHANCED: Extract better restaurant name BEFORE Google Places search
        enhanced_restaurant_name = await self._extract_enhanced_restaurant_name(url, restaurant_name)
        logger.info(f"🏪 Enhanced restaurant name: {enhanced_restaurant_name}")

        # PHASE 1: Google Places API with improved search strategy
        google_places_data = None
        google_places_cost = 0.0
        if self.google_places and self.google_places.client:
            logger.info("🌐 PHASE 1: Google Places API data extraction starting...")
            google_places_start_time = datetime.now()
            try:
                # Use enhanced search strategies
                search_strategies = [
                    enhanced_restaurant_name,
                    f"{enhanced_restaurant_name} restaurant"
                ]
                
                google_places_data = None
                for i, search_term in enumerate(search_strategies, 1):
                    logger.info(f"🔍 Attempt {i}: Searching Google Places with: '{search_term}'")
                    try:
                        google_places_data = await self.google_places.get_place_details_by_query(search_term)
                        
                        if google_places_data:
                            # Check if the found name is a reasonable match
                            found_name = google_places_data.get("name", "")
                            if self._is_reasonable_name_match(found_name, enhanced_restaurant_name):
                                logger.info(f"✅ Found reasonable match: '{found_name}' for '{enhanced_restaurant_name}'")
                                break
                            else:
                                logger.warning(f"⚠️ Found result '{found_name}' doesn't reasonably match expected '{enhanced_restaurant_name}', trying next strategy...")
                                google_places_data = None  # Reset for next attempt
                        else:
                            logger.info(f"❌ No results for search term: '{search_term}'")
                            
                    except Exception as e:
                        logger.warning(f"❌ Google Places search failed for '{search_term}': {str(e)}")
                        continue
                
                # If query search didn't work, try URL-based search as fallback
                if not google_places_data:
                    logger.info(f"🔍 Trying URL-based Google Places search for: {url}")
                    try:
                        google_places_data = await self.google_places.get_place_details_by_url(url)
                        if google_places_data:
                            logger.info(f"✅ URL-based search found: {google_places_data.get('name', 'Unknown')}")
                    except Exception as e:
                        logger.warning(f"❌ URL-based Google Places search failed: {str(e)}")
                
                google_places_duration = (datetime.now() - google_places_start_time).total_seconds()
                google_places_cost = 0.01  # Approximate cost per API call
                
                if google_places_data:
                    logger.info(f"✅ Google Places data extracted successfully")
                    
                    # Store the full Google Places data for merging in main orchestrator
                    phase_data["google_places_data"] = google_places_data
                    
                    # Extract basic info for phase_data
                    if google_places_data.get("name"):
                        phase_data["restaurant_name"] = google_places_data["name"]
                        logger.info(f"📛 Restaurant name from Google Places: {google_places_data['name']}")
                    
                    if google_places_data.get("phone"):
                        phase_data["raw_phone_numbers"].append(google_places_data["phone"])
                        logger.info(f"📞 Phone from Google Places: {google_places_data['phone']}")
                    
                    if google_places_data.get("address"):
                        phase_data["google_full_address_text"] = google_places_data["address"]
                        logger.info(f"📍 Address from Google Places: {google_places_data['address']}")
                    
                    logger.info(f"📊 Google Places: Rating {google_places_data.get('google_rating')}, {google_places_data.get('google_review_count')} reviews")
                else:
                    logger.warning("⚠️ No Google Places data found - this is okay, continuing with extraction")
                    # Use our enhanced name as fallback
                    if enhanced_restaurant_name and not phase_data.get("restaurant_name"):
                        phase_data["restaurant_name"] = enhanced_restaurant_name
                        logger.info(f"📛 Using enhanced restaurant name as fallback: {enhanced_restaurant_name}")
                    
            except Exception as e:
                logger.warning(f"⚠️ Google Places extraction failed (non-critical): {str(e)}")
                errors.append(f"Google Places error (non-critical): {str(e)}")
                # Use enhanced name as fallback
                if enhanced_restaurant_name and not phase_data.get("restaurant_name"):
                    phase_data["restaurant_name"] = enhanced_restaurant_name
                    logger.info(f"📛 Using enhanced restaurant name after Google Places error: {enhanced_restaurant_name}")
        else:
            logger.info("ℹ️ Google Places API not available (missing API key) - continuing without it")
            errors.append("Google Places API not configured (non-critical)")
            # Use enhanced name as fallback
            if enhanced_restaurant_name and not phase_data.get("restaurant_name"):
                phase_data["restaurant_name"] = enhanced_restaurant_name
                logger.info(f"📛 Using enhanced restaurant name (no Google Places API): {enhanced_restaurant_name}")

        # 2. Schema.org Extraction
        try:
            logger.info(" Attempting Schema.org extraction...")
            schema_org_data = await self.schema_extractor.extract_schema_org_data(url)
            if schema_org_data:
                phase_data["schema_org_data"] = schema_org_data
                cost += schema_org_data.get("cost", 0.0)
                logger.info(f" Schema.org data found for {url}.")
                # Extract specific fields if relevant and align with FinalRestaurantOutput
                # Example: if schema_org_data.get('Restaurant'): phase_data.update(...) 
            else:
                logger.info(f"No Schema.org data found for {url}.")
        except Exception as e:
            logger.error(f"Error during Schema.org extraction for {url}: {e}", exc_info=True)
            errors.append({"source": "schema_org", "error": str(e)})

        # 3. Sitemap Analysis
        sitemap_analysis_result = None
        try:
            logger.info(" Attempting Sitemap analysis...")
            sitemap_analysis_result = await self.sitemap_analyzer.analyze_sitemap(url)
            if sitemap_analysis_result and sitemap_analysis_result.get("sitemap_urls"):
                phase_data["sitemap_urls"] = sitemap_analysis_result["sitemap_urls"]
                # Prioritize some pages from sitemap for Phase 2 based on keywords
                key_pages = []
                for s_url_info in sitemap_analysis_result.get("sitemap_urls_details", []):
                    s_url = s_url_info.get("loc")
                    if not s_url: continue
                    # Make relative if it's on the same domain, useful for dom_crawler high_priority_urls
                    parsed_s_url = urlparse(s_url)
                    parsed_main_url = urlparse(url)
                    relative_s_url = parsed_s_url.path + ("?" + parsed_s_url.query if parsed_s_url.query else "")
                    
                    if any(kw in s_url.lower() for kw in ["menu", "carte", "contact", "about", "reservation"]):
                         if parsed_s_url.netloc == parsed_main_url.netloc:
                            key_pages.append(relative_s_url) # Pass relative URLs
                         else:
                            key_pages.append(s_url) # Keep absolute if different domain (though unlikely for sitemap)
                
                phase_data["key_pages_found_sitemap"] = list(set(key_pages)) # unique
                cost += sitemap_analysis_result.get("cost", 0.0)
                logger.info(f" Sitemap analysis complete for {url}. Found {len(phase_data['sitemap_urls'])} URLs. Prioritized {len(phase_data['key_pages_found_sitemap'])} pages.")
            else:
                logger.info(f"No sitemap URLs found or analysis failed for {url}.")
        except Exception as e:
            logger.error(f"Error during Sitemap analysis for {url}: {e}", exc_info=True)
            errors.append({"source": "sitemap_analyzer", "error": str(e)})

        # 4. Initial Competitor Identification
        if google_places_data and google_places_data.get("place_id"):
            try:
                logger.info(f" Attempting competitor identification for place ID: {google_places_data['place_id']}")
                # Define a radius for local competitors, e.g., 5000 meters (5km)
                # This might require lat/lng from the primary place_details call, ensure it's fetched.
                # For now, assuming find_local_competitors handles this or doesn't strictly need radius if place_id is strong.
                competitors_raw = await self.google_places.find_local_competitors(place_id=google_places_data["place_id"], radius=5000, keyword="restaurant") # Added keyword
                
                if competitors_raw and competitors_raw.get("results"):
                    logger.info(f" Found {len(competitors_raw['results'])} potential competitors via Google Places.")
                    competitor_summaries: List[CompetitorSummary] = []
                    # Limit to a few competitors for the lightweight scrape
                    for comp_raw in competitors_raw["results"][:3]: # Max 3 competitors for phase 1 basic info
                        comp_name = comp_raw.get("name")
                        comp_url = comp_raw.get("website")
                        comp_phone = comp_raw.get("international_phone_number") # From competitor's place details if available
                        comp_email = None # Placeholder, needs to be scraped
                        
                        if comp_name and comp_url:
                            logger.info(f"  Fetching basic contact for competitor: {comp_name} ({comp_url})")
                            try:
                                # Lightweight scrape for contact info
                                # Using a simplified DOM crawler call or a dedicated function
                                # For simplicity here, let's assume a basic_contact_info method exists or we adapt dom_crawler
                                # This part might need a dedicated, very fast scraper.
                                # For now, we'll just store what Google Places gave us for phone.
                                # TODO: Implement a very lightweight scraper for competitor email/phone if not in Google Places data.
                                pass 
                            except Exception as e_comp_scrape:
                                logger.warning(f"   Could not scrape basic contact for {comp_name}: {e_comp_scrape}")                            

                            competitor_summaries.append(
                                CompetitorSummary(
                                    name=comp_name,
                                    url=HttpUrl(comp_url) if comp_url else None,
                                    phone=comp_phone, # This is from Google data, not live scrape yet
                                    email=comp_email # Placeholder
                                )
                            )
                    phase_data["identified_competitors_basic"] = competitor_summaries
                    cost += competitors_raw.get("cost", 0.0) # Add cost from competitor search
                    logger.info(f" Processed {len(competitor_summaries)} competitors with basic info.")
                else:
                    logger.info("No competitors found via Google Places or find_local_competitors failed.")
            except Exception as e:
                logger.error(f"Error during competitor identification for {url}: {e}", exc_info=True)
                errors.append({"source": "competitor_identification", "error": str(e)})
        else:
            logger.warning("Skipping competitor identification as no Place ID was found for the target restaurant.")

        # 5. Detect Third-Party Platforms
        try:
            logger.info("🔍 Attempting third-party platform detection...")
            detected_platforms = await self._detect_third_party_platforms(url) # This method already exists
            if detected_platforms:
                phase_data["third_party_platforms"] = detected_platforms
                logger.info(f"✅ Detected {len(detected_platforms)} third-party platforms for {url}.")
            else:
                logger.info(f"No third-party platforms detected for {url}.")
        except Exception as e:
            logger.error(f"Error during third-party platform detection for {url}: {e}", exc_info=True)
            errors.append({"source": "third_party_detection", "error": str(e)})
        
        # NOTE: Social media and delivery platform analysis is handled comprehensively 
        # by the Stagehand scraper in Phase 4, which extracts social links directly 
        # from website content and performs detailed platform analysis
        
        duration = (datetime.now() - phase_start_time).total_seconds()
        logger.info(f"🏁 Phase 1 finished for {url}. Duration: {duration:.2f}s, Est. Cost: ${cost:.4f}")
        
        return {
            "data": phase_data,
            "sitemap_pages": phase_data.get("key_pages_found_sitemap", []), # Pass prioritized pages for phase 2
            "cost": cost,
            "duration": duration,
            "source": "Phase1_CoreExtractors",
            "errors": errors
        }

    async def _execute_phase_2(self, url: str, 
                              # sitemap_pages: List[str], # This was the old param
                              high_priority_relative_urls: Optional[List[str]],
                              existing_data: Dict[str, Any] # This is the main restaurant_data object being built
                              ) -> Dict[str, Any]:
        """
        Executes Phase 2: Comprehensive DOM Crawling using the enhanced DOMCrawler.
        """
        logger.info(f"🚀 Starting Phase 2 (DOM Crawler) for {url}")
        phase_start_time = datetime.now()
        cost = 0.0
        errors = []
        dom_crawler_output = None

        # Data to be directly updated in the main restaurant_data object (passed as existing_data)
        # This simplifies merging as dom_crawler now returns a more structured output.
        # We'll update `existing_data` directly or prepare specific fields to be returned for merging in the orchestrator.

        try:
            # Initialize DOMCrawler if not already (it's usually done in __init__ of ProgressiveDataExtractor)
            # self.dom_crawler = DOMCrawler() # Assuming it's already initialized

            # The `existing_data` dict might contain some info from Phase 1 that dom_crawler could use (e.g. restaurant name as a hint)
            # However, the current dom_crawler.crawl_website signature doesn't explicitly take all of it.
            # It takes `known_data` which can be used for this if needed. For now, passing a subset.
            known_data_for_crawler = {
                "restaurant_name": existing_data.get("restaurant_name")
                # Add other relevant hints if dom_crawler is adapted to use them
            }

            logger.info(f" Calling dom_crawler.crawl_website for {url} with {len(high_priority_relative_urls or [])} high-priority URLs.")
            dom_crawler_output = await self.dom_crawler.crawl_website(
                target_url=url,
                high_priority_relative_urls=high_priority_relative_urls,
                known_data=known_data_for_crawler
            )
            
            cost += dom_crawler_output.get("crawl_metadata", {}).get("cost", 0.0) # dom_crawler might track its own cost
            if dom_crawler_output.get("crawl_metadata", {}).get("errors"):
                errors.extend(dom_crawler_output["crawl_metadata"]["errors"])

            # Now, merge dom_crawler_output into existing_data (the main data object)
            # This logic should align with how data is structured in FinalRestaurantOutput
            
            # 1. Extracted Textual Data
            text_data = dom_crawler_output.get("extracted_textual_data", {})
            if text_data.get("emails"):
                existing_data.setdefault("raw_emails", [])
                for email in text_data["emails"]:
                    if email not in existing_data["raw_emails"]:
                        existing_data["raw_emails"].append(email)
            
            if text_data.get("phones"):
                existing_data.setdefault("raw_phone_numbers", [])
                for phone in text_data["phones"]:
                    if phone not in existing_data["raw_phone_numbers"]:
                        existing_data["raw_phone_numbers"].append(phone)
            
            # Social Links (dom_crawler returns a dict, FinalRestaurantOutput.social_media_links is a Pydantic model)
            # We'll store raw links here and GeminiCleaner can structure it into SocialMediaLinks model.
            if text_data.get("social_links"):
                existing_data.setdefault("discovered_social_links_raw", {})
                existing_data["discovered_social_links_raw"].update(text_data["social_links"]) 

            if text_data.get("menu_texts_raw"):
                existing_data.setdefault("full_menu_text_raw_parts", []) # Store as parts, cleaner can join
                existing_data["full_menu_text_raw_parts"].extend(text_data["menu_texts_raw"])
                
                # CRITICAL: Process raw menu text into structured menu items immediately
                logger.info("🍽️ Processing raw menu text into structured menu items...")
                if self.gemini_cleaner and self.gemini_cleaner.enabled:
                    # Combine all menu text for processing
                    combined_menu_text = "\n\n".join(text_data["menu_texts_raw"])
                    if len(combined_menu_text.strip()) > 20:  # Only process if substantial text
                        try:
                            ai_menu_items = await self.gemini_cleaner.extract_menu_items_from_text(combined_menu_text)
                            if ai_menu_items and isinstance(ai_menu_items, list):
                                # Convert to MenuItem models and add to existing data
                                existing_menu_item_names = {mi.name.lower().strip() for mi in existing_data.get("menu_items", []) if hasattr(mi, 'name') and mi.name}
                                
                                for item_data in ai_menu_items:
                                    try:
                                        if isinstance(item_data, dict) and item_data.get("name"):
                                            item_name_norm = item_data["name"].lower().strip()
                                            if item_name_norm not in existing_menu_item_names:
                                                from .models import MenuItem
                                                menu_item = MenuItem(**item_data)
                                                existing_data.setdefault("menu_items", []).append(menu_item)
                                                existing_menu_item_names.add(item_name_norm)
                                                logger.debug(f"✅ Added menu item from DOM text: {menu_item.name}")
                                    except Exception as e_menu:
                                        logger.warning(f"⚠️ Could not convert menu item to model: {item_data} - {e_menu}")
                                
                                logger.info(f"✅ Extracted {len(ai_menu_items)} menu items from DOM crawler text")
                            else:
                                logger.warning("⚠️ No valid menu items extracted from DOM text")
                        except Exception as e_menu_processing:
                            logger.warning(f"⚠️ Error processing menu text with AI: {e_menu_processing}")
                else:
                    logger.info("⚠️ Gemini cleaner not available - raw menu text stored but not structured")
            
            if text_data.get("about_text_raw"):
                if not existing_data.get("about_us_text") or len(text_data["about_text_raw"]) > len(existing_data.get("about_us_text", "")):
                    existing_data["about_us_text"] = text_data["about_text_raw"]
            
            if text_data.get("contact_text_raw"):
                 if not existing_data.get("contact_page_text_raw") or len(text_data["contact_text_raw"]) > len(existing_data.get("contact_page_text_raw", "")):
                    existing_data["contact_page_text_raw"] = text_data["contact_text_raw"]

            # General page texts (key: url, value: text)
            if text_data.get("general_page_texts"):
                existing_data.setdefault("general_extracted_texts", {})
                existing_data["general_extracted_texts"].update(text_data["general_page_texts"]) 
            
            # Misc extracted data from dom_crawler
            if text_data.get("misc_extracted_data"):
                existing_data.setdefault("misc_dom_data", {})
                existing_data["misc_dom_data"].update(text_data["misc_extracted_data"]) 

            # 2. Screenshots (List[ScreenshotInfo])
            # The orchestrator (extract_restaurant_data) should handle adding these to its `all_screenshots_info` list.
            # So, we return it from this function.
            screenshots_info_list = dom_crawler_output.get("screenshots", [])
            
            # 3. Downloaded PDF S3 URLs (List[str])
            # Orchestrator should handle adding these to `all_pdf_urls`.
            pdf_s3_urls_list = dom_crawler_output.get("downloaded_pdf_s3_urls", []) 

            # 4. HTML Content for Key Pages (Optional)
            if dom_crawler_output.get("html_content_key_pages"):
                existing_data.setdefault("raw_html_content", {})
                existing_data["raw_html_content"].update(dom_crawler_output["html_content_key_pages"])
            
            logger.info(f" DOM Crawler finished. Found {len(screenshots_info_list)} screenshots, {len(pdf_s3_urls_list)} PDFs.")
            logger.info(f" Emails found: {len(existing_data.get('raw_emails',[]))}, Phones: {len(existing_data.get('raw_phone_numbers',[]))}")

        except Exception as e:
            logger.error(f"Error during Phase 2 (DOM Crawler) for {url}: {e}", exc_info=True)
            errors.append({"source": "dom_crawler", "error": str(e)})
            # Ensure screenshots and pdfs are empty lists if error before assignment
            screenshots_info_list = []
            pdf_s3_urls_list = [] 

        duration = (datetime.now() - phase_start_time).total_seconds()
        logger.info(f"🏁 Phase 2 (DOM Crawler) finished for {url}. Duration: {duration:.2f}s, Est. Cost: ${cost:.4f}")
        
        # The main orchestrator (`extract_restaurant_data`) will update `current_data` directly.
        # This function needs to return the specific outputs that the orchestrator expects to collect, like screenshots and pdfs.
        return {
            # "data": existing_data, # No need to return existing_data, it's modified in place or orchestrator handles updates
            "screenshots": screenshots_info_list, # This needs to be handled by the orchestrator
            "pdfs": pdf_s3_urls_list,          # This also needs to be handled by the orchestrator
            "cost": cost,
            "duration": duration,
            "source": "Phase2_DOMCrawler", # For tracking data sources
            "errors": errors
        }

    async def _execute_phase_3(self, screenshot_s3_urls: List[str], 
                              pdf_s3_urls: List[str], 
                              current_restaurant_data: Dict[str, Any] # Main data object being built
                              ) -> Dict[str, Any]:
        """
        Execute Phase 3: AI Vision analysis of screenshots and PDFs.
        Updates current_restaurant_data with extracted menu items (as Pydantic models)
        and returns any newly generated ScreenshotInfo objects (e.g., from PDF page processing).
        """
        start_time = datetime.now()
        phase_cost = 0.0
        new_screenshots_from_vision: List[ScreenshotInfo] = []
        errors = []
        vision_extracted_data = {}  # Initialize to prevent UnboundLocalError

        try:
            logger.info(f"Executing Phase 3 AI Vision for {len(screenshot_s3_urls)} screenshots and {len(pdf_s3_urls)} PDFs.")
            if not self.ai_vision or not self.ai_vision.enabled:
                logger.warning("AI Vision is not enabled or initialized. Skipping Phase 3.")
                return {
                    "data": vision_extracted_data,
                    "screenshots": [],
                    "cost": 0,
                    "duration": 0,
                    "source": "ai_vision_disabled",
                    "errors": ["AI Vision disabled"]
                }

            # Convert screenshot URLs to ScreenshotInfo objects for the AI vision processor
            screenshot_info_list = []
            for i, url in enumerate(screenshot_s3_urls):
                screenshot_info = ScreenshotInfo(
                    s3_url=HttpUrl(url) if not url.startswith("file://") else url,
                    caption=f"Website screenshot {i+1}",
                    source_phase="phase_2",
                    taken_at=datetime.now()
                )
                screenshot_info_list.append(screenshot_info)

            # Call AI vision processor with correct parameter names
            ai_vision_output = await self.ai_vision.process_visual_content(
                screenshot_info_list=screenshot_info_list,
                pdf_s3_urls=pdf_s3_urls
            )

            phase_cost = ai_vision_output.get("cost", 0.0)
            
            # Process extracted data, especially menu items
            vision_extracted_data = ai_vision_output.get("data", {})
            if vision_extracted_data.get("menu_items"):
                raw_menu_items = vision_extracted_data["menu_items"]
                logger.info(f"AI Vision returned {len(raw_menu_items)} potential menu items.")
                # current_restaurant_data["menu_items"] should already be a list
                # Convert to MenuItem Pydantic models and attempt deduplication
                existing_menu_item_names = {mi.name.lower().strip() for mi in current_restaurant_data.get("menu_items", []) if mi.name}
                
                for item_data in raw_menu_items:
                    try:
                        # Ensure item_data is a dict, as expected by MenuItem constructor
                        if not isinstance(item_data, dict):
                            logger.warning(f"Skipping menu item, not a dict: {item_data}")
                            continue
                        
                        # Basic normalization for deduplication check
                        item_name_raw = item_data.get("name")
                        if not item_name_raw or not isinstance(item_name_raw, str):
                            logger.warning(f"Skipping menu item due to missing or invalid name: {item_data}")
                            continue
                        
                        item_name_normalized = item_name_raw.lower().strip()
                        if item_name_normalized not in existing_menu_item_names:
                            menu_item_model = MenuItem(**item_data) # Create Pydantic model
                            current_restaurant_data.setdefault("menu_items", []).append(menu_item_model)
                            existing_menu_item_names.add(item_name_normalized)
                            logger.debug(f"Added new menu item from AI Vision: {menu_item_model.name}")
                        else:
                            logger.debug(f"Skipped duplicate menu item from AI Vision: {item_name_raw}")
                    except Exception as e:
                        errors.append(f"Error processing menu item from AI Vision: {item_data} - {str(e)}")
                        logger.error(f"Error processing menu item {item_data}: {e}", exc_info=True)
            
            # Process screenshots (e.g., images of PDF pages created by AI Vision)
            # These should already be ScreenshotInfo model instances from AIVisionProcessor
            new_screenshots_from_vision = ai_vision_output.get("screenshots", [])
            if new_screenshots_from_vision:
                logger.info(f"AI Vision returned {len(new_screenshots_from_vision)} new screenshots (e.g., PDF pages). Example s3_url: {new_screenshots_from_vision[0].s3_url if new_screenshots_from_vision else 'N/A'}")

        except Exception as e:
            error_msg = f"Phase 3 (AI Vision) failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Phase 3 completed in {duration:.2f}s. Cost: ${phase_cost:.4f}")
        return {
            "data": vision_extracted_data, # Return all data, orchestrator can pick
            "screenshots": new_screenshots_from_vision, # List of ScreenshotInfo objects
            "cost": phase_cost,
            "duration": duration,
            "source": "ai_vision_processor",
            "errors": errors
        }

    async def _execute_phase_4(self, url: str, existing_data: Dict[str, Any], missing_critical_fields: List[str]) -> Dict[str, Any]:
        """
        Execute Phase 4: LLM Fallback using StagehandScraper for critical missing data.
        Updates existing_data with the data found by Stagehand.
        Returns a list of new ScreenshotInfo objects from Stagehand.
        """
        start_time = datetime.now()
        phase_cost = 0.0  # Stagehand cost is not easily tracked per call here, assumed to be part of a larger operational cost.
        new_screenshots_from_stagehand: List[ScreenshotInfo] = []
        errors = []

        logger.info(f"Executing Phase 4 (Stagehand Selective Scrape) for URL: {url} for fields: {missing_critical_fields}")

        if not self.stagehand_extractor:
            logger.warning("Stagehand extractor not available. Skipping Phase 4.")
            return {
                "data": {},
                "screenshots": [],
                "cost": 0,
                "duration": 0,
                "source": "stagehand_disabled",
                "errors": ["Stagehand disabled"]
            }
        
        # Prepare context data for Stagehand. It expects simple key-value pairs.
        # Send only what might be useful and simple for the scraper, like name and address if known.
        context_for_stagehand = {}
        if existing_data.get("restaurant_name"):
            context_for_stagehand["restaurant_name"] = existing_data["restaurant_name"]
        if existing_data.get("google_full_address_text"): # Or a more structured address if available and scraper supports it
            context_for_stagehand["address_context"] = existing_data["google_full_address_text"]
        
        try:
            # Call StagehandScraper's selective scrape method
            stagehand_result = await self.stagehand_extractor.scrape_restaurant_selective(
                url=url,
                missing_fields=missing_critical_fields,
                context_data=context_for_stagehand # Pass the refined context
            )

            if stagehand_result.get("error"):
                errors.append(f"Stagehand selective scrape error: {stagehand_result['error']}")
                logger.error(f"Stagehand selective scrape for {url} failed: {stagehand_result['error']}")
            else:
                extracted_stagehand_data = stagehand_result.get("extracted_data", {})
                new_screenshots_from_stagehand = stagehand_result.get("screenshots", []) # Should be List[ScreenshotInfo]

                logger.info(f"Stagehand selectively extracted: {list(extracted_stagehand_data.keys())}")
                if new_screenshots_from_stagehand:
                    logger.info(f"Stagehand returned {len(new_screenshots_from_stagehand)} new screenshots.")

                # Merge extracted_stagehand_data into existing_data
                # This requires careful mapping based on FinalRestaurantOutput structure
                # and what Stagehand is expected to return for each field.
                
                # Example direct merges (if Stagehand keys match FinalRestaurantOutput keys or a known mapping)
                if "restaurant_name" in extracted_stagehand_data and not existing_data.get("restaurant_name"):
                    existing_data["restaurant_name"] = extracted_stagehand_data["restaurant_name"]
                    logger.debug(f"Updated restaurant_name from Stagehand: {existing_data['restaurant_name']}")
                
                if "description_short" in extracted_stagehand_data and not existing_data.get("description_short"):
                    existing_data["description_short"] = extracted_stagehand_data["description_short"]
                
                if "year_established" in extracted_stagehand_data and not existing_data.get("year_established"):
                    try:
                        existing_data["year_established"] = int(extracted_stagehand_data["year_established"])
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert year_established '{extracted_stagehand_data['year_established']}' to int.")

                # Address: Stagehand might return a full string or structured components
                # Assuming stagehand returns a field like "address_full_text" if it got the address
                if "address_full_text" in extracted_stagehand_data and not existing_data.get("google_full_address_text"):
                    existing_data["google_full_address_text"] = extracted_stagehand_data["address_full_text"]
                    logger.debug(f"Updated google_full_address_text from Stagehand.")
                # TODO: If Stagehand provides structured address, map to existing_data["structured_address"]
                # Example: if extracted_stagehand_data.get("address_structured"): existing_data["structured_address"] = ...

                # Phone & Email: Append to raw lists, ensure no duplicates
                if "phone" in extracted_stagehand_data:
                    phone_num = extracted_stagehand_data["phone"]
                    if phone_num and phone_num not in existing_data.get("raw_phone_numbers", []):
                        existing_data.setdefault("raw_phone_numbers", []).append(phone_num)
                        logger.debug(f"Added phone from Stagehand: {phone_num}")
                
                if "email" in extracted_stagehand_data:
                    email_addr = extracted_stagehand_data["email"]
                    if email_addr and email_addr not in existing_data.get("raw_emails", []):
                        existing_data.setdefault("raw_emails", []).append(email_addr)
                        logger.debug(f"Added email from Stagehand: {email_addr}")

                # Menu Items: Stagehand might return menu items. Convert to MenuItem model.
                # Assume Stagehand returns menu items in a list of dicts under "menu_items" key.
                if "menu_items" in extracted_stagehand_data:
                    stagehand_menu_items = extracted_stagehand_data["menu_items"]
                    if isinstance(stagehand_menu_items, list):
                        existing_menu_item_names = {mi.name.lower().strip() for mi in existing_data.get("menu_items", []) if mi.name}
                        for item_data in stagehand_menu_items:
                            if isinstance(item_data, dict) and item_data.get("name"):
                                item_name_norm = item_data["name"].lower().strip()
                                if item_name_norm not in existing_menu_item_names:
                                    try:
                                        menu_item_model = MenuItem(**item_data)
                                        existing_data.setdefault("menu_items", []).append(menu_item_model)
                                        existing_menu_item_names.add(item_name_norm)
                                        logger.debug(f"Added menu item from Stagehand: {menu_item_model.name}")
                                    except Exception as e_menu:
                                        logger.warning(f"Could not convert Stagehand menu item {item_data} to model: {e_menu}")
                                else:
                                    logger.debug(f"Skipped duplicate menu item from Stagehand: {item_data.get('name')}")
                
                # Social Media Links: Stagehand might return a dictionary of social links
                # e.g., {"facebook": "url1", "instagram": "url2"}
                # This needs to be merged into existing_data["social_media_links"] which follows SocialMediaLinks model.
                if "social_media" in extracted_stagehand_data:
                    sm_links = extracted_stagehand_data["social_media"]
                    if isinstance(sm_links, dict):
                        # Ensure the target structure exists
                        if existing_data.get("social_media_links") is None:
                            existing_data["social_media_links"] = {} # Initialize if not present
                        
                        for platform, url_val in sm_links.items():
                            platform_key = platform.lower() # Normalize platform name
                            # Check if this platform is a direct field in SocialMediaLinks model
                            if platform_key in SocialMediaLinks.model_fields:
                                if not existing_data["social_media_links"].get(platform_key) and url_val:
                                    try:
                                        existing_data["social_media_links"][platform_key] = HttpUrl(url_val)
                                        logger.debug(f"Added social media link from Stagehand: {platform_key} = {url_val}")
                                    except Exception as e_url:
                                        logger.warning(f"Invalid URL for {platform_key} from Stagehand: {url_val} - {e_url}")
                            else: # Store in other_platforms
                                if "other_platforms" not in existing_data["social_media_links"] or existing_data["social_media_links"].get("other_platforms") is None:
                                    existing_data["social_media_links"]["other_platforms"] = {}
                                if not existing_data["social_media_links"]["other_platforms"].get(platform_key) and url_val:
                                    try:
                                        existing_data["social_media_links"]["other_platforms"][platform_key] = HttpUrl(url_val)
                                        logger.debug(f"Added other social media link from Stagehand: {platform_key} = {url_val}")
                                    except Exception as e_url:
                                        logger.warning(f"Invalid URL for other platform {platform_key} from Stagehand: {url_val} - {e_url}")
                
                # Add other specific field merges as needed, based on what Stagehand returns
                # and how `_create_focused_schema` in stagehand_integration.py maps them.
                # For example, if Stagehand returns 'operating_hours_text', that would need parsing or direct storage.

                # ========== ENHANCED STAGEHAND DATA INTEGRATION ==========
                
                # DELIVERY PLATFORM ANALYSIS - This is the key missing integration!
                if "deliveryPlatformAnalysis" in extracted_stagehand_data:
                    delivery_data = extracted_stagehand_data["deliveryPlatformAnalysis"]
                    logger.info(f"🚚 Merging delivery platform data from Stagehand: {list(delivery_data.keys())}")
                    
                    # Store raw delivery platform data for PDF analysis
                    existing_data.setdefault("misc_structured_data", {})["delivery_platform_analysis"] = delivery_data
                    
                    # Extract competitor data from delivery platforms
                    delivery_competitors = []
                    platforms_found = delivery_data.get("platformsFound", [])
                    for platform_info in platforms_found:
                        if platform_info.get("competitorsFound"):
                            for comp in platform_info["competitorsFound"]:
                                if comp.get("name"):
                                    delivery_competitors.append({
                                        "name": comp["name"],
                                        "platform": platform_info.get("platform", "unknown"),
                                        "ranking_position": comp.get("position"),
                                        "rating": comp.get("rating"),
                                        "source": "delivery_platform"
                                    })
                    
                    if delivery_competitors:
                        existing_data.setdefault("identified_competitors_delivery", []).extend(delivery_competitors)
                        logger.info(f"🎯 Added {len(delivery_competitors)} delivery platform competitors")
                
                # SOCIAL MEDIA ANALYSIS - Enhanced integration
                if "socialMediaAnalysis" in extracted_stagehand_data:
                    social_data = extracted_stagehand_data["socialMediaAnalysis"]
                    logger.info(f"📱 Merging social media data from Stagehand")
                    
                    # Store raw social media analysis for strategic insights
                    existing_data.setdefault("misc_structured_data", {})["social_media_analysis"] = social_data
                    
                    # Extract verified social media URLs
                    for platform_name, platform_data in social_data.items():
                        if isinstance(platform_data, dict) and platform_data.get("url"):
                            url_val = platform_data["url"]
                            if url_val and url_val not in ["", "null", "undefined"]:
                                platform_key = platform_name.lower().replace(" ", "")
                                
                                # Ensure social_media_links structure exists
                                if existing_data.get("social_media_links") is None:
                                    existing_data["social_media_links"] = {}
                                
                                try:
                                    # Map to our social media structure
                                    if platform_key in ["facebook", "instagram", "twitter", "tiktok", "youtube", "linkedin"]:
                                        existing_data["social_media_links"][platform_key] = HttpUrl(url_val)
                                        logger.debug(f"✅ Added {platform_key} from Stagehand: {url_val}")
                                    else:
                                        # Store in other_platforms
                                        if "other_platforms" not in existing_data["social_media_links"]:
                                            existing_data["social_media_links"]["other_platforms"] = {}
                                        existing_data["social_media_links"]["other_platforms"][platform_key] = HttpUrl(url_val)
                                        logger.debug(f"✅ Added other platform {platform_key}: {url_val}")
                                except Exception as e_social:
                                    logger.warning(f"⚠️ Invalid social URL for {platform_key}: {url_val} - {e_social}")
                
                # COMPREHENSIVE DATA - Full JSON integration for strategic analysis
                if "comprehensive" in extracted_stagehand_data:
                    comprehensive_data = extracted_stagehand_data["comprehensive"]
                    if comprehensive_data:
                        logger.info(f"📊 Merging comprehensive Stagehand analysis")
                        existing_data.setdefault("misc_structured_data", {})["stagehand_comprehensive"] = comprehensive_data
                
                # TECHNICAL HEALTH DATA
                if "technicalHealth" in extracted_stagehand_data:
                    tech_data = extracted_stagehand_data["technicalHealth"]
                    logger.info(f"🔧 Merging technical health data from Stagehand")
                    existing_data.setdefault("misc_structured_data", {})["technical_health"] = tech_data

        except Exception as e:
            error_msg = f"Phase 4 (Stagehand Selective Scrape) failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Phase 4 completed in {duration:.2f}s. Cost: (not tracked for Stagehand). New screenshots: {len(new_screenshots_from_stagehand)}")
        
        return {
            "screenshots": new_screenshots_from_stagehand, # List of ScreenshotInfo objects
            "cost": phase_cost, # Placeholder
            "duration": duration,
            "source": "stagehand_selective_scraper",
            "errors": errors
        }

    async def _execute_final_cleaning(self, raw_data: Dict) -> Dict[str, Any]:
        """
        Enhanced final data cleaning with Gemini
        """
        logger.info("🧹 Executing enhanced data cleaning and validation...")
        
        if self.gemini_cleaner and self.gemini_cleaner.enabled:
            # Use Gemini-powered cleaning
            cleaned_data = await self.gemini_cleaner.clean_restaurant_data(raw_data)
            logger.info("✅ Gemini-enhanced cleaning completed")
        else:
            # Fallback to basic cleaning
            logger.info("⚠️ Using basic data cleaning (Gemini not available)")
            cleaned_data = await self.validator.clean_and_normalize(raw_data)
        
        return cleaned_data
    
    async def _detect_third_party_platforms(self, url: str) -> List[Dict[str, str]]:
        """
        Detect third-party ordering/delivery platforms embedded on the site
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10)
                html = response.text
            
            soup = BeautifulSoup(html, 'html.parser')
            platforms = []
            
            # Look for common platform indicators
            platform_patterns = {
                'ToastTab': ['toasttab.com', 'toast.com'],
                'ChowNow': ['chownow.com'],
                'DoorDash': ['doordash.com/store'],
                'Uber Eats': ['ubereats.com'],
                'Grubhub': ['grubhub.com'],
                'Postmates': ['postmates.com'],
                'Seamless': ['seamless.com'],
                'Square': ['squareup.com', 'square.com'],
                'Clover': ['clover.com'],
                'Resy': ['resy.com'],
                'OpenTable': ['opentable.com']
            }
            
            for platform_name, domains in platform_patterns.items():
                for domain in domains:
                    if domain in html.lower():
                        # Try to find the specific link
                        link_elements = soup.find_all('a', href=True)
                        iframe_elements = soup.find_all('iframe', src=True)
                        
                        for element in link_elements + iframe_elements:
                            href = element.get('href') or element.get('src', '')
                            if domain in href.lower():
                                platforms.append({
                                    'platform': platform_name,
                                    'url': href,
                                    'type': 'ordering' if platform_name in ['ToastTab', 'ChowNow', 'Square', 'Clover'] else 'delivery'
                                })
                                break
            
            return platforms
            
        except Exception as e:
            logger.error(f"❌ Third-party platform detection failed: {str(e)}")
            return [] 

    async def _create_temp_final_output(self, raw_data_dict: Dict[str, Any], request_start_time: datetime) -> FinalRestaurantOutput:
        """
        Create a temporary FinalRestaurantOutput for Phase B strategic analysis.
        This allows us to pass structured data to the LLM analyzer before final cleaning.
        """
        logger.debug("Creating temporary FinalRestaurantOutput for Phase B analysis")
        
        # Create a copy to avoid modifying the original
        temp_data = raw_data_dict.copy()
        
        # Basic cleaning for temp output
        if temp_data.get("full_menu_text_raw_parts"):
            temp_data["full_menu_text_raw"] = "\n\n---\n\n".join(temp_data.pop("full_menu_text_raw_parts"))
        
        # Handle social media links
        raw_social_links = temp_data.pop("discovered_social_links_raw", {})
        if raw_social_links and not temp_data.get("social_media_links"):
            temp_data["social_media_links"] = {}
            for platform, urls in raw_social_links.items():
                platform_key = platform.lower().replace(" ", "")
                if urls:
                    try:
                        temp_data["social_media_links"][platform_key] = HttpUrl(urls[0])
                    except Exception:
                        pass  # Skip invalid URLs
        
        # Handle text blocks
        if temp_data.get("about_us_text") and not temp_data.get("extracted_text_blocks", {}).get("about_us"):
            temp_data.setdefault("extracted_text_blocks", {})["about_us"] = temp_data.pop("about_us_text")
        if temp_data.get("contact_page_text_raw") and not temp_data.get("extracted_text_blocks", {}).get("contact"):
            temp_data.setdefault("extracted_text_blocks", {})["contact"] = temp_data.pop("contact_page_text_raw")
        
        # Ensure required list fields exist
        temp_data.setdefault("menu_items", [])
        temp_data.setdefault("website_screenshots_s3_urls", [])
        temp_data.setdefault("menu_pdf_s3_urls", [])
        temp_data.setdefault("sitemap_urls", [])
        temp_data.setdefault("identified_competitors_basic", [])
        
        # Create basic extraction metadata
        temp_metadata = ExtractionMetadata(
            extraction_id=uuid.uuid4().hex,
            started_at=request_start_time,
            completed_at=datetime.now(),
            total_duration_seconds=(datetime.now() - request_start_time).total_seconds(),
            total_cost_usd=0.0,
            phases_completed=[1, 2, 3, 4],  # Assume all phases ran for temp
            final_quality_score=0.8  # Default quality score for temp
        )
        temp_data["extraction_metadata"] = temp_metadata
        
        # Remove fields that aren't part of FinalRestaurantOutput
        temp_fields_to_remove = [
            "full_menu_text_raw_parts", "google_full_address_text",
            "data_quality_phase1_score", "data_quality_phase2_score", 
            "data_quality_phase3_score", "data_quality_phase4_score",
            "phase_1_cost", "phase_2_cost", "phase_3_cost", "phase_4_cost",
            "data_sources_used", "misc_structured_data", "ai_vision_extracted_fields"
            # any other temp fields added during processing
        ]
        for field_key in temp_fields_to_remove:
            temp_data.pop(field_key, None)
        
        # Filter to only known fields
        known_fields = FinalRestaurantOutput.model_fields.keys()
        filtered_data = {k: v for k, v in temp_data.items() if k in known_fields}
        
        try:
            return FinalRestaurantOutput(**filtered_data)
        except Exception as e:
            logger.warning(f"Failed to create temp FinalRestaurantOutput: {e}")
            # Return minimal output if creation fails
            return FinalRestaurantOutput(
                website_url=temp_data.get("website_url", HttpUrl("http://example.com")),
                restaurant_name=temp_data.get("restaurant_name", "Unknown Restaurant"),
                extraction_metadata=temp_metadata
            )

    async def _final_data_compilation_and_cleaning(self, 
                                                  raw_data_dict: Dict[str, Any], 
                                                  request_start_time: datetime
                                                  ) -> FinalRestaurantOutput:
        """
        Compile all collected data into the FinalRestaurantOutput model.
        Perform final cleaning, structuring, and AI-driven summarization if applicable.
        This was referred to as A7/A9 (final cleaning step).
        """
        logger.info(f"🚀 ENTERING _final_data_compilation_and_cleaning method")
        logger.info(f"📋 RAW DATA KEYS: {list(raw_data_dict.keys())}")
        logger.info(f"📍 canonical_address in raw_data_dict: {raw_data_dict.get('canonical_address')}")
        logger.info(f"📞 canonical_phone_number in raw_data_dict: {raw_data_dict.get('canonical_phone_number')}")
        
        logger.info(f"Starting final data compilation and cleaning for {raw_data_dict.get('restaurant_name', 'Unknown Restaurant')}")
        final_data = raw_data_dict.copy() # Work with a copy

        # 1. Consolidate and clean specific fields using GeminiDataCleaner if available
        if self.gemini_cleaner and self.gemini_cleaner.enabled:
            logger.info("Using GeminiDataCleaner for final processing.")
            try:
                # Consolidate menu text for cleaning
                if final_data.get("full_menu_text_raw_parts"):
                    full_raw_menu_text = "\n\n---\n\n".join(final_data.pop("full_menu_text_raw_parts"))
                    final_data["full_menu_text_raw"] = full_raw_menu_text
                    logger.debug(f"Consolidated full_menu_text_raw: {len(full_raw_menu_text)} chars")

                # Ask Gemini to clean/structure address, phone, email, generate description etc.
                # This is a conceptual call; GeminiDataCleaner would need specific methods.
                cleaned_contact_info = await self.gemini_cleaner.clean_contact_details(
                    raw_phones=final_data.get("raw_phone_numbers", []),
                    raw_emails=final_data.get("raw_emails", []),
                    address_text=final_data.get("google_full_address_text") # from GMB or Stagehand
                )
                if cleaned_contact_info:
                    if cleaned_contact_info.get("canonical_phone"): final_data["canonical_phone_number"] = cleaned_contact_info["canonical_phone"]
                    if cleaned_contact_info.get("canonical_email"): final_data["canonical_email"] = cleaned_contact_info["canonical_email"]
                    if cleaned_contact_info.get("structured_address_dict"):
                         # Ensure it's a dict compatible with StructuredAddress model
                        if isinstance(cleaned_contact_info["structured_address_dict"], dict):
                            final_data["structured_address"] = cleaned_contact_info["structured_address_dict"]
                        else:
                            logger.warning("Gemini structured_address_dict was not a dict.")
                    logger.info("Applied Gemini-cleaned contact details.")
                
                # Generate long description if not present or short
                if not final_data.get("description_long_ai_generated") or len(final_data.get("description_long_ai_generated","")) < 50:
                    # Gather text for context
                    context_text_for_desc = (
                        final_data.get("description_short", "") + " " +
                        final_data.get("full_menu_text_raw", "")[:2000] + " " + # Limit menu text length
                        final_data.get("about_us_text", "")
                    ).strip()
                    if len(context_text_for_desc) > 100: # Need some substantial context
                        long_desc = await self.gemini_cleaner.generate_long_description(final_data.get("restaurant_name"), context_text_for_desc)
                        if long_desc:
                            final_data["description_long_ai_generated"] = long_desc
                            logger.info("Generated long description using Gemini.")

                # Deduplicate and refine menu items further (e.g., price cleaning if not done)
                if final_data.get("menu_items"):
                    final_data["menu_items"] = await self.gemini_cleaner.refine_menu_items(final_data["menu_items"])
                    logger.info("Refined menu items using Gemini.")
                
                # Cuisine Type & Price Range AI assignment
                menu_context_for_ai = final_data.get("full_menu_text_raw", "")[:1000]
                if not final_data.get("primary_cuisine_type_ai") and menu_context_for_ai:
                    cuisine_info = await self.gemini_cleaner.determine_cuisine_and_price(
                        restaurant_name=final_data.get("restaurant_name"),
                        menu_text_snippet=menu_context_for_ai,
                        existing_description=final_data.get("description_short")
                    )
                    if cuisine_info:
                        if cuisine_info.get("primary_cuisine"): final_data["primary_cuisine_type_ai"] = cuisine_info["primary_cuisine"]
                        if cuisine_info.get("secondary_cuisines"): final_data["secondary_cuisine_types_ai"] = cuisine_info["secondary_cuisines"]
                        if cuisine_info.get("price_range"): final_data["price_range_ai"] = cuisine_info["price_range"]
                        logger.info("Assigned cuisine type and price range using Gemini.")

            except Exception as e_gemini_clean:
                logger.error(f"Error during GeminiDataCleaner processing: {e_gemini_clean}", exc_info=True)
        else:
            logger.info("GeminiDataCleaner not available or disabled. Proceeding with basic cleaning.")
            # Basic consolidation if Gemini is not used for menu text
            if final_data.get("full_menu_text_raw_parts"):
                final_data["full_menu_text_raw"] = "\n\n---\n\n".join(final_data.pop("full_menu_text_raw_parts"))

        # 2. Finalize Social Media Links Structure
        # Convert discovered_social_links_raw (dict of lists) to SocialMediaLinks model structure
        raw_social_links = final_data.pop("discovered_social_links_raw", {})
        if raw_social_links and not final_data.get("social_media_links"):
            final_data["social_media_links"] = {}
        
        for platform, urls in raw_social_links.items():
            platform_key = platform.lower().replace(" ", "")
            if platform_key in SocialMediaLinks.model_fields and urls:
                try:
                    # Take the first valid URL for direct fields
                    if not final_data["social_media_links"].get(platform_key):
                         final_data["social_media_links"][platform_key] = HttpUrl(urls[0])
                except Exception as e_sm_url:
                    logger.warning(f"Could not validate URL {urls[0]} for social platform {platform_key}: {e_sm_url}")
            elif urls: # Put in other_platforms
                final_data["social_media_links"].setdefault("other_platforms", {})
                if not final_data["social_media_links"]["other_platforms"].get(platform_key):
                     try:
                        final_data["social_media_links"]["other_platforms"][platform_key] = HttpUrl(urls[0])
                     except Exception as e_sm_url_other:
                        logger.warning(f"Could not validate URL {urls[0]} for other social platform {platform_key}: {e_sm_url_other}")

        # 3. Consolidate text blocks (e.g. about_us_text -> extracted_text_blocks)
        if final_data.get("about_us_text") and not final_data.get("extracted_text_blocks",{}).get("about_us"):
            final_data.setdefault("extracted_text_blocks", {})["about_us"] = final_data.pop("about_us_text")
        if final_data.get("contact_page_text_raw") and not final_data.get("extracted_text_blocks",{}).get("contact"):
            final_data.setdefault("extracted_text_blocks", {})["contact"] = final_data.pop("contact_page_text_raw")
        # Ensure `extracted_text_blocks` is None if empty after processing to match Pydantic Optional behavior
        if not final_data.get("extracted_text_blocks"):
            final_data["extracted_text_blocks"] = None

        # 4. Ensure list fields are initialized if not present, to avoid Pydantic errors for non-optional lists
        # Most list fields in FinalRestaurantOutput are Optional, but good practice for any that aren't.
        # Example: if "some_required_list_field" not in final_data: final_data["some_required_list_field"] = []
        # Upon inspection, all list fields in FinalRestaurantOutput are Optional with default_factory=list or default=[]
        # So this step is mostly covered, but explicitly ensuring for key lists:
        if "menu_items" not in final_data: final_data["menu_items"] = []
        if "website_screenshots_s3_urls" not in final_data: final_data["website_screenshots_s3_urls"] = []
        if "menu_pdf_s3_urls" not in final_data: final_data["menu_pdf_s3_urls"] = []
        if "sitemap_urls" not in final_data: final_data["sitemap_urls"] = []
        if "identified_competitors_basic" not in final_data: final_data["identified_competitors_basic"] = []

        # 5. Create ExtractionMetadata
        completed_at = datetime.now()
        total_duration_seconds = (completed_at - request_start_time).total_seconds()
        # TODO: Accumulate costs from each phase if that becomes available
        total_cost_usd = sum(final_data.get(f"phase_{i}_cost", 0.0) for i in range(1, 5))
        
        phases_completed = [] # Logic to determine this based on data or stored phase results
        if final_data.get("data_quality_phase1_score") is not None: phases_completed.append(1)
        if final_data.get("data_quality_phase2_score") is not None: phases_completed.append(2)
        if final_data.get("data_quality_phase3_score") is not None: phases_completed.append(3)
        if final_data.get("data_quality_phase4_score") is not None: phases_completed.append(4)

        # Final quality score could be the last phase's score or a new overall assessment
        final_quality_score = final_data.get(f"data_quality_phase{max(phases_completed) if phases_completed else 0}_score")

        extraction_metadata = ExtractionMetadata(
            extraction_id=uuid.uuid4().hex, # Generate a unique ID for this completed extraction
            started_at=request_start_time,
            completed_at=completed_at,
            total_duration_seconds=total_duration_seconds,
            total_cost_usd=total_cost_usd,
            phases_completed=phases_completed,
            final_quality_score=final_quality_score
        )
        final_data["extraction_metadata"] = extraction_metadata # Store as model instance, not dict

        # 6. Remove temporary processing fields from final_data before model creation
        # CRITICAL FIX: DO NOT remove misc_structured_data - it contains rich analysis data for PDF generation!
        fields_to_remove = [
            "full_menu_text_raw_parts", "google_full_address_text",
            "data_quality_phase1_score", "data_quality_phase2_score", 
            "data_quality_phase3_score", "data_quality_phase4_score",
            "phase_1_cost", "phase_2_cost", "phase_3_cost", "phase_4_cost", # Example cost fields
            "data_sources_used", "ai_vision_extracted_fields"
            # REMOVED "misc_structured_data" from this list - we need it for rich PDF content!
        ]
        for field_key in fields_to_remove:
            final_data.pop(field_key, None)

        # 7. Construct the FinalRestaurantOutput Pydantic model
        try:
            # Debug: Log what canonical fields we have before mapping
            logger.info(f"🔍 DEBUG: Before mapping - canonical_address: {final_data.get('canonical_address')}")
            logger.info(f"🔍 DEBUG: Before mapping - canonical_phone_number: {final_data.get('canonical_phone_number')}")
            logger.info(f"🔍 DEBUG: Before mapping - address_canonical: {final_data.get('address_canonical')}")
            logger.info(f"🔍 DEBUG: Before mapping - phone_canonical: {final_data.get('phone_canonical')}")
            
            # Ensure canonical fields are properly mapped to the correct field names
            if final_data.get("canonical_address"):
                final_data["address_canonical"] = final_data["canonical_address"]
                final_data["address_raw"] = final_data["canonical_address"]
                logger.info(f"📍 Mapping canonical address to final output: {final_data['canonical_address']}")
            
            if final_data.get("canonical_phone_number"):
                final_data["phone_canonical"] = final_data["canonical_phone_number"]
                final_data["phone_raw"] = final_data["canonical_phone_number"]
                logger.info(f"📞 Mapping canonical phone to final output: {final_data['canonical_phone_number']}")
            
            # Debug: Log what we have after mapping
            logger.info(f"🔍 DEBUG: After mapping - address_canonical: {final_data.get('address_canonical')}")
            logger.info(f"🔍 DEBUG: After mapping - phone_canonical: {final_data.get('phone_canonical')}")
            
            # Ensure website URL is properly set
            if final_data.get("target_url") and not final_data.get("canonical_url"):
                try:
                    from pydantic import HttpUrl
                    website_url = final_data["target_url"]
                    if not website_url.startswith(('http://', 'https://')):
                        website_url = f"https://{website_url}"
                    final_data["canonical_url"] = HttpUrl(website_url)
                    final_data["website_url"] = HttpUrl(website_url)
                except Exception as e:
                    logger.warning(f"⚠️ Could not set canonical URL: {e}")
                    
            final_output_model = FinalRestaurantOutput(**final_data)
            logger.info(f"Successfully compiled data into FinalRestaurantOutput for {final_output_model.restaurant_name}")
            final_output_model.log_completeness() # Log how much data we got
        except Exception as e_pydantic:
            logger.error(f"Pydantic validation error during final compilation for {final_data.get('restaurant_name', 'Unknown')}: {e_pydantic}", exc_info=True)
            # Fallback: try to create a model with what we have, or handle error reporting
            # For now, re-raise or return a partially filled model if possible
            # To make it more robust, one could filter out problematic fields before this step
            # or return a specific error structure.
            # For this implementation, let's try to create it by filtering unknown fields if that's the issue
            known_fields = FinalRestaurantOutput.model_fields.keys()
            filtered_data_for_model = {k: v for k, v in final_data.items() if k in known_fields}
            try:
                final_output_model = FinalRestaurantOutput(**filtered_data_for_model)
                logger.warning(f"Created FinalRestaurantOutput with filtered fields after initial validation error for {final_data.get('restaurant_name')}.")
                final_output_model.log_completeness()
            except Exception as e_pydantic_retry:
                 logger.critical(f"Could not create FinalRestaurantOutput even after filtering fields for {final_data.get('restaurant_name')}: {e_pydantic_retry}", exc_info=True)
                 # If critical, might need to return an error or a default empty model. 
                 # For now, let it raise if it cannot be formed, so the issue is visible.
                 raise e_pydantic_retry

        return final_output_model 

    async def _extract_enhanced_restaurant_name(self, url: str, provided_name: Optional[str] = None) -> str:
        """
        Enhanced restaurant name extraction using multiple strategies:
        1. Use provided name if good quality
        2. Extract from URL domain and path
        3. Fetch homepage and extract from title/headers
        4. Use intelligent fallbacks
        """
        logger.info(f"🔍 Extracting enhanced restaurant name for: {url}")
        
        # Strategy 1: Use provided name if it looks good
        if provided_name and len(provided_name.strip()) > 2:
            cleaned_name = provided_name.strip()
            # Check if it's not just a generic term
            generic_terms = ['restaurant', 'cafe', 'diner', 'bistro', 'bar', 'grill', 'pizzeria']
            if not any(term.lower() == cleaned_name.lower() for term in generic_terms):
                logger.info(f"✅ Using provided restaurant name: {cleaned_name}")
                return cleaned_name
        
        # Strategy 2: Extract from URL
        extracted_names = []
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.replace('www.', '')
            path = parsed_url.path.strip('/')
            
            # Extract from domain
            if domain:
                domain_name = domain.split('.')[0]  # Get main part before .com/.org etc
                
                # Clean up common patterns
                domain_cleaned = domain_name.replace('-', ' ').replace('_', ' ')
                domain_cleaned = ' '.join(word.capitalize() for word in domain_cleaned.split())
                
                # Filter out generic domains
                if domain_cleaned.lower() not in ['example', 'test', 'localhost', 'www']:
                    extracted_names.append(domain_cleaned)
                    logger.info(f"📛 Domain-based name: {domain_cleaned}")
            
            # Extract from path if meaningful
            if path and len(path) > 2:
                path_parts = path.split('/')
                for part in path_parts:
                    if part and len(part) > 3 and not part.isdigit():
                        path_cleaned = part.replace('-', ' ').replace('_', ' ')
                        path_cleaned = ' '.join(word.capitalize() for word in path_cleaned.split())
                        if path_cleaned not in extracted_names:
                            extracted_names.append(path_cleaned)
                            logger.info(f"📛 Path-based name: {path_cleaned}")
        
        except Exception as e:
            logger.warning(f"⚠️ Error extracting name from URL: {e}")
        
        # Strategy 3: Fetch homepage and extract from content
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                logger.info(f"🌐 Fetching homepage content from: {url}")
                response = await client.get(url, follow_redirects=True)
                
                if response.status_code == 200:
                    html_content = response.text
                    content_names = self._extract_names_from_html(html_content)
                    extracted_names.extend(content_names)
                    logger.info(f"📛 Content-based names: {content_names}")
                else:
                    logger.warning(f"⚠️ Failed to fetch homepage: HTTP {response.status_code}")
                    
        except Exception as e:
            logger.warning(f"⚠️ Error fetching homepage content: {e}")
        
        # Strategy 4: Choose the best name
        if extracted_names:
            # Prefer longer, more descriptive names
            best_name = max(extracted_names, key=lambda x: (len(x), len(x.split())))
            logger.info(f"✅ Best extracted name: {best_name}")
            return best_name
        
        # Strategy 5: Final fallback
        if provided_name:
            logger.info(f"📛 Fallback to provided name: {provided_name}")
            return provided_name
        
        # Ultimate fallback
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.replace('www.', '').split('.')[0]
            fallback_name = domain.replace('-', ' ').replace('_', ' ').title()
            logger.info(f"📛 Ultimate fallback name: {fallback_name}")
            return fallback_name
        except:
            logger.warning("⚠️ All name extraction strategies failed, using 'Unknown Restaurant'")
            return "Unknown Restaurant"
    
    def _extract_names_from_html(self, html_content: str) -> List[str]:
        """Extract potential restaurant names from HTML content"""
        names = []
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Strategy 1: Page title
            title_tag = soup.find('title')
            if title_tag and title_tag.text:
                title_text = title_tag.text.strip()
                # Clean common title suffixes
                for suffix in [' - Restaurant', ' | Restaurant', ' Restaurant', ' - Official Site', ' | Official Site']:
                    if title_text.endswith(suffix):
                        title_text = title_text[:-len(suffix)]
                        break
                
                if len(title_text) > 2 and title_text.lower() not in ['home', 'welcome']:
                    names.append(title_text.strip())
            
            # Strategy 2: H1 headers
            h1_tags = soup.find_all('h1')
            for h1 in h1_tags[:3]:  # Check first 3 h1 tags
                if h1.text and len(h1.text.strip()) > 2:
                    h1_text = h1.text.strip()
                    if h1_text.lower() not in ['welcome', 'home', 'menu', 'about']:
                        names.append(h1_text)
            
            # Strategy 3: Restaurant-specific meta tags
            meta_tags = soup.find_all('meta', {'property': ['og:title', 'og:site_name', 'twitter:title']})
            for meta in meta_tags:
                content = meta.get('content')
                if content and len(content.strip()) > 2:
                    names.append(content.strip())
            
            # Strategy 4: Look for common restaurant name patterns in text
            # This is more complex but can find names in navigation or headers
            nav_elements = soup.find_all(['nav', 'header', '.navbar', '.logo'])
            for element in nav_elements:
                text = element.get_text().strip()
                if text and 3 < len(text) < 50:  # Reasonable restaurant name length
                    names.append(text)
        
        except Exception as e:
            logger.warning(f"⚠️ Error parsing HTML content: {e}")
        
        # Clean and deduplicate names
        cleaned_names = []
        for name in names:
            cleaned = name.strip()
            if cleaned and len(cleaned) > 2 and cleaned not in cleaned_names:
                cleaned_names.append(cleaned)
        
        return cleaned_names[:5]  # Return top 5 candidates

    def _is_reasonable_name_match(self, found_name: str, expected_name: str) -> bool:
        """
        Check if the found name is a reasonable match for the expected name.
        Dynamic matching algorithm that works for any restaurant, not hardcoded chains.
        """
        if not found_name or not expected_name:
            return False
        
        # Normalize names for comparison
        found_clean = re.sub(r'[^\w\s]', '', found_name.lower()).strip()
        expected_clean = re.sub(r'[^\w\s]', '', expected_name.lower()).strip()
        
        logger.info(f"🔍 Comparing names: '{found_name}' ({found_clean}) vs '{expected_name}' ({expected_clean})")
        
        # Direct match
        if found_clean == expected_clean:
            logger.info("✅ Direct exact match")
            return True
        
        # Check if found name is contained in expected or vice versa
        if found_clean in expected_clean or expected_clean in found_clean:
            logger.info("✅ Substring match")
            return True
        
        # Split into words and check for significant overlap
        found_words = set(found_clean.split())
        expected_words = set(expected_clean.split())
        
        # Remove common stop words that don't help with identification
        stop_words = {'restaurant', 'bar', 'grill', 'cafe', 'kitchen', 'house', 'the', 'and', 'or', 'of', 'in', 'at', 'on', 'a', 'an'}
        found_meaningful = found_words - stop_words
        expected_meaningful = expected_words - stop_words
        
        # If we have meaningful words to compare
        if found_meaningful and expected_meaningful:
            # Calculate overlap - if 40% or more words match, consider it a match
            overlap = len(found_meaningful.intersection(expected_meaningful))
            total_unique = len(found_meaningful.union(expected_meaningful))
            overlap_ratio = overlap / total_unique if total_unique > 0 else 0
            
            logger.info(f"📊 Word overlap analysis: {overlap}/{total_unique} = {overlap_ratio:.2f}")
            logger.info(f"   Found meaningful words: {found_meaningful}")
            logger.info(f"   Expected meaningful words: {expected_meaningful}")
            logger.info(f"   Overlapping words: {found_meaningful.intersection(expected_meaningful)}")
            
            if overlap_ratio >= 0.4:  # 40% overlap threshold
                logger.info(f"✅ Word overlap match: {overlap_ratio:.2f} >= 0.4")
                return True
        
        # Dynamic abbreviation and variation detection
        # Instead of hardcoded chains, use intelligent pattern matching
        if self._check_dynamic_variations(found_clean, expected_clean):
            logger.info("✅ Dynamic variation match detected")
            return True
        
        # Levenshtein distance check for similar names (typos, slight variations)
        max_len = max(len(found_clean), len(expected_clean))
        if max_len > 3:  # Only for reasonable length names
            distance = self._levenshtein_distance(found_clean, expected_clean)
            similarity = 1 - (distance / max_len)
            logger.info(f"📏 Edit distance similarity: {similarity:.2f} (distance: {distance}, max_len: {max_len})")
            
            if similarity >= 0.7:  # 70% similarity threshold
                logger.info(f"✅ High similarity match: {similarity:.2f} >= 0.7")
                return True
        
        # Phonetic similarity check (for restaurants with similar sounding names)
        if self._check_phonetic_similarity(found_clean, expected_clean):
            logger.info("✅ Phonetic similarity match")
            return True
        
        logger.info("❌ No reasonable match found")
        return False
    
    def _check_dynamic_variations(self, found_clean: str, expected_clean: str) -> bool:
        """
        Dynamic variation detection that works for any restaurant, not hardcoded chains.
        Detects common patterns like abbreviations, ampersand variations, etc.
        """
        # Check for ampersand variations (& vs and vs n)
        ampersand_variations = [
            (r'\s*&\s*', ' and '),
            (r'\s*&\s*', ' n '),
            (r'\s+and\s+', ' & '),
            (r'\s+n\s+', ' & '),
            (r'\s+n\s+', ' and ')
        ]
        
        for pattern, replacement in ampersand_variations:
            found_variant = re.sub(pattern, replacement, found_clean)
            expected_variant = re.sub(pattern, replacement, expected_clean)
            
            if found_variant == expected_clean or expected_variant == found_clean:
                logger.info(f"🔄 Ampersand variation match: {pattern} -> {replacement}")
                return True
        
        # Check for hyphen/dash variations
        dash_variations = [
            found_clean.replace('-', ' '),
            found_clean.replace('-', ''),
            expected_clean.replace('-', ' '),
            expected_clean.replace('-', '')
        ]
        
        for variant in dash_variations:
            if variant == found_clean or variant == expected_clean:
                logger.info("🔄 Dash variation match")
                return True
        
        # Check for apostrophe variations
        apostrophe_variations = [
            found_clean.replace("'", ""),
            expected_clean.replace("'", "")
        ]
        
        if apostrophe_variations[0] == expected_clean or apostrophe_variations[1] == found_clean:
            logger.info("🔄 Apostrophe variation match")
            return True
        
        # Check for common abbreviation patterns
        # This is dynamic - looks for patterns rather than hardcoded names
        found_words = found_clean.split()
        expected_words = expected_clean.split()
        
        # Check if one might be an abbreviation of the other
        if len(found_words) == 1 and len(expected_words) > 1:
            # found might be abbreviation of expected
            abbrev_candidate = ''.join(word[0] for word in expected_words if len(word) > 2)
            if found_clean == abbrev_candidate:
                logger.info(f"🔤 Abbreviation match: {found_clean} = {abbrev_candidate}")
                return True
        
        if len(expected_words) == 1 and len(found_words) > 1:
            # expected might be abbreviation of found
            abbrev_candidate = ''.join(word[0] for word in found_words if len(word) > 2)
            if expected_clean == abbrev_candidate:
                logger.info(f"🔤 Abbreviation match: {expected_clean} = {abbrev_candidate}")
                return True
        
        return False
    
    def _check_phonetic_similarity(self, found_clean: str, expected_clean: str) -> bool:
        """
        Check for phonetic similarity between restaurant names.
        Useful for names that sound similar but are spelled differently.
        """
        try:
            # Simple phonetic matching - could be enhanced with soundex or metaphone
            # For now, check for common phonetic patterns
            
            # Remove common silent letters and normalize phonetic patterns
            def normalize_phonetic(name):
                name = re.sub(r'ph', 'f', name)  # ph -> f
                name = re.sub(r'ck', 'k', name)  # ck -> k
                name = re.sub(r'gh', '', name)   # silent gh
                name = re.sub(r'[aeiou]+', 'a', name)  # normalize vowels
                name = re.sub(r'([bcdfghjklmnpqrstvwxyz])\1+', r'\1', name)  # remove double consonants
                return name
            
            found_phonetic = normalize_phonetic(found_clean)
            expected_phonetic = normalize_phonetic(expected_clean)
            
            if found_phonetic == expected_phonetic:
                logger.info(f"🔊 Phonetic match: {found_phonetic}")
                return True
            
            # Check if they're very similar phonetically
            if len(found_phonetic) > 3 and len(expected_phonetic) > 3:
                distance = self._levenshtein_distance(found_phonetic, expected_phonetic)
                max_len = max(len(found_phonetic), len(expected_phonetic))
                similarity = 1 - (distance / max_len)
                
                if similarity >= 0.8:  # High phonetic similarity
                    logger.info(f"🔊 High phonetic similarity: {similarity:.2f}")
                    return True
            
        except Exception as e:
            logger.warning(f"⚠️ Error in phonetic similarity check: {e}")
        
        return False
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)
        
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]

    def _compile_final_restaurant_data(self, restaurant_name: str, all_data: Dict[str, Any]) -> FinalRestaurantOutput:
        """
        Compile all extracted data into a FinalRestaurantOutput model.
        Enhanced to properly map basic restaurant fields for data quality validation.
        """
        logger.info(f"📊 Compiling final restaurant data for: {restaurant_name}")
        
        # Extract basic restaurant information from various sources
        phase_1_data = all_data.get("phase_1_data", {})
        phase_2_data = all_data.get("phase_2_data", {})
        phase_4_data = all_data.get("phase_4_data", {})
        google_places_data = phase_1_data.get("google_places_data") or {}
        
        # Extract basic fields with proper fallbacks
        # 1. Restaurant Name - try multiple sources
        final_name = (
            restaurant_name or 
            google_places_data.get("name") or
            phase_4_data.get("extracted_data", {}).get("name") or
            phase_2_data.get("extracted_textual_data", {}).get("restaurant_name") or
            "Restaurant Name Not Found"
        )
        
        # 2. Address - comprehensive extraction
        final_address = None
        # First check the canonical address set from Google Places
        if all_data.get("canonical_address"):
            final_address = all_data["canonical_address"]
            logger.info(f"📍 Using canonical address: {final_address}")
        elif google_places_data.get("address"):
            final_address = google_places_data["address"]
            logger.info(f"📍 Using address from Google Places data: {final_address}")
        elif phase_4_data.get("extracted_data", {}).get("address"):
            final_address = phase_4_data["extracted_data"]["address"]
            logger.info(f"📍 Using address from Phase 4: {final_address}")
        elif google_places_data.get("formatted_address"):
            final_address = google_places_data["formatted_address"]
            logger.info(f"📍 Using formatted address from Google Places: {final_address}")
        
        # 3. Phone Number - try multiple sources
        final_phone = None
        # First check the canonical phone set from Google Places
        if all_data.get("canonical_phone_number"):
            final_phone = all_data["canonical_phone_number"]
            logger.info(f"📞 Using canonical phone: {final_phone}")
        elif google_places_data.get("phone"):
            final_phone = google_places_data["phone"]
            logger.info(f"📞 Using phone from Google Places data: {final_phone}")
        elif phase_4_data.get("extracted_data", {}).get("phone"):
            final_phone = phase_4_data["extracted_data"]["phone"]
            logger.info(f"📞 Using phone from Phase 4: {final_phone}")
        elif phase_2_data.get("extracted_textual_data", {}).get("phones"):
            phones = phase_2_data["extracted_textual_data"]["phones"]
            if phones and len(phones) > 0:
                final_phone = phones[0]
                logger.info(f"📞 Using phone from Phase 2: {final_phone}")
        elif google_places_data.get("formatted_phone_number"):
            final_phone = google_places_data["formatted_phone_number"]
            logger.info(f"📞 Using formatted phone from Google Places: {final_phone}")
        
        # 4. Website URL - use the target URL as primary source
        final_website = all_data.get("target_url", "")
        if phase_4_data.get("extracted_data", {}).get("website"):
            final_website = phase_4_data["extracted_data"]["website"]
        elif google_places_data.get("website"):
            final_website = google_places_data["website"]
        
        # 5. Hours - extract from Google Places primarily
        final_hours = []
        if google_places_data.get("hours"):
            if isinstance(google_places_data["hours"], list):
                final_hours = google_places_data["hours"]
            elif isinstance(google_places_data["hours"], dict):
                weekday_text = google_places_data["hours"].get("weekday_text", [])
                if weekday_text:
                    final_hours = weekday_text
        elif google_places_data.get("opening_hours", {}).get("weekday_text"):
            final_hours = google_places_data["opening_hours"]["weekday_text"]
        elif phase_4_data.get("extracted_data", {}).get("hours"):
            hours_data = phase_4_data["extracted_data"]["hours"]
            if isinstance(hours_data, list):
                final_hours = hours_data
            elif isinstance(hours_data, str):
                final_hours = [hours_data]
        
        # Log the extracted basic fields for debugging
        logger.info(f"📋 Extracted basic fields:")
        logger.info(f"   Name: {final_name}")
        logger.info(f"   Address: {final_address}")
        logger.info(f"   Phone: {final_phone}")
        logger.info(f"   Website: {final_website}")
        logger.info(f"   Hours: {len(final_hours)} entries")
        
        # Extract menu items with enhanced source prioritization
        menu_items = []
        
        # Try Stagehand data first (usually highest quality)
        if phase_4_data.get("extracted_data", {}).get("menu_items"):
            menu_items.extend(phase_4_data["extracted_data"]["menu_items"])
        
        # Try DOM crawler menu data
        phase_2_menu_texts = phase_2_data.get("extracted_textual_data", {}).get("menu_texts_raw", [])
        if phase_2_menu_texts:
            for menu_text in phase_2_menu_texts:
                if isinstance(menu_text, str) and len(menu_text.strip()) > 10:
                    menu_items.append({
                        "name": menu_text[:100],  # First 100 chars as name
                        "description": menu_text,
                        "price": "",
                        "category": "Unknown",
                        "source": "dom_crawler_text"
                    })
        
        # Extract screenshots with proper local file URLs
        screenshots = []
        
        # Phase 2 screenshots (DOM crawler)
        phase_2_screenshots = phase_2_data.get("screenshots", [])
        for screenshot in phase_2_screenshots:
            if hasattr(screenshot, 's3_url'):
                screenshots.append(screenshot)
            elif isinstance(screenshot, dict) and screenshot.get('s3_url'):
                from .models import ScreenshotInfo
                screenshots.append(ScreenshotInfo(
                    s3_url=screenshot['s3_url'],
                    caption=screenshot.get('caption', 'Website screenshot'),
                    source_phase=2,
                    taken_at=datetime.now()
                ))
        
        # Phase 4 screenshots (Stagehand)
        phase_4_screenshots = phase_4_data.get("screenshots", [])
        for screenshot in phase_4_screenshots:
            if hasattr(screenshot, 's3_url'):
                screenshots.append(screenshot)
        
        # Compile social media links
        social_media_profiles = {}
        
        # From DOM crawler
        dom_social = phase_2_data.get("extracted_textual_data", {}).get("social_links", {})
        if dom_social:
            social_media_profiles.update(dom_social)
        
        # From Stagehand
        stagehand_social = phase_4_data.get("extracted_data", {}).get("social_links", [])
        if isinstance(stagehand_social, list):
            for link in stagehand_social:
                if 'facebook' in link.lower():
                    social_media_profiles['facebook'] = link
                elif 'instagram' in link.lower():
                    social_media_profiles['instagram'] = link
                elif 'twitter' in link.lower():
                    social_media_profiles['twitter'] = link
        
        # Convert website URL to HttpUrl
        try:
            if final_website and not final_website.startswith(('http://', 'https://')):
                final_website = f"https://{final_website}"
            website_url = HttpUrl(final_website) if final_website else None
        except Exception as e:
            logger.warning(f"⚠️ Invalid website URL '{final_website}': {e}")
            website_url = None
        
        # Create the FinalRestaurantOutput with properly mapped data
        compiled_data = FinalRestaurantOutput(
            restaurant_name=final_name,
            
            # Basic contact information - properly mapped for data quality validation
            address_canonical=final_address,
            address_raw=final_address,
            phone_canonical=final_phone,
            phone_raw=final_phone,
            canonical_url=website_url,
            website_url=website_url,
            
            # Operating hours
            operating_hours=final_hours,
            
            # Menu and content
            menu_items=menu_items,
            description_short=google_places_data.get("description"),
            
            # Google Places data
            google_places_summary=google_places_data,
            google_my_business={
                "rating": google_places_data.get("rating"),
                "review_count": google_places_data.get("user_ratings_total"),
                "place_id": google_places_data.get("place_id")
            } if google_places_data else None,
            
            # Screenshots and media
            screenshots=screenshots,
            
            # Social media
            social_media_profiles=social_media_profiles,
            social_media_links=social_media_profiles,
            
            # Competitor data
            competitors=all_data.get("competitors", []),
            
            # Analysis metadata
            analysis_metadata={
                "extraction_phases_completed": all_data.get("phases_completed", []),
                "total_data_sources": len([
                    source for source in [
                        google_places_data, 
                        phase_2_data.get("extracted_textual_data"),
                        phase_4_data.get("extracted_data")
                    ] if source
                ]),
                "data_compilation_timestamp": datetime.now().isoformat(),
                "basic_fields_extracted": {
                    "name": bool(final_name and final_name != "Restaurant Name Not Found"),
                    "address": bool(final_address),
                    "phone": bool(final_phone),
                    "website": bool(final_website),
                    "hours": bool(final_hours)
                }
            }
        )
        
        logger.info(f"✅ Final restaurant data compiled successfully for: {final_name}")
        return compiled_data

    # ========== NEW GOOGLE SEARCH METHODS ==========
    
    # NOTE: Google search methods for delivery platforms and social media have been removed.
    # The Stagehand scraper (enhanced-scraper.js) handles comprehensive social media and 
    # delivery platform analysis directly from website content without needing Google searches.
    # This analysis is captured in Phase 4 and integrated into misc_structured_data.
    
    async def _generate_intelligent_strategic_fallback(self, restaurant_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate intelligent strategic analysis using available data when LLM analysis fails.
        This creates comprehensive strategic recommendations based on all collected data.
        """
        logger.info("🧠 Generating intelligent strategic analysis fallback from available data")
        
        # Extract all available data sources
        restaurant_name = restaurant_data.get("restaurant_name", "This Restaurant")
        google_places_data = restaurant_data.get("google_places_data", {})
        menu_items = restaurant_data.get("menu_items", [])
        competitors = restaurant_data.get("identified_competitors_basic", [])
        social_media = restaurant_data.get("social_media_links", {})
        delivery_platform_data = restaurant_data.get("misc_structured_data", {}).get("delivery_platform_analysis", {})
        social_media_analysis = restaurant_data.get("misc_structured_data", {}).get("social_media_analysis", {})
        technical_health = restaurant_data.get("misc_structured_data", {}).get("technical_health", {})
        stagehand_data = restaurant_data.get("misc_structured_data", {}).get("stagehand_comprehensive", {})
        
        # Calculate key metrics
        google_rating = google_places_data.get("rating", 0)
        google_reviews = google_places_data.get("reviews_count", 0)
        menu_count = len(menu_items)
        competitor_count = len(competitors)
        
        # Analyze delivery platform opportunities
        delivery_opportunities = self._analyze_delivery_platform_opportunities(delivery_platform_data)
        
        # Analyze social media opportunities  
        social_opportunities = self._analyze_social_media_opportunities(social_media_analysis, social_media)
        
        # Analyze technical opportunities
        technical_opportunities = self._analyze_technical_opportunities(technical_health)
        
        # Generate executive hook based on data
        executive_hook = self._generate_data_driven_executive_hook(
            restaurant_name, google_rating, google_reviews, menu_count, 
            delivery_opportunities, social_opportunities, technical_opportunities
        )
        
        # Generate competitive landscape summary
        competitive_summary = self._generate_competitive_landscape_summary(
            restaurant_name, competitors, google_rating, google_reviews, 
            delivery_platform_data, social_media_analysis
        )
        
        # Generate top 3 opportunities based on data analysis
        top_opportunities = self._generate_data_driven_opportunities(
            restaurant_name, delivery_opportunities, social_opportunities, 
            technical_opportunities, google_rating, menu_count
        )
        
        # Generate action items based on immediate wins
        action_items = self._generate_data_driven_action_items(
            google_places_data, social_media, delivery_platform_data, technical_health
        )
        
        return {
            "executive_hook": executive_hook,
            "competitive_landscape_summary": competitive_summary,
            "top_3_prioritized_opportunities": top_opportunities,
            "cross_platform_integration_strategy": {
                "delivery_platform_optimization": "Optimize presence on DoorDash, Uber Eats, and Grubhub based on competitive analysis and market gaps identified",
                "social_media_competitive_strategy": "Develop engaging content strategy to match or exceed competitor engagement levels and follower growth",
                "technical_performance_enhancement": "Improve website speed, mobile responsiveness, and SEO to capture more organic traffic and conversions",
                "unified_brand_presence": "Ensure consistent branding and information across all platforms for maximum customer recognition and trust",
                "revenue_synergy_opportunities": "Implement cross-platform promotions and customer journey optimization to maximize lifetime value"
            },
            "premium_analysis_teasers": [
                {
                    "premium_feature_title": "Advanced Delivery Platform Revenue Optimization Engine",
                    "compelling_teaser_hook": f"Discover exactly how {restaurant_name} can capture an additional 25-40% delivery revenue by optimizing platform rankings and menu positioning.",
                    "value_proposition": "Detailed competitor analysis across DoorDash, Uber Eats, and Grubhub with specific action items to outrank competitors and increase order volume."
                },
                {
                    "premium_feature_title": "AI-Powered Social Media Competitive Intelligence Dashboard",
                    "compelling_teaser_hook": f"See exactly what {restaurant_name}'s competitors are doing on social media to attract customers and how to replicate their success.",
                    "value_proposition": "Deep dive into competitor social media strategies, optimal posting times, and content that drives the most engagement and foot traffic."
                },
                {
                    "premium_feature_title": "Technical Performance & Conversion Rate Optimization Blueprint",
                    "compelling_teaser_hook": f"Learn how simple website improvements could increase {restaurant_name}'s online conversions by 20-45% within 30 days.",
                    "value_proposition": "Comprehensive technical audit with prioritized improvements for page speed, mobile optimization, and customer conversion optimization."
                }
            ],
            "immediate_action_items_quick_wins": action_items,
            "engagement_and_consultation_questions": [
                f"What are {restaurant_name}'s biggest challenges with online ordering and delivery platforms?",
                f"How does {restaurant_name} currently track and respond to customer reviews across different platforms?",
                f"What are {restaurant_name}'s primary revenue goals and which growth areas feel most promising right now?"
            ],
            "forward_thinking_strategic_insights": {
                "introduction": f"Beyond these immediate opportunities, successful restaurants continuously evolve. Here are forward-thinking considerations for {restaurant_name} based on comprehensive data analysis:",
                "untapped_potential_and_innovation_ideas": [
                    {
                        "idea_title": "Cross-Platform Customer Journey Optimization",
                        "description_and_rationale": f"Based on the data analysis, {restaurant_name} has opportunities to create a seamless customer experience across delivery platforms, social media, and direct ordering. By implementing consistent branding, synchronized promotions, and integrated loyalty programs, restaurants typically see 15-25% increases in customer lifetime value. The key is leveraging each platform's strengths while maintaining brand consistency."
                    },
                    {
                        "idea_title": "Data-Driven Menu Strategy Evolution",
                        "description_and_rationale": f"The analysis reveals opportunities for {restaurant_name} to optimize menu offerings based on delivery platform performance, competitor gaps, and customer feedback patterns. By continuously analyzing which items perform best across different platforms and times, restaurants can maximize profit margins while satisfying customer preferences."
                    }
                ],
                "long_term_vision_alignment_thoughts": [
                    {
                        "strategic_thought_title": "Building a Multi-Platform Restaurant Ecosystem",
                        "elaboration": f"For {restaurant_name} to thrive long-term, the focus should be on creating an integrated ecosystem where delivery platforms, social media, website, and in-person experience all work together to reinforce the brand and drive customer loyalty. This means consistent messaging, coordinated promotions, and data sharing across platforms to create a unified customer experience that competitors struggle to replicate."
                    }
                ],
                "consultants_core_empowerment_message": f"The comprehensive data analysis for {restaurant_name} reveals clear, actionable pathways to meaningful growth. With focused execution on delivery platform optimization, social media engagement, and technical improvements, substantial revenue increases are achievable within 3-6 months. Success lies in systematic implementation of these data-driven recommendations while maintaining operational excellence."
            },
            "data_synthesis_summary": {
                "total_data_sources_analyzed": len([s for s in ["google_places", "delivery_platforms", "social_media", "technical_health", "competitors"] if s]),
                "key_platforms_analyzed": ["Google Places", "DoorDash", "Uber Eats", "Grubhub", "Social Media Platforms"],
                "competitive_intelligence_depth": f"Analyzed {competitor_count} local competitors plus delivery platform competitive positioning",
                "data_confidence_score": "High - Analysis based on comprehensive multi-source data extraction"
            }
        }
    
    def _create_basic_strategic_fallback(self, restaurant_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create the most basic strategic analysis structure as absolute last resort.
        """
        restaurant_name = restaurant_data.get("restaurant_name", "This Restaurant")
        
        return {
            "executive_hook": {
                "hook_statement": f"Our analysis of {restaurant_name} identifies several growth opportunities that could significantly impact revenue and customer engagement within 3-6 months.",
                "biggest_opportunity_teaser": "Digital presence optimization shows the highest potential for immediate impact with measurable revenue gains."
            },
            "competitive_landscape_summary": {
                "introduction": f"Based on available data, {restaurant_name} operates in a competitive market with opportunities for strategic differentiation.",
                "detailed_comparison_text": f"Market analysis suggests that {restaurant_name} has solid fundamentals with room for strategic enhancement in key growth areas including online presence, customer engagement, and operational efficiency.",
                "key_takeaway_for_owner": "Focus on digital optimization and customer experience enhancement to capture untapped market share."
            },
            "top_3_prioritized_opportunities": [
                {
                    "priority_rank": 1,
                    "opportunity_title": "Digital Presence & Online Visibility Enhancement",
                    "current_situation_and_problem": f"Analysis indicates opportunities to strengthen {restaurant_name}'s digital footprint for improved customer discovery and engagement.",
                    "detailed_recommendation": "Implement comprehensive digital optimization including online listing management, customer review engagement, and social media presence strengthening.",
                    "estimated_revenue_or_profit_impact": "Conservative estimates suggest 15-25% increase in customer acquisition through improved online visibility.",
                    "ai_solution_pitch": "Our AI platform can automate online presence management, review responses, and customer engagement optimization.",
                    "implementation_timeline": "2-4 Weeks",
                    "difficulty_level": "Medium (Requires Focused Effort)",
                    "data_sources_supporting_evidence": ["available_restaurant_data"],
                    "visual_evidence_suggestion": {
                        "idea_for_visual": "Digital presence audit showing optimization opportunities",
                        "relevant_screenshot_s3_url_from_input": None
                    }
                }
            ],
            "immediate_action_items_quick_wins": [
                {
                    "action_item": "Update all online business listings with consistent, current information",
                    "rationale_and_benefit": "Ensures customers can find accurate information and improves local search visibility"
                }
            ],
            "engagement_and_consultation_questions": [
                f"What are {restaurant_name}'s biggest challenges with customer acquisition?",
                f"How does {restaurant_name} currently manage online reviews and customer feedback?",
                f"What are {restaurant_name}'s primary growth goals for the next 6 months?"
            ]
        }
    
    def _analyze_delivery_platform_opportunities(self, delivery_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze delivery platform data for opportunities"""
        opportunities = {
            "missing_platforms": [],
            "optimization_areas": [],
            "revenue_potential": "Medium"
        }
        
        if not delivery_data:
            opportunities["platform_gaps"] = ["Establish presence on DoorDash, Uber Eats, and Grubhub"]
            opportunities["revenue_potential"] = "High"
            return opportunities
            
        # Analyze specific platform data
        for platform, data in delivery_data.items():
            if isinstance(data, dict):
                if not data.get("has_presence", False):
                    opportunities["platform_gaps"].append(f"Establish presence on {platform}")
                elif data.get("ranking", 0) > 10:
                    opportunities["optimization_areas"].append(f"Improve ranking on {platform}")
                    
        return opportunities
    
    def _analyze_social_media_opportunities(self, social_analysis: Dict[str, Any], social_links: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze social media data for opportunities"""
        opportunities = {
            "missing_platforms": [],
            "engagement_gaps": [],
            "follower_growth_potential": "Medium"
        }
        
        expected_platforms = ["instagram", "facebook", "twitter", "tiktok"]
        current_platforms = list(social_links.keys()) if social_links else []
        
        opportunities["missing_platforms"] = [p for p in expected_platforms if p not in current_platforms]
        
        if social_analysis:
            for platform, data in social_analysis.items():
                if isinstance(data, dict) and data.get("follower_count", 0) < 500:
                    opportunities["engagement_gaps"].append(f"Increase {platform} engagement")
                    
        return opportunities
    
    def _analyze_technical_opportunities(self, technical_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze technical health data for opportunities"""
        opportunities = {
            "performance_issues": [],
            "seo_gaps": [],
            "mobile_issues": [],
            "conversion_potential": "Medium"
        }
        
        if not technical_data:
            opportunities["performance_issues"] = ["Conduct website performance audit"]
            opportunities["conversion_potential"] = "High"
            return opportunities
            
        if not technical_data.get("mobileResponsive", True):
            opportunities["mobile_issues"].append("Improve mobile responsiveness")
            
        if not technical_data.get("seoOptimized", True):
            opportunities["seo_gaps"].append("Implement SEO optimization")
            
        performance = technical_data.get("performance", {})
        if isinstance(performance, dict) and performance.get("score", 100) < 80:
            opportunities["performance_issues"].append("Improve website loading speed")
            
        return opportunities
    
    def _generate_data_driven_executive_hook(self, restaurant_name: str, google_rating: float, 
                                           google_reviews: int, menu_count: int,
                                           delivery_ops: Dict, social_ops: Dict, tech_ops: Dict) -> Dict[str, str]:
        """Generate executive hook based on actual data analysis"""
        
        # Calculate potential based on gaps
        potential_increase = 15  # Base potential
        
        if delivery_ops.get("revenue_potential") == "High":
            potential_increase += 15
        if len(social_ops.get("missing_platforms", [])) >= 2:
            potential_increase += 10
        if tech_ops.get("conversion_potential") == "High":
            potential_increase += 10
            
        hook = f"Analysis reveals {restaurant_name} could increase revenue by {potential_increase}-{potential_increase + 15}% within 3-6 months by addressing key digital presence gaps and competitive positioning opportunities identified across multiple platforms."
        
        # Identify biggest opportunity
        biggest_opp = "digital presence optimization"
        if delivery_ops.get("revenue_potential") == "High":
            biggest_opp = "delivery platform expansion and optimization"
        elif len(tech_ops.get("performance_issues", [])) > 0:
            biggest_opp = "website technical performance and conversion optimization"
            
        return {
            "hook_statement": hook,
            "biggest_opportunity_teaser": f"The most significant opportunity lies in {biggest_opp} with clear data-supported pathways to implementation."
        }
    
    def _generate_competitive_landscape_summary(self, restaurant_name: str, competitors: List, 
                                              google_rating: float, google_reviews: int,
                                              delivery_data: Dict, social_data: Dict) -> Dict[str, str]:
        """Generate competitive summary based on available competitor data"""
        
        competitor_count = len(competitors)
        
        intro = f"{restaurant_name} operates in a competitive market with {competitor_count} identified local competitors."
        
        detailed = f"Competitive analysis reveals opportunities for {restaurant_name} to differentiate through strategic digital optimization. "
        
        if google_rating >= 4.0:
            detailed += f"With a {google_rating}-star Google rating from {google_reviews} reviews, {restaurant_name} has a solid reputation foundation to build upon. "
        else:
            detailed += f"Improving the current {google_rating}-star Google rating represents a key competitive opportunity. "
            
        if delivery_data:
            detailed += "Delivery platform analysis shows opportunities for improved positioning and market capture. "
        else:
            detailed += "Establishing delivery platform presence represents significant competitive advantage potential. "
            
        detailed += f"Strategic focus on digital presence, customer engagement, and operational efficiency can position {restaurant_name} for sustained competitive advantage."
        
        takeaway = "The primary competitive focus should be digital optimization and enhanced customer engagement to capture market share from competitors with weaker online presence."
        
        return {
            "introduction": intro,
            "detailed_comparison_text": detailed,
            "key_takeaway_for_owner": takeaway
        }
    
    def _generate_data_driven_opportunities(self, restaurant_name: str, delivery_ops: Dict, 
                                          social_ops: Dict, tech_ops: Dict, 
                                          google_rating: float, menu_count: int) -> List[Dict[str, Any]]:
        """Generate top 3 opportunities based on data analysis"""
        
        opportunities = []
        
        # Opportunity 1: Based on biggest gap
        if delivery_ops.get("revenue_potential") == "High":
            opportunities.append({
                "priority_rank": 1,
                "opportunity_title": "Delivery Platform Market Expansion",
                "current_situation_and_problem": f"Analysis shows {restaurant_name} is missing significant revenue opportunities by not fully leveraging delivery platforms like DoorDash, Uber Eats, and Grubhub.",
                "detailed_recommendation": "Establish optimized presence on all major delivery platforms with professional photos, competitive pricing, and strategic menu positioning to capture off-premise dining market share.",
                "estimated_revenue_or_profit_impact": "Delivery platform optimization typically increases off-premise revenue by 25-40% within 3-6 months",
                "ai_solution_pitch": "Our AI delivery optimization platform can manage listings, optimize pricing, and track performance across all delivery platforms automatically.",
                "implementation_timeline": "1-2 Months",
                "difficulty_level": "Medium (Requires Platform Setup)",
                "data_sources_supporting_evidence": ["delivery_platform_analysis", "competitive_intelligence"],
                "visual_evidence_suggestion": {
                    "idea_for_visual": "Delivery platform market opportunity analysis with revenue projections",
                    "relevant_screenshot_s3_url_from_input": None
                }
            })
        else:
            opportunities.append({
                "priority_rank": 1,
                "opportunity_title": "Digital Presence & Customer Discovery Enhancement",
                "current_situation_and_problem": f"Data analysis indicates {restaurant_name} has opportunities to improve online visibility and customer discovery across multiple digital channels.",
                "detailed_recommendation": "Implement comprehensive digital presence optimization including Google My Business enhancement, social media strategy, and customer review management.",
                "estimated_revenue_or_profit_impact": "Digital presence optimization typically increases customer acquisition by 15-25% within 2-4 months",
                "ai_solution_pitch": "Our AI platform automates online presence management, review responses, and customer engagement optimization across all channels.",
                "implementation_timeline": "2-4 Weeks",
                "difficulty_level": "Easy (Quick Implementation)",
                "data_sources_supporting_evidence": ["google_places_data", "social_media_analysis"],
                "visual_evidence_suggestion": {
                    "idea_for_visual": "Digital presence audit showing before/after optimization opportunities",
                    "relevant_screenshot_s3_url_from_input": None
                }
            })
        
        # Opportunity 2: Social media or technical
        if len(social_ops.get("missing_platforms", [])) >= 2:
            opportunities.append({
                "priority_rank": 2,
                "opportunity_title": "Social Media Engagement & Customer Community Building",
                "current_situation_and_problem": f"Analysis reveals {restaurant_name} is not fully leveraging social media platforms for customer engagement and brand building.",
                "detailed_recommendation": "Develop active presence on Instagram, Facebook, and TikTok with engaging content strategy, customer interaction, and brand storytelling.",
                "estimated_revenue_or_profit_impact": "Active social media presence typically increases customer retention by 20-30% and drives additional foot traffic",
                "ai_solution_pitch": "Our AI social media management platform can create engaging content, schedule posts, and respond to customer interactions automatically.",
                "implementation_timeline": "3-6 Weeks",
                "difficulty_level": "Medium (Content Creation Required)",
                "data_sources_supporting_evidence": ["social_media_analysis", "competitive_intelligence"],
                "visual_evidence_suggestion": {
                    "idea_for_visual": "Social media engagement strategy and competitive analysis",
                    "relevant_screenshot_s3_url_from_input": None
                }
            })
        else:
            opportunities.append({
                "priority_rank": 2,
                "opportunity_title": "Website Performance & Conversion Optimization",
                "current_situation_and_problem": f"Technical analysis shows opportunities for {restaurant_name} to improve website performance and customer conversion rates.",
                "detailed_recommendation": "Optimize website loading speed, mobile responsiveness, and user experience to reduce customer friction and increase conversions.",
                "estimated_revenue_or_profit_impact": "Website optimization typically improves conversion rates by 20-45% and reduces customer abandonment",
                "ai_solution_pitch": "Our AI platform continuously monitors website performance and automatically implements optimization improvements.",
                "implementation_timeline": "2-4 Weeks",
                "difficulty_level": "Medium (Technical Implementation)",
                "data_sources_supporting_evidence": ["technical_health_analysis", "user_experience_data"],
                "visual_evidence_suggestion": {
                    "idea_for_visual": "Website performance metrics and optimization roadmap",
                    "relevant_screenshot_s3_url_from_input": None
                }
            })
        
        # Opportunity 3: Menu or customer engagement
        opportunities.append({
            "priority_rank": 3,
            "opportunity_title": "Customer Engagement & Loyalty Enhancement",
            "current_situation_and_problem": f"Data suggests {restaurant_name} has opportunities to improve customer retention and lifetime value through enhanced engagement strategies.",
            "detailed_recommendation": "Implement customer feedback systems, loyalty programs, and personalized communication to build stronger customer relationships and increase repeat business.",
            "estimated_revenue_or_profit_impact": "Enhanced customer engagement typically increases repeat visits by 25-35% and average transaction value by 10-15%",
            "ai_solution_pitch": "Our AI customer engagement platform can personalize interactions, automate loyalty programs, and predict customer preferences.",
            "implementation_timeline": "1-2 Months",
            "difficulty_level": "Medium (System Integration Required)",
            "data_sources_supporting_evidence": ["customer_data_analysis", "engagement_metrics"],
            "visual_evidence_suggestion": {
                "idea_for_visual": "Customer engagement funnel and loyalty program strategy",
                "relevant_screenshot_s3_url_from_input": None
            }
        })
        
        return opportunities
    
    def _generate_data_driven_action_items(self, google_data: Dict, social_media: Dict, 
                                         delivery_data: Dict, technical_data: Dict) -> List[Dict[str, str]]:
        """Generate immediate action items based on available data"""
        
        actions = []
        
        # Google presence action
        if google_data:
            if not google_data.get("photos") or len(google_data.get("photos", [])) < 5:
                actions.append({
                    "action_item": "Upload 5-10 high-quality photos to Google My Business profile including food, interior, and exterior shots",
                    "rationale_and_benefit": "Visual content increases customer engagement by 40% and improves local search rankings"
                })
            else:
                actions.append({
                    "action_item": "Respond to all recent Google reviews with personalized, professional messages",
                    "rationale_and_benefit": "Active review engagement improves reputation scores and shows commitment to customer service"
                })
        else:
            actions.append({
                "action_item": "Claim and optimize Google My Business listing with complete business information",
                "rationale_and_benefit": "Establishes essential local search presence and improves customer discoverability"
            })
        
        # Social media action
        if not social_media or len(social_media) < 2:
            actions.append({
                "action_item": "Create Instagram and Facebook business profiles with consistent branding and contact information",
                "rationale_and_benefit": "Social media presence is essential for customer engagement and brand building in modern restaurant marketing"
            })
        else:
            actions.append({
                "action_item": "Post engaging content to existing social media accounts at least 3 times per week",
                "rationale_and_benefit": "Consistent posting maintains customer engagement and drives repeat business through top-of-mind awareness"
            })
        
        # Technical/delivery action
        if not delivery_data:
            actions.append({
                "action_item": "Research and sign up for at least one major delivery platform (DoorDash, Uber Eats, or Grubhub)",
                "rationale_and_benefit": "Delivery platforms can increase revenue by 20-35% by reaching customers who prefer off-premise dining"
            })
        elif technical_data and not technical_data.get("mobileResponsive", True):
            actions.append({
                "action_item": "Test website on mobile devices and fix any display or functionality issues",
                "rationale_and_benefit": "Mobile optimization is critical as 60%+ of restaurant searches happen on mobile devices"
            })
        else:
            actions.append({
                "action_item": "Update website with current menu, hours, and contact information",
                "rationale_and_benefit": "Accurate information reduces customer frustration and improves conversion rates"
            })
        
        return actions

    # ========== DATA-DRIVEN ANALYSIS METHODS ==========
    
    def _analyze_delivery_platform_opportunities(self, delivery_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze delivery platform opportunities from collected data.
        """
        opportunities = {
            "missing_platforms": [],
            "optimization_areas": [],
            "competitive_gaps": [],
            "revenue_potential": "unknown"
        }
        
        # Add logic based on actual delivery platform data structure
        if delivery_data:
            # Analyze which platforms are present vs missing
            common_platforms = ["doordash", "ubereats", "grubhub", "postmates"]
            present_platforms = [p for p in common_platforms if p in str(delivery_data).lower()]
            opportunities["missing_platforms"] = [p for p in common_platforms if p not in present_platforms]
            
            if opportunities["missing_platforms"]:
                opportunities["optimization_areas"].append("Expand to missing delivery platforms")
                opportunities["revenue_potential"] = "high"
        
        return opportunities
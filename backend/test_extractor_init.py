#!/usr/bin/env python3
"""
Test script to identify which extractor is failing during initialization
"""

import os
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_extractor_imports():
    """Test each extractor import individually"""
    logger.info("🧪 Testing individual extractor imports...")
    
    try:
        from restaurant_consultant.google_places_extractor import GooglePlacesExtractor
        logger.info("✅ GooglePlacesExtractor import successful")
    except Exception as e:
        logger.error(f"❌ GooglePlacesExtractor import failed: {e}")
    
    try:
        from restaurant_consultant.schema_org_extractor import SchemaOrgExtractor
        logger.info("✅ SchemaOrgExtractor import successful")
    except Exception as e:
        logger.error(f"❌ SchemaOrgExtractor import failed: {e}")
    
    try:
        from restaurant_consultant.sitemap_analyzer import SitemapAnalyzer
        logger.info("✅ SitemapAnalyzer import successful")
    except Exception as e:
        logger.error(f"❌ SitemapAnalyzer import failed: {e}")
    
    try:
        from restaurant_consultant.dom_crawler import DOMCrawler
        logger.info("✅ DOMCrawler import successful")
    except Exception as e:
        logger.error(f"❌ DOMCrawler import failed: {e}")
    
    try:
        from restaurant_consultant.ai_vision_processor import AIVisionProcessor
        logger.info("✅ AIVisionProcessor import successful")
    except Exception as e:
        logger.error(f"❌ AIVisionProcessor import failed: {e}")
    
    try:
        from restaurant_consultant.llm_analyzer_module import LLMAnalyzer
        logger.info("✅ LLMAnalyzer import successful")
    except Exception as e:
        logger.error(f"❌ LLMAnalyzer import failed: {e}")
    
    try:
        from restaurant_consultant.data_quality_validator import DataQualityValidator
        logger.info("✅ DataQualityValidator import successful")
    except Exception as e:
        logger.error(f"❌ DataQualityValidator import failed: {e}")
    
    try:
        from restaurant_consultant.stagehand_scraper import StagehandScraper
        logger.info("✅ StagehandScraper import successful")
    except Exception as e:
        logger.error(f"❌ StagehandScraper import failed: {e}")

def test_extractor_initialization():
    """Test each extractor initialization individually"""
    logger.info("🧪 Testing individual extractor initialization...")
    
    try:
        from restaurant_consultant.google_places_extractor import GooglePlacesExtractor
        google_places = GooglePlacesExtractor()
        logger.info(f"✅ GooglePlacesExtractor initialized: {type(google_places)}")
    except Exception as e:
        logger.error(f"❌ GooglePlacesExtractor initialization failed: {e}")
    
    try:
        from restaurant_consultant.data_quality_validator import DataQualityValidator
        validator = DataQualityValidator()
        logger.info(f"✅ DataQualityValidator initialized: {type(validator)}")
    except Exception as e:
        logger.error(f"❌ DataQualityValidator initialization failed: {e}")

def test_progressive_extractor():
    """Test ProgressiveDataExtractor initialization"""
    logger.info("🧪 Testing ProgressiveDataExtractor initialization...")
    
    try:
        from restaurant_consultant.progressive_data_extractor import ProgressiveDataExtractor
        extractor = ProgressiveDataExtractor()
        logger.info(f"✅ ProgressiveDataExtractor initialized: {type(extractor)}")
    except Exception as e:
        logger.error(f"❌ ProgressiveDataExtractor initialization failed: {e}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")

def check_env_vars():
    """Check environment variables"""
    logger.info("🧪 Checking environment variables...")
    
    required_vars = [
        'GOOGLE_API_KEY',
        'GOOGLE_MAPS_API_KEY', 
        'GEMINI_API_KEY',
        'BROWSERBASE_API_KEY',
        'OPENAI_API_KEY'
    ]
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            logger.info(f"✅ {var}: SET")
        else:
            logger.warning(f"⚠️ {var}: NOT SET")

if __name__ == "__main__":
    logger.info("🚀 Starting extractor initialization test...")
    
    check_env_vars()
    test_extractor_imports()
    test_extractor_initialization()
    test_progressive_extractor()
    
    logger.info("🏁 Test completed!") 
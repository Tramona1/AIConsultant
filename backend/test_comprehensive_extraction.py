#!/usr/bin/env python3
"""
Comprehensive Test Suite for Restaurant AI Consulting System
Tests all major components with real data
"""

import logging
import asyncio
import sys
import os
from datetime import datetime
from pathlib import Path

# Add the parent directory to Python path for imports
sys.path.append(str(Path(__file__).parent))

from restaurant_consultant.progressive_data_extractor import ProgressiveDataExtractor
from restaurant_consultant.google_places_extractor import GooglePlacesExtractor
from restaurant_consultant.models import FinalRestaurantOutput, ScreenshotInfo
from pydantic import HttpUrl

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_node_js():
    """Check if Node.js is installed and provide installation guidance"""
    import subprocess
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            logger.info(f"✅ Node.js is installed: {result.stdout.strip()}")
            return True
        else:
            logger.warning("⚠️ Node.js command failed")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("⚠️ Node.js is not installed or not in PATH")
        logger.info("📝 To install Node.js on macOS:")
        logger.info("   1. Install Homebrew: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
        logger.info("   2. Install Node.js: brew install node")
        logger.info("   3. Verify installation: node --version")
        return False

async def test_google_places_api():
    """Test Google Places API integration"""
    logger.info("🧪 Testing Google Places API with real restaurant...")
    
    try:
        extractor = GooglePlacesExtractor()
        if not extractor.client:
            logger.error("❌ Google Places API client not initialized - missing API key")
            return False
        
        # Test with a well-known restaurant
        result = await extractor.get_place_details_by_query("Eleven Madison Park New York")
        
        if result:
            logger.info(f"✅ Found restaurant: {result.get('name')}")
            logger.info(f"📍 Address: {result.get('address')}")
            logger.info(f"⭐ Rating: {result.get('google_rating')} ({result.get('google_review_count')} reviews)")
            return True
        else:
            logger.error("❌ No results returned from Google Places API")
            return False
            
    except Exception as e:
        logger.error(f"❌ Google Places API test failed: {str(e)}")
        return False

async def test_models_completeness():
    """Test that all Pydantic models work correctly"""
    logger.info("🧪 Testing Pydantic models completeness...")
    
    try:
        # Test FinalRestaurantOutput with comprehensive data
        test_data = {
            "website_url": "https://test-restaurant.com",
            "restaurant_name": "Test Restaurant",
            "google_rating": 4.5,
            "google_review_count": 150,
            "google_place_id": "test_place_id_123",
            "google_maps_url": "https://maps.google.com/test",
            "google_recent_reviews": [
                {"author": "John Doe", "rating": 5, "text": "Great food!", "time": 1640995200}
            ],
            "structured_address": {
                "street_address": "123 Test St",
                "city": "Test City",
                "state": "TS", 
                "zip_code": "12345",
                "full_address_text": "123 Test St, Test City, TS 12345"
            },
            "menu_items": [
                {
                    "name": "Test Burger",
                    "description": "Delicious test burger",
                    "price_original": "$15.99",
                    "price_cleaned": 15.99
                }
            ],
            "website_screenshots_s3_urls": [
                ScreenshotInfo(
                    s3_url="https://s3.test.com/screenshot1.png",
                    caption="Test screenshot",
                    source_phase=2,
                    taken_at=datetime.now()
                )
            ]
        }
        
        # Create FinalRestaurantOutput instance
        restaurant = FinalRestaurantOutput(**test_data)
        logger.info("✅ FinalRestaurantOutput model created successfully")
        
        # Check for Google Places dedicated fields
        logger.info("📊 Checking for missing Google Places integration...")
        if hasattr(restaurant, 'google_rating') and hasattr(restaurant, 'google_review_count'):
            logger.info("✅ Google Places dedicated fields present")
        else:
            logger.warning("⚠️ Google Places dedicated fields missing")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Models test failed: {str(e)}")
        return False

async def test_end_to_end_extraction():
    """Test complete end-to-end extraction"""
    logger.info("🧪 Testing end-to-end extraction...")
    
    try:
        extractor = ProgressiveDataExtractor()
        
        # Test with a real restaurant website
        test_url = "https://www.elevenmadisonpark.com"
        restaurant_name = "Eleven Madison Park"
        
        logger.info(f"🎯 Testing end-to-end extraction with: {test_url}")
        
        # Start extraction
        start_time = datetime.now()
        result = await extractor.extract_restaurant_data(
            url=test_url,
            restaurant_name=restaurant_name
        )
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"⏱️ Extraction completed in {duration:.2f} seconds")
        
        # Analyze results
        if isinstance(result, FinalRestaurantOutput):
            logger.info(f"✅ Returned FinalRestaurantOutput for: {result.restaurant_name}")
            
            # Calculate completeness score
            total_fields = len(FinalRestaurantOutput.model_fields)
            populated_fields = 0
            
            for field_name, field_info in FinalRestaurantOutput.model_fields.items():
                value = getattr(result, field_name, None)
                if value is not None and value != [] and value != {}:
                    populated_fields += 1
            
            completeness_score = (populated_fields / total_fields) * 100
            logger.info(f"📊 Extraction completeness score: {completeness_score:.2f}%")
            
            # Check specific important fields
            if result.google_rating and result.google_review_count:
                logger.info("✅ Google Places data populated")
                logger.info(f"📝 Google reviews found: {len(result.google_recent_reviews or [])}")
            else:
                logger.warning("⚠️ Google Places data missing")
                
            if result.menu_items and len(result.menu_items) > 0:
                logger.info(f"🍽️ Menu items extracted: {len(result.menu_items)}")
            else:
                logger.warning("⚠️ No menu items extracted")
                
            if result.website_screenshots_s3_urls and len(result.website_screenshots_s3_urls) > 0:
                logger.info(f"📸 Screenshots captured: {len(result.website_screenshots_s3_urls)}")
            else:
                logger.warning("⚠️ No screenshots captured")
                
            if result.llm_strategic_analysis:
                logger.info("🧠 Strategic analysis generated")
            else:
                logger.warning("⚠️ No strategic analysis generated")
            
            # Require at least 60% completeness to pass
            return completeness_score >= 60.0
        else:
            logger.error("❌ Extraction did not return FinalRestaurantOutput")
            return False
            
    except Exception as e:
        logger.error(f"❌ End-to-end extraction test failed: {str(e)}")
        return False

async def main():
    """Run comprehensive test suite"""
    logger.info("🚀 Starting Comprehensive Test Suite")
    
    # Check Node.js installation first
    node_installed = check_node_js()
    if not node_installed:
        logger.warning("⚠️ Node.js not installed - Phase 4 (Stagehand) will be limited")
    
    test_results = {}
    
    # Test 1: Google Places API
    logger.info("\n" + "="*50)
    logger.info("🧪 Running: Google Places API") 
    logger.info("="*50)
    test_results["google_places"] = await test_google_places_api()
    logger.info(f"📊 Google Places API: {'✅ PASS' if test_results['google_places'] else '❌ FAIL'}")
    
    # Test 2: Models Completeness  
    logger.info("\n" + "="*50)
    logger.info("🧪 Running: Models Completeness")
    logger.info("="*50)
    test_results["models"] = await test_models_completeness()
    logger.info(f"📊 Models Completeness: {'✅ PASS' if test_results['models'] else '❌ FAIL'}")
    
    # Test 3: End-to-End Extraction
    logger.info("\n" + "="*50)
    logger.info("🧪 Running: End-to-End Extraction")
    logger.info("="*50)
    test_results["end_to_end"] = await test_end_to_end_extraction()
    logger.info(f"📊 End-to-End Extraction: {'✅ PASS' if test_results['end_to_end'] else '❌ FAIL'}")
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("📋 TEST SUMMARY")
    logger.info("="*50)
    
    passed_tests = sum(test_results.values())
    total_tests = len(test_results)
    
    logger.info(f"Tests Passed: {passed_tests}/{total_tests}")
    for test_name, passed in test_results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        test_display_name = {
            "google_places": "Google Places API",
            "models": "Models Completeness", 
            "end_to_end": "End-to-End Extraction"
        }.get(test_name, test_name)
        logger.info(f"  {test_display_name}: {status}")
    
    # Report issues
    issues = []
    if not test_results.get("google_places"):
        issues.append("Google Places API client not initialized - missing API key")
    if not node_installed:
        issues.append("Node.js not installed - Stagehand functionality limited")
    
    if issues:
        logger.info(f"\n🚨 ISSUES FOUND ({len(issues)}):")
        for i, issue in enumerate(issues, 1):
            logger.info(f"  {i}. {issue}")
    
    if passed_tests < total_tests:
        logger.error("💥 Some tests failed. Review issues above.")
        sys.exit(1)
    else:
        logger.info("🎉 All tests passed!")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main()) 
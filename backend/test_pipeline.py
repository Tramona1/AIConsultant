#!/usr/bin/env python3

import asyncio
import json
import httpx
from datetime import datetime

async def test_full_pipeline():
    """Test the full restaurant analysis pipeline step by step"""
    print("🔍 Testing Full Restaurant Analysis Pipeline...")
    
    # Test with a simple restaurant
    test_url = "https://www.chipotle.com"
    print(f"🌐 Testing restaurant: {test_url}")
    
    # Start analysis
    print("📡 Making API request...")
    start_time = datetime.now()
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "http://localhost:8000/analyze-restaurant-progressive",
                json={"url": test_url},
                headers={"Content-Type": "application/json"}
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print(f"⏱️ Analysis completed in {duration:.1f} seconds")
            print(f"📊 Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                # Check key metrics
                print("\n📋 **KEY METRICS:**")
                print(f"  • Restaurant name: {result.get('restaurant_name', 'Not found')}")
                print(f"  • Address: {result.get('address', 'Not found')}")
                print(f"  • Phone: {result.get('phone', 'Not found')}")
                print(f"  • Menu items: {result.get('menu_items_count', 0)} items")
                print(f"  • Screenshots: {result.get('screenshots_captured', 0)} captured")
                print(f"  • Analysis phases: {result.get('phases_completed', [])}")
                
                # Check data extraction
                print("\n🔍 **DATA EXTRACTION STATUS:**")
                google_data = result.get('google_places_data', {})
                print(f"  • Google Places API: {'✅ Working' if google_data else '❌ No data'}")
                
                scraping_data = result.get('website_data', {})
                print(f"  • Website scraping: {'✅ Working' if scraping_data else '❌ No data'}")
                
                vision_data = result.get('ai_vision_analysis', {})
                print(f"  • AI Vision analysis: {'✅ Working' if vision_data else '❌ No data'}")
                
                # Check specific issues
                print("\n🎯 **SPECIFIC ISSUES TO INVESTIGATE:**")
                
                if result.get('menu_items_count', 0) == 0:
                    print("  ❌ ISSUE: No menu items extracted")
                    print("    → Need to check: DOM crawler, AI vision integration")
                
                if result.get('screenshots_captured', 0) == 0:
                    print("  ❌ ISSUE: No screenshots captured")
                    print("    → Need to check: Screenshot taking, file saving")
                
                if not result.get('address'):
                    print("  ❌ ISSUE: No address found")
                    print("    → Need to check: Google Places data mapping")
                
                # Show raw result for debugging
                print(f"\n📄 **RESULT KEYS:** {list(result.keys())}")
                
                return result
                
            else:
                print(f"❌ API request failed with status {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
    except httpx.TimeoutException:
        print("❌ Request timed out")
        return None
    except Exception as e:
        print(f"❌ Error during request: {str(e)}")
        return None

async def test_individual_components():
    """Test individual components to isolate issues"""
    print("\n🧪 Testing Individual Components...")
    
    # Test 1: Basic server health
    print("1️⃣ Testing server health...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8000/")
            print(f"   Server health: {'✅ OK' if response.status_code == 200 else '❌ Failed'}")
    except Exception as e:
        print(f"   Server health: ❌ Failed - {str(e)}")
        return
    
    # Test 2: Vision processor
    print("2️⃣ Testing AI Vision processor...")
    try:
        from restaurant_consultant.ai_vision_processor import AIVisionProcessor
        processor = AIVisionProcessor()
        print(f"   Vision API: {'✅ Enabled' if processor.enabled else '❌ Disabled'}")
    except Exception as e:
        print(f"   Vision API: ❌ Failed - {str(e)}")
    
    # Test 3: Environment variables
    print("3️⃣ Testing environment variables...")
    import os
    print(f"   GEMINI_API_KEY: {'✅ Set' if os.getenv('GEMINI_API_KEY') else '❌ Missing'}")
    print(f"   GOOGLE_MAPS_API_KEY: {'✅ Set' if os.getenv('GOOGLE_MAPS_API_KEY') else '❌ Missing'}")

if __name__ == "__main__":
    async def main():
        await test_individual_components()
        print("\n" + "="*60)
        await test_full_pipeline()
    
    asyncio.run(main()) 
#!/usr/bin/env python3

import asyncio
import sys
from pathlib import Path

# Add the backend directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from restaurant_consultant.ai_vision_processor import AIVisionProcessor

async def test_vision_analysis():
    """Test the simplified vision analysis"""
    print("🔍 Testing AI Vision Analysis...")
    
    processor = AIVisionProcessor()
    print(f"✅ Processor initialized - Enabled: {processor.enabled}")
    
    if not processor.enabled:
        print("❌ Vision processor not enabled - check API keys")
        return
    
    # Test with actual screenshot
    test_url = "file:///Users/blakesingleton/Ai%20Consulting%20MVP/restaurant-ai-consulting/backend/analysis_data/screenshots/20250601201705_www.zentarousf.com_homepage_homepage.png"
    print(f"📸 Testing screenshot: {test_url}")
    
    try:
        result = await processor._analyze_image(test_url)
        
        if result:
            print("✅ Analysis successful!")
            print(f"📋 Menu items found: {len(result.get('menu_items', []))}")
            print(f"📄 Page type: {result.get('page_type', 'unknown')}")
            print(f"📞 Contact info: {result.get('contact_info', {})}")
            
            if result.get('menu_items'):
                print(f"🍽️ First menu item: {result['menu_items'][0]}")
            
            if result.get('raw_analysis'):
                print(f"📝 Raw analysis (first 200 chars): {result['raw_analysis'][:200]}...")
        else:
            print("❌ Analysis returned None")
            
    except Exception as e:
        print(f"❌ Error during analysis: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_vision_analysis()) 
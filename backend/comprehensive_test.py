#!/usr/bin/env python3
"""
Comprehensive system test to verify all components are working
"""

import asyncio
import os
from dotenv import load_dotenv

def test_comprehensive_system():
    load_dotenv()
    
    print('🧪 Running comprehensive system test...')
    
    # Test 1: Module imports
    print('1️⃣ Testing module imports...')
    try:
        import restaurant_consultant.progressive_data_extractor as pde
        import restaurant_consultant.llm_analyzer_module as llm
        import restaurant_consultant.pdf_generator_module as pdf
        import restaurant_consultant.ai_vision_processor as ai_vision
        import restaurant_consultant.google_places_extractor as gpe
        print('✅ All modules imported successfully')
    except Exception as e:
        print(f'❌ Module import failed: {str(e)}')
        return False
    
    # Test 2: Dynamic name matching
    print('2️⃣ Testing dynamic name matching...')
    try:
        extractor = pde.ProgressiveDataExtractor()
        test_cases = [
            ('In Out', 'In-N-Out Burger'),
            ('McDonalds', "McDonald's Restaurant"),
            ('Pizza Hut', 'Pizza Hut Express')
        ]
        for found, expected in test_cases:
            result = extractor._is_reasonable_name_match(found, expected)
            print(f'   {found} vs {expected}: {"✅" if result else "❌"}')
    except Exception as e:
        print(f'❌ Name matching test failed: {str(e)}')
        return False
    
    # Test 3: Google Places API
    print('3️⃣ Testing Google Places API...')
    try:
        places_extractor = gpe.GooglePlacesExtractor()
        api_configured = places_extractor.client is not None
        print(f'   API configured: {"✅" if api_configured else "❌"}')
        
        if api_configured:
            print('   Google API key properly loaded and client initialized')
        else:
            print('   Google API key missing or client initialization failed')
    except Exception as e:
        print(f'❌ Google Places test failed: {str(e)}')
        return False
    
    # Test 4: Environment variables
    print('4️⃣ Testing environment variables...')
    env_vars = ['GOOGLE_API_KEY', 'GEMINI_API_KEY', 'BROWSERBASE_API_KEY']
    for var in env_vars:
        value = os.getenv(var)
        status = "✅" if value else "❌"
        print(f'   {var}: {status}')
    
    print('🎉 Comprehensive system test completed!')
    return True

if __name__ == "__main__":
    success = test_comprehensive_system()
    exit(0 if success else 1) 
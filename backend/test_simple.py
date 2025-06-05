#!/usr/bin/env python3

import asyncio
import httpx
import time

async def test_simple_analysis():
    """Test with a very simple URL to isolate the problem"""
    print("🎯 Testing Simple Analysis...")
    
    test_cases = [
        "https://www.example.com",  # Simple static site
        "https://httpbin.org/get",   # Test endpoint 
        "https://www.google.com",    # Simple but real site
    ]
    
    for i, test_url in enumerate(test_cases):
        print(f"\n{i+1}. Testing: {test_url}")
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                print("   📡 Making request...")
                response = await client.post(
                    "http://localhost:8000/analyze-restaurant-progressive",
                    json={"url": test_url}
                )
                
                duration = time.time() - start_time
                print(f"   ⏱️ Completed in {duration:.1f}s")
                print(f"   📊 Status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"   ✅ Success - got {len(result)} response fields")
                    
                    # Key checks
                    phases = result.get('phases_completed', [])
                    print(f"   📋 Phases completed: {phases}")
                    
                    if len(phases) > 0:
                        print(f"   🎯 Last phase: {phases[-1]}")
                    
                    return True  # Found working case
                    
                elif response.status_code == 422:
                    print(f"   ⚠️ Validation error: {response.text}")
                else:
                    print(f"   ❌ Error: {response.text}")
                    
        except httpx.TimeoutException:
            duration = time.time() - start_time
            print(f"   ❌ Timeout after {duration:.1f}s")
        except Exception as e:
            duration = time.time() - start_time
            print(f"   ❌ Error after {duration:.1f}s: {str(e)}")
    
    return False

if __name__ == "__main__":
    asyncio.run(test_simple_analysis()) 
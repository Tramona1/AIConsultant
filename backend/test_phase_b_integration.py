#!/usr/bin/env python3
"""
Test Phase B: LLM Strategic Analysis Integration
Tests the complete integration of Phase B with the Progressive Data Extractor
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

# Add the restaurant_consultant package to the path
sys.path.insert(0, str(Path(__file__).parent / "restaurant_consultant"))

# Set up logging with emojis for visual clarity
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def test_phase_b_integration():
    """Test the complete Phase B integration with Progressive Data Extractor"""
    
    logger.info("🧪 Starting Phase B Integration Test")
    
    try:
        # Import modules
        from restaurant_consultant.progressive_data_extractor import ProgressiveDataExtractor
        from restaurant_consultant.llm_analyzer_module import LLMAnalyzer
        logger.info("✅ Successfully imported required modules")
        
        # Check if Gemini API key is available
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            logger.warning("⚠️ GEMINI_API_KEY not found in environment - Phase B will be skipped")
        else:
            logger.info("✅ GEMINI_API_KEY found - Phase B will be executed")
        
        # Initialize the Progressive Data Extractor
        extractor = ProgressiveDataExtractor()
        logger.info("✅ Progressive Data Extractor initialized")
        
        # Check LLM Analyzer initialization
        if extractor.llm_analyzer:
            logger.info(f"✅ LLM Analyzer initialized: enabled={extractor.llm_analyzer.enabled}")
        else:
            logger.warning("⚠️ LLM Analyzer not initialized")
        
        # Test with a sample restaurant website
        test_url = "https://www.joesrestaurant.com"  # Placeholder URL for testing
        restaurant_name = "Joe's Restaurant"
        
        logger.info(f"🎯 Testing Phase B integration with: {test_url}")
        
        # Run the complete extraction (including Phase B)
        start_time = datetime.now()
        
        try:
            result = await extractor.extract_restaurant_data(
                url=test_url,
                restaurant_name=restaurant_name
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"⏱️ Complete extraction took {duration:.2f} seconds")
            
            # Validate the result
            logger.info(f"📊 Result validation:")
            logger.info(f"  Restaurant Name: {result.restaurant_name}")
            logger.info(f"  Website URL: {result.website_url}")
            logger.info(f"  LLM Strategic Analysis: {'✅ Present' if result.llm_strategic_analysis else '❌ Missing'}")
            
            if result.llm_strategic_analysis:
                analysis = result.llm_strategic_analysis
                logger.info(f"  Strategic Analysis Details:")
                
                # Check for executive hook
                if analysis.get('executive_hook'):
                    exec_hook = analysis['executive_hook']
                    logger.info(f"    📈 Growth Potential: {exec_hook.get('growth_potential_statement', 'N/A')}")
                    logger.info(f"    ⏰ Timeframe: {exec_hook.get('timeframe', 'N/A')}")
                else:
                    logger.info(f"    📈 Executive Hook: ❌ Missing")
                
                # Check for competitive positioning
                if analysis.get('competitive_positioning'):
                    comp_pos = analysis['competitive_positioning']
                    logger.info(f"    🏆 Market Position: {comp_pos.get('market_position_summary', 'N/A')[:100]}...")
                else:
                    logger.info(f"    🏆 Competitive Positioning: ❌ Missing")
                
                # Check for opportunities
                if analysis.get('top_3_opportunities'):
                    opportunities = analysis['top_3_opportunities']
                    logger.info(f"    💡 Opportunities Found: {len(opportunities)}")
                    for i, opp in enumerate(opportunities[:3], 1):
                        logger.info(f"      {i}. {opp.get('opportunity_title', 'Untitled')}")
                else:
                    logger.info(f"    💡 Opportunities: ❌ Missing")
                
                # Check metadata
                if analysis.get('analysis_metadata'):
                    metadata = analysis['analysis_metadata']
                    logger.info(f"    📊 Analysis Cost: ${metadata.get('estimated_cost_usd', 0):.4f}")
                    logger.info(f"    📸 Screenshots Analyzed: {metadata.get('screenshots_analyzed', 0)}")
                    logger.info(f"    🏢 Competitors Analyzed: {metadata.get('competitors_analyzed', 0)}")
                else:
                    logger.info(f"    📊 Analysis Metadata: ❌ Missing")
            
            # Check extraction metadata
            if result.extraction_metadata:
                meta = result.extraction_metadata
                logger.info(f"  Extraction Metadata:")
                logger.info(f"    🔢 Phases Completed: {meta.phases_completed}")
                logger.info(f"    💰 Total Cost: ${meta.total_cost_usd:.4f}")
                logger.info(f"    📊 Final Quality Score: {meta.final_quality_score:.2f}")
                logger.info(f"    ⏱️ Duration: {meta.total_duration_seconds:.2f}s")
            
            logger.info("✅ Phase B Integration Test completed successfully!")
            return True
            
        except Exception as e_extraction:
            logger.error(f"❌ Extraction failed: {str(e_extraction)}", exc_info=True)
            return False
        
    except ImportError as e_import:
        logger.error(f"❌ Import error: {str(e_import)}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}", exc_info=True)
        return False

async def test_llm_analyzer_standalone():
    """Test the LLM Analyzer as a standalone component"""
    
    logger.info("🧪 Testing LLM Analyzer Standalone")
    
    try:
        from restaurant_consultant.llm_analyzer_module import LLMAnalyzer
        from restaurant_consultant.models import FinalRestaurantOutput, ExtractionMetadata
        from pydantic import HttpUrl
        
        # Create a sample FinalRestaurantOutput for testing
        sample_metadata = ExtractionMetadata(
            extraction_id="test_123",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            total_duration_seconds=60.0,
            total_cost_usd=0.10,
            phases_completed=[1, 2, 3, 4],
            final_quality_score=0.85
        )
        
        sample_restaurant_data = FinalRestaurantOutput(
            website_url=HttpUrl("https://www.joesrestaurant.com"),
            restaurant_name="Joe's Italian Restaurant",
            description_short="Authentic Italian cuisine in downtown",
            primary_cuisine_type_ai="Italian",
            price_range_ai="$$",
            extraction_metadata=sample_metadata
        )
        
        # Initialize LLM Analyzer
        analyzer = LLMAnalyzer()
        
        if analyzer.enabled:
            logger.info("✅ LLM Analyzer initialized and enabled")
            
            # Test strategic analysis generation
            logger.info("🧠 Testing strategic analysis generation...")
            
            strategic_analysis = await analyzer.generate_strategic_report_content(sample_restaurant_data)
            
            if strategic_analysis:
                logger.info("✅ Strategic analysis generated successfully")
                logger.info(f"📊 Analysis type: {type(strategic_analysis)}")
                
                # Convert to dict for inspection
                analysis_dict = strategic_analysis.model_dump() if hasattr(strategic_analysis, 'model_dump') else strategic_analysis
                
                logger.info(f"📈 Executive Hook: {'✅' if analysis_dict.get('executive_hook') else '❌'}")
                logger.info(f"🏆 Competitive Positioning: {'✅' if analysis_dict.get('competitive_positioning') else '❌'}")
                logger.info(f"💡 Opportunities: {'✅' if analysis_dict.get('top_3_opportunities') else '❌'}")
                logger.info(f"📊 Metadata: {'✅' if analysis_dict.get('analysis_metadata') else '❌'}")
                
                return True
            else:
                logger.warning("⚠️ Strategic analysis returned None")
                return False
        else:
            logger.warning("⚠️ LLM Analyzer not enabled (missing API key)")
            return False
            
    except Exception as e:
        logger.error(f"❌ Standalone LLM Analyzer test failed: {str(e)}", exc_info=True)
        return False

async def main():
    """Run all Phase B integration tests"""
    
    logger.info("🚀 Starting Phase B Integration Test Suite")
    
    # Test 1: Standalone LLM Analyzer
    test1_result = await test_llm_analyzer_standalone()
    
    # Test 2: Full Integration
    test2_result = await test_phase_b_integration()
    
    # Summary
    logger.info("📋 Test Results Summary:")
    logger.info(f"  Standalone LLM Analyzer: {'✅ PASS' if test1_result else '❌ FAIL'}")
    logger.info(f"  Full Phase B Integration: {'✅ PASS' if test2_result else '❌ FAIL'}")
    
    if test1_result and test2_result:
        logger.info("🎉 All Phase B tests passed!")
        return 0
    else:
        logger.error("💥 Some Phase B tests failed!")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 
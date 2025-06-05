from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Union
import uuid
import json
import os
import logging
from dotenv import load_dotenv
from pathlib import Path
import traceback
from datetime import datetime

# Core new system imports
from restaurant_consultant.progressive_data_extractor import ProgressiveDataExtractor
from restaurant_consultant.models import FinalRestaurantOutput, ExtractionMetadata
from restaurant_consultant.pdf_generator_module import RestaurantReportGenerator
from restaurant_consultant.stagehand_integration import stagehand_scraper

# Load environment variables
load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = BASE_DIR / "analysis_data"
ANALYSIS_DIR.mkdir(exist_ok=True)

# Create generated PDFs directory
GENERATED_PDFS_DIR = BASE_DIR / "generated_pdfs"
GENERATED_PDFS_DIR.mkdir(exist_ok=True)

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)
logger.info("🚀 FastAPI Restaurant AI Consulting application starting...")

# Create FastAPI app with enhanced metadata
app = FastAPI(
    title="Restaurant AI Consulting API",
    description="AI-powered restaurant analysis and outreach automation with Progressive Extraction",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Initialize PDF generator
pdf_generator = RestaurantReportGenerator()

# Mount static files for serving generated PDFs
app.mount("/generated_pdfs", StaticFiles(directory=str(GENERATED_PDFS_DIR)), name="generated_pdfs")
logger.info(f"📁 Static file serving enabled for PDFs at: {GENERATED_PDFS_DIR}")

# Enhanced CORS configuration
origins = [
    "http://localhost:3000",  # Next.js dev server
    "http://127.0.0.1:3000",  # Alternative localhost
    "http://localhost:3001",  # Alternative dev port
    # Add production URLs here:
    # "https://your-restaurant-ai.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Pydantic models
class AnalysisRequest(BaseModel):
    url: str
    email: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None

class ProgressiveAnalysisRequest(BaseModel):
    url: str  # Renamed from restaurant_url for consistency
    restaurant_name: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None

class OutreachRequest(BaseModel):
    report_id: str
    target_type: str = Field(..., description="Target type: 'target' or 'competitor'")
    competitor_name: Optional[str] = None
    user_consent: bool = Field(default=False, description="Required for competitor outreach")

class HealthResponse(BaseModel):
    status: str
    version: str
    services: Dict[str, Any]

def make_json_serializable(obj: Any) -> Any:
    """
    Convert Pydantic objects and other non-serializable objects to JSON-serializable format.
    
    Args:
        obj: Any object that might contain Pydantic models
        
    Returns:
        JSON-serializable version of the object
    """
    if hasattr(obj, 'model_dump'):
        # Pydantic v2 method
        return obj.model_dump()
    elif hasattr(obj, 'dict'):
        # Pydantic v1 method (legacy)
        return obj.dict()
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        # Try to convert to string as fallback
        try:
            return str(obj)
        except:
            return None

# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint to verify service status and dependencies."""
    logger.info("Health check requested")
    
    services_status = {}
    
    # Check Stagehand availability
    try:
        stagehand_available = stagehand_scraper.is_available()
        services_status["stagehand"] = {
            "status": "available" if stagehand_available else "unavailable",
            "capabilities": stagehand_scraper.get_capabilities() if stagehand_available else {}
        }
    except Exception as e:
        services_status["stagehand"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Check environment variables
    required_env_vars = ["GOOGLE_API_KEY", "GEMINI_API_KEY"]
    optional_env_vars = ["BROWSERBASE_API_KEY", "ELEVENLABS_API_KEY", "TWILIO_ACCOUNT_SID", "AWS_ACCESS_KEY_ID"]
    
    env_status = {}
    for var in required_env_vars:
        env_status[var] = "configured" if os.getenv(var) else "missing"
    
    for var in optional_env_vars:
        env_status[var] = "configured" if os.getenv(var) else "not_configured"
    
    services_status["environment"] = env_status
    
    # Check directories
    required_dirs = ["analysis_data", "menus"]
    dir_status = {}
    for dir_name in required_dirs:
        dir_path = os.path.join(os.getcwd(), dir_name)
        dir_status[dir_name] = "exists" if os.path.exists(dir_path) else "missing"
    
    services_status["directories"] = dir_status
    
    # Overall status
    overall_status = "healthy"
    if any(status.get("status") == "error" for status in services_status.values() if isinstance(status, dict)):
        overall_status = "degraded"
    
    missing_required = [var for var in required_env_vars if not os.getenv(var)]
    if missing_required:
        overall_status = "degraded"
        services_status["missing_required_env"] = missing_required
    
    return HealthResponse(
        status=overall_status,
        version="2.0.0",
        services=services_status
    )

@app.get("/")
async def root():
    """Root endpoint with basic API information."""
    return {
        "message": "Restaurant AI Consulting API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health"
    }

# --- LEGACY ENDPOINT: Updated to use new system for backward compatibility ---
@app.post("/api/v1/analyze-restaurant/")
async def legacy_analyze_restaurant_endpoint(request: AnalysisRequest):
    """Legacy analyze restaurant endpoint - forwards to new progressive system for backward compatibility."""
    logger.info(f"🔄 Legacy endpoint /api/v1/analyze-restaurant/ called for URL: {request.url}. Forwarding to new progressive system.")
    
    # Convert legacy request to new progressive request format
    progressive_request = ProgressiveAnalysisRequest(
        url=request.url,
        restaurant_name=request.name,
        address=request.address,
        email=request.email
    )
    
    # Call the new progressive system internally
    try:
        result = await analyze_restaurant_progressive(progressive_request)
        
        # Convert the response to legacy format if needed
        if isinstance(result, JSONResponse):
            return result
        elif hasattr(result, 'model_dump'):
            # Convert FinalRestaurantOutput to legacy format
            legacy_response = {
                "reportId": str(uuid.uuid4()),
                "summary": f"Analysis completed for {result.restaurant_name or 'restaurant'}",
                "initialData": {
                    "restaurant_name": result.restaurant_name,
                    "website_data": {
                        "menu": {
                            "items": [
                                {
                                    "name": item.name,
                                    "description": item.description or "",
                                    "price": item.price_original or "",
                                } 
                                for item in (result.menu_items or [])
                            ]
                        }
                    },
                    "competitors": {
                        "competitors": [
                            {
                                "name": comp.name,
                                "address": comp.address_raw if hasattr(comp, 'address_raw') else getattr(comp, 'address', None),
                            } 
                            for comp in (result.competitors or [])
                        ]
                    }
                },
                "summary_data": {
                    "scraper_used": "progressive_extractor",
                    "menu_items_found": len(result.menu_items or []),
                    "competitors_found": len(result.competitors or []),
                    "data_quality": {
                        "quality_score": result.extraction_metadata.final_quality_score if result.extraction_metadata else None
                    }
                }
            }
            return legacy_response
        else:
            return result
            
    except Exception as e:
        logger.error(f"❌ Legacy endpoint failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Legacy analysis failed: {str(e)}")

# --- NEW PRIMARY ENDPOINT ---
@app.post("/analyze-restaurant-progressive")
async def analyze_restaurant_progressive(request: ProgressiveAnalysisRequest):
    """
    Complete restaurant analysis pipeline: Phase A + Phase B + Phase C
    - Phase A: Progressive data extraction (4-phase system)
    - Phase B: LLM strategic analysis with competitive intelligence
    - Phase C: Professional PDF report generation
    """
    report_id = str(uuid.uuid4())
    logger.info(f"🚀 Progressive analysis (Report ID: {report_id}) starting for URL: {request.url}")
    
    try:
        if not request.url.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

        # Initialize ProgressiveDataExtractor
        extractor = ProgressiveDataExtractor()
        
        # Phase A + Phase B: Extract restaurant data and generate strategic analysis
        logger.info("📊 Executing Phase A (Data Extraction) + Phase B (LLM Strategic Analysis)...")
        final_restaurant_output: FinalRestaurantOutput = await extractor.extract_restaurant_data(
            url=request.url,
            restaurant_name=request.restaurant_name,
            address=request.address,
            # report_id_for_artifacts=report_id  # Pass report_id if the extractor supports it
        )
        
        if not final_restaurant_output:
            logger.error("❌ Progressive extraction returned None")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Progressive extraction failed - no data returned",
                    "phase": "Phase A (Data Extraction)",
                    "reportId": report_id
                }
            )
        
        # Check extraction status
        restaurant_name = final_restaurant_output.restaurant_name or 'Unknown Restaurant'
        metadata = final_restaurant_output.extraction_metadata
        
        if metadata and metadata.overall_status == "error":
            logger.error(f"❌ Progressive extraction failed for Report ID {report_id}, URL {request.url}: {metadata.error_message}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": f"Progressive extraction failed: {metadata.error_message}",
                    "phase": "Phase A (Data Extraction)",
                    "reportId": report_id
                }
            )
        
        logger.info(f"✅ Phase A + Phase B completed for: {restaurant_name}")
        
        # Log data quality metrics
        if metadata:
            logger.info(f"📊 Extraction Quality: {metadata.final_quality_score or 'N/A'}")
            logger.info(f"⏱️ Total Duration: {metadata.total_duration_seconds:.2f}s")
            logger.info(f"💰 Total Cost: ${metadata.total_cost_usd:.4f}")
            logger.info(f"🔢 Phases Completed: {metadata.phases_completed}")
        
        # Log strategic analysis status
        has_strategic_analysis = final_restaurant_output.llm_strategic_analysis is not None
        strategic = final_restaurant_output.llm_strategic_analysis  # This could be None
        logger.info(f"🧠 Strategic Analysis Available: {has_strategic_analysis}")
        
        if has_strategic_analysis and strategic is not None:
            logger.info(f"🧠 Strategic Analysis Type: {type(strategic)}")
            if isinstance(strategic, dict):
                logger.info(f"🧠 Strategic Analysis Keys: {list(strategic.keys())}")
                opportunities_count = len(strategic.get('top_3_prioritized_opportunities', []))
                logger.info(f"🎯 Strategic Opportunities Identified: {opportunities_count}")
            else:
                logger.warning(f"⚠️ Strategic analysis is not a dict: {type(strategic)}")
                opportunities_count = 0
        else:
            logger.info("🧠 No strategic analysis available")
            opportunities_count = 0
        
        # Phase C: Generate PDF Report
        logger.info("📄 Phase C: Generating professional PDF report...")
        pdf_result = await pdf_generator.generate_pdf_report(final_restaurant_output)
        
        # Initialize pdf_generation_info if not present
        if not final_restaurant_output.pdf_generation_info:
            final_restaurant_output.pdf_generation_info = {}
        
        if pdf_result and pdf_result.get('success'):
            final_restaurant_output.pdf_generation_info.update(pdf_result)
            logger.info(f"✅ PDF report generated successfully: {pdf_result.get('pdf_size_bytes', 0)} bytes")
            if pdf_result.get('pdf_s3_url'):
                logger.info(f"🔗 PDF available at: {pdf_result['pdf_s3_url']}")
        else:
            error_msg = pdf_result.get('error', 'Unknown PDF generation error') if pdf_result else 'PDF generation returned None'
            final_restaurant_output.pdf_generation_info.update({
                "success": False,
                "error": error_msg
            })
            logger.error(f"❌ PDF generation failed: {error_msg}")
        
        # Store the final comprehensive report
        try:
            final_json_path = ANALYSIS_DIR / f"{report_id}_final_comprehensive_report.json"
            with open(final_json_path, "w", encoding='utf-8') as f:
                f.write(final_restaurant_output.model_dump_json(indent=4, exclude_none=True))
            logger.info(f"💾 Final comprehensive report JSON stored: {final_json_path}")
        except Exception as storage_error:
            logger.error(f"❌ Failed to store final comprehensive report JSON for Report ID {report_id}: {storage_error}")
            # Continue, as the main object is still in memory
        
        # Prepare comprehensive response with proper None checks
        executive_summary = None
        competitive_position = None
        
        if has_strategic_analysis and strategic is not None and isinstance(strategic, dict):
            try:
                # Safely extract executive summary
                executive_hook = strategic.get('executive_hook')
                if isinstance(executive_hook, dict):
                    executive_summary = executive_hook.get('hook_statement')
                
                # Safely extract competitive position
                comp_landscape = strategic.get('competitive_landscape_summary')
                if isinstance(comp_landscape, dict):
                    competitive_position = comp_landscape.get('introduction')
                    
                logger.debug(f"🔍 Extracted executive_summary: {bool(executive_summary)}")
                logger.debug(f"🔍 Extracted competitive_position: {bool(competitive_position)}")
            except Exception as e:
                logger.warning(f"⚠️ Error extracting strategic analysis details: {e}")
                # Set to None if extraction fails
                executive_summary = None
                competitive_position = None
        
        response_data = {
            "success": True,
            "reportId": report_id,
            "restaurant_name": restaurant_name,
            "analysis_type": "complete_pipeline",
            "phases_completed": ["Phase A: Data Extraction", "Phase B: LLM Strategic Analysis", "Phase C: PDF Generation"],
            
            # Phase A Results
            "data_extraction": {
                "restaurant_data": {
                    "name": final_restaurant_output.restaurant_name,
                    "address": final_restaurant_output.address_canonical or final_restaurant_output.address_raw,
                    "phone": final_restaurant_output.phone_canonical or final_restaurant_output.phone_raw,
                    "website": str(final_restaurant_output.canonical_url) if final_restaurant_output.canonical_url else str(final_restaurant_output.website_url),
                    "cuisine_types": final_restaurant_output.cuisine_types,
                    "price_range": final_restaurant_output.price_range,
                    "menu_items_count": len(final_restaurant_output.menu_items or []),
                    "screenshots_captured": len(final_restaurant_output.screenshots or []),
                    "competitors_identified": len(final_restaurant_output.competitors or [])
                },
                "extraction_metadata": metadata.model_dump() if metadata else None
            },
            
            # Phase B Results  
            "strategic_analysis": {
                "available": has_strategic_analysis,
                "opportunities_count": opportunities_count,
                "executive_summary": executive_summary,
                "competitive_position": competitive_position
            },
            
            # Phase C Results
            "pdf_report": final_restaurant_output.pdf_generation_info,
            
            # Overall metrics
            "analysis_summary": {
                "data_points_analyzed": len(final_restaurant_output.menu_items or []) + len(final_restaurant_output.competitors or []) + len(final_restaurant_output.screenshots or []),
                "total_processing_time_seconds": metadata.total_duration_seconds if metadata else 0,
                "estimated_cost_usd": metadata.total_cost_usd if metadata else 0,
                "quality_score": metadata.final_quality_score if metadata else None
            }
        }
        
        logger.info("🎉 Complete restaurant analysis pipeline completed successfully!")
        return JSONResponse(content=make_json_serializable(response_data))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Complete restaurant analysis failed: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Complete restaurant analysis failed",
                "details": str(e),
                "pipeline": "Phase A + Phase B + Phase C",
                "reportId": report_id,
                "failed_at": "See logs for detailed error information"
            }
        )

@app.get("/api/v1/report/{report_id}")
async def get_report_endpoint(report_id: str):
    """Retrieve a complete analysis report by ID."""
    logger.info(f"📋 Report request received for ID: {report_id}")
    
    try:
        # Try new format first
        final_json_path = ANALYSIS_DIR / f"{report_id}_final_comprehensive_report.json"
        
        if final_json_path.exists():
            with open(final_json_path, "r", encoding='utf-8') as f:
                final_report = json.load(f)
            
            logger.info(f"✅ Returning comprehensive analysis report for ID: {report_id}")
            return {
                "reportId": report_id, 
                "reportData": final_report,
                "analysisType": "comprehensive_progressive"
            }
        
        # Fallback to legacy format
        analysis_json_path = ANALYSIS_DIR / f"{report_id}_analysis.json"
        report_json_path = ANALYSIS_DIR / f"{report_id}_report.json"

        if analysis_json_path.exists() and report_json_path.exists():
            with open(analysis_json_path, "r", encoding='utf-8') as f:
                llm_analysis = json.load(f)
            
            with open(report_json_path, "r", encoding='utf-8') as f:
                report_data = json.load(f)
            
            logger.info(f"✅ Returning legacy analysis report for ID: {report_id}")
            return {
                "reportId": report_id, 
                "llmAnalysis": llm_analysis,
                "reportData": report_data,
                "analysisType": "legacy_comprehensive"
            }
        
        logger.warning(f"❌ Report not found for ID: {report_id}")
        raise HTTPException(status_code=404, detail="Report not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"💥 Error retrieving report {report_id}")
        raise HTTPException(status_code=500, detail=f"Error retrieving report: {str(e)}")

@app.post("/api/v1/trigger-outreach/")
async def trigger_outreach_endpoint(request: OutreachRequest):
    """Trigger outreach campaigns for target restaurant or competitors."""
    logger.info(f"📞 Outreach request for report ID: {request.report_id}, type: {request.target_type}")
    
    try:
        # Import here to avoid circular imports
        from restaurant_consultant.outreach_automation_module import send_outreach_to_target, send_outreach_to_competitor
        
        if not request.user_consent and request.target_type == "competitor":
            logger.warning(f"❌ Competitor outreach blocked for {request.report_id} - no consent")
            raise HTTPException(status_code=403, detail="User consent required for competitor outreach.")

        # Try to load from new format first
        final_json_path = ANALYSIS_DIR / f"{request.report_id}_final_comprehensive_report.json"
        report_data = None
        
        if final_json_path.exists():
            with open(final_json_path, "r", encoding='utf-8') as f:
                final_report = json.load(f)
                # Convert to legacy format for outreach modules
                report_data = {
                    "restaurant_name": final_report.get("restaurant_name"),
                    "competitors": {
                        "competitors": final_report.get("competitors", [])
                    }
                }
        else:
            # Fallback to legacy format
            report_json_path = ANALYSIS_DIR / f"{request.report_id}_report.json"
            if not report_json_path.exists():
                logger.error(f"❌ Report data not found for outreach request: {request.report_id}")
                raise HTTPException(status_code=404, detail="Report data not found")
            
            with open(report_json_path, "r", encoding='utf-8') as f:
                report_data = json.load(f)

        if request.target_type == "target":
            # For now, we'll skip the target analysis XML requirement
            # In future, we can generate this from the strategic analysis
            logger.info(f"✅ Outreach would be triggered for target restaurant: {report_data.get('restaurant_name', 'Unknown')}")
            return {
                "status": "success", 
                "message": "Target outreach capability available - contact sales for implementation.", 
                "reportId": request.report_id
            }

        elif request.target_type == "competitor":
            if not request.competitor_name:
                logger.warning(f"❌ Competitor name missing for outreach request: {request.report_id}")
                raise HTTPException(status_code=400, detail="Competitor name is required for competitor outreach.")

            competitor_data = next(
                (comp for comp in report_data.get("competitors", {}).get("competitors", []) 
                 if comp.get("name") == request.competitor_name), 
                None
            )
            
            if not competitor_data:
                logger.warning(f"❌ Competitor '{request.competitor_name}' not found in report {request.report_id}")
                raise HTTPException(status_code=404, detail=f"Competitor '{request.competitor_name}' not found in report.")
            
            logger.info(f"✅ Outreach would be triggered for competitor: {request.competitor_name}")
            return {
                "status": "success", 
                "message": f"Competitor outreach capability available for {request.competitor_name} - contact sales for implementation.", 
                "reportId": request.report_id
            }
        
        else:
            logger.warning(f"❌ Invalid target_type for outreach: {request.target_type}")
            raise HTTPException(status_code=400, detail="Invalid target_type. Must be 'target' or 'competitor'.")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"💥 Unhandled error in /trigger-outreach for report ID: {request.report_id}")
        raise HTTPException(status_code=500, detail=f"Outreach error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    logger.info("🌟 Starting Restaurant AI Consulting API server...")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        timeout_keep_alive=300,  # 5 minutes keep-alive
        timeout_graceful_shutdown=30,  # 30 seconds for graceful shutdown
        access_log=True
    )

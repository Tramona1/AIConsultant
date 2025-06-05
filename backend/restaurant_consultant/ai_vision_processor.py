"""
AI Vision Processor for Restaurant Data Extraction
Uses Google Gemini Vision API for image and PDF analysis
"""

import logging
import asyncio
import base64
import io
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import json
import os
from urllib.parse import unquote

import httpx
import google.generativeai as genai
from PIL import Image
import fitz  # PyMuPDF for PDF processing

from .models import ScreenshotInfo, MenuItem

logger = logging.getLogger(__name__)

class AIVisionProcessor:
    """
    Processes screenshots and PDFs using AI vision models to extract:
    - Menu items
    - Text content
    - Key visual elements
    """
    
    def __init__(self):
        """Initialize the AI Vision processor"""
        # Initialize Gemini client
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_AI_API_KEY')
        self.enabled = bool(api_key)
        self.api_key = api_key
        
        if self.enabled:
            logger.info("✅ AI Vision Processor initialized with Gemini API")
        else:
            logger.warning("⚠️ AI Vision Processor disabled - no API key found")

    async def _make_simple_gemini_vision_call(self, image_data: bytes, prompt: str) -> Optional[str]:
        """Make a simple Gemini Vision API call"""
        if not self.enabled:
            return None
            
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            
            # Convert image to PIL Image
            image = Image.open(io.BytesIO(image_data))
            
            # Use Gemini Flash model for vision
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            logger.info("🔗 Making simple Gemini Vision API call")
            response = model.generate_content([prompt, image])
            
            if response and response.text:
                logger.info("✅ Gemini Vision API call successful")
                return response.text.strip()
            else:
                logger.warning("⚠️ Empty response from Gemini Vision API")
                return None
                
        except Exception as e:
            logger.error(f"❌ Gemini Vision API call failed: {str(e)}")
            return None

    async def _analyze_image(self, image_s3_url: str) -> Optional[Dict[str, Any]]:
        """Analyze a single image using AI vision"""
        try:
            # For S3 URLs (mock), return mock data
            if image_s3_url.startswith("s3://"):
                logger.debug(f"Mock processing image S3 URL: {image_s3_url}")
                return await self._mock_analyze_image()
            
            # Handle local file paths with file:// protocol
            if image_s3_url.startswith("file://"):
                local_file_path = image_s3_url.replace("file://", "")
                # URL decode the path to handle %20 and other encoded characters
                local_file_path = unquote(local_file_path)
                logger.info(f"📂 Processing local image file: {local_file_path}")
                
                try:
                    with open(local_file_path, 'rb') as f:
                        image_data = f.read()
                    
                    logger.info(f"✅ Successfully loaded image: {len(image_data)} bytes")
                    
                    # Simple prompt for menu analysis
                    prompt = """
                    Analyze this restaurant website screenshot. Look for:
                    1. Menu items with names and prices
                    2. Contact information (phone, email, address)
                    3. Restaurant hours
                    4. Special offers or promotions
                    
                    Extract any menu items you can see clearly. Return a JSON object with:
                    {
                        "menu_items": [{"name": "item name", "price": "price", "description": "description"}],
                        "contact_info": {"phone": "", "email": "", "address": ""},
                        "hours": "business hours if visible",
                        "special_offers": ["any offers or promotions"],
                        "page_type": "homepage|menu|contact|about|other"
                    }
                    """
                    
                    # Make simple API call
                    response_text = await self._make_simple_gemini_vision_call(image_data, prompt)
                    
                    if response_text:
                        try:
                            # Try to parse JSON from response
                            import re
                            # Look for JSON in the response
                            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                            if json_match:
                                result = json.loads(json_match.group())
                                logger.info(f"✅ Successfully analyzed image - found {len(result.get('menu_items', []))} menu items")
                                return result
                            else:
                                # If no JSON, create structured response
                                return {
                                    "menu_items": [],
                                    "contact_info": {},
                                    "hours": "",
                                    "special_offers": [],
                                    "page_type": "other",
                                    "raw_analysis": response_text
                                }
                        except json.JSONDecodeError:
                            logger.warning("⚠️ Could not parse JSON from vision response, using raw text")
                            return {
                                "menu_items": [],
                                "contact_info": {},
                                "hours": "",
                                "special_offers": [],
                                "page_type": "other",
                                "raw_analysis": response_text
                            }
                    
                except FileNotFoundError:
                    logger.error(f"❌ Local image file not found: {local_file_path}")
                    return None
                except Exception as e:
                    logger.error(f"❌ Error processing local image {local_file_path}: {str(e)}")
                    return None
            
            # Handle real S3 or HTTP URLs
            if image_s3_url.startswith(("http://", "https://")):
                logger.info(f"🌐 Processing remote image: {image_s3_url}")
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.get(image_s3_url)
                        response.raise_for_status()
                        image_data = response.content
                        
                        # Use same analysis as local files
                        prompt = "Analyze this restaurant screenshot and extract menu items, contact info, and other relevant information. Return results as JSON."
                        response_text = await self._make_simple_gemini_vision_call(image_data, prompt)
                        
                        if response_text:
                            return {"raw_analysis": response_text, "menu_items": [], "contact_info": {}}
                        
                except Exception as e:
                    logger.error(f"❌ Error processing remote image {image_s3_url}: {str(e)}")
                    return None
            
            logger.warning(f"⚠️ Unsupported image URL format: {image_s3_url}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Image analysis failed: {str(e)}")
            return None

    async def _analyze_pdf(self, pdf_s3_url: str) -> Optional[Dict[str, Any]]:
        """Analyze a PDF for menu items, converting pages to images first"""
        try:
            # For S3 URLs (mock), return mock data
            if pdf_s3_url.startswith("s3://"):
                logger.debug(f"Mock processing PDF S3 URL: {pdf_s3_url}")
                return await self._mock_analyze_pdf()
            
            # Handle local file paths with file:// protocol
            if pdf_s3_url.startswith("file://"):
                local_file_path = pdf_s3_url.replace("file://", "")
                # URL decode the path to handle %20 and other encoded characters
                local_file_path = unquote(local_file_path)
                logger.info(f"📂 Processing local PDF file: {local_file_path}")
                
                try:
                    # Open PDF and convert first page to image
                    doc = fitz.open(local_file_path)
                    page = doc[0]  # Get first page
                    pix = page.get_pixmap()
                    img_data = pix.tobytes("png")
                    doc.close()
                    
                    # Analyze the PDF page as an image
                    prompt = "This is a page from a restaurant menu PDF. Extract all menu items with names, prices, and descriptions. Return as JSON."
                    response_text = await self._make_simple_gemini_vision_call(img_data, prompt)
                    
                    if response_text:
                        try:
                            import re
                            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                            if json_match:
                                result = json.loads(json_match.group())
                                return result
                        except:
                            pass
                        
                        return {"raw_analysis": response_text, "menu_items": []}
                        
                except FileNotFoundError:
                    logger.error(f"❌ Local PDF file not found: {local_file_path}")
                    return None
                except Exception as e:
                    logger.error(f"❌ Error processing local PDF {local_file_path}: {str(e)}")
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"❌ PDF analysis failed: {str(e)}")
            return None

    async def _mock_analyze_image(self) -> Dict[str, Any]:
        """Return mock analysis for testing"""
        return {
            "menu_items": [],
            "contact_info": {},
            "hours": "",
            "special_offers": [],
            "page_type": "mock",
            "analysis_status": "mock_data"
        }

    async def _mock_analyze_pdf(self) -> Dict[str, Any]:
        """Return mock PDF analysis for testing"""
        return {
            "menu_items": [],
            "analysis_status": "mock_pdf_data"
        }

    async def process_screenshots(self, screenshot_urls: List[str]) -> List[Dict[str, Any]]:
        """Process multiple screenshots and return analysis results"""
        logger.info(f"🔄 Processing {len(screenshot_urls)} screenshots for AI analysis")
        
        if not self.enabled:
            logger.warning("⚠️ AI Vision disabled - skipping screenshot analysis")
            return []
        
        results = []
        
        for i, url in enumerate(screenshot_urls):
            logger.info(f"📸 Processing screenshot {i+1}/{len(screenshot_urls)}: {url}")
            
            try:
                analysis_result = await self._analyze_image(url)
                
                if analysis_result:
                    analysis_result['screenshot_url'] = url
                    analysis_result['processed_at'] = datetime.now().isoformat()
                    results.append(analysis_result)
                    logger.info(f"✅ Successfully processed screenshot {i+1}")
                else:
                    logger.warning(f"⚠️ Failed to analyze screenshot {i+1}")
                    
            except Exception as e:
                logger.error(f"❌ Error processing screenshot {i+1}: {str(e)}")
                continue
        
        logger.info(f"✅ Completed screenshot processing: {len(results)}/{len(screenshot_urls)} successful")
        return results

    async def process_pdfs(self, pdf_urls: List[str]) -> List[Dict[str, Any]]:
        """Process multiple PDFs and return analysis results"""
        logger.info(f"🔄 Processing {len(pdf_urls)} PDFs for AI analysis")
        
        if not self.enabled:
            logger.warning("⚠️ AI Vision disabled - skipping PDF analysis")
            return []
        
        results = []
        
        for i, url in enumerate(pdf_urls):
            logger.info(f"📄 Processing PDF {i+1}/{len(pdf_urls)}: {url}")
            
            try:
                analysis_result = await self._analyze_pdf(url)
                
                if analysis_result:
                    analysis_result['pdf_url'] = url
                    analysis_result['processed_at'] = datetime.now().isoformat()
                    results.append(analysis_result)
                    logger.info(f"✅ Successfully processed PDF {i+1}")
                else:
                    logger.warning(f"⚠️ Failed to analyze PDF {i+1}")
                    
            except Exception as e:
                logger.error(f"❌ Error processing PDF {i+1}: {str(e)}")
                continue
        
        logger.info(f"✅ Completed PDF processing: {len(results)}/{len(pdf_urls)} successful")
        return results

    async def process_visual_content(self,
                                   screenshot_info_list: List[ScreenshotInfo],
                                   pdf_s3_urls: List[str]) -> Dict[str, Any]:
        """
        Process both screenshots and PDFs for comprehensive visual analysis.
        This is the main entry point called by progressive_data_extractor.
        """
        logger.info(f"🔍 Processing {len(screenshot_info_list)} screenshots and {len(pdf_s3_urls)} PDFs")
        
        try:
            # Process screenshots
            screenshot_urls = [info.s3_url for info in screenshot_info_list]
            screenshot_results = await self.process_screenshots(screenshot_urls)
            
            # Process PDFs
            pdf_results = await self.process_pdfs(pdf_s3_urls)
            
            # Combine and structure results
            all_menu_items = []
            contact_info = {}
            hours_found = ""
            special_offers = []
            
            # Extract from screenshots
            for result in screenshot_results:
                if result and isinstance(result, dict):
                    all_menu_items.extend(result.get('menu_items', []))
                    if result.get('contact_info'):
                        contact_info.update(result.get('contact_info', {}))
                    if result.get('hours'):
                        hours_found = result.get('hours', '')
                    special_offers.extend(result.get('special_offers', []))
            
            # Extract from PDFs
            for result in pdf_results:
                if result and isinstance(result, dict):
                    all_menu_items.extend(result.get('menu_items', []))
                    if result.get('contact_info'):
                        contact_info.update(result.get('contact_info', {}))
            
            # Return structured output
            final_result = {
                "menu_items": all_menu_items,
                "contact_info": contact_info,
                "hours": hours_found,
                "special_offers": special_offers,
                "screenshots_processed": len(screenshot_results),
                "pdfs_processed": len(pdf_results),
                "total_menu_items_found": len(all_menu_items)
            }
            
            logger.info(f"✅ Visual content processing complete: {len(all_menu_items)} menu items found")
            return final_result
            
        except Exception as e:
            logger.error(f"❌ Visual content processing failed: {str(e)}")
            return {
                "menu_items": [],
                "contact_info": {},
                "hours": "",
                "special_offers": [],
                "screenshots_processed": 0,
                "pdfs_processed": 0,
                "total_menu_items_found": 0,
                "error": str(e)
            } 
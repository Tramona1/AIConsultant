import subprocess
import json
import os
import asyncio
import logging
from typing import Dict, Optional, List, TypedDict, Any
from pathlib import Path
import aiofiles
import httpx
from datetime import datetime
import re
import uuid
import time
import traceback
import shutil
from .models import ScreenshotInfo, MenuItem

# Set up logging
logger = logging.getLogger(__name__)

class ScrapingResult(TypedDict, total=False):
    """Type-safe structure for scraping results."""
    name: Optional[str]
    url: str
    html_content: str
    menu_screenshot: Optional[str]
    all_screenshots: List[str]
    contact: Dict[str, Optional[str]]
    address: Optional[str]
    social_links: List[str]
    menu: Dict
    products: List[Dict]
    services: List[Dict]
    business_info: Dict
    scraped_at: Optional[str]
    scraper_used: str
    data_quality: Dict
    crawling_stats: Dict
    screenshot_type: str
    enhanced_raw_data: Dict

def _safe_env_log(env_vars: Dict[str, str]) -> List[str]:
    """Safely log environment variable names without exposing secrets."""
    # Only log variable names that are safe to expose
    safe_prefixes = ['BROWSERBASE_', 'GOOGLE_', 'OPENAI_']
    safe_keys = []
    
    for key in env_vars:
        # Only log the key name if it's a known safe prefix and ends with safe suffixes
        if any(key.startswith(prefix) for prefix in safe_prefixes):
            if key.endswith(('_URL', '_REGION', '_VERSION')):
                safe_keys.append(key)
            elif key.endswith(('_KEY', '_SECRET', '_TOKEN')):
                # For secrets, just indicate presence without showing the name
                safe_keys.append(f"{key.split('_')[0]}_***")
            elif key.endswith('_ID'):
                safe_keys.append(key)  # IDs are generally safe to log
    
    return safe_keys

async def load_env_file_async(env_path: Path) -> Dict[str, str]:
    """Load environment variables from a .env file asynchronously."""
    env_vars = {}
    if env_path.exists():
        try:
            async with aiofiles.open(env_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
            
            safe_keys = _safe_env_log(env_vars)
            logger.info(f"✅ Loaded {len(env_vars)} environment variables from {env_path}")
            logger.debug(f"Safe environment variables: {safe_keys}")
        except Exception as e:
            logger.warning(f"Failed to load .env file {env_path}: {str(e)}")
    return env_vars

def _safe_latest_file(pattern: str, base_dir: Path) -> Optional[Path]:
    """Safely find the latest file matching pattern, preventing path traversal."""
    try:
        base_dir = base_dir.resolve()  # Normalize the base directory
        candidates = []
        
        for file_path in base_dir.glob(pattern):
            resolved_path = file_path.resolve()
            # Ensure the resolved path is still within the base directory
            try:
                resolved_path.relative_to(base_dir)
                candidates.append(resolved_path)
            except ValueError:
                # Path is outside base directory - potential traversal attack
                logger.warning(f"Blocked potential path traversal attempt: {file_path}")
                continue
        
        if not candidates:
            return None
            
        # Return the most recently created file
        return max(candidates, key=lambda p: p.stat().st_ctime)
        
    except Exception as e:
        logger.error(f"Error finding latest file with pattern {pattern}: {str(e)}")
        return None

# Helper function to find the root project directory more reliably
def find_project_root(current_path: Path, marker_file: str = "pyproject.toml") -> Path:
    """Traverse upwards to find the project root directory."""
    path = current_path.resolve()
    while path != path.parent:
        if (path / marker_file).exists() or (path / ".git").exists(): # Common markers
            return path
        path = path.parent
    # Fallback or raise error if not found
    logger.warning(f"Could not find project root from {current_path} using marker {marker_file}. Falling back to a default relative path assumption.")
    # Adjust this fallback based on your typical project structure
    # This assumes backend/ is one level down from the project root where stagehand-scraper/ might be
    return current_path.parent.parent

class StagehandScraper:
    """Python wrapper for the Node.js Stagehand scraper with enhanced security and async support."""
    
    def __init__(self):
        # Determine project root and then construct paths
        # Assuming this script is within backend/restaurant_consultant/
        current_file = Path(__file__).resolve()
        backend_dir = current_file.parent.parent  # Go up from restaurant_consultant/ to backend/
        project_root = backend_dir.parent  # Go up from backend/ to project root
        
        # Set up paths
        self.scraper_dir = project_root / "stagehand-scraper"
        self.scraper_script = self.scraper_dir / "enhanced-scraper.js"
        
        # Cache the Node.js executable path for performance
        self._node_executable = None
        
        # Environment variables will be loaded on demand
        self.env_vars = None
        
        logger.info(f"🔧 StagehandScraper initialized")
        logger.info(f"   Project root: {project_root}")
        logger.info(f"   Scraper directory: {self.scraper_dir}")
        logger.info(f"   Scraper script: {self.scraper_script}")
        
        # Verify the script exists
        if not self.scraper_script.exists():
            logger.warning(f"⚠️ Scraper script not found: {self.scraper_script}")
    
    def _get_node_executable(self) -> str:
        """Get the Node.js executable, using cached value if available."""
        if self._node_executable is None:
            logger.info("🔍 Detecting Node.js installation...")
            self._node_executable = _find_node_executable()
        return self._node_executable
    
    async def _ensure_env_loaded(self) -> None:
        """Ensure environment variables are loaded asynchronously."""
        if self.env_vars is None:
            env_file = self.scraper_dir / ".env"
            self.env_vars = await load_env_file_async(env_file)
    
    async def scrape_restaurant(self, url: str, timeout: float = 90.0) -> ScrapingResult:
        """
        Scrape a restaurant website using enhanced Stagehand scraper with unique output files.
        """
        logger.info(f"Starting enhanced Stagehand scrape for: {url}")
        
        await self._ensure_env_loaded()
        
        try:
            # FIXED: Generate unique output filename to prevent conflicts
            unique_id = uuid.uuid4().hex[:8]  # Short unique ID
            output_filename = f"enhanced-scraping-results-{unique_id}.json"
            output_file_path = self.scraper_dir / output_filename
            
            # Create command for comprehensive scraping
            cmd_args = [self._get_node_executable(), str(self.scraper_script), url, '--output-file', output_filename]
            
            logger.info(f"🚀 Running enhanced scraper with unique output: {output_filename}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                cwd=str(self.scraper_dir),
                env=self.env_vars,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait for the process to complete with configurable timeout
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()  # Ensure cleanup
                logger.error(f"Stagehand scraper timed out for {url} after {timeout}s")
                raise RuntimeError(f"Stagehand scraper timed out after {timeout} seconds")
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown error"
                # Log first few lines of stderr for debugging
                stderr_lines = error_msg.split('\n')[:5]
                logger.error(f"Stagehand scraper failed with return code {process.returncode}")
                logger.error(f"Error preview: {stderr_lines}")
                raise RuntimeError(f"Stagehand scraper failed: {error_msg}")
            
            # Parse the output for JSON data
            output = stdout.decode('utf-8') if stdout else ""
            logger.info(f"📏 Stagehand output length: {len(output)} characters")
            
            # Parse the output for JSON data
            json_data = await self._extract_json_from_output_async(output, output_file_path)
            
            if not json_data:
                logger.warning("Failed to extract JSON from Stagehand output")
                return self._create_fallback_result(url)
                
            logger.info("✅ Successfully parsed JSON from Stagehand")
            
            # Clean up the output file after successful parsing
            try:
                if output_file_path.exists():
                    output_file_path.unlink()
                    logger.debug(f"🗑️ Cleaned up output file: {output_filename}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup output file: {cleanup_error}")
            
            # Log extraction quality for debugging
            quality_score = sum(json_data.get('dataQuality', {}).values()) if json_data.get('dataQuality') else 0
            name = json_data.get('combinedData', {}).get('name') or json_data.get('name') or 'Unknown'
            logger.info(f"📊 Stagehand extraction quality: {quality_score} fields extracted for {name}")
            
            # Transform the enhanced Stagehand data into our expected format
            result = await self._transform_stagehand_data_async(json_data, url)
            
            return result
            
        except Exception as e:
            logger.error(f"Error running Stagehand scraper for {url}: {str(e)}")
            raise
    
    async def _extract_json_from_output_async(self, output: str, output_file_path: Path) -> Optional[Dict]:
        """Extract JSON from output with improved error handling."""
        if not output or not output.strip():
            logger.warning("Empty output received from Stagehand")
            return None
            
        # Strategy 1: Look for the specific output file first
        if output_file_path and output_file_path.exists():
            try:
                json_data = await self._load_json_file_async(output_file_path)
                if json_data and isinstance(json_data, dict):
                    # FIXED: Preserve root-level structure including dataQuality field
                    # Don't extract just combinedData, return the full structure
                    logger.info(f"✅ Loaded enhanced results from: {output_file_path.name}")
                    
                    # Log the dataQuality field to verify it exists
                    data_quality = json_data.get('dataQuality', {})
                    if data_quality:
                        quality_score = sum(1 for v in data_quality.values() if v)
                        logger.info(f"📊 DataQuality field found with {quality_score} true values: {data_quality}")
                    else:
                        logger.warning("📊 No dataQuality field found in JSON data")
                    
                    return json_data
            except Exception as e:
                logger.warning(f"Failed to load specific output file: {str(e)}")
        
        # Strategy 2: Try to parse JSON directly from output
        try:
            return json.loads(output.strip())
        except json.JSONDecodeError:
            # Strategy 3: Try to extract from lines
            return self._parse_json_from_lines(output)
        except Exception as e:
            logger.warning(f"JSON extraction failed: {str(e)}")
            return None

    async def _find_latest_results_file_async(self, pattern: str) -> Optional[Path]:
        """Find the latest results file matching the pattern safely."""
        return _safe_latest_file(pattern, self.scraper_dir)

    async def _load_json_file_async(self, file_path: Path) -> Optional[Dict]:
        """Load JSON file asynchronously with proper error handling."""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to load JSON file {file_path}: {str(e)}")
            return None
    
    def _parse_json_from_lines(self, output: str) -> Optional[Dict]:
        """Parse JSON from output lines as fallback method."""
        lines = output.strip().split('\n')
        
        # Look for complete JSON objects in single lines first
        for line in reversed(lines):
            line = line.strip()
            if line.startswith('{') and line.endswith('}'):
                try:
                    parsed = json.loads(line)
                    logger.info("✅ Successfully parsed JSON from output line")
                    return parsed
                except json.JSONDecodeError:
                    continue
        
        logger.error("❌ Could not extract valid JSON from output")
        return None
    
    async def _transform_stagehand_data_async(self, stagehand_data: Dict, url: str) -> ScrapingResult:
        """Transform Enhanced Stagehand output to match our expected data format."""
        
        logger.info("🔄 Transforming enhanced Stagehand data with business intelligence...")
        
        # FIXED: Handle preserved root-level structure properly
        # The stagehand_data now contains the full JSON structure with dataQuality at root level
        combined_data = stagehand_data.get('combinedData', {})
        
        # If no combinedData, the data might be at root level (fallback handling)
        if not combined_data and stagehand_data.get('name'):
            combined_data = stagehand_data
            logger.info("Using root-level data as combined_data (fallback mode)")
        
        business_intelligence = combined_data.get('businessIntelligence', {})
        
        # Extract menu items from business intelligence
        menu_items = []
        enhanced_menu_items = business_intelligence.get('menuItems', [])
        
        if not enhanced_menu_items:
            enhanced_menu_items = combined_data.get('menuItems', [])
        
        # Process menu items with validation
        for item in enhanced_menu_items:
            if isinstance(item, dict) and item.get('name'):
                menu_items.append({
                    'name': str(item.get('name', '')),
                    'description': str(item.get('description', '')),
                    'price': str(item.get('price', '')),
                    'category': str(item.get('category', '')),
                    'source': 'enhanced_stagehand'
                })
        
        # Extract products and services with validation
        products = self._extract_items_list(business_intelligence.get('products', []), 'product')
        services = self._extract_items_list(business_intelligence.get('services', []), 'service')
        
        logger.info(f"🔄 Enhanced data extraction: {len(menu_items)} menu items, {len(products)} products, {len(services)} services")
        
        # Extract comprehensive business information
        business_info = await self._extract_business_info_async(combined_data, business_intelligence)
        
        # Handle screenshots safely (check both root and pages structure)
        screenshot_urls, screenshots = await self._process_screenshots_async(stagehand_data)
        
        # FIXED: Extract dataQuality from root level where enhanced scraper puts it
        data_quality = stagehand_data.get('dataQuality', {})
        
        # Create the result with type safety
        result: ScrapingResult = {
            'name': combined_data.get('name'),
            'url': url,
            'html_content': '',  # Enhanced scraper uses AI extraction
            'menu_screenshot': screenshot_urls[0] if screenshot_urls else (screenshots[0] if screenshots else None),
            'all_screenshots': screenshot_urls + screenshots,
            
            'contact': {
                'email': combined_data.get('email'),
                'phone': combined_data.get('phone')
            },
            'address': combined_data.get('address'),
            'social_links': combined_data.get('socialLinks', []),
            
            'menu': {
                'items': menu_items,
                'screenshot': screenshot_urls[0] if screenshot_urls else (screenshots[0] if screenshots else None),
                'total_items': len(menu_items),
                'categories': list(set(item.get('category', '') for item in menu_items if item.get('category')))
            },
            
            'products': products,
            'services': services,
            'business_info': business_info,
            
            'scraped_at': stagehand_data.get('scrapedAt') or datetime.now().isoformat(),
            'scraper_used': 'enhanced_stagehand',
            'data_quality': data_quality,  # Now correctly gets from root level
            'crawling_stats': combined_data.get('crawlingStats', {}),
            'screenshot_type': 'enhanced_multi_page',
            'enhanced_raw_data': stagehand_data
        }
        
        # Log transformation summary with improved quality reporting
        self._log_transformation_summary(result)
        
        # Log final data quality score
        if data_quality:
            quality_score = sum(1 for v in data_quality.values() if v)
            logger.info(f"📊 Final transformation quality score: {quality_score}/{len(data_quality)} fields extracted")
        
        return result
    
    def _extract_items_list(self, items: List, item_type: str) -> List[Dict]:
        """Extract and validate items from business intelligence data."""
        result = []
        for item in items:
            if isinstance(item, dict) and item.get('name'):
                validated_item = {
                    'name': str(item.get('name', '')),
                    'description': str(item.get('description', '')),
                    'source': 'enhanced_stagehand'
                }
                
                if item_type == 'product':
                    validated_item.update({
                        'price': str(item.get('price', '')),
                        'category': str(item.get('category', ''))
                    })
                elif item_type == 'service':
                    validated_item.update({
                        'pricing': str(item.get('pricing', '')),
                        'serviceArea': str(item.get('serviceArea', '')),
                        'capacity': str(item.get('capacity', '')),
                        'bookingProcess': str(item.get('bookingProcess', ''))
                    })
                
                result.append(validated_item)
        
        return result
    
    async def _extract_business_info_async(self, combined_data: Dict, business_intelligence: Dict) -> Dict:
        """Extract comprehensive business information asynchronously."""
        business_info = {}
        
        # Basic restaurant info
        basic_fields = ['restaurant_name', 'restaurant_type', 'phone', 'address', 'email']
        field_mapping = {
            'restaurant_name': 'name',
            'restaurant_type': 'restaurantType'
        }
        
        for field in basic_fields:
            source_field = field_mapping.get(field, field)
            value = combined_data.get(source_field)
            if value:
                business_info[field] = str(value)
        
        # Enhanced business intelligence data
        if business_intelligence:
            intelligence_fields = [
                'revenueStreams', 'competitiveAdvantages', 'businessModel',
                'companyInfo', 'operations', 'summary'
            ]
            
            for field in intelligence_fields:
                value = business_intelligence.get(field)
                if value:
                    if field == 'summary':
                        summary = value
                        business_info.update({
                            'business_scope': summary.get('businessScope', []),
                            'market_position': summary.get('marketPosition', []),
                            'operational_scale': summary.get('operationalScale', [])
                        })
                    else:
                        snake_case_field = self._camel_to_snake(field)
                        business_info[snake_case_field] = value
        
        # Crawling statistics
        crawling_stats = combined_data.get('crawlingStats', {})
        if crawling_stats:
            stats_mapping = {
                'pages_analyzed': 'totalPagesFound',
                'successful_extractions': 'successfulExtractions',
                'products_count': 'totalProducts',
                'services_count': 'totalServices'
            }
            
            for target_field, source_field in stats_mapping.items():
                value = crawling_stats.get(source_field)
                if value is not None:
                    business_info[target_field] = value
        
        return business_info
    
    async def _process_screenshots_async(self, stagehand_data: Dict) -> tuple[List[str], List[str]]:
        """Process screenshots from stagehand data with enhanced page-level support."""
        screenshot_urls = []
        screenshots = []
        
        # FIXED: Process screenshots from all pages, not just main screenshot
        pages = stagehand_data.get('pages', {})
        for page_type, page_data in pages.items():
            page_screenshots = page_data.get('screenshots', [])
            for screenshot_info in page_screenshots:
                if isinstance(screenshot_info, dict):
                    # Enhanced scraper provides detailed screenshot info
                    s3_url = screenshot_info.get('s3Url')
                    local_path = screenshot_info.get('path')
                    
                    if s3_url and s3_url.startswith('http'):
                        screenshot_urls.append(s3_url)
                        logger.info(f"✅ Found S3 screenshot for {page_type}: {s3_url}")
                    elif local_path:
                        screenshots.append(local_path)
                        logger.info(f"📁 Found local screenshot for {page_type}: {local_path}")
                elif isinstance(screenshot_info, str):
                    # Simple string path
                    if screenshot_info.startswith('http'):
                        screenshot_urls.append(screenshot_info)
                    else:
                        screenshots.append(screenshot_info)
        
        # Also check main screenshot for backward compatibility
        main_screenshot = stagehand_data.get('screenshot')
        if main_screenshot:
            if main_screenshot.startswith('http'):
                if main_screenshot not in screenshot_urls:
                    screenshot_urls.append(main_screenshot)
                    logger.info(f"✅ Added main S3 screenshot: {main_screenshot}")
            else:
                if main_screenshot not in screenshots:
                    screenshots.append(main_screenshot)
                    logger.info(f"📁 Added main local screenshot: {main_screenshot}")
        
        total_screenshots = len(screenshot_urls) + len(screenshots)
        logger.info(f"📸 Processed {total_screenshots} total screenshots: {len(screenshot_urls)} S3, {len(screenshots)} local")
        
        return screenshot_urls, screenshots
    
    def _camel_to_snake(self, camel_str: str) -> str:
        """Convert camelCase to snake_case."""
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', camel_str).lower()
    
    def _log_transformation_summary(self, result: ScrapingResult) -> None:
        """Log comprehensive transformation summary."""
        logger.info("🎉 Enhanced Stagehand transformation complete:")
        logger.info(f"   📋 Menu items: {len(result['menu']['items'])}")
        logger.info(f"   🛍️ Products: {len(result['products'])}")
        logger.info(f"   🔧 Services: {len(result['services'])}")
        
        business_info = result['business_info']
        logger.info(f"   💰 Revenue streams: {len(business_info.get('revenue_streams', []))}")
        logger.info(f"   🎯 Competitive advantages: {len(business_info.get('competitive_advantages', []))}")
        logger.info(f"   📱 Social platforms: {len(result['social_links'])}")
        logger.info(f"   📸 Screenshots: {len(result['all_screenshots'])}")

    async def is_available_async(self) -> bool:
        """Check if Stagehand scraper is available and properly configured asynchronously."""
        try:
            # Check if Node.js is accessible
            process = await asyncio.create_subprocess_exec(
                self._get_node_executable(), '--version',
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10.0)
                if process.returncode != 0:
                    logger.warning("Node.js not found - Stagehand unavailable")
                    return False
                
                node_version = stdout.decode('utf-8').strip()
                logger.info(f"Node.js version detected: {node_version}")
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                logger.warning("Node.js check timed out - Stagehand unavailable")
                return False
            
            # Check if the scraper script exists
            if not self.scraper_script.exists():
                logger.warning(f"Stagehand scraper script not found at {self.scraper_script}")
                return False
            
            # Check if package.json and node_modules exist
            package_json_path = self.scraper_dir / "package.json"
            node_modules_path = self.scraper_dir / "node_modules"
            
            if not package_json_path.exists():
                logger.warning(f"package.json not found in {self.scraper_dir}")
                return False
            
            if not node_modules_path.exists():
                logger.warning(f"node_modules not found in {self.scraper_dir} - run 'npm install'")
                return False
            
            # Load and check environment variables
            await self._ensure_env_loaded()
            
            api_key = self.env_vars.get('BROWSERBASE_API_KEY') or os.getenv('BROWSERBASE_API_KEY')
            project_id = self.env_vars.get('BROWSERBASE_PROJECT_ID') or os.getenv('BROWSERBASE_PROJECT_ID')
            
            if not api_key:
                logger.warning("BROWSERBASE_API_KEY not configured - Stagehand unavailable")
                return False
                
            if not project_id:
                logger.warning("BROWSERBASE_PROJECT_ID not configured - Stagehand unavailable")
                return False
            
            logger.info("✅ Stagehand scraper is available and properly configured")
            return True
            
        except Exception as e:
            logger.warning(f"Error checking Stagehand availability: {str(e)}")
            return False

    def is_available(self) -> bool:
        """Synchronous wrapper for async availability check."""
        try:
            # Create a new event loop if none exists
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, we can't use run_until_complete
                    # Return a basic check instead
                    return (self.scraper_script.exists() and 
                           (self.scraper_dir / "package.json").exists() and
                           (self.scraper_dir / "node_modules").exists())
                else:
                    return loop.run_until_complete(self.is_available_async())
            except RuntimeError:
                # No event loop in current thread
                return asyncio.run(self.is_available_async())
        except Exception as e:
            logger.warning(f"Error in sync availability check: {str(e)}")
            return False

    def get_capabilities(self) -> Dict[str, bool]:
        """Return the capabilities of the Stagehand scraper."""
        return {
            'extract_name': True,
            'extract_contact': True,
            'extract_address': True,
            'extract_menu': True,
            'extract_social_links': True,
            'extract_business_hours': True,
            'extract_restaurant_type': True,
            'extract_seo_data': True,
            'take_screenshots': True,
            'data_quality_assessment': True,
            'async_processing': True,
            'security_hardened': True,
            'comprehensive_business_intelligence': True
        }

    def _check_for_api_errors(self, json_data: Dict) -> bool:
        """Check for API quota/billing errors in Stagehand results."""
        pages = json_data.get('pages', {})
        
        for page_type, page_data in pages.items():
            error = page_data.get('error', '')
            if error and ('429' in error or 'quota' in error.lower() or 'billing' in error.lower()):
                logger.error(f"🚨 API Quota Error in {page_type}: {error}")
                return True
                
        # Check combined data for errors too
        combined_data = json_data.get('combinedData', {})
        if combined_data.get('error'):
            error = combined_data['error']
            if '429' in error or 'quota' in error.lower() or 'billing' in error.lower():
                logger.error(f"🚨 API Quota Error in combined data: {error}")
                return True
                
        return False

    def _create_fallback_result(self, url: str) -> ScrapingResult:
        """Create a fallback result when JSON extraction fails."""
        logger.warning(f"Creating fallback result for {url}")
        return {
            'name': 'Unknown',
            'url': url,
            'html_content': '',
            'menu_screenshot': None,
            'all_screenshots': [],
            'contact': {},
            'address': '',
            'social_links': [],
            'menu': {'items': [], 'screenshot': None, 'total_items': 0, 'categories': []},
            'products': [],
            'services': [],
            'business_info': {},
            'scraped_at': datetime.now().isoformat(),
            'scraper_used': 'fallback',
            'data_quality': {},
            'crawling_stats': {},
            'screenshot_type': 'fallback',
            'enhanced_raw_data': {}
        }

    async def scrape_restaurant_selective(self, url: str, missing_fields: List[str], 
                                        context_data: Dict[str, Any], timeout: float = 120.0) -> Dict[str, Any]:
        """
        Selectively scrape a restaurant website using Stagehand for specific missing fields.
        Instructs the scraper to upload screenshots to S3 and returns their S3 URLs.
        """
        logger.info(f"Starting SELECTIVE Stagehand scrape for: {url} for fields: {missing_fields}")
        await self._ensure_env_loaded()

        request_id = uuid.uuid4().hex[:8]
        # Create a focused schema for the scraper
        focused_schema = self._create_focused_schema(missing_fields)
        focused_schema_json_string = json.dumps(focused_schema)

        # Define the output file path within the stagehand-scraper/tmp directory
        # Ensure the tmp directory exists
        tmp_dir = self.scraper_dir / "tmp"
        try:
            tmp_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured tmp directory exists at {tmp_dir}")
        except OSError as e:
            logger.error(f"Could not create tmp directory at {tmp_dir}: {e}")
            # Depending on desired behavior, you might want to raise an error here
            # or attempt to continue without a tmp file if the scraper can handle it.


        # Pass a unique ID for this run to help with output management if needed
        # Also, instruct to upload to S3 and define where to get screenshot info
        output_filename = f"selective_results_{request_id}.json"
        cmd_args = [
            self._get_node_executable(), 
            str(self.scraper_script), 
            url,
            "--focused-schema", focused_schema_json_string,
            "--upload-screenshots-s3",
            "--output-file", output_filename,
            "--run-id", request_id
        ]
        
        # Add context data if any (e.g., known name, address to help the scraper)
        if context_data:
            # Convert context_data to a JSON string to pass as a command line argument
            # This assumes enhanced-scraper.js is updated to handle a --context-data argument
            context_data_json_string = json.dumps(context_data)
            cmd_args.extend(['--context-data', context_data_json_string])


        logger.info(f"🚀 Running SELECTIVE scraper. Command: {' '.join(cmd_args)}")
        # Log the schema being sent for debugging
        logger.debug(f"Focused schema for selective scrape: {focused_schema_json_string}")

        process = await asyncio.create_subprocess_exec(
            *cmd_args,
            cwd=str(self.scraper_dir),
            env=self.env_vars,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            logger.error(f"Selective Stagehand scraper timed out for {url} after {timeout}s")
            # Consider what to return or raise here.
            # For now, returning empty results, but specific error handling might be better.
            return {"extracted_data": {}, "screenshots": [], "error": "Timeout"}

        if process.returncode != 0:
            error_msg = stderr.decode('utf-8', 'replace') if stderr else "Unknown error"
            logger.error(f"Selective Stagehand scraper failed for {url} with code {process.returncode}. Error: {error_msg[:500]}")
            return {"extracted_data": {}, "screenshots": [], "error": f"Scraper failed: {error_msg[:200]}"}

        # Attempt to load results from the specified output file
        output_file_path = tmp_dir / output_filename
        extracted_data: Dict[str, Any] = {}
        screenshot_infos: List[ScreenshotInfo] = []

        if output_file_path.exists():
            try:
                async with aiofiles.open(output_file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    json_results = json.loads(content)
                logger.info(f"Successfully loaded selective scrape results from {output_file_path}")
                
                # Process the results - this structure depends on enhanced-scraper.js output
                # Assuming it returns a dict where keys are the focused fields,
                # and a special key 'screenshots' for screenshot info.
                extracted_data = json_results.get("data", {}) # Main data
                
                # Process screenshots
                # Assuming enhanced-scraper.js output for screenshots is a list of dicts
                # like [{"s3_url": "...", "caption": "...", "taken_at": "ISO_TIMESTAMP"}, ...]
                raw_screenshots = json_results.get("screenshots", [])
                for sc_data in raw_screenshots:
                    try:
                        # Convert taken_at to datetime if present and it's a string
                        taken_at_raw = sc_data.get("taken_at")
                        taken_at_dt = None
                        if isinstance(taken_at_raw, str):
                            try:
                                taken_at_dt = datetime.fromisoformat(taken_at_raw.replace("Z", "+00:00"))
                            except ValueError:
                                logger.warning(f"Could not parse taken_at timestamp: {taken_at_raw}")
                        elif isinstance(taken_at_raw, datetime): # If already datetime
                             taken_at_dt = taken_at_raw
                        
                        screenshot_infos.append(
                            ScreenshotInfo(
                                s3_url=sc_data["s3_url"], # Required
                                caption=sc_data.get("caption"),
                                source_phase=4, # Phase 4 for Stagehand
                                taken_at=taken_at_dt or datetime.now() # Fallback to now if not provided or parse error
                            )
                        )
                    except KeyError as e:
                        logger.warning(f"Skipping screenshot due to missing key {e} in data: {sc_data}")
                    except Exception as e: # Catch any Pydantic validation errors or others
                        logger.error(f"Error processing screenshot data {sc_data}: {e}")
                
                logger.info(f"Processed {len(screenshot_infos)} screenshots from selective scrape.")

            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON from {output_file_path}: {e}. Content: {content[:500]}")
                return {"extracted_data": {}, "screenshots": [], "error": "JSONDecodeError"}
            except Exception as e:
                logger.error(f"Error reading or processing selective scrape output file {output_file_path}: {e}")
                return {"extracted_data": {}, "screenshots": [], "error": f"FileProcessingError: {str(e)}"}
            finally:
                # Clean up the output file
                try:
                    if output_file_path.exists():
                        output_file_path.unlink()
                        logger.debug(f"Cleaned up selective output file: {output_file_path}")
                except OSError as e:
                    logger.warning(f"Could not delete selective output file {output_file_path}: {e}")
        else:
            logger.warning(f"Selective scrape output file not found: {output_file_path}. Stdout: {stdout.decode('utf-8', 'replace')[:500] if stdout else 'N/A'}")
            # If no file, attempt to parse stdout directly, though this is less robust for large outputs
            # This part can be expanded if stdout parsing is a primary method for selective scrapes.
            # For now, relying on the output file is cleaner.
            return {"extracted_data": {}, "screenshots": [], "error": "OutputFileMissing"}


        logger.info(f"Selective Stagehand scrape for {url} completed. Extracted fields: {list(extracted_data.keys())}, Screenshots: {len(screenshot_infos)}")
        return {"extracted_data": extracted_data, "screenshots": screenshot_infos}

    def _create_focused_schema(self, missing_fields: List[str]) -> Dict[str, Any]:
        """
        Create a focused schema for the Node.js scraper based on missing fields.
        This schema tells the scraper what specific pieces of information to target.
        The structure of this schema must align with what enhanced-scraper.js expects.
        """
        # This is a simplified example. The actual schema structure will depend heavily
        # on how `enhanced-scraper.js` is designed to interpret it.
        # We assume it expects a dictionary where keys are data points it knows how to find.
        
        # Mapping from FinalRestaurantOutput field names to Stagehand/Zod schema field names if they differ.
        # For now, assuming a direct or similar mapping.
        # Example: 'canonical_phone_number' -> 'phone', 'structured_address' -> 'address'
        field_map = {
            "restaurant_name": "name",
            "website_url": "url", # Usually the input, but can be verified
            "description_short": "description", # Or a more specific "tagline"
            "year_established": "yearEstablished", # Example of camelCase in JS
            "specialties": "specialties",
            # For structured_address, we might want to request the whole block or individual parts
            "structured_address": "address", # Tells scraper to get the full address object/string
            "street_address": "address.street", # If scraper supports deep targeting
            "city": "address.city",
            "state": "address.state",
            "zip_code": "address.zipCode",
            "country": "address.country",
            "canonical_phone_number": "contact.phone", # Assuming contact object in Zod
            "raw_phone_numbers": "contact.phones", # If it can collect multiple
            "canonical_email": "contact.email",
            "raw_emails": "contact.emails",
            "menu_items": "menu.items", # This would be complex, tell it to look for menu section
            "full_menu_text_raw": "menu.fullText",
            # Social media links might be grouped or individual
            "social_media_links.facebook": "socialMedia.facebook",
            "social_media_links.instagram": "socialMedia.instagram",
            "social_media_links.twitter": "socialMedia.twitter",
            "social_media_links.tiktok": "socialMedia.tiktok",
            "social_media_links.youtube": "socialMedia.youtube",
            "social_media_links.linkedin": "socialMedia.linkedin",
            "social_media_links.yelp": "socialMedia.yelp",
            "social_media_links.tripadvisor": "socialMedia.tripadvisor",
            # Generic request for any screenshots of important pages
            "website_screenshots_s3_urls": "screenshots.general", # A flag to take some default screenshots
            # More specific screenshot requests if needed:
            # "screenshots.homepage": True,
            # "screenshots.menuPage": True,
        }

        schema: Dict[str, Any] = {
            # Default fields that are always useful for context, even if not explicitly "missing"
            # "contextual_name": True, # e.g., always try to confirm name
            # "contextual_url": True,  # e.g., always confirm the primary URL
        }
        
        # It's crucial that these schema keys match what the Node.js scraper's Zod schema expects
        # or how it's designed to interpret these directives.
        for field in missing_fields:
            if field in field_map:
                # Handle nested fields (e.g., "structured_address.city")
                keys = field_map[field].split('.')
                current_level = schema
                for i, key_part in enumerate(keys):
                    if i == len(keys) - 1: # Last part of the key
                        current_level[key_part] = True # Request this field
                    else:
                        current_level = current_level.setdefault(key_part, {})
            elif field.startswith("social_media_links."): # Handle specific social links
                platform = field.split('.')[-1]
                schema.setdefault("socialMedia", {})[platform] = True
            elif field == "website_screenshots_s3_urls": # Generic request for screenshots
                 schema.setdefault("screenshots", {})["general"] = True # Or specific types like "homepage", "menu"
                 # For example, always grab homepage and menu if screenshots are requested generally
                 schema["screenshots"]["homepage"] = True
                 schema["screenshots"]["menuPage"] = True
            else:
                # If no direct map, pass the field name as is, hoping the scraper understands
                schema[field] = True 
                logger.warning(f"No specific mapping for missing field '{field}' in _create_focused_schema. Passing as is.")

        # Always include a directive to attempt to identify the type of page for context
        # schema["pageContext"] = True # Example: tells scraper to identify if it's on a menu, contact page etc.
        
        # Ensure general screenshot capability is requested if any specific screenshot field is missing
        # or if the generic website_screenshots_s3_urls is requested.
        if any(f.startswith("screenshots.") for f in schema.get("screenshots", {}).keys()) or schema.get("screenshots", {}).get("general"):
            schema.setdefault("screenshots", {})["enabled"] = True # Master switch for screenshotting in scraper

        logger.info(f"Generated focused schema for Stagehand: {schema}")
        return schema

def _find_node_executable() -> str:
    """
    Find the Node.js executable by checking multiple common paths.
    Returns the first working Node.js path found.
    """
    logger.info("🔍 Searching for Node.js executable...")
    
    # First, try to find node in the system PATH
    try:
        result = shutil.which("node")
        if result:
            # Verify it actually works
            try:
                proc = subprocess.run([result, "--version"], capture_output=True, text=True, timeout=5)
                if proc.returncode == 0:
                    version = proc.stdout.strip()
                    logger.info(f"✅ Found Node.js in PATH: {result} ({version})")
                    return result
            except Exception as e:
                logger.warning(f"Found node in PATH but failed to verify: {e}")
        else:
            logger.info("❌ Node.js not found in system PATH")
    except Exception as e:
        logger.warning(f"Error checking system PATH for node: {e}")
    
    # Fallback to common installation paths
    possible_paths = [
        "/opt/homebrew/bin/node",           # Homebrew on Apple Silicon (most common)
        "/usr/local/bin/node",              # Homebrew on Intel Mac
        "/usr/bin/node",                    # System installation
        "/bin/node",                        # Alternative system path
        f"{os.path.expanduser('~')}/.nvm/versions/node/v18.20.5/bin/node",  # NVM common version
        f"{os.path.expanduser('~')}/.nvm/versions/node/v20.9.0/bin/node",   # NVM newer version
        f"{os.path.expanduser('~')}/.nvm/versions/node/v16.20.0/bin/node",  # NVM older version
        f"{os.path.expanduser('~')}/.volta/bin/node",                       # Volta
        f"{os.path.expanduser('~')}/.local/bin/node",                       # Local installation
    ]
    
    logger.info(f"🔍 Checking {len(possible_paths)} potential Node.js locations...")
    
    for node_path in possible_paths:
        try:
            if Path(node_path).exists() and os.access(node_path, os.X_OK):
                # Verify it actually works
                try:
                    proc = subprocess.run([node_path, "--version"], capture_output=True, text=True, timeout=5)
                    if proc.returncode == 0:
                        version = proc.stdout.strip()
                        logger.info(f"✅ Found working Node.js executable: {node_path} ({version})")
                        return node_path
                except Exception as e:
                    logger.warning(f"Path {node_path} exists but failed verification: {e}")
            else:
                logger.debug(f"❌ Node.js not found at: {node_path}")
        except Exception as e:
            logger.debug(f"Error checking Node.js path {node_path}: {e}")
    
    # If we get here, we couldn't find a working Node.js installation
    logger.error("❌ No working Node.js installation found!")
    logger.error("🔧 Installation suggestions:")
    logger.error("   • macOS: brew install node")
    logger.error("   • NVM: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash && nvm install node")
    logger.error("   • Volta: curl https://get.volta.sh | bash && volta install node")
    logger.error("   • Download: https://nodejs.org/en/download/")
    
    # Return a fallback that will likely fail but won't cause import errors
    logger.warning("⚠️ Returning 'node' as fallback - this will likely fail unless Node.js is added to PATH")
    return "node"

# Create a global instance
stagehand_scraper = StagehandScraper() 
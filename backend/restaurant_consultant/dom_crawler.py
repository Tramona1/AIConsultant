"""
DOM Crawler for Targeted Page Extraction
Part of the Progressive Data Extraction System (Phase 2)
"""

import logging
import asyncio
import re
from typing import Dict, List, Optional, Any, Set, Deque, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright
from collections import deque
import json
from pydantic import HttpUrl
import time
from bs4 import BeautifulSoup

from .models import ScreenshotInfo

logger = logging.getLogger(__name__)

# Configuration Constants with more realistic timeouts
DEFAULT_MAX_PAGES_TO_CRAWL = 15
DEFAULT_MAX_CRAWL_TIME_SECONDS = 120 # 2 minutes max total
PAGE_NAVIGATION_TIMEOUT_MS = 15000 # 15 seconds max per page navigation
PAGE_CONTENT_TIMEOUT_MS = 10000 # 10 seconds max for content extraction
NETWORK_IDLE_TIMEOUT_MS = 5000 # Only 5 seconds for network idle
AFTER_NAV_WAIT_MS = 1000 # 1 second wait after navigation
MAX_PAGE_ATTEMPTS = 2 # Reduce attempts to prevent getting stuck

class DOMCrawler:
    """
    Phase 2: Comprehensive DOM crawling using Playwright.
    Extracts structured and semi-structured data, screenshots, and PDFs.
    """

    def __init__(self, max_pages_to_crawl: int = DEFAULT_MAX_PAGES_TO_CRAWL,
                 max_crawl_time_seconds: int = DEFAULT_MAX_CRAWL_TIME_SECONDS):
        self.base_download_dir = Path("analysis_data/downloads")
        self.base_screenshot_dir = Path("analysis_data/screenshots")
        
        # Ensure directories exist
        self.base_download_dir.mkdir(parents=True, exist_ok=True)
        self.base_screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_pages_to_crawl = max_pages_to_crawl
        self.max_crawl_time_seconds = max_crawl_time_seconds
        
        # TODO: Initialize actual S3 client (e.g., boto3.client('s3'))
        self.s3_client = None # Placeholder for S3 client
        
        logger.info(f"✅ DOM crawler initialized. Max pages: {self.max_pages_to_crawl}, Max time: {self.max_crawl_time_seconds}s")
        logger.info(f"Download directory: {self.base_download_dir.resolve()}")
        logger.info(f"Screenshot directory: {self.base_screenshot_dir.resolve()}")

    def _get_local_file_url(self, file_path: Path) -> str:
        """
        Convert a local file path to a file:// URL for consistent handling.
        """
        if not file_path.exists():
            logger.warning(f"File {file_path} does not exist")
            return f"file://error/file_not_found/{file_path.name}"

        # Convert to absolute path and create file:// URL
        absolute_path = file_path.resolve()
        file_url = f"file://{absolute_path}"
        logger.info(f"📎 Local file URL: {file_url}")
        return file_url

    async def crawl_website(self,
                            target_url: str,
                            high_priority_relative_urls: Optional[List[str]] = None,
                            known_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Comprehensive DOM Crawling with Circuit Breakers and Resilient Error Handling.
        Enhanced to never get stuck on problematic pages.
        """
        logger.info(f"🚀 Starting resilient DOM crawl for {target_url}")
        start_time = datetime.now()

        # Initialize results structure
        final_output = {
            "extracted_textual_data": {
                "emails": [],
                "phones": [],
                "social_links": {},
                "menu_texts_raw": [],
                "about_text_raw": "",
                "contact_text_raw": "",
                "general_page_texts": {},
                "misc_extracted_data": {}
            },
            "screenshots": [],
            "downloaded_pdf_s3_urls": [],
            "html_content_key_pages": {},
            "crawl_metadata": {
                "target_url": target_url,
                "pages_crawled_count": 0,
                "pages_attempted": 0,
                "pages_failed": 0,
                "crawl_duration_seconds": 0,
                "errors": [],
                "crawled_urls": [],
                "failed_urls": [],
                "stuck_pages": []
            }
        }

        if not high_priority_relative_urls:
            high_priority_relative_urls = []
        
        # Normalize target_url
        parsed_target_url = urlparse(target_url)
        if not parsed_target_url.scheme:
            target_url = "http://" + target_url
            parsed_target_url = urlparse(target_url)
        
        base_url = f"{parsed_target_url.scheme}://{parsed_target_url.netloc}"

        # Queue for URLs to visit with priority scoring
        url_queue: Deque[Tuple[str, str, int, int]] = deque()
        visited_urls: Set[str] = set()
        failed_urls: Set[str] = set()

        # Add homepage to queue with high priority
        url_queue.append((target_url, "homepage", 0, 100))
        
        # Add high priority URLs
        for rel_url in high_priority_relative_urls:
            abs_url = urljoin(base_url, rel_url)
            if abs_url not in visited_urls:
                page_type_hint = self._classify_page_type(abs_url)
                priority_score = self._calculate_page_priority(page_type_hint)
                url_queue.appendleft((abs_url, page_type_hint, 0, priority_score))

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox', 
                    '--disable-dev-shm-usage', 
                    '--disable-gpu',
                    '--disable-background-networking',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-web-security',
                    '--window-size=1920,1080'
                ]
            )
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                java_script_enabled=True,
                accept_downloads=True,
                # Add these settings to prevent hanging
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Cache-Control': 'no-cache'
                }
            )

            try:
                page_crawl_count = 0
                total_attempts = 0
                
                while url_queue and page_crawl_count < self.max_pages_to_crawl:
                    # Check time limits
                    current_crawl_time = (datetime.now() - start_time).total_seconds()
                    if current_crawl_time >= self.max_crawl_time_seconds:
                        logger.info(f"🏁 Reached max crawl time: {self.max_crawl_time_seconds}s")
                        break

                    # Get next URL (prioritized queue)
                    url_queue = deque(sorted(url_queue, key=lambda x: (-x[3], x[2])))  # Sort by priority desc, depth asc
                    current_url, current_page_type_hint, depth, priority_score = url_queue.popleft()

                    if current_url in visited_urls or current_url in failed_urls:
                        continue
                    
                    total_attempts += 1
                    final_output["crawl_metadata"]["pages_attempted"] = total_attempts
                    
                    logger.info(f"🔍 Attempting page #{total_attempts} (priority: {priority_score}): {current_url} ({current_page_type_hint})")

                    # Circuit breaker: Try to crawl the page with multiple fallback strategies
                    page_success = False
                    page_data = None
                    
                    for attempt in range(MAX_PAGE_ATTEMPTS):
                        try:
                            page = await context.new_page()
                            
                            # Use circuit breaker navigation with fallback strategies
                            navigation_success = await self._navigate_with_circuit_breaker(page, current_url, attempt)
                            
                            if not navigation_success:
                                logger.warning(f"⚠️ Navigation failed for {current_url} on attempt {attempt + 1}")
                                await page.close()
                                continue
                            
                            # Extract data with timeout protection
                            page_data = await self._extract_data_with_timeout(page, current_url, current_page_type_hint)
                            
                            # Take screenshot with timeout protection
                            await self._take_screenshot_with_timeout(page, current_url, current_page_type_hint, final_output)
                            
                            # Discover links for further crawling (but don't let this block us)
                            if depth < 2:  # Reduced depth to prevent too much crawling
                                try:
                                    internal_links = await asyncio.wait_for(
                                        self._discover_internal_links(page, base_url, current_url),
                                        timeout=10.0
                                    )
                                    for link_url, link_type_hint in internal_links[:20]:  # Limit discovered links
                                        if link_url not in visited_urls and link_url not in failed_urls:
                                            priority = self._calculate_page_priority(link_type_hint)
                                            if not any(q_item[0] == link_url for q_item in url_queue):
                                                url_queue.append((link_url, link_type_hint, depth + 1, priority))
                                except asyncio.TimeoutError:
                                    logger.warning(f"⚠️ Link discovery timeout for {current_url}")
                                except Exception as link_error:
                                    logger.warning(f"⚠️ Link discovery error for {current_url}: {link_error}")
                            
                            await page.close()
                            page_success = True
                            break  # Success, exit attempt loop
                            
                        except Exception as page_error:
                            logger.warning(f"⚠️ Page attempt {attempt + 1} failed for {current_url}: {str(page_error)}")
                            try:
                                if 'page' in locals() and not page.is_closed():
                                    await page.close()
                            except:
                                pass
                            
                            if attempt < MAX_PAGE_ATTEMPTS - 1:
                                await asyncio.sleep(1)  # Brief pause between attempts
                    
                    # Process results
                    if page_success and page_data:
                        visited_urls.add(current_url)
                        page_crawl_count += 1
                        final_output["crawl_metadata"]["crawled_urls"].append(current_url)
                        final_output["crawl_metadata"]["pages_crawled_count"] = page_crawl_count
                        
                        # Merge extracted data
                        self._merge_extracted_page_data(
                            final_output["extracted_textual_data"], 
                            page_data, 
                            current_url, 
                            current_page_type_hint
                        )
                        
                        # Store HTML for key pages if needed
                        if current_page_type_hint in ["menu", "contact", "about"] and page_data.get("html_content"):
                            final_output["html_content_key_pages"][current_url] = page_data["html_content"]
                        
                        logger.info(f"✅ Successfully processed {current_url}")
                        
                    else:
                        failed_urls.add(current_url)
                        final_output["crawl_metadata"]["pages_failed"] += 1
                        final_output["crawl_metadata"]["failed_urls"].append(current_url)
                        final_output["crawl_metadata"]["errors"].append({
                            "url": current_url,
                            "error": f"Failed after {MAX_PAGE_ATTEMPTS} attempts",
                            "page_type": current_page_type_hint
                        })
                        logger.error(f"❌ Failed to process {current_url} after {MAX_PAGE_ATTEMPTS} attempts")
                    
                    # Small delay between pages to be respectful
                    await asyncio.sleep(0.5)

            finally:
                await browser.close()
                logger.info("🔒 Browser closed")

        final_output["crawl_metadata"]["crawl_duration_seconds"] = (datetime.now() - start_time).total_seconds()
        
        # Consolidate collected text
        self._consolidate_text_data(final_output["extracted_textual_data"])

        logger.info(f"✅ Resilient DOM crawl finished for {target_url}")
        logger.info(f"📊 Stats: {page_crawl_count} successful, {final_output['crawl_metadata']['pages_failed']} failed, "
                   f"{len(final_output['screenshots'])} screenshots, {len(final_output['downloaded_pdf_s3_urls'])} PDFs")
        logger.info(f"⏱️ Duration: {final_output['crawl_metadata']['crawl_duration_seconds']:.2f}s")
        
        return final_output

    async def _extract_data_from_page(self, page, url: str, page_type: str) -> Dict[str, Any]:
        """
        Main dispatcher for extracting data from a loaded Playwright page.
        Enhanced with better error handling and timeout protection.
        """
        logger.info(f"📊 Extracting data from {url} (type: {page_type})")
        extracted_data = {
            "phones": [], "emails": [], "social_links": {},
            "menu_items_raw": [], 
            "page_text_content": ""
        }

        try:
            # Common Extractions with timeout protection
            await self._extract_contact_info_safely(page, extracted_data, url)
            await self._extract_social_links_safely(page, extracted_data, url)
            
            # Page-type specific extraction with timeout protection
            if page_type == 'homepage':
                data = await self._extract_homepage_data_safely(page, url)
                extracted_data.update(data)
            elif page_type == 'menu':
                data = await self._extract_menu_data_safely(page, url)
                if "menu_items_raw" in data and data["menu_items_raw"]:
                    extracted_data["menu_items_raw"].extend(data["menu_items_raw"])
                extracted_data.update(data)
            elif page_type == 'contact':
                data = await self._extract_contact_data_safely(page, url)
                extracted_data["page_text_content"] = data.get("contact_page_text", "")
                extracted_data.update(data)
            elif page_type == 'about':
                data = await self._extract_about_data_safely(page, url)
                extracted_data["page_text_content"] = data.get("about_page_text", "")
                extracted_data.update(data)
            else:
                data = await self._extract_general_text_content_safely(page, url)
                extracted_data["page_text_content"] = data.get("general_text", "")
                extracted_data.update(data)
            
            # Fallback: extract all visible text if no specific extractors worked
            if not extracted_data.get("page_text_content") and not extracted_data.get("menu_items_raw"):
                try:
                    body_text = await asyncio.wait_for(
                        page.locator('body').text_content(),
                        timeout=5.0
                    )
                    if body_text:
                        extracted_data["page_text_content"] = re.sub(r'\s{2,}', ' ', body_text).strip()
                        logger.info(f"✅ Extracted fallback body text for {url}")
                except Exception as fallback_error:
                    logger.warning(f"⚠️ Fallback text extraction failed for {url}: {fallback_error}")

        except Exception as e:
            logger.error(f"❌ Data extraction failed for {url}: {str(e)}")
            # Return minimal data structure to prevent downstream errors
            extracted_data = {
                "phones": [], "emails": [], "social_links": {},
                "menu_items_raw": [], "page_text_content": ""
            }

        logger.info(f"✅ Data extraction completed for {url}. "
                   f"Phones: {len(extracted_data['phones'])}, "
                   f"Emails: {len(extracted_data['emails'])}, "
                   f"Social: {len(extracted_data['social_links'])}, "
                   f"Menu items: {len(extracted_data['menu_items_raw'])}")
        
        return extracted_data

    async def _extract_contact_info_safely(self, page, extracted_data: Dict, url: str):
        """Extract phone and email with timeout protection."""
        try:
            logger.info(f"📞 Extracting contact info from {url}")
            
            # Phone Numbers with timeout
            phone_selectors = [
                'a[href^="tel:"]', '.phone', '.contact-phone', '.telephone',
                '[data-testid="phone"]', '.business-phone', 'span[class*="phone"]', 'div[class*="phone"]'
            ]
            
            for selector in phone_selectors:
                try:
                    elements = await asyncio.wait_for(
                        page.query_selector_all(selector),
                        timeout=2.0
                    )
                    for el in elements[:5]:  # Limit to prevent hanging on too many elements
                        try:
                            href = await asyncio.wait_for(el.get_attribute('href'), timeout=1.0)
                            if href and href.startswith('tel:'):
                                phone = href.replace('tel:', '').strip()
                                if phone not in extracted_data["phones"]:
                                    extracted_data["phones"].append(phone)
                                continue
                            
                            text_content = await asyncio.wait_for(el.text_content(), timeout=1.0) or ""
                            phone_matches = re.findall(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text_content)
                            for phone in phone_matches:
                                if phone not in extracted_data["phones"]:
                                    extracted_data["phones"].append(phone.strip())
                        except:
                            continue
                except:
                    continue

            # Email Addresses with timeout
            email_selectors = [
                'a[href^="mailto:"]', '.email', '.contact-email', '[data-testid="email"]'
            ]
            
            for selector in email_selectors:
                try:
                    elements = await asyncio.wait_for(
                        page.query_selector_all(selector),
                        timeout=2.0
                    )
                    for el in elements[:5]:  # Limit elements
                        try:
                            href = await asyncio.wait_for(el.get_attribute('href'), timeout=1.0)
                            if href and href.startswith('mailto:'):
                                email = href.replace('mailto:', '').split('?')[0].strip()
                                if email not in extracted_data["emails"]:
                                    extracted_data["emails"].append(email)
                                continue
                            
                            text_content = await asyncio.wait_for(el.text_content(), timeout=1.0) or ""
                            email_matches = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text_content)
                            for email in email_matches:
                                if email not in extracted_data["emails"]:
                                    extracted_data["emails"].append(email.strip())
                        except:
                            continue
                except:
                    continue
                    
        except Exception as e:
            logger.warning(f"⚠️ Contact info extraction error for {url}: {str(e)}")

    async def _extract_social_links_safely(self, page, extracted_data: Dict, url: str):
        """Extract social media links with timeout protection."""
        try:
            logger.info(f"🔗 Extracting social links from {url}")
            
            social_keywords = {"facebook", "instagram", "twitter", "linkedin", "youtube", "yelp", "tripadvisor", "tiktok"}
            
            links = await asyncio.wait_for(
                page.query_selector_all('a[href]'),
                timeout=3.0
            )
            
            for link_el in links[:50]:  # Limit to prevent hanging
                try:
                    href = await asyncio.wait_for(link_el.get_attribute('href'), timeout=1.0)
                    if href:
                        href_lower = href.lower()
                        for keyword in social_keywords:
                            if keyword in href_lower and keyword not in extracted_data["social_links"]:
                                parsed_href = urlparse(href)
                                if keyword in parsed_href.netloc:
                                    extracted_data["social_links"][keyword] = href
                                    break
                except:
                    continue
                    
        except Exception as e:
            logger.warning(f"⚠️ Social links extraction error for {url}: {str(e)}")

    async def _extract_general_text_content_safely(self, page, url: str) -> Dict[str, str]:
        """Extract general text content with timeout protection."""
        data = {"general_text": ""}
        try:
            logger.info(f"📄 Extracting general content from {url}")
            
            main_content_selectors = ['main', 'article', 'div[role="main"]', 'div.content', 'div.main-content']
            content_text = ""
            
            for selector in main_content_selectors:
                try:
                    main_element = await asyncio.wait_for(
                        page.query_selector(selector),
                        timeout=2.0
                    )
                    if main_element:
                        content_text = await asyncio.wait_for(
                            main_element.inner_text(),
                            timeout=3.0
                        )
                        break
                except:
                    continue
                    
            if not content_text:
                try:
                    content_text = await asyncio.wait_for(
                        page.locator('body').text_content(),
                        timeout=5.0
                    )
                except:
                    content_text = ""
            
            if content_text:
                data["general_text"] = re.sub(r'\s{2,}', ' ', content_text).strip()
                
        except Exception as e:
            logger.warning(f"⚠️ General text extraction error for {url}: {str(e)}")
            
        return data

    def _merge_extracted_page_data(self, main_data_store: Dict, page_data: Dict, page_url: str, page_type: str):
        """
        Merges data extracted from a single page into the main data store.
        """
        # Emails
        for email in page_data.get("emails", []):
            if email not in main_data_store["emails"]:
                main_data_store["emails"].append(email)
        # Phones
        for phone in page_data.get("phones", []):
            if phone not in main_data_store["phones"]:
                main_data_store["phones"].append(phone)
        # Social Links
        for platform, link in page_data.get("social_links", {}).items():
            if platform not in main_data_store["social_links"]: # First one found wins for now
                main_data_store["social_links"][platform] = link
        
        # Menu Texts
        if page_data.get("menu_items_raw"):
             main_data_store["menu_texts_raw"].extend(page_data["menu_items_raw"])

        # Page specific texts
        page_text = page_data.get("page_text_content", "")
        if page_type == "about" and page_text:
            if not main_data_store["about_text_raw"]: # Take the first one found, or longest?
                 main_data_store["about_text_raw"] = page_text
            else: # Append if multiple about pages found
                 main_data_store["about_text_raw"] += "\n\n--- (additional about text from " + page_url + ") ---\n" + page_text
        elif page_type == "contact" and page_text:
            if not main_data_store["contact_text_raw"]:
                 main_data_store["contact_text_raw"] = page_text
            else:
                 main_data_store["contact_text_raw"] += "\n\n--- (additional contact text from " + page_url + ") ---\n" + page_text
        elif page_text: # General page text
            main_data_store["general_page_texts"][page_url] = page_text
            
        # Merge any other misc data that specific extractors might return
        for key, value in page_data.items():
            if key not in ["emails", "phones", "social_links", "menu_items_raw", "page_text_content"] and value:
                if key not in main_data_store["misc_extracted_data"]:
                    main_data_store["misc_extracted_data"][key] = value
                elif isinstance(main_data_store["misc_extracted_data"][key], list) and isinstance(value, list):
                    main_data_store["misc_extracted_data"][key].extend(v for v in value if v not in main_data_store["misc_extracted_data"][key])
                elif isinstance(main_data_store["misc_extracted_data"][key], dict) and isinstance(value, dict):
                    main_data_store["misc_extracted_data"][key].update(value)
                # else, just keep the first one found for simple values for now
                
        logger.debug(f"Data merged for page {page_url}. Current emails: {len(main_data_store['emails'])}, phones: {len(main_data_store['phones'])}")

    async def _discover_internal_links(self, page, base_url: str, current_page_url: str) -> List[Tuple[str, str]]:
        """
        Extracts, filters, normalizes, and categorizes internal links from a page.
        Returns a list of tuples: (absolute_url, page_type_hint)
        """
        internal_links = []
        try:
            link_elements = await page.query_selector_all("a[href]")
        except Exception as e:
            logger.warning(f"Could not query links on {current_page_url}: {e}")
            return []

        current_page_parsed = urlparse(current_page_url)
        base_domain = current_page_parsed.netloc

        for link_el in link_elements:
            try:
                href = await link_el.get_attribute("href")
                if not href:
                    continue

                href = href.strip()
                # Ignore common non-navigational links
                if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue
                
                # Resolve to absolute URL
                abs_url = urljoin(base_url, href)
                parsed_abs_url = urlparse(abs_url)

                # Filter for internal links (same domain)
                if parsed_abs_url.netloc == base_domain:
                    # Normalize: remove fragment, trailing slash (optional, but good for visited check)
                    normalized_url = parsed_abs_url._replace(fragment="", query="").geturl()
                    if normalized_url.endswith('/') and normalized_url != base_url + '/': # avoid stripping slash from root
                        normalized_url = normalized_url[:-1]
                    
                    # Avoid asset links (can be expanded)
                    if any(normalized_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.css', '.js', '.svg', '.webp']):
                        continue

                    page_type_hint = self._classify_page_type(normalized_url, link_el)
                    internal_links.append((normalized_url, page_type_hint))
                    
            except Exception as e:
                logger.debug(f"Error processing a link on {current_page_url}: {href if 'href' in locals() else 'unknown'}. Error: {e}")
        
        # Deduplicate based on URL
        unique_links = list(dict(internal_links).items()) # Relies on dict preserving insertion order for type hint if multiple same URLs
        logger.info(f"Discovered {len(unique_links)} potential internal links on {current_page_url}")
        return unique_links
        
    def _consolidate_text_data(self, extracted_data_store: Dict):
        """
        Consolidates various text fields into more structured outputs if possible,
        or prepares them for the FinalRestaurantOutput model.
        Currently, this mainly ensures menu_texts_raw is a list of strings.
        """
        # Ensure menu_texts_raw is a flat list of strings
        if isinstance(extracted_data_store.get("menu_texts_raw"), list):
            flat_menu_texts = []
            for item in extracted_data_store["menu_texts_raw"]:
                if isinstance(item, str):
                    flat_menu_texts.append(item)
                elif isinstance(item, list): # If a sub-extractor returned a list of strings
                    flat_menu_texts.extend(s for s in item if isinstance(s,str))
            extracted_data_store["menu_texts_raw"] = flat_menu_texts
        logger.info("Text data consolidation step complete.")


    # --- Existing Helper Methods (to be reviewed and adapted) ---
    
    # Note: The original _extract_homepage_data, _extract_menu_data, etc.
    # need to be refactored to:
    # 1. Fit into the new `_extract_data_from_page` -> `_merge_extracted_page_data` flow.
    # 2. Return data in a format that `_merge_extracted_page_data` expects.
    #    Specifically, `menu_items_raw` should be a list of strings (text blocks of menu items/sections).
    #    Other text should go into `page_text_content`.
    #    Phones, emails, social links are handled by the common extractor in `_extract_data_from_page`.

    async def _extract_homepage_data_safely(self, page, url: str) -> Dict[str, Any]:
        """Extract data from homepage. Focus on unique homepage elements like taglines or hero text."""
        # Phones, emails, addresses, social links are now handled by the common extractor.
        # This method should focus on what's uniquely on a homepage.
        logger.debug(f"Extracting specific homepage data for {url}")
        data = {"homepage_tagline": None, "hero_text": None}
        
        # Example: Extracting a tagline or hero text
        hero_selectors = [
            '.hero-title', '.tagline', 'h1.site-title + p', '.hero-section .subtitle',
             'header h2', 'section[data-testid="hero"] p'
        ]
        for selector in hero_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = (await element.text_content() or "").strip()
                    if text and len(text) > 10 and len(text) < 300: # Basic check for relevance
                        if not data["hero_text"]: data["hero_text"] = text
                        elif not data["homepage_tagline"]: data["homepage_tagline"] = text # if hero_text already found
                        # Could add more logic to distinguish
                        logger.debug(f"Found hero/tagline text using {selector}: {text[:50]}...")
                        # break # Decide if we want first or all
            except Exception as e:
                logger.debug(f"Selector {selector} error on homepage: {e}")
        
        # Extract general text content of the homepage if not covered by hero/tagline
        general_text_data = await self._extract_general_text_content_safely(page, url)
        data["page_text_content"] = general_text_data.get("general_text", "")

        return data
    
    async def _extract_menu_data_safely(self, page, url: str) -> Dict[str, Any]:
        """
        Extracts raw text blocks that likely contain menu items.
        This is a challenging task and will often require LLM processing later.
        The goal here is to get good chunks of text that represent the menu.
        """
        logger.debug(f"Extracting menu data from {url}")
        data = {"menu_items_raw": []}
        menu_texts = []

        # Common selectors for menu sections or individual items
        # This list needs to be extensive and might be site-specific
        menu_selectors = [
            ".menu-item", ".dish", ".menu-section", ".category-name", # Structure based
            "div[class*='menu-item']", "article[class*='menu_item']",
            "ul[class*='menu-list'] li", "dl[class*='menu'] dt", "dl[class*='menu'] dd",
            ".menu-card", ".food-item", ".price", ".menu-title", ".menu-description",
            # Heuristic: look for elements with price-like patterns
            "//*[contains(text(), '$') or contains(text(), '€') or contains(text(), '£')]/ancestor::div[string-length(normalize-space(.)) > 20 and string-length(normalize-space(.)) < 500]"
        ]
        # More generic block selectors that might contain menu content
        block_selectors = [
            "section[id*='menu']", "div[id*='menu']", 
            "section[class*='menu']", "div[class*='menu-content']",
        ]

        # Try block selectors first to get large chunks
        for selector in block_selectors:
            elements = await page.query_selector_all(selector)
            for el in elements:
                try:
                    text = (await el.text_content() or "").strip()
                    text_cleaned = re.sub(r'\s{2,}', ' ', text)
                    if text_cleaned and len(text_cleaned) > 50: # Arbitrary length to consider it a block
                        menu_texts.append(text_cleaned)
                        logger.debug(f"Extracted menu block via '{selector}': {text_cleaned[:100]}...")
                except Exception as e:
                    logger.debug(f"Error with block selector {selector} for menu: {e}")
        
        # If block selectors didn't yield much, or to supplement, try item selectors
        if not menu_texts or len("".join(menu_texts)) < 300 : # If total text is small
            for selector in menu_selectors:
                elements = await page.query_selector_all(selector)
                for i, el in enumerate(elements):
                    try:
                        # Heuristic: If it's a price, try to get its parent's or sibling's text
                        text_content = (await el.text_content() or "").strip()
                        text_cleaned = re.sub(r'\s{2,}', ' ', text_content)

                        # Attempt to get a more complete menu item text if current element is small (e.g. just a price)
                        if len(text_cleaned) < 30 and ("$" in text_cleaned or "€" in text_cleaned or "£" in text_cleaned or re.match(r'\d+\.?\d*', text_cleaned)):
                            parent = el.locator("xpath=..") # Get parent element
                            if parent:
                                parent_text = (await parent.text_content() or "").strip()
                                parent_text_cleaned = re.sub(r'\s{2,}', ' ', parent_text)
                                if len(parent_text_cleaned) > len(text_cleaned) and len(parent_text_cleaned) < 300 : # Parent has more text & not too large
                                    text_cleaned = parent_text_cleaned
                        
                        if text_cleaned and len(text_cleaned) > 5: # Minimum length for an item/description part
                             menu_texts.append(text_cleaned)
                             # logger.debug(f"Extracted menu item/text via '{selector}' ({i}): {text_cleaned[:70]}...")
                    except Exception as e:
                        logger.debug(f"Error with item selector {selector} for menu: {e}")

        if not menu_texts:
            logger.warning(f"No significant menu text found on {url} using selectors. Falling back to full page text if classified as menu.")
            # Fallback: If the page is strongly hinted as 'menu', take larger portion of text.
            # Get page type from URL classification
            current_page_type = self._classify_page_type(url)
            if current_page_type == "menu":
                body_text_data = await self._extract_general_text_content_safely(page, url)
                body_text = body_text_data.get("general_text", "")
                if body_text:
                    menu_texts.append(body_text)
                    logger.info(f"Used general body text as menu_items_raw for {url}")

        # Deduplicate and filter very short strings that are unlikely to be useful menu text
        unique_menu_texts = []
        seen_texts = set()
        for mt in menu_texts:
            if mt not in seen_texts and len(mt) > 10: # Filter out very short/empty strings
                unique_menu_texts.append(mt)
                seen_texts.add(mt)

        data["menu_items_raw"] = unique_menu_texts
        if unique_menu_texts:
            logger.info(f"Extracted {len(unique_menu_texts)} raw menu text segments from {url}.")
        else:
            logger.warning(f"Could not extract any distinct menu text segments from {url}.")
            
        # Extract general text content of the menu page as well
        general_text_data = await self._extract_general_text_content_safely(page, url)
        data["page_text_content"] = general_text_data.get("general_text", "")

        return data

    async def _extract_contact_data_safely(self, page, url: str) -> Dict[str, Any]:
        """Extract data from contact page. Phones/emails are common, focus on forms or specific contact instructions."""
        logger.debug(f"Extracting contact page specific data for {url}")
        data = {"contact_page_text": "", "has_contact_form": False}
        
        # Check for contact forms (basic check)
        form_selectors = ['form[action*="contact"]', 'form[id*="contact"]', 'form .form-submit', 'form button[type="submit"]']
        for selector in form_selectors:
            if await page.query_selector(selector):
                data["has_contact_form"] = True
                logger.info(f"Contact form detected on {url} using selector: {selector}")
                break
        
        # Extract overall text of the contact page
        try:
            # Prioritize sections often containing contact info text
            contact_section_selectors = [
                "section[id*='contact']", "div[class*='contact-info']", 
                "main[class*='contact']", "article[class*='contact']"
            ]
            page_text = ""
            for selector in contact_section_selectors:
                element = await page.query_selector(selector)
                if element:
                    text = await element.text_content()
                    if text:
                        page_text = re.sub(r'\s{2,}', ' ', text.strip())
                        logger.debug(f"Extracted contact text using selector {selector}.")
                        break
            if not page_text: # Fallback to general text extraction
                general_text_data = await self._extract_general_text_content_safely(page, url)
                page_text = general_text_data.get("general_text", "")
            
            data["contact_page_text"] = page_text

        except Exception as e:
            logger.warning(f"Could not extract text from contact page {url}: {e}")
            
        return data

    async def _extract_about_data_safely(self, page, url: str) -> Dict[str, Any]:
        """Extract text from an about/history/story page."""
        logger.debug(f"Extracting about page specific data for {url}")
        data = {"about_page_text": ""}
        
        try:
            # Prioritize sections like "about us", "our story", "history"
            about_section_selectors = [
                "section[id*='about']", "div[class*='about-us']", "article[class*='story']",
                "section[class*='history']", "main[class*='about']"
            ]
            page_text = ""
            for selector in about_section_selectors:
                element = await page.query_selector(selector)
                if element:
                    text = await element.text_content()
                    if text:
                        page_text = re.sub(r'\s{2,}', ' ', text.strip())
                        logger.debug(f"Extracted about text using selector {selector}.")
                        break
            if not page_text: # Fallback to general text extraction
                general_text_data = await self._extract_general_text_content_safely(page, url)
                page_text = general_text_data.get("general_text", "")

            data["about_page_text"] = page_text
            if page_text:
                logger.info(f"Extracted about page text (length: {len(page_text)}) from {url}")

        except Exception as e:
            logger.warning(f"Could not extract text from about page {url}: {e}")
        return data
    
    def _classify_page_type(self, url: str, link_element = None) -> str:
        """
        Classify page type based on URL patterns and link text if available.
        """
        url_lower = url.lower()
        path_lower = urlparse(url_lower).path

        # Link text analysis if element provided
        link_text = ""
        if link_element:
            try: # This needs to be async if called from async context, but _classify_page_type is sync
                  # For now, this part won't work if link_element is a Playwright handle needing await
                  # Consider passing pre-extracted text or making this async if live element access is needed
                  # link_text = (await link_element.text_content() or "").lower() # Needs await if link_element is live
                  pass # Placeholder: link text analysis needs async or pre-fetched text
            except: pass


        if any(keyword in url_lower or keyword in link_text for keyword in ["menu", "carte", "dishes", "food", "prix"]):
            return "menu"
        if any(keyword in url_lower or keyword in link_text for keyword in ["contact", "find-us", "location", "direction", "visit", "reach"]):
            return "contact"
        if any(keyword in url_lower or keyword in link_text for keyword in ["about", "story", "history", "mission", "equipe", "team", "who-we-are"]):
            return "about"
        if any(keyword in url_lower or keyword in link_text for keyword in ["gallery", "photo", "media"]):
            return "gallery"
        if any(keyword in url_lower or keyword in link_text for keyword in ["reservation", "booking", "book-table"]):
            return "reservation"
        if any(keyword in url_lower or keyword in link_text for keyword in ["blog", "news", "article"]):
            return "blog"
        if path_lower == "/" or not path_lower:
            return "homepage"
        
        # More specific checks for PDFs that might be menus
        if url_lower.endswith(".pdf"):
            if any(keyword in url_lower for keyword in ["menu", "carte"]):
                return "menu_pdf" # Special type for PDF menus
            return "pdf_document"

        return "other" # Default category

    # Methods related to PDF download and screenshots (_find_pdf_links, _download_pdf, _take_screenshot)
    # are now integrated into the main crawl_website loop or _crawl_page_internal logic.
    # The `page.on("download", ...)` handler in `crawl_website` handles PDF downloads.
    # Screenshots are taken directly in `crawl_website`.

    # _prioritize_pages is replaced by the logic in crawl_website that uses a deque
    # and adds high_priority_urls to the front.

    # _merge_page_data is replaced by _merge_extracted_page_data.

    def _get_clean_domain_name(self, url: str) -> str:
        """Extract a clean domain name from URL for file naming"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. and clean for file naming
            domain = domain.replace('www.', '')
            # Replace dots and other characters that might be problematic in filenames
            domain = domain.replace('.', '_').replace(':', '_').replace('/', '_')
            return domain
        except Exception:
            return "unknown_domain"

    async def _get_browser_context(self):
        """Get or create browser context with enhanced stealth settings."""
        if not self.browser:
            playwright = await async_playwright().start()
            # Enhanced browser settings to avoid detection
            self.browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ]
            )
            logger.info("✅ Enhanced browser launched with stealth settings")
        
        # Create context with realistic settings
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York'
        )
        
        # Add stealth scripts to avoid detection
        await context.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
        """)
        
        return context

    async def _crawl_single_page(self, page, url: str, hint: str = "", depth: int = 0) -> Dict[str, Any]:
        """
        Crawl a single page with enhanced timeout and retry logic.
        
        Args:
            page: Playwright page object
            url: URL to crawl
            hint: Context hint for the page
            depth: Current crawl depth
            
        Returns:
            Dictionary with crawl results
        """
        start_time = time.time()
        result = {
            "url": url,
            "hint": hint,
            "depth": depth,
            "success": False,
            "error": None,
            "content": "",
            "screenshot_path": None,
            "emails": [],
            "phones": [],
            "download_urls": [],
            "internal_links": [],
            "external_links": [],
            "menu_indicators": False,
            "contact_indicators": False,
            "page_title": "",
            "meta_description": "",
            "load_time": 0
        }
        
        try:
            logger.info(f"Crawling page #{len(self.crawled_urls) + 1} (depth {depth}): {url} ({hint})")
            
            # Enhanced navigation with multiple timeout strategies
            navigation_success = False
            timeouts = [60000, 90000, 120000]  # 1min, 1.5min, 2min
            
            for attempt, timeout in enumerate(timeouts, 1):
                try:
                    logger.info(f"🔄 Navigation attempt {attempt}/{len(timeouts)} with {timeout/1000}s timeout")
                    
                    # Try different wait strategies
                    if attempt == 1:
                        # First attempt: wait for network idle
                        await page.goto(url, wait_until="networkidle", timeout=timeout)
                    elif attempt == 2:
                        # Second attempt: wait for DOM content loaded
                        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                    else:
                        # Final attempt: just wait for load event
                        await page.goto(url, wait_until="load", timeout=timeout)
                    
                    navigation_success = True
                    logger.info(f"✅ Navigation successful on attempt {attempt}")
                    break
                    
                except Exception as nav_error:
                    logger.warning(f"⚠️ Navigation attempt {attempt} failed: {str(nav_error)}")
                    if attempt < len(timeouts):
                        await asyncio.sleep(2)  # Brief pause between attempts
                    continue
            
            if not navigation_success:
                raise Exception("All navigation attempts failed")
            
            # Wait a bit more for dynamic content
            try:
                await page.wait_for_timeout(3000)  # 3 second buffer for JS
            except:
                pass
            
            # Extract page content with timeout protection
            try:
                result["page_title"] = await page.title() or ""
            except:
                result["page_title"] = ""
            
            try:
                content = await asyncio.wait_for(page.content(), timeout=30.0)
                result["content"] = content
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ Content extraction timeout for {url}")
                result["content"] = await page.evaluate("document.documentElement.outerHTML") or ""
            
            # Enhanced content analysis
            soup = BeautifulSoup(result["content"], 'html.parser')
            
            # Extract emails and phones with better patterns
            text_content = soup.get_text() if soup else ""
            
            # Email extraction
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
            emails = re.findall(email_pattern, text_content)
            result["emails"] = list(set(emails))  # Remove duplicates
            
            # Phone extraction (US and international formats)
            phone_patterns = [
                r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # US format
                r'\+1[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # US with country code
                r'\+\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}'  # International
            ]
            phones = []
            for pattern in phone_patterns:
                phones.extend(re.findall(pattern, text_content))
            result["phones"] = list(set(phones))
            
            # Check for menu and contact indicators
            menu_keywords = ['menu', 'food', 'drink', 'dish', 'meal', 'cuisine', 'order', 'delivery']
            contact_keywords = ['contact', 'phone', 'email', 'address', 'location', 'hours', 'about']
            
            result["menu_indicators"] = any(keyword in text_content.lower() for keyword in menu_keywords)
            result["contact_indicators"] = any(keyword in text_content.lower() for keyword in contact_keywords)
            
            # Extract meta description
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                result["meta_description"] = meta_desc.get("content", "")
            
            # Take screenshot with error handling
            try:
                screenshot_filename = f"screenshot_{int(time.time())}_{hash(url) % 10000}.png"
                screenshot_path = self.screenshot_dir / screenshot_filename
                
                await page.screenshot(path=str(screenshot_path), full_page=True, timeout=30000)
                result["screenshot_path"] = str(screenshot_path)
                logger.info(f"📸 Screenshot saved: {screenshot_filename}")
            except Exception as screenshot_error:
                logger.warning(f"⚠️ Screenshot failed for {url}: {str(screenshot_error)}")
            
            # Extract links for further crawling
            try:
                links = await page.evaluate("""
                    () => {
                        const links = Array.from(document.querySelectorAll('a[href]'));
                        return links.map(link => ({
                            href: link.href,
                            text: link.textContent.trim(),
                            title: link.title || ''
                        }));
                    }
                """)
                
                base_domain = urlparse(url).netloc
                internal_links = []
                external_links = []
                
                for link in links:
                    href = link.get('href', '')
                    if not href:
                        continue
                        
                    try:
                        parsed = urlparse(href)
                        if parsed.netloc == base_domain or not parsed.netloc:
                            internal_links.append(href)
                        else:
                            external_links.append(href)
                    except:
                        continue
                
                result["internal_links"] = internal_links[:50]  # Limit to prevent huge lists
                result["external_links"] = external_links[:20]
                
            except Exception as link_error:
                logger.warning(f"⚠️ Link extraction failed: {str(link_error)}")
            
            result["success"] = True
            result["load_time"] = time.time() - start_time
            logger.info(f"✅ Successfully crawled {url} in {result['load_time']:.2f}s")
            
        except Exception as e:
            result["error"] = str(e)
            result["load_time"] = time.time() - start_time
            logger.error(f"❌ Error crawling page {url}: {str(e)}")
        
        return result

    async def _navigate_with_circuit_breaker(self, page, url: str, attempt: int) -> bool:
        """
        Navigate to a page with circuit breaker logic and multiple fallback strategies.
        Returns True if navigation successful, False otherwise.
        """
        logger.info(f"🔄 Navigating to {url} (attempt {attempt + 1})")
        
        try:
            # Strategy 1: Try domcontentloaded with short timeout (skip networkidle as it hangs)
            if attempt == 0:
                logger.info(f"🌐 Strategy 1: domcontentloaded with {PAGE_NAVIGATION_TIMEOUT_MS/1000}s timeout")
                await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_NAVIGATION_TIMEOUT_MS)
                await page.wait_for_timeout(AFTER_NAV_WAIT_MS)
                return True
                
            # Strategy 2: Just wait for basic load event
            else:
                logger.info(f"🌐 Strategy 2: basic load with {PAGE_NAVIGATION_TIMEOUT_MS/1000}s timeout")
                await page.goto(url, wait_until="load", timeout=PAGE_NAVIGATION_TIMEOUT_MS)
                await page.wait_for_timeout(AFTER_NAV_WAIT_MS)
                return True
                
        except Exception as nav_error:
            logger.warning(f"⚠️ Navigation strategy {attempt + 1} failed for {url}: {str(nav_error)}")
            return False

    async def _extract_data_with_timeout(self, page, url: str, page_type: str) -> Dict[str, Any]:
        """
        Extract data from page with strict timeout protection to prevent hanging.
        """
        logger.info(f"📊 Extracting data from {url} with timeout protection")
        
        try:
            # Wrap the extraction in a timeout
            page_data = await asyncio.wait_for(
                self._extract_data_from_page(page, url, page_type),
                timeout=PAGE_CONTENT_TIMEOUT_MS / 1000.0
            )
            
            # Also try to get HTML content with timeout protection
            try:
                html_content = await asyncio.wait_for(
                    page.content(),
                    timeout=5.0  # 5 second timeout for HTML
                )
                page_data["html_content"] = html_content
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ HTML content extraction timeout for {url}")
                page_data["html_content"] = ""
            except Exception as html_error:
                logger.warning(f"⚠️ HTML content extraction error for {url}: {html_error}")
                page_data["html_content"] = ""
            
            return page_data
            
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ Data extraction timeout for {url}")
            return {
                "phones": [], "emails": [], "social_links": {},
                "menu_items_raw": [], "page_text_content": "", "html_content": ""
            }
        except Exception as extract_error:
            logger.warning(f"⚠️ Data extraction error for {url}: {str(extract_error)}")
            return {
                "phones": [], "emails": [], "social_links": {},
                "menu_items_raw": [], "page_text_content": "", "html_content": ""
            }

    async def _take_screenshot_with_timeout(self, page, url: str, page_type: str, final_output: Dict) -> None:
        """
        Take screenshot with timeout protection to prevent hanging.
        """
        try:
            logger.info(f"📸 Taking screenshot of {url}")
            
            # Create screenshot with timeout
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            parsed_url = urlparse(url)
            safe_url_part = re.sub(r'[^a-zA-Z0-9]', '_', parsed_url.path.strip('/') or "homepage")
            
            screenshot_filename = f"{timestamp}_{parsed_url.netloc}_{safe_url_part}_{page_type}.png"
            screenshot_path = self.base_screenshot_dir / screenshot_filename
            
            # Take screenshot with timeout
            await asyncio.wait_for(
                page.screenshot(path=screenshot_path, full_page=True),
                timeout=10.0  # 10 second timeout for screenshot
            )
            
            # Create proper local file URL
            local_file_url = f"file://{screenshot_path.resolve()}"
            
            # Create ScreenshotInfo object with local file URL
            screenshot_info = ScreenshotInfo(
                s3_url=local_file_url,  # Using local file URL instead of mock S3
                caption=f"Screenshot of {url} ({page_type})",
                source_phase=2,
                taken_at=datetime.now()
            )
            
            final_output["screenshots"].append(screenshot_info)
            logger.info(f"📸 Screenshot saved locally: {screenshot_filename}")
            logger.info(f"📁 Local file URL: {local_file_url}")
            
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ Screenshot timeout for {url}")
        except Exception as screenshot_error:
            logger.warning(f"⚠️ Screenshot error for {url}: {str(screenshot_error)}")

    def _calculate_page_priority(self, page_type: str) -> int:
        """
        Calculate priority score for different page types.
        Higher score = higher priority.
        """
        priority_map = {
            "homepage": 100,
            "menu": 90,
            "contact": 85,
            "about": 80,
            "reservation": 75,
            "gallery": 70,
            "menu_pdf": 95,
            "blog": 60,
            "other": 50,
            "pdf_document": 65
        }
        return priority_map.get(page_type, 50)

# Example Usage (Async)
async def main_example():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    crawler = DOMCrawler(max_pages_to_crawl=5, max_crawl_time_seconds=120) # Quick test
    
    # Test URL (replace with a real, simple restaurant website for testing)
    # For example, a local test HTML file server or a simple public site.
    test_restaurant_url = "https://www.thetestrestaurant.com" # Fictional
    # Create dummy files for local testing if using a fictional URL and want to test S3 mock
    # (Path(crawler.base_download_dir) / "dummy.pdf").touch(exist_ok=True)
    # (Path(crawler.base_screenshot_dir) / "dummy.png").touch(exist_ok=True)


    logger.info(f"Starting example crawl for: {test_restaurant_url}")
    
    # Simulate some high priority URLs that might come from Phase 1 (sitemap analysis)
    # These should be relative paths usually
    high_priority = ["/menu", "/contact-us.html"] 

    try:
        # For a real test, use a site you have permission to crawl or a test environment.
        # This example will likely fail for "thetestrestaurant.com" as it's fictional.
        # To test locally, you might serve a simple HTML site.
        # e.g., by running `python -m http.server` in a directory with some HTML files.
        # And then set test_restaurant_url = "http://localhost:8000"
        
        # Because thetestrestaurant.com is fictional, let's mock a very simple HTML page for demonstration
        # This part is just for making the example runnable without a live complex site.
        # In reality, you would point this to an actual website.
        
        # Mocked Playwright behavior for the example if the URL is the fictional one.
        # This is complex to fully mock here. The best test is against a real (simple) site.
        
        # Let's assume we are testing against a real, simple site that is accessible
        # For example: test_restaurant_url = "http://example.com" (though it won't have much restaurant data)
        
        # A more realistic test scenario for local dev:
        # 1. Create `test_site/index.html`, `test_site/menu.html`, `test_site/contact.html`
        # 2. Run `python -m http.server 8000 --directory test_site` from the project root.
        # 3. Set `test_restaurant_url = "http://localhost:8000"`
        
        # Example of local test setup:
        # Create test_site directory
        test_site_dir = Path("test_site_temp_domcrawler")
        test_site_dir.mkdir(exist_ok=True)
        (test_site_dir / "index.html").write_text("<html><body><h1>Welcome</h1><a href='menu.html'>Menu</a> <a href='contact.html'>Contact Us</a> <p>Call us at 123-456-7890</p> <a href='menu.pdf'>Download Menu PDF</a></body></html>")
        (test_site_dir / "menu.html").write_text("<html><body><h2>Our Menu</h2><p>Pizza - $10</p><p>Pasta - $12</p> <a href='/'>Home</a></body></html>")
        (test_site_dir / "contact.html").write_text("<html><body><h3>Contact</h3><p>Email: info@example.com</p> <a href='mailto:info@example.com'>Email Us</a></body></html>")
        # Create a dummy PDF for download testing
        (test_site_dir / "menu.pdf").write_text("%PDF-1.4\n%Dummy PDF content\n%%EOF")

        # Update crawler directories to be relative to this test site for cleanliness during example run
        # This is only for the example to keep outputs organized if you run it multiple times
        # In actual use, the default backend/analysis_data paths are fine.
        crawler.base_download_dir = test_site_dir / "downloads"
        crawler.base_screenshot_dir = test_site_dir / "screenshots"
        crawler.base_download_dir.mkdir(parents=True, exist_ok=True)
        crawler.base_screenshot_dir.mkdir(parents=True, exist_ok=True)


        test_url_local = "http://localhost:8001" # Assuming http.server runs on 8001
        logger.info(f"--- To run this example fully, ensure you have a local server serving the '{test_site_dir.name}' directory ---")
        logger.info(f"--- For example, run: python -m http.server 8001 --directory {test_site_dir.name} (from the parent of {test_site_dir.name}) ---")
        
        # You would need to run the http server in a separate terminal.
        # For now, this example will try to connect but might fail if server not running.
        # If you want to prevent actual network calls in a unit test, extensive mocking of Playwright is needed.

        results = await crawler.crawl_website(test_url_local, high_priority_relative_urls=["menu.html", "contact.html"])
        
        print("\n--- CRAWLER RESULTS ---")
        print(f"Target URL: {results['crawl_metadata']['target_url']}")
        print(f"Pages Crawled: {results['crawl_metadata']['pages_crawled_count']}")
        print(f"Duration: {results['crawl_metadata']['crawl_duration_seconds']:.2f}s")
        
        print("\nExtracted Textual Data:")
        # print(f"  Emails: {results['extracted_textual_data']['emails']}")
        # print(f"  Phones: {results['extracted_textual_data']['phones']}")
        # print(f"  Social: {results['extracted_textual_data']['social_links']}")
        # print(f"  Menu Raw Texts Count: {len(results['extracted_textual_data']['menu_texts_raw'])}")
        # if results['extracted_textual_data']['menu_texts_raw']:
        #     print(f"    Example Menu Text: {results['extracted_textual_data']['menu_texts_raw'][0][:100]}...")
        # print(f"  About Text Length: {len(results['extracted_textual_data']['about_text_raw'])}")
        # print(f"  Contact Text Length: {len(results['extracted_textual_data']['contact_text_raw'])}")
        
        # More compact print for the example
        import json
        print(json.dumps(results['extracted_textual_data'], indent=2, ensure_ascii=False))

        print(f"\nScreenshots ({len(results['screenshots'])}):")
        for sc_info in results['screenshots']:
            print(f"  - {sc_info.get('s3_url')} (Type: {sc_info.get('page_type')})")
            
        print(f"\nDownloaded PDF S3 URLs ({len(results['downloaded_pdf_s3_urls'])}):")
        for pdf_url in results['downloaded_pdf_s3_urls']:
            print(f"  - {pdf_url}")
            
        print(f"\nHTML Content for Key Pages ({len(results['html_content_key_pages'])}):")
        for page_url, _ in results['html_content_key_pages'].items():
            print(f"  - HTML stored for: {page_url}")

        if results['crawl_metadata']['errors']:
            print("\n--- ERRORS ---")
            for error in results['crawl_metadata']['errors']:
                print(f"  URL: {error['url']}, Error: {error['error']}")
                
    except ConnectionRefusedError:
        logger.error(f"🛑 Example crawl for {test_url_local} failed: Connection refused. Ensure local HTTP server is running.")
    except Exception as e:
        logger.error(f"💥 Example crawl failed: {e}", exc_info=True)
    finally:
        # Clean up test site directory
        # import shutil
        # if test_site_dir.exists():
        #     shutil.rmtree(test_site_dir)
        # logger.info(f"Cleaned up {test_site_dir.name}")
        pass # Keep test files for inspection for now


if __name__ == "__main__":
    # To run the example:
    # 1. Ensure Playwright browsers are installed: `playwright install`
    # 2. In one terminal, navigate to the parent directory of `test_site_temp_domcrawler` (likely project root)
    #    and run: `python -m http.server 8001 --directory test_site_temp_domcrawler`
    # 3. In another terminal, run this script: `python backend/restaurant_consultant/dom_crawler.py`
    asyncio.run(main_example()) 
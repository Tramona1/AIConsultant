"""
Sitemap and Robots.txt Analyzer
Part of the Progressive Data Extraction System (Phase 1)
"""

import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)

class SitemapAnalyzer:
    """
    Analyze robots.txt and sitemaps to identify relevant pages for targeted extraction
    """
    
    def __init__(self):
        logger.info("✅ Sitemap analyzer initialized")
    
    async def analyze_site(self, url: str) -> Dict[str, Any]:
        """
        Analyze site structure via robots.txt and sitemaps
        
        Args:
            url: Website base URL
            
        Returns:
            Dictionary with relevant pages and site structure info
        """
        try:
            logger.info(f"🗺️ Analyzing site structure for: {url}")
            
            result = {
                'relevant_pages': [],
                'sitemap_urls': [],
                'robots_txt_found': False,
                'data_source': 'sitemap_analysis',
                'extraction_timestamp': datetime.now().isoformat()
            }
            
            # Step 1: Check robots.txt
            robots_data = await self._fetch_robots_txt(url)
            if robots_data:
                result['robots_txt_found'] = True
                result['sitemap_urls'] = robots_data.get('sitemaps', [])
            
            # Step 2: Try common sitemap locations
            if not result['sitemap_urls']:
                common_sitemap_paths = [
                    '/sitemap.xml',
                    '/sitemap_index.xml',
                    '/sitemaps.xml',
                    '/sitemap.txt'
                ]
                
                for path in common_sitemap_paths:
                    sitemap_url = urljoin(url, path)
                    if await self._check_url_exists(sitemap_url):
                        result['sitemap_urls'].append(sitemap_url)
                        break
            
            # Step 3: Parse sitemaps and find relevant pages
            relevant_pages = []
            for sitemap_url in result['sitemap_urls']:
                pages = await self._parse_sitemap(sitemap_url)
                relevant_pages.extend(pages)
            
            # Step 4: Filter for restaurant-relevant pages
            result['relevant_pages'] = self._filter_relevant_pages(relevant_pages)
            
            logger.info(f"✅ Site analysis complete: {len(result['relevant_pages'])} relevant pages found")
            return result
            
        except Exception as e:
            logger.error(f"❌ Sitemap analysis failed: {str(e)}")
            return {
                'relevant_pages': [],
                'sitemap_urls': [],
                'robots_txt_found': False,
                'error': str(e)
            }
    
    async def _fetch_robots_txt(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch and parse robots.txt"""
        try:
            robots_url = urljoin(url, '/robots.txt')
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(robots_url)
                
                if response.status_code == 200:
                    content = response.text
                    sitemaps = []
                    
                    for line in content.split('\n'):
                        line = line.strip()
                        if line.lower().startswith('sitemap:'):
                            sitemap_url = line[8:].strip()
                            sitemaps.append(sitemap_url)
                    
                    return {'sitemaps': sitemaps}
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch robots.txt: {str(e)}")
            return None
    
    async def _check_url_exists(self, url: str) -> bool:
        """Check if a URL exists"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.head(url)
                return response.status_code == 200
        except:
            return False
    
    async def _parse_sitemap(self, sitemap_url: str) -> List[str]:
        """Parse XML sitemap and extract URLs"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(sitemap_url)
                
                if response.status_code != 200:
                    return []
                
                # Handle sitemap index files
                if 'index' in sitemap_url.lower():
                    return await self._parse_sitemap_index(response.text)
                else:
                    return self._parse_sitemap_xml(response.text)
                    
        except Exception as e:
            logger.error(f"❌ Failed to parse sitemap {sitemap_url}: {str(e)}")
            return []
    
    async def _parse_sitemap_index(self, xml_content: str) -> List[str]:
        """Parse sitemap index and recursively get URLs from sub-sitemaps"""
        urls = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # Find sitemap URLs in index
            sitemap_urls = []
            for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
                loc = sitemap.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc is not None:
                    sitemap_urls.append(loc.text)
            
            # Parse each sub-sitemap (limit to prevent infinite recursion)
            for sitemap_url in sitemap_urls[:10]:  # Limit to 10 sitemaps
                sub_urls = await self._parse_sitemap(sitemap_url)
                urls.extend(sub_urls)
                
        except ET.ParseError as e:
            logger.error(f"❌ XML parsing error in sitemap index: {str(e)}")
        
        return urls
    
    def _parse_sitemap_xml(self, xml_content: str) -> List[str]:
        """Parse regular sitemap XML"""
        urls = []
        
        try:
            root = ET.fromstring(xml_content)
            
            for url_elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
                loc = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc is not None:
                    urls.append(loc.text)
                    
        except ET.ParseError as e:
            logger.error(f"❌ XML parsing error in sitemap: {str(e)}")
        
        return urls
    
    def _filter_relevant_pages(self, urls: List[str]) -> List[str]:
        """Filter URLs for restaurant-relevant pages"""
        relevant_keywords = [
            'menu', 'food', 'drink', 'dinner', 'lunch', 'breakfast',
            'contact', 'about', 'location', 'hours', 'order',
            'catering', 'reservation', 'book', 'delivery',
            'takeout', 'cuisine', 'specials', 'wine', 'beer'
        ]
        
        relevant_pages = []
        
        for url in urls:
            url_lower = url.lower()
            
            # Check if URL contains relevant keywords
            if any(keyword in url_lower for keyword in relevant_keywords):
                relevant_pages.append(url)
            
            # Also include pages that might be PDF menus
            elif url_lower.endswith('.pdf') and 'menu' in url_lower:
                relevant_pages.append(url)
        
        # Remove duplicates and limit
        relevant_pages = list(set(relevant_pages))[:20]  # Limit to 20 most relevant
        
        logger.info(f"🎯 Filtered {len(urls)} total URLs to {len(relevant_pages)} relevant pages")
        return relevant_pages
    
    async def analyze_sitemap(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Analyze sitemaps for a given URL to discover important pages
        
        Args:
            url: Website URL to analyze sitemaps for
            
        Returns:
            Dictionary with sitemap analysis results
        """
        logger.info(f"🗺️ Analyzing sitemaps for: {url}")
        
        try:
            # Parse the base URL
            from urllib.parse import urljoin, urlparse
            parsed_url = urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            # Try common sitemap locations
            sitemap_urls = [
                urljoin(base_url, '/sitemap.xml'),
                urljoin(base_url, '/sitemap_index.xml'),
                urljoin(base_url, '/sitemaps.xml'),
                urljoin(base_url, '/sitemap/'),
                urljoin(base_url, '/sitemap/sitemap.xml')
            ]
            
            sitemap_data = []
            sitemap_urls_found = []
            
            async with httpx.AsyncClient(timeout=10) as client:
                for sitemap_url in sitemap_urls:
                    try:
                        logger.debug(f"📄 Checking sitemap: {sitemap_url}")
                        response = await client.get(sitemap_url)
                        
                        if response.status_code == 200:
                            logger.info(f"✅ Found sitemap: {sitemap_url}")
                            sitemap_urls_found.append(sitemap_url)
                            
                            # Parse the sitemap XML
                            sitemap_content = await self._parse_sitemap_xml(response.text, base_url)
                            if sitemap_content:
                                sitemap_data.extend(sitemap_content)
                                
                    except Exception as e:
                        logger.debug(f"❌ Could not access sitemap {sitemap_url}: {str(e)}")
                        continue
            
            if not sitemap_data:
                logger.info(f"❌ No accessible sitemaps found for {url}")
                return None
            
            # Analyze and categorize the URLs
            analyzed_data = self._analyze_sitemap_urls(sitemap_data)
            
            result = {
                "sitemap_urls": sitemap_urls_found,
                "sitemap_urls_details": sitemap_data,
                "total_urls_found": len(sitemap_data),
                "key_pages_analysis": analyzed_data,
                "cost": 0.0,  # No API cost for sitemap analysis
                "extraction_timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"✅ Sitemap analysis complete: Found {len(sitemap_data)} URLs in {len(sitemap_urls_found)} sitemaps")
            return result
            
        except Exception as e:
            logger.error(f"❌ Sitemap analysis failed for {url}: {str(e)}")
            return None
    
    async def _parse_sitemap_xml(self, xml_content: str, base_url: str) -> List[Dict[str, Any]]:
        """Parse sitemap XML content and extract URLs"""
        try:
            import xml.etree.ElementTree as ET
            from urllib.parse import urljoin
            
            root = ET.fromstring(xml_content)
            urls = []
            
            # Handle sitemap index files (containing references to other sitemaps)
            if root.tag.endswith('sitemapindex'):
                logger.debug("📋 Found sitemap index file")
                async with httpx.AsyncClient(timeout=10) as client:
                    for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
                        loc_elem = sitemap.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                        if loc_elem is not None and loc_elem.text:
                            try:
                                # Recursively parse sub-sitemaps
                                sub_response = await client.get(loc_elem.text)
                                if sub_response.status_code == 200:
                                    sub_urls = await self._parse_sitemap_xml(sub_response.text, base_url)
                                    urls.extend(sub_urls)
                            except Exception as e:
                                logger.debug(f"❌ Could not parse sub-sitemap {loc_elem.text}: {str(e)}")
                                continue
            
            # Handle regular sitemap files (containing URLs)
            else:
                logger.debug("📄 Found regular sitemap file")
                for url_elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
                    loc_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                    lastmod_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod')
                    priority_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}priority')
                    changefreq_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}changefreq')
                    
                    if loc_elem is not None and loc_elem.text:
                        url_data = {
                            "loc": loc_elem.text,
                            "lastmod": lastmod_elem.text if lastmod_elem is not None else None,
                            "priority": float(priority_elem.text) if priority_elem is not None else None,
                            "changefreq": changefreq_elem.text if changefreq_elem is not None else None
                        }
                        urls.append(url_data)
            
            return urls
            
        except ET.ParseError as e:
            logger.warning(f"❌ Could not parse sitemap XML: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"❌ Error parsing sitemap XML: {str(e)}")
            return []
    
    def _analyze_sitemap_urls(self, sitemap_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze sitemap URLs to identify key page types"""
        
        key_pages = {
            "menu_pages": [],
            "contact_pages": [],
            "about_pages": [],
            "reservation_pages": [],
            "location_pages": [],
            "other_pages": []
        }
        
        for url_data in sitemap_data:
            url = url_data.get("loc", "").lower()
            
            # Categorize URLs based on path keywords
            if any(keyword in url for keyword in ["menu", "carte", "food", "dining"]):
                key_pages["menu_pages"].append(url_data)
            elif any(keyword in url for keyword in ["contact", "reach", "phone", "email"]):
                key_pages["contact_pages"].append(url_data)
            elif any(keyword in url for keyword in ["about", "story", "history", "chef"]):
                key_pages["about_pages"].append(url_data)
            elif any(keyword in url for keyword in ["reservation", "booking", "table", "reserve"]):
                key_pages["reservation_pages"].append(url_data)
            elif any(keyword in url for keyword in ["location", "directions", "find", "map"]):
                key_pages["location_pages"].append(url_data)
            else:
                key_pages["other_pages"].append(url_data)
        
        # Calculate statistics
        analysis = {
            "categories": key_pages,
            "statistics": {
                "total_urls": len(sitemap_data),
                "menu_pages_count": len(key_pages["menu_pages"]),
                "contact_pages_count": len(key_pages["contact_pages"]),
                "about_pages_count": len(key_pages["about_pages"]),
                "reservation_pages_count": len(key_pages["reservation_pages"]),
                "location_pages_count": len(key_pages["location_pages"]),
                "other_pages_count": len(key_pages["other_pages"])
            }
        }
        
        return analysis 
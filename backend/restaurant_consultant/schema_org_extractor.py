"""
Schema.org Structured Data Extractor
Part of the Progressive Data Extraction System (Phase 1)
"""

import logging
import json
import re
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)

class SchemaOrgExtractor:
    """
    Extract structured data from websites using Schema.org markup
    Provides high-quality, machine-readable data for Phase 1
    """
    
    def __init__(self):
        logger.info("✅ Schema.org extractor initialized")
    
    async def extract_from_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract Schema.org structured data from a URL
        
        Args:
            url: Website URL to extract from
            
        Returns:
            Dictionary with extracted structured data
        """
        try:
            logger.info(f"🔍 Extracting Schema.org data from: {url}")
            
            # Fetch the HTML content
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                html_content = response.text
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract JSON-LD structured data
            structured_data = {}
            
            # Find all JSON-LD script tags
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    parsed_data = self._parse_schema_data(data)
                    if parsed_data:
                        structured_data.update(parsed_data)
                except json.JSONDecodeError:
                    continue
            
            # Extract microdata (as fallback)
            microdata = self._extract_microdata(soup)
            if microdata:
                structured_data.update(microdata)
            
            if structured_data:
                structured_data['data_source'] = 'schema_org'
                structured_data['extraction_timestamp'] = datetime.now().isoformat()
                logger.info(f"✅ Schema.org: Found {len(structured_data)} structured fields")
                return structured_data
            else:
                logger.info("❌ No Schema.org structured data found")
                return None
                
        except Exception as e:
            logger.error(f"❌ Schema.org extraction failed: {str(e)}")
            return None
    
    def _parse_schema_data(self, data: Any) -> Dict[str, Any]:
        """
        Parse JSON-LD schema data recursively
        """
        result = {}
        
        if isinstance(data, list):
            for item in data:
                parsed = self._parse_schema_data(item)
                result.update(parsed)
        elif isinstance(data, dict):
            schema_type = data.get('@type', '').lower()
            
            # Handle Restaurant schema
            if 'restaurant' in schema_type or 'localbusiness' in schema_type:
                result.update(self._extract_restaurant_schema(data))
            
            # Handle Menu schema
            elif 'menu' in schema_type:
                result.update(self._extract_menu_schema(data))
            
            # Handle Organization schema
            elif 'organization' in schema_type:
                result.update(self._extract_organization_schema(data))
            
            # Handle nested structures
            for key, value in data.items():
                if isinstance(value, (dict, list)) and key != '@context':
                    nested = self._parse_schema_data(value)
                    result.update(nested)
        
        return result
    
    def _extract_restaurant_schema(self, data: Dict) -> Dict[str, Any]:
        """Extract restaurant-specific Schema.org data"""
        result = {}
        
        if data.get('name'):
            result['name'] = data['name']
        
        if data.get('description'):
            result['description'] = data['description']
        
        # Address
        address = data.get('address')
        if address:
            if isinstance(address, dict):
                result['address'] = self._format_address(address)
            elif isinstance(address, str):
                result['address'] = address
        
        # Contact info
        if data.get('telephone'):
            result['phone'] = data['telephone']
        
        if data.get('url'):
            result['website'] = data['url']
        
        # Opening hours
        opening_hours = data.get('openingHours')
        if opening_hours:
            result['hours'] = opening_hours if isinstance(opening_hours, list) else [opening_hours]
        
        # Price range
        if data.get('priceRange'):
            result['price_range'] = data['priceRange']
        
        # Cuisine
        serves_cuisine = data.get('servesCuisine')
        if serves_cuisine:
            result['cuisine'] = serves_cuisine if isinstance(serves_cuisine, list) else [serves_cuisine]
        
        # Menu
        menu = data.get('menu')
        if menu:
            result['menu_url'] = menu if isinstance(menu, str) else menu.get('url')
        
        # Social media
        same_as = data.get('sameAs')
        if same_as:
            result['social_media'] = same_as if isinstance(same_as, list) else [same_as]
        
        # Location/coordinates
        geo = data.get('geo')
        if geo:
            result['coordinates'] = {
                'latitude': geo.get('latitude'),
                'longitude': geo.get('longitude')
            }
        
        return result
    
    def _extract_menu_schema(self, data: Dict) -> Dict[str, Any]:
        """Extract menu-specific Schema.org data"""
        result = {}
        
        # Menu sections
        has_menu_section = data.get('hasMenuSection')
        if has_menu_section:
            sections = has_menu_section if isinstance(has_menu_section, list) else [has_menu_section]
            menu_items = []
            
            for section in sections:
                section_name = section.get('name', 'Menu Items')
                items = section.get('hasMenuItem', [])
                if not isinstance(items, list):
                    items = [items]
                
                for item in items:
                    menu_item = {
                        'name': item.get('name'),
                        'description': item.get('description'),
                        'section': section_name
                    }
                    
                    # Price
                    offers = item.get('offers')
                    if offers:
                        price = offers.get('price') if isinstance(offers, dict) else offers[0].get('price')
                        if price:
                            menu_item['price'] = price
                    
                    menu_items.append(menu_item)
            
            if menu_items:
                result['menu_items'] = menu_items
        
        return result
    
    def _extract_organization_schema(self, data: Dict) -> Dict[str, Any]:
        """Extract organization-specific Schema.org data"""
        result = {}
        
        if data.get('name'):
            result['business_name'] = data['name']
        
        if data.get('logo'):
            logo = data['logo']
            result['logo_url'] = logo.get('url') if isinstance(logo, dict) else logo
        
        return result
    
    def _format_address(self, address: Dict) -> str:
        """Format address from Schema.org address object"""
        parts = []
        
        if address.get('streetAddress'):
            parts.append(address['streetAddress'])
        
        if address.get('addressLocality'):
            parts.append(address['addressLocality'])
        
        if address.get('addressRegion'):
            parts.append(address['addressRegion'])
        
        if address.get('postalCode'):
            parts.append(address['postalCode'])
        
        return ', '.join(parts)
    
    def _extract_microdata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract microdata as fallback"""
        result = {}
        
        # Look for itemscope with Restaurant type
        restaurant_elements = soup.find_all(attrs={'itemtype': re.compile(r'.*restaurant.*', re.I)})
        
        for element in restaurant_elements:
            # Extract name
            name_elem = element.find(attrs={'itemprop': 'name'})
            if name_elem:
                result['name'] = name_elem.get_text(strip=True)
            
            # Extract phone
            phone_elem = element.find(attrs={'itemprop': 'telephone'})
            if phone_elem:
                result['phone'] = phone_elem.get_text(strip=True)
            
            # Extract address
            address_elem = element.find(attrs={'itemprop': 'address'})
            if address_elem:
                result['address'] = address_elem.get_text(strip=True)
        
        return result
    
    async def extract_schema_org_data(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract Schema.org structured data from a URL (full implementation)"""
        logger.info(f"🔍 Extracting Schema.org data from: {url}")
        
        try:
            # Use the existing extract_from_url method which has full implementation
            return await self.extract_from_url(url)
            
        except Exception as e:
            logger.error(f"❌ Schema.org extraction failed for {url}: {str(e)}")
            return None 
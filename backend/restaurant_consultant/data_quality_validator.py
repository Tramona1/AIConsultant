"""
Data Quality Validator for Progressive Extraction
Manages quality assessment and cleaning for the 4-phase extraction system
"""

import logging
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class DataQualityScore(BaseModel):
    """Track data quality metrics"""
    completeness: float = 0.0  # 0-1 score
    confidence: float = 0.0    # 0-1 score
    source_reliability: float = 0.0  # 0-1 score
    overall_score: float = 0.0  # 0-1 score
    missing_critical_fields: List[str] = Field(default_factory=list)
    data_sources: List[str] = Field(default_factory=list)

class DataQualityValidator:
    """
    Assess data quality and determine if additional extraction phases are needed
    """
    
    def __init__(self):
        # Define critical fields for restaurant data
        self.critical_fields = [
            'name', 'address', 'phone', 'website', 'hours'
        ]
        
        # Define important fields (nice to have)
        self.important_fields = [
            'menu_items', 'cuisine', 'price_range', 'rating',
            'social_media', 'description', 'coordinates'
        ]
        
        # Define source reliability scores
        self.source_reliability = {
            'google_places_api': 0.95,
            'schema_org': 0.85,
            'sitemap_analysis': 0.70,
            'dom_crawler': 0.60,
            'ai_vision': 0.75,
            'stagehand_llm': 0.65,
            'manual_fallback': 0.40
        }
        
        logger.info("✅ Data quality validator initialized")
    
    async def assess_quality(self, data: Dict[str, Any], phase: int) -> DataQualityScore:
        """
        Assess the quality of extracted data to determine if more phases are needed
        
        Args:
            data: Restaurant data collected so far
            phase: Current extraction phase (1-4)
            
        Returns:
            DataQualityScore with metrics and recommendations
        """
        logger.info(f"📊 Assessing data quality after Phase {phase}...")
        
        # Calculate completeness score
        completeness = self._calculate_completeness(data)
        
        # Calculate confidence score based on data sources
        confidence = self._calculate_confidence(data)
        
        # Calculate source reliability
        source_reliability = self._calculate_source_reliability(data)
        
        # Calculate overall score (weighted average)
        overall_score = (
            completeness * 0.4 +
            confidence * 0.3 +
            source_reliability * 0.3
        )
        
        # Identify missing critical fields
        missing_critical = self.identify_missing_critical_fields(data)
        
        # Identify data sources used
        data_sources = self._identify_data_sources(data)
        
        quality_score = DataQualityScore(
            completeness=completeness,
            confidence=confidence,
            source_reliability=source_reliability,
            overall_score=overall_score,
            missing_critical_fields=missing_critical,
            data_sources=data_sources
        )
        
        logger.info(f"📊 Quality Assessment Results:")
        logger.info(f"   🎯 Overall Score: {overall_score:.2f}")
        logger.info(f"   📋 Completeness: {completeness:.2f}")
        logger.info(f"   🎭 Confidence: {confidence:.2f}")
        logger.info(f"   🔗 Source Reliability: {source_reliability:.2f}")
        logger.info(f"   ❌ Missing Critical: {missing_critical}")
        logger.info(f"   📊 Data Sources: {data_sources}")
        
        return quality_score
    
    def _calculate_completeness(self, data: Dict[str, Any]) -> float:
        """Calculate how complete the data is (0-1 score)"""
        total_fields = len(self.critical_fields) + len(self.important_fields)
        found_fields = 0
        
        # Count critical fields (weighted more heavily)
        for field in self.critical_fields:
            if self._field_has_value(data, field):
                found_fields += 2  # Critical fields count double
        
        # Count important fields
        for field in self.important_fields:
            if self._field_has_value(data, field):
                found_fields += 1
        
        # Adjust total to account for critical field weighting
        weighted_total = len(self.critical_fields) * 2 + len(self.important_fields)
        
        return min(found_fields / weighted_total, 1.0)
    
    def _calculate_confidence(self, data: Dict[str, Any]) -> float:
        """Calculate confidence in the data accuracy"""
        confidence_scores = []
        
        # Check for multiple sources confirming the same data
        if self._has_multiple_sources(data, 'name'):
            confidence_scores.append(0.9)
        elif self._field_has_value(data, 'name'):
            confidence_scores.append(0.7)
        
        if self._has_multiple_sources(data, 'address'):
            confidence_scores.append(0.9)
        elif self._field_has_value(data, 'address'):
            confidence_scores.append(0.7)
        
        # Check for structured data vs. extracted data
        if data.get('data_source') == 'google_places_api':
            confidence_scores.append(0.95)
        elif data.get('data_source') == 'schema_org':
            confidence_scores.append(0.85)
        
        return sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5
    
    def _calculate_source_reliability(self, data: Dict[str, Any]) -> float:
        """Calculate reliability based on data sources used"""
        sources = self._identify_data_sources(data)
        
        if not sources:
            return 0.0
        
        reliability_scores = [
            self.source_reliability.get(source, 0.5) for source in sources
        ]
        
        # Weight by the best source found
        return max(reliability_scores) if reliability_scores else 0.5
    
    def _field_has_value(self, data: Dict[str, Any], field: str) -> bool:
        """Check if a field has a meaningful value with enhanced field mapping."""
        
        # Enhanced field mapping for FinalRestaurantOutput model
        field_mappings = {
            'name': ['restaurant_name', 'name'],
            'address': ['address_canonical', 'address_raw', 'address', 'formatted_address'],
            'phone': ['phone_canonical', 'phone_raw', 'phone', 'formatted_phone_number'],
            'website': ['website_url', 'canonical_url', 'url', 'website'],
            'hours': ['operating_hours', 'hours', 'opening_hours'],
            'menu_items': ['menu_items'],
            'cuisine': ['cuisine_types', 'cuisine'],
            'price_range': ['price_range', 'price_level'],
            'rating': ['google_rating', 'rating'],
            'social_media': ['social_media_profiles', 'social_media_links', 'social_links'],
            'description': ['description_short', 'description'],
            'coordinates': ['coordinates', 'location']
        }
        
        # Get possible field names for this field
        possible_fields = field_mappings.get(field, [field])
        
        for field_name in possible_fields:
            value = data.get(field_name)
            
            # Enhanced value checking
            if value is not None:
                if isinstance(value, str):
                    # Check for meaningful string values
                    if value.strip() and value.strip() not in ['', 'null', 'None', 'N/A', 'Unknown', 'Not Available']:
                        logger.debug(f"✅ Field '{field}' found via '{field_name}': {value[:50]}...")
                        return True
                elif isinstance(value, (list, dict)):
                    # Check for non-empty collections
                    if value:
                        logger.debug(f"✅ Field '{field}' found via '{field_name}': {len(value)} items")
                        return True
                elif isinstance(value, (int, float)):
                    # Check for meaningful numeric values
                    if value > 0:
                        logger.debug(f"✅ Field '{field}' found via '{field_name}': {value}")
                        return True
                elif hasattr(value, '__str__'):
                    # Handle objects like HttpUrl
                    str_value = str(value)
                    if str_value and str_value not in ['', 'null', 'None']:
                        logger.debug(f"✅ Field '{field}' found via '{field_name}': {str_value[:50]}...")
                        return True
        
        logger.debug(f"❌ Field '{field}' not found in any of: {possible_fields}")
        return False
    
    def _has_multiple_sources(self, data: Dict[str, Any], field: str) -> bool:
        """Check if multiple sources confirm the same field"""
        # This is a simplified check - in a full implementation,
        # we'd track source metadata for each field
        sources = self._identify_data_sources(data)
        return len(sources) > 1 and self._field_has_value(data, field)
    
    def _identify_data_sources(self, data: Dict[str, Any]) -> List[str]:
        """Identify which data sources contributed to this data"""
        sources = []
        
        if data.get('data_source'):
            sources.append(data['data_source'])
        
        # Look for source indicators in the data
        if data.get('google_rating') or data.get('google_review_count'):
            sources.append('google_places_api')
        
        if data.get('schema_org_data'):
            sources.append('schema_org')
        
        if data.get('phase_2_note'):
            sources.append('dom_crawler')
        
        if data.get('phase_3_note'):
            sources.append('ai_vision')
        
        return list(set(sources))  # Remove duplicates
    
    def identify_missing_critical_fields(self, data: Dict[str, Any]) -> List[str]:
        """Identify which critical fields are missing with enhanced logging."""
        missing = []
        found = []
        
        logger.info("🔍 Checking critical fields availability...")
        
        for field in self.critical_fields:
            if self._field_has_value(data, field):
                found.append(field)
            else:
                missing.append(field)
        
        # Enhanced logging for debugging
        if found:
            logger.info(f"   ✅ Found Critical: {found}")
        if missing:
            logger.info(f"   ❌ Missing Critical: {missing}")
        else:
            logger.info("   🎉 All critical fields found!")
        
        # Log some sample data for debugging
        if missing and logger.isEnabledFor(logging.DEBUG):
            logger.debug("📊 Sample data structure for debugging:")
            sample_keys = list(data.keys())[:10]  # First 10 keys
            for key in sample_keys:
                value = data[key]
                if isinstance(value, str):
                    logger.debug(f"   {key}: '{value[:50]}{'...' if len(str(value)) > 50 else ''}'")
                elif isinstance(value, (list, dict)):
                    logger.debug(f"   {key}: {type(value).__name__}({len(value)} items)")
                else:
                    logger.debug(f"   {key}: {type(value).__name__}({value})")
        
        return missing
    
    async def clean_and_normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean and normalize the final extracted data
        
        Args:
            raw_data: Raw extracted data from all phases
            
        Returns:
            Cleaned and normalized data
        """
        logger.info("🧹 Cleaning and normalizing data...")
        
        cleaned_data = raw_data.copy()
        
        # Clean phone numbers
        if cleaned_data.get('phone'):
            cleaned_data['phone'] = self._clean_phone_number(cleaned_data['phone'])
        
        # Clean and validate URLs
        if cleaned_data.get('website'):
            cleaned_data['website'] = self._clean_url(cleaned_data['website'])
        
        # Normalize address
        if cleaned_data.get('address'):
            cleaned_data['address'] = self._clean_address(cleaned_data['address'])
        
        # Clean menu items
        if cleaned_data.get('menu_items'):
            cleaned_data['menu_items'] = self._clean_menu_items(cleaned_data['menu_items'])
        
        # Add cleaning metadata
        cleaned_data['data_cleaning'] = {
            'cleaned_at': datetime.now().isoformat(),
            'cleaning_version': '1.0'
        }
        
        logger.info("✅ Data cleaning completed")
        return cleaned_data
    
    def _clean_phone_number(self, phone: str) -> str:
        """Clean and normalize phone numbers"""
        if not isinstance(phone, str):
            return str(phone)
        
        # Remove all non-digit characters except + for international numbers
        cleaned = re.sub(r'[^\d+]', '', phone)
        
        # Format US phone numbers
        if len(cleaned) == 10 and cleaned.isdigit():
            return f"({cleaned[:3]}) {cleaned[3:6]}-{cleaned[6:]}"
        elif len(cleaned) == 11 and cleaned.startswith('1'):
            return f"+1 ({cleaned[1:4]}) {cleaned[4:7]}-{cleaned[7:]}"
        
        return cleaned
    
    def _clean_url(self, url: str) -> str:
        """Clean and validate URLs"""
        if not isinstance(url, str):
            return str(url)
        
        url = url.strip()
        
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        return url
    
    def _clean_address(self, address: str) -> str:
        """Clean and normalize addresses"""
        if not isinstance(address, str):
            return str(address)
        
        # Basic address cleaning
        address = address.strip()
        address = re.sub(r'\s+', ' ', address)  # Normalize whitespace
        
        return address
    
    def _clean_menu_items(self, menu_items: Any) -> List[Dict[str, Any]]:
        """Clean and normalize menu items"""
        if not isinstance(menu_items, list):
            return []
        
        cleaned_items = []
        for item in menu_items:
            if isinstance(item, dict):
                cleaned_item = {}
                
                # Clean item name
                if item.get('name'):
                    cleaned_item['name'] = item['name'].strip()
                
                # Clean description
                if item.get('description'):
                    cleaned_item['description'] = item['description'].strip()
                
                # Clean price
                if item.get('price'):
                    price = str(item['price']).strip()
                    # Extract numeric price
                    price_match = re.search(r'[\d,]+\.?\d*', price)
                    if price_match:
                        cleaned_item['price'] = price_match.group()
                    else:
                        cleaned_item['price'] = price
                
                # Only add if we have at least a name
                if cleaned_item.get('name'):
                    cleaned_items.append(cleaned_item)
        
        return cleaned_items 
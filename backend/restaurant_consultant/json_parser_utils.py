"""
Robust JSON parsing utilities for LLM outputs following Google Gemini best practices.
Handles common issues like markdown wrapping, extra text, and malformed JSON.
"""

import json
import logging
import re
from typing import Dict, List, Optional, Union, Any

logger = logging.getLogger(__name__)

def parse_llm_json_output(
    raw_llm_text: str, 
    function_name: str = "unknown",
    expected_keys: Optional[List[str]] = None
) -> Optional[Union[Dict, List]]:
    """
    Robust JSON parsing for LLM outputs with multiple fallback strategies.
    
    Args:
        raw_llm_text: Raw text response from LLM
        function_name: Name of calling function for logging context
        expected_keys: Optional list of expected top-level keys for validation
        
    Returns:
        Parsed JSON as dict/list or None if parsing fails
    """
    if not raw_llm_text or not raw_llm_text.strip():
        logger.warning(f"🔍 [{function_name}] Empty or whitespace-only LLM response")
        return None
    
    original_text = raw_llm_text
    logger.info(f"🔍 [{function_name}] Parsing LLM JSON response ({len(raw_llm_text)} chars)")
    
    # Strategy 1: Direct JSON parsing (for response_mime_type="application/json")
    try:
        cleaned_text = raw_llm_text.strip()
        result = json.loads(cleaned_text)
        logger.info(f"✅ [{function_name}] Direct JSON parsing successful")
        
        # Validate expected keys if provided
        if expected_keys and isinstance(result, dict):
            missing_keys = [key for key in expected_keys if key not in result]
            if missing_keys:
                logger.warning(f"⚠️ [{function_name}] Missing expected keys: {missing_keys}")
            else:
                logger.info(f"✅ [{function_name}] All expected keys present: {expected_keys}")
        
        return result
        
    except json.JSONDecodeError as e:
        logger.info(f"🔄 [{function_name}] Direct parsing failed: {str(e)}, trying fallback strategies")
    
    # Strategy 2: Strip markdown code fences
    try:
        # Remove ```json ... ``` or ``` ... ```
        fence_pattern = r'```(?:json)?\s*(.*?)\s*```'
        match = re.search(fence_pattern, raw_llm_text, re.DOTALL)
        
        if match:
            cleaned_text = match.group(1).strip()
            logger.info(f"🔄 [{function_name}] Found JSON in markdown fences, attempting parse")
        else:
            # Remove leading/trailing non-JSON text
            cleaned_text = raw_llm_text.strip()
            logger.info(f"🔄 [{function_name}] No markdown fences found, using original text")
        
        result = json.loads(cleaned_text)
        logger.info(f"✅ [{function_name}] Markdown fence removal successful")
        
        # Validate expected keys
        if expected_keys and isinstance(result, dict):
            missing_keys = [key for key in expected_keys if key not in result]
            if missing_keys:
                logger.warning(f"⚠️ [{function_name}] Missing expected keys: {missing_keys}")
        
        return result
        
    except json.JSONDecodeError as e:
        logger.info(f"🔄 [{function_name}] Markdown fence removal failed: {str(e)}, trying bracket extraction")
    
    # Strategy 3: Extract JSON by finding first { and last } (or [ and ])
    try:
        # Try to find object boundaries
        first_brace = raw_llm_text.find('{')
        last_brace = raw_llm_text.rfind('}')
        
        first_bracket = raw_llm_text.find('[')
        last_bracket = raw_llm_text.rfind(']')
        
        # Determine if we likely have an object or array
        if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
            # Likely an object
            if last_brace != -1 and last_brace > first_brace:
                extracted_json = raw_llm_text[first_brace:last_brace + 1]
                logger.info(f"🔄 [{function_name}] Extracted object JSON by brackets")
            else:
                raise ValueError("No valid object closing brace found")
        elif first_bracket != -1:
            # Likely an array
            if last_bracket != -1 and last_bracket > first_bracket:
                extracted_json = raw_llm_text[first_bracket:last_bracket + 1]
                logger.info(f"🔄 [{function_name}] Extracted array JSON by brackets")
            else:
                raise ValueError("No valid array closing bracket found")
        else:
            raise ValueError("No JSON object or array boundaries found")
        
        result = json.loads(extracted_json)
        logger.info(f"✅ [{function_name}] Bracket extraction successful")
        
        # Validate expected keys
        if expected_keys and isinstance(result, dict):
            missing_keys = [key for key in expected_keys if key not in result]
            if missing_keys:
                logger.warning(f"⚠️ [{function_name}] Missing expected keys: {missing_keys}")
        
        return result
        
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"❌ [{function_name}] Bracket extraction failed: {str(e)}")
    
    # Strategy 4: Try to clean common issues and parse again
    try:
        # Remove common text patterns that might prefix/suffix JSON
        cleaned_text = raw_llm_text
        
        # Remove common prefixes
        prefixes_to_remove = [
            "Here's the JSON response:",
            "Here is the JSON:",
            "JSON response:",
            "Response:",
            "Result:",
            "Output:",
        ]
        
        for prefix in prefixes_to_remove:
            if cleaned_text.strip().startswith(prefix):
                cleaned_text = cleaned_text.strip()[len(prefix):].strip()
                break
        
        # Remove common suffixes
        suffixes_to_remove = [
            "That's the complete analysis.",
            "This completes the analysis.",
            "End of analysis.",
        ]
        
        for suffix in suffixes_to_remove:
            if cleaned_text.strip().endswith(suffix):
                cleaned_text = cleaned_text.strip()[:-len(suffix)].strip()
                break
        
        result = json.loads(cleaned_text)
        logger.info(f"✅ [{function_name}] Text cleaning strategy successful")
        
        # Validate expected keys
        if expected_keys and isinstance(result, dict):
            missing_keys = [key for key in expected_keys if key not in result]
            if missing_keys:
                logger.warning(f"⚠️ [{function_name}] Missing expected keys: {missing_keys}")
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ [{function_name}] Text cleaning strategy failed: {str(e)}")
    
    # All strategies failed - log detailed error information
    logger.error(f"❌ [{function_name}] ALL JSON parsing strategies failed!")
    logger.error(f"❌ [{function_name}] Original response length: {len(original_text)} characters")
    logger.error(f"❌ [{function_name}] First 200 chars: {repr(original_text[:200])}")
    logger.error(f"❌ [{function_name}] Last 200 chars: {repr(original_text[-200:])}")
    
    # Log response patterns for debugging
    has_braces = '{' in original_text and '}' in original_text
    has_brackets = '[' in original_text and ']' in original_text
    has_quotes = '"' in original_text
    has_markdown = '```' in original_text
    
    logger.error(f"❌ [{function_name}] Response analysis: braces={has_braces}, brackets={has_brackets}, quotes={has_quotes}, markdown={has_markdown}")
    
    return None


def validate_json_structure(
    parsed_json: Union[Dict, List], 
    required_keys: List[str],
    function_name: str = "unknown"
) -> bool:
    """
    Validate that parsed JSON has required structure.
    
    Args:
        parsed_json: The parsed JSON object
        required_keys: List of required top-level keys
        function_name: Name of calling function for logging
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(parsed_json, dict):
        logger.error(f"❌ [{function_name}] Expected dict but got {type(parsed_json)}")
        return False
    
    missing_keys = [key for key in required_keys if key not in parsed_json]
    
    if missing_keys:
        logger.error(f"❌ [{function_name}] Missing required keys: {missing_keys}")
        logger.error(f"❌ [{function_name}] Available keys: {list(parsed_json.keys())}")
        return False
    
    logger.info(f"✅ [{function_name}] JSON structure validation passed")
    return True


def safe_get_nested_value(
    data: Dict, 
    key_path: str, 
    default: Any = None,
    function_name: str = "unknown"
) -> Any:
    """
    Safely get nested values from parsed JSON with logging.
    
    Args:
        data: Parsed JSON dictionary
        key_path: Dot-separated key path (e.g., "restaurant_info.name")
        default: Default value if key path not found
        function_name: Name of calling function for logging
        
    Returns:
        Value at key path or default
    """
    try:
        keys = key_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                logger.warning(f"⚠️ [{function_name}] Key path '{key_path}' not found, using default: {default}")
                return default
        
        logger.debug(f"🔍 [{function_name}] Retrieved '{key_path}': {repr(current)}")
        return current
        
    except Exception as e:
        logger.error(f"❌ [{function_name}] Error retrieving key path '{key_path}': {str(e)}")
        return default


def log_json_parsing_attempt(
    function_name: str,
    prompt_snippet: str,
    response_length: int,
    success: bool,
    error_msg: str = None
) -> None:
    """
    Log JSON parsing attempts for monitoring and debugging.
    
    Args:
        function_name: Name of the function attempting parsing
        prompt_snippet: First 100 chars of the prompt sent to LLM
        response_length: Length of LLM response
        success: Whether parsing was successful
        error_msg: Error message if parsing failed
    """
    status = "✅ SUCCESS" if success else "❌ FAILED"
    logger.info(f"📊 JSON_PARSE_LOG: {status} | Function: {function_name} | Response: {response_length} chars")
    logger.debug(f"📊 JSON_PARSE_LOG: Prompt snippet: {repr(prompt_snippet[:100])}")
    
    if not success and error_msg:
        logger.error(f"📊 JSON_PARSE_LOG: Error: {error_msg}") 
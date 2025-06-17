"""
Scoring utilities for long answer questions.
Handles keyword-based scoring algorithms and manual review helpers.
"""

import json
import re
from typing import List, Dict, Optional, Tuple
from enum import Enum


class KeywordMatchType(str, Enum):
    """Types of keyword matching"""
    EXACT = "exact"
    PARTIAL = "partial"
    FUZZY = "fuzzy"


class ScoringResult:
    """Result of keyword-based scoring"""
    def __init__(self, score: float, max_score: float, found_keywords: List[str], 
                 missing_keywords: List[str], match_details: Dict[str, any]):
        self.score = score
        self.max_score = max_score
        self.found_keywords = found_keywords
        self.missing_keywords = missing_keywords
        self.match_details = match_details
        self.percentage = (score / max_score * 100) if max_score > 0 else 0


def normalize_text(text: str) -> str:
    """
    Normalize text for keyword matching.
    
    Args:
        text: Input text to normalize
        
    Returns:
        Normalized text (lowercase, cleaned)
    """
    if not text:
        return ""
    
    # Convert to lowercase and remove extra whitespace
    normalized = re.sub(r'\s+', ' ', text.lower().strip())
    
    # Remove common punctuation but keep meaningful characters
    normalized = re.sub(r'[^\w\s\-]', ' ', normalized)
    
    return normalized


def extract_keywords_from_text(text: str, keywords: List[str], 
                              match_type: KeywordMatchType = KeywordMatchType.EXACT) -> Tuple[List[str], Dict[str, any]]:
    """
    Extract found keywords from text.
    
    Args:
        text: Text to search in
        keywords: List of keywords to find
        match_type: Type of matching to perform
        
    Returns:
        Tuple of (found_keywords, match_details)
    """
    if not text or not keywords:
        return [], {}
    
    normalized_text = normalize_text(text)
    found_keywords = []
    match_details = {}
    
    for keyword in keywords:
        normalized_keyword = normalize_text(keyword)
        
        if not normalized_keyword:
            continue
            
        found = False
        match_info = {
            "keyword": keyword,
            "found": False,
            "match_type": match_type.value,
            "positions": []
        }
        
        if match_type == KeywordMatchType.EXACT:
            # Exact word boundary matching
            pattern = r'\b' + re.escape(normalized_keyword) + r'\b'
            matches = list(re.finditer(pattern, normalized_text))
            if matches:
                found = True
                match_info["positions"] = [m.start() for m in matches]
                
        elif match_type == KeywordMatchType.PARTIAL:
            # Partial matching (keyword appears anywhere)
            if normalized_keyword in normalized_text:
                found = True
                start = 0
                while True:
                    pos = normalized_text.find(normalized_keyword, start)
                    if pos == -1:
                        break
                    match_info["positions"].append(pos)
                    start = pos + 1
                    
        elif match_type == KeywordMatchType.FUZZY:
            # Simple fuzzy matching (for future enhancement)
            # For now, fall back to partial matching
            if normalized_keyword in normalized_text:
                found = True
                match_info["positions"] = [normalized_text.find(normalized_keyword)]
        
        match_info["found"] = found
        match_details[keyword] = match_info
        
        if found:
            found_keywords.append(keyword)
    
    return found_keywords, match_details


def calculate_keyword_score(student_answer: str, keywords_json: str, max_score: float,
                          essential_weight: float = 0.8, bonus_weight: float = 0.2) -> ScoringResult:
    """
    Calculate score based on keyword matching.
    
    Args:
        student_answer: Student's text answer
        keywords_json: JSON string containing keywords configuration
        max_score: Maximum possible score for this question
        essential_weight: Weight for essential keywords (0.8 = 80% of score)
        bonus_weight: Weight for bonus keywords (0.2 = 20% of score)
        
    Returns:
        ScoringResult object with detailed scoring information
    """
    if not student_answer or not keywords_json:
        return ScoringResult(0.0, max_score, [], [], {})
    
    try:
        # Parse keywords configuration
        if isinstance(keywords_json, str):
            keywords_config = json.loads(keywords_json)
        else:
            keywords_config = keywords_json
            
        # Handle simple list format (backward compatibility)
        if isinstance(keywords_config, list):
            keywords_config = {
                "essential": keywords_config,
                "bonus": []
            }
            
        essential_keywords = keywords_config.get("essential", keywords_config.get("keywords", []))
        bonus_keywords = keywords_config.get("bonus", [])
        
    except (json.JSONDecodeError, TypeError):
        # Fallback: treat as comma-separated string
        keyword_list = [k.strip() for k in str(keywords_json).split(',') if k.strip()]
        essential_keywords = keyword_list
        bonus_keywords = []
    
    # Find keywords in student answer
    found_essential, essential_details = extract_keywords_from_text(
        student_answer, essential_keywords, KeywordMatchType.PARTIAL
    )
    found_bonus, bonus_details = extract_keywords_from_text(
        student_answer, bonus_keywords, KeywordMatchType.PARTIAL
    )
    
    # Calculate scores
    essential_score = 0.0
    if essential_keywords:
        essential_percentage = len(found_essential) / len(essential_keywords)
        essential_score = essential_percentage * max_score * essential_weight
    
    bonus_score = 0.0
    if bonus_keywords:
        bonus_percentage = len(found_bonus) / len(bonus_keywords)
        bonus_score = bonus_percentage * max_score * bonus_weight
    
    total_score = min(essential_score + bonus_score, max_score)
    
    # Combine results
    all_found = found_essential + found_bonus
    all_keywords = essential_keywords + bonus_keywords
    missing_keywords = [k for k in all_keywords if k not in all_found]
    
    match_details = {
        "essential": essential_details,
        "bonus": bonus_details,
        "scoring": {
            "essential_found": len(found_essential),
            "essential_total": len(essential_keywords),
            "bonus_found": len(found_bonus),
            "bonus_total": len(bonus_keywords),
            "essential_score": essential_score,
            "bonus_score": bonus_score,
            "total_score": total_score
        }
    }
    
    return ScoringResult(
        score=round(total_score, 2),
        max_score=max_score,
        found_keywords=all_found,
        missing_keywords=missing_keywords,
        match_details=match_details
    )


def validate_keyword_configuration(keywords_json: str) -> Tuple[bool, str]:
    """
    Validate keyword configuration format.
    
    Args:
        keywords_json: JSON string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not keywords_json:
        return False, "Keywords configuration is required"
    
    try:
        if isinstance(keywords_json, str):
            config = json.loads(keywords_json)
        else:
            config = keywords_json
            
        # Accept simple list format
        if isinstance(config, list):
            if not config:
                return False, "At least one keyword is required"
            return True, ""
            
        # Accept object format
        if isinstance(config, dict):
            essential = config.get("essential", config.get("keywords", []))
            bonus = config.get("bonus", [])
            
            if not essential and not bonus:
                return False, "At least one essential or bonus keyword is required"
                
            return True, ""
            
        return False, "Keywords must be a list or object"
        
    except json.JSONDecodeError:
        # Try as comma-separated string
        keyword_list = [k.strip() for k in str(keywords_json).split(',') if k.strip()]
        if not keyword_list:
            return False, "No valid keywords found"
        return True, ""
    except Exception as e:
        return False, f"Invalid keyword configuration: {str(e)}"


# Backward compatibility function
def simple_keyword_score(student_answer: str, keywords: List[str], max_score: float) -> float:
    """
    Simple keyword scoring for backward compatibility.
    
    Args:
        student_answer: Student's answer
        keywords: List of keywords to find
        max_score: Maximum score possible
        
    Returns:
        Calculated score
    """
    if not student_answer or not keywords:
        return 0.0
        
    found_keywords, _ = extract_keywords_from_text(student_answer, keywords)
    percentage = len(found_keywords) / len(keywords)
    return round(percentage * max_score, 2) 
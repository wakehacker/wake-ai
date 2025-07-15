"""YAML validator for AI detector findings."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False

import yaml


FINDING_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "AI Detector Finding Schema",
    "type": "object",
    "required": ["contract_name", "start_line", "message", "impact", "confidence"],
    "properties": {
        "contract_name": {
            "type": "string",
            "description": "Contract containing the issue"
        },
        "start_line": {
            "type": "integer",
            "description": "Starting line number of the issue",
            "minimum": 1
        },
        "end_line": {
            "type": "integer",
            "description": "Ending line number (optional, defaults to start_line)",
            "minimum": 1
        },
        "message": {
            "type": "string",
            "description": "Brief description of the vulnerability",
            "minLength": 10
        },
        "impact": {
            "type": "string",
            "enum": ["info", "warning", "low", "medium", "high"]
        },
        "confidence": {
            "type": "string",
            "enum": ["low", "medium", "high"]
        },
        "subdetections": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["contract_name", "start_line", "message"],
                "properties": {
                    "contract_name": {
                        "type": "string"
                    },
                    "start_line": {
                        "type": "integer",
                        "minimum": 1
                    },
                    "end_line": {
                        "type": "integer",
                        "minimum": 1
                    },
                    "message": {
                        "type": "string",
                        "minLength": 5
                    }
                }
            }
        }
    }
}


def validate_finding(finding_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate a single finding against the schema.
    
    Args:
        finding_data: Dictionary containing finding data
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not JSONSCHEMA_AVAILABLE:
        # Basic validation without jsonschema
        required_fields = ["contract_name", "start_line", "message", "impact", "confidence"]
        for field in required_fields:
            if field not in finding_data:
                return False, f"Missing required field: {field}"
        
        # Check impact and confidence values
        valid_impacts = ["info", "warning", "low", "medium", "high"]
        valid_confidences = ["low", "medium", "high"]
        
        if finding_data["impact"] not in valid_impacts:
            return False, f"Invalid impact: {finding_data['impact']}"
        if finding_data["confidence"] not in valid_confidences:
            return False, f"Invalid confidence: {finding_data['confidence']}"
        
        # Check line numbers
        if not isinstance(finding_data["start_line"], int) or finding_data["start_line"] < 1:
            return False, "start_line must be a positive integer"
        
        return True, None
    
    try:
        jsonschema.validate(finding_data, FINDING_SCHEMA)
        
        # Additional validation: end_line should be >= start_line
        if "end_line" in finding_data and finding_data["end_line"] < finding_data["start_line"]:
            return False, "end_line must be greater than or equal to start_line"
            
        # Validate subdetections have proper line numbers
        if "subdetections" in finding_data:
            for i, subdet in enumerate(finding_data["subdetections"]):
                if "end_line" in subdet and subdet["end_line"] < subdet["start_line"]:
                    return False, f"Subdetection {i}: end_line must be >= start_line"
                    
        return True, None
    except Exception as e:
        return False, str(e)


def validate_findings_file(file_path: Path) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """Validate a YAML findings file.
    
    Args:
        file_path: Path to YAML file
        
    Returns:
        Tuple of (is_valid, error_message, parsed_data)
    """
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            
        if data is None:
            return False, "Empty YAML file", None
            
        is_valid, error = validate_finding(data)
        if not is_valid:
            return False, error, None
            
        return True, None, data
        
    except yaml.YAMLError as e:
        return False, f"YAML parsing error: {e}", None
    except Exception as e:
        return False, f"Error reading file: {e}", None


def validate_all_findings(findings_dir: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Validate all YAML files in the findings directory.
    
    Args:
        findings_dir: Directory containing finding YAML files
        
    Returns:
        Tuple of (valid_findings, errors)
    """
    valid_findings = []
    errors = []
    
    if not findings_dir.exists():
        errors.append(f"Findings directory does not exist: {findings_dir}")
        return valid_findings, errors
        
    # Find all YAML files
    yaml_files = sorted(findings_dir.glob("finding-*.yaml"))
    
    if not yaml_files:
        errors.append(f"No finding files found in {findings_dir}")
        return valid_findings, errors
        
    for yaml_file in yaml_files:
        is_valid, error, data = validate_findings_file(yaml_file)
        if is_valid and data:
            valid_findings.append(data)
        else:
            errors.append(f"{yaml_file.name}: {error}")
            
    return valid_findings, errors
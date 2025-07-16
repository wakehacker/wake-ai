"""AI-powered detectors for Wake."""

# Import all AI detectors to register them
from .audit.detector import AIAuditDetector
from .detections.detector import AIDetector  
from .simple_detections.detector import SimpleAIDetector
from .test_detections.detector import TestDetector
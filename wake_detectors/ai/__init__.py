"""AI-powered detectors for Wake."""

# Import all AI detectors to register them
from .audit.detector import AuditDetector
from .detections.detector import DetectionsDetector  
from .simple_detections.detector import SimpleAIDetector
from .test_detections.detector import TestDetector
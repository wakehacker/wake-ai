"""Base class for AI-powered detectors."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from wake.detectors.api import Detector
from wake.ai.detector_result import AIDetectorResult

if TYPE_CHECKING:
    from pathlib import Path
    from wake.compiler.build_data_model import ProjectBuild, ProjectBuildInfo
    from wake.config import WakeConfig
    import networkx as nx


class AIDetector(Detector, ABC):
    """
    Base class for AI-powered detectors that return AIDetectorResult objects.
    
    This class extends the regular Detector but overrides the detect method
    to return AIDetectorResult objects instead of DetectorResult objects.
    """
    
    build: "ProjectBuild"
    build_info: "ProjectBuildInfo"
    config: "WakeConfig"
    paths: List["Path"]
    extra: Dict[Any, Any]
    imports_graph: "nx.DiGraph"
    
    @property
    def visit_mode(self) -> str:
        """AI detectors typically don't need to visit IR nodes."""
        return "paths"
    
    @abstractmethod
    def ai_detect(self) -> List[AIDetectorResult]:
        """
        Abstract method that must be implemented in an AI detector to return detections.
        
        Returns:
            List of AI detector results.
        """
        ...
    
    def detect(self) -> List[AIDetectorResult]:
        """
        Override the base detect method to return AIDetectorResult objects.
        
        This method simply calls ai_detect() to maintain compatibility with
        the base Detector interface while allowing AI detectors to return
        their specific result type.
        
        Returns:
            List of AI detector results.
        """
        return self.ai_detect()
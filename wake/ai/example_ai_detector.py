"""Example of using DetectorResultFactory for AI-based detections."""

from pathlib import Path
from typing import List

from wake.detectors.api import DetectorResult
from wake.ai.detector_result_mock import DetectorResultFactory, MockLocation


def create_ai_detector_results(build, ai_analysis_results: List[dict]) -> List[DetectorResult]:
    """
    Convert AI analysis results to DetectorResults.
    
    Example ai_analysis_results format:
    [
        {
            "contract_name": "MyToken",
            "start_line": 42,
            "end_line": 45,
            "message": "Potential reentrancy vulnerability in withdraw function",
            "impact": "high",
            "confidence": "medium",
            "uri": "https://example.com/reentrancy",
            "subdetections": [
                {
                    "contract_name": "MyToken",
                    "start_line": 43,
                    "message": "State change after external call"
                }
            ]
        }
    ]
    """
    factory = DetectorResultFactory(build)
    return factory.create_detector_results_batch(ai_analysis_results)


# Example usage in an AI workflow
def example_ai_detector_workflow(build):
    """Example workflow showing how to use the factory."""
    
    factory = DetectorResultFactory(build)
    
    # Example 1: Simple detection
    detection1 = factory.create_detector_result(
        location=MockLocation(
            contract_name="MyContract",
            start_line=10,
            end_line=15,
        ),
        message="Unchecked return value from external call",
        impact="medium",
        confidence="high",
    )
    
    # Example 2: Detection with subdetections
    detection2 = factory.create_detector_result(
        location=MockLocation(
            contract_name="TokenSale",
            start_line=50,
            end_line=60,
        ),
        message="Complex reentrancy pattern detected",
        impact="high",
        confidence="medium",
        subdetections=[
            (MockLocation("TokenSale", 52, 53), "External call to untrusted contract"),
            (MockLocation("TokenSale", 55, 56), "State modification after call"),
        ],
    )
    
    # Example 3: Batch creation from AI analysis output
    ai_results = [
        {
            "contract_name": "Vault",
            "start_line": 100,
            "end_line": 120,
            "message": "Missing access control on critical function",
            "impact": "high",
            "confidence": "high",
            "uri": "https://docs.example.com/access-control",
        },
        {
            "contract_name": "Vault", 
            "start_line": 150,
            "message": "Integer overflow possibility",
            "impact": "medium",
            "confidence": "low",
        },
    ]
    
    batch_results = factory.create_detector_results_batch(ai_results)
    
    return [detection1, detection2] + batch_results


# Integration with AI workflow
class AIDetectorIntegration:
    """Example integration with AI workflow."""
    
    def __init__(self, build):
        self.factory = DetectorResultFactory(build)
    
    def parse_ai_output(self, ai_response: str) -> List[dict]:
        """
        Parse AI response into structured format.
        This would contain logic to extract contract names, line numbers,
        and vulnerability information from the AI's text output.
        """
        # Implementation would parse AI response and extract:
        # - Contract names mentioned
        # - Line numbers or code snippets
        # - Vulnerability descriptions
        # - Severity assessments
        # And convert them to the expected dictionary format
        pass
    
    def create_detections_from_ai(self, ai_response: str) -> List[DetectorResult]:
        """Convert AI analysis to DetectorResults."""
        parsed_results = self.parse_ai_output(ai_response)
        return self.factory.create_detector_results_batch(parsed_results)
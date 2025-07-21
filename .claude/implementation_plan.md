# Implementation Plan for AI Detector Results

## Summary

We've created a new detector result hierarchy under `wake/ai/` that allows AI detectors to return structured results without requiring IR nodes. This provides flexibility for AI-driven detectors that analyze code at a higher level.

## Created Files

### 1. `wake/ai/detector_result.py`
- **AILocation**: Location info without IR dependency (target, file path, line numbers, etc.)
- **AIDetection**: Detection with name, location, detection text, recommendation, exploit
- **AIDetectorResult**: Main result class with severity, detection type, and metadata
- **print_ai_detection()**: Console printing function for AI results
- **export_ai_detections_json()**: JSON export function

### 2. `wake/ai/detector.py`
- **AIDetector**: Base class for AI detectors that return AIDetectorResult
- Inherits from regular Detector but overrides detect() to return AI results

### 3. `wake/cli/detect_ai_handler.py`
- Helper functions to integrate AI results with existing CLI
- **get_detection_sort_key()**: Unified sorting for mixed result types
- **print_mixed_detection()**: Prints either type of result
- **process_ai_detection_for_json()**: Converts AI results to compatible JSON format

## Integration Points

### 1. Detect CLI (`wake/cli/detect.py`)
Need to update:
- Import AI types and handler functions
- Modify type hints to accept Union[DetectorResult, AIDetectorResult]
- Replace sorting logic with get_detection_sort_key()
- Replace print_detection calls with print_mixed_detection()
- Update JSON export to handle both types

### 2. Detector Collection (`wake/detectors/api.py`)
The detect() function currently filters DetectorResult objects. Options:
- Create a separate AI detector collection flow
- Update _filter_detections to handle AI results
- Or bypass filtering for AI detectors

### 3. SARIF Export (`wake/detectors/utils.py`)
May need updates to handle AIDetectorResult in create_sarif_log()

## Usage Example

```python
from wake.ai import AIDetector, AIDetectorResult, AIDetection, AILocation, AISeverity

class MyAIDetector(AIDetector):
    def ai_detect(self) -> List[AIDetectorResult]:
        # AI analysis logic here
        
        location = AILocation(
            target="MyContract.transfer",
            file_path=Path("contracts/MyContract.sol"),
            start_line=42,
            end_line=45,
            source_snippet="function transfer() { ... }"
        )
        
        detection = AIDetection(
            name="Potential Reentrancy Vulnerability",
            location=location,
            detection="The transfer function calls external contracts...",
            recommendation="Add reentrancy guard",
            exploit="An attacker could call back into..."
        )
        
        return [AIDetectorResult(
            detection=detection,
            severity=AISeverity.HIGH,
            detection_type="vulnerability",
            uri="https://example.com/reentrancy"
        )]
```

## Benefits

1. **No IR Dependency**: AI detectors don't need to create mock IR nodes
2. **Structured Output**: Clear fields for detection, recommendation, exploit
3. **Flexible Severity**: Single severity field instead of impact+confidence
4. **Better Semantics**: detection_type field for categorization
5. **Future-Proof**: Can extend with more fields as needed

## Next Steps

1. Update wake/cli/detect.py to use the handler functions
2. Test with actual AI detector implementations
3. Update documentation
4. Consider SARIF export compatibility
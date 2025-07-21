# Detect.py Update Plan

## Changes needed to support AIDetectorResult

### 1. Import Changes
Add imports for AI detector types:
```python
from wake.ai import AIDetectorResult, print_ai_detection
```

### 2. Type Updates
Update type hints to support both result types:
```python
all_detections: List[Tuple[str, Union[DetectorResult, AIDetectorResult]]] = []
```

### 3. Sorting Logic
The current sorting logic assumes DetectorResult with ir_node. Need to handle AIDetectorResult:
```python
# Current problematic code:
all_detections.sort(
    key=lambda d: (
        severity_map[d[1].impact][d[1].confidence],
        d[1].detection.ir_node.source_unit.source_unit_name,
        d[1].detection.ir_node.byte_location[0],
        d[1].detection.ir_node.byte_location[1],
    )
)
```

Need to create a sorting key function that handles both types.

### 4. Printing Logic
Current code calls `print_detection` for all results. Need to check type and call appropriate function:
```python
for detector_name, detection in all_detections:
    if isinstance(detection, AIDetectorResult):
        print_ai_detection(detector_name, detection, console, theme)
    else:
        print_detection(detector_name, detection, config, console, theme)
```

### 5. Export Logic
JSON export needs to handle both types:
- Check instance type
- Call appropriate serialization method
- Merge into unified export format

### 6. SARIF Export
May need updates to handle AIDetectorResult in create_sarif_log function.
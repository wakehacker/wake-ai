"""Mock classes for creating DetectorResults from contract names and line numbers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple, List
from unittest.mock import MagicMock

from wake.detectors.api import Detection, DetectorResult, DetectorImpact, DetectorConfidence

if TYPE_CHECKING:
    from wake.compiler.build_data_model import ProjectBuild
    from wake.ir import SourceUnit


@dataclass
class MockLocation:
    """Represents a location in source code by contract name and line numbers."""
    contract_name: str
    start_line: int
    end_line: Optional[int] = None
    file_path: Optional[Path] = None
    
    def __post_init__(self):
        if self.end_line is None:
            self.end_line = self.start_line


class MockIrNode:
    """Mock IrAbc node for creating detections without actual IR nodes."""
    
    def __init__(
        self,
        source_unit: SourceUnit,
        byte_location: Tuple[int, int],
        source: bytes = b"",
        contract_name: Optional[str] = None,
    ):
        self.source_unit = source_unit
        self.byte_location = byte_location
        self.source = source
        self.contract_name = contract_name
        self.parent = None
        
        # Mock other IrAbc attributes that might be accessed
        self.ast_node = MagicMock()
        self.ast_node.node_type = "MockNode"


class DetectorResultFactory:
    """Factory for creating DetectorResults from contract names and line numbers."""
    
    def __init__(self, build: ProjectBuild):
        self.build = build
        self._contract_to_source_unit: dict[str, List[SourceUnit]] = {}
        self._build_contract_index()
    
    def _build_contract_index(self):
        """Build an index mapping contract names to their source units."""
        from wake.ir import ContractDefinition
        
        for source_unit in self.build.source_units.values():
            for contract in source_unit.contracts:
                if contract.name not in self._contract_to_source_unit:
                    self._contract_to_source_unit[contract.name] = []
                self._contract_to_source_unit[contract.name].append(source_unit)
    
    def _find_source_unit(self, location: MockLocation) -> Optional[SourceUnit]:
        """Find the source unit containing the specified contract."""
        if location.file_path:
            # If file path is provided, use it directly
            for path, source_unit in self.build.source_units.items():
                if path == location.file_path:
                    return source_unit
        
        # Otherwise, search by contract name
        source_units = self._contract_to_source_unit.get(location.contract_name, [])
        if len(source_units) == 1:
            return source_units[0]
        elif len(source_units) > 1:
            # Multiple contracts with same name, need file path to disambiguate
            raise ValueError(
                f"Multiple contracts named '{location.contract_name}' found. "
                f"Please specify file_path to disambiguate."
            )
        return None
    
    def _lines_to_bytes(
        self, 
        source_unit: SourceUnit, 
        start_line: int, 
        end_line: int
    ) -> Tuple[int, int]:
        """Convert line numbers to byte offsets."""
        # Use SourceUnit's built-in method to get byte offset for start line
        # This will automatically build the lines index if needed
        start_byte = source_unit.get_line_col_from_byte_offset(0)[0]  # Trigger index build
        
        # Now access the _lines_index which should be built
        if not hasattr(source_unit, '_lines_index') or source_unit._lines_index is None:
            # Fallback: build index manually like SourceUnit does
            source_unit._lines_index = []
            prefix_sum = 0
            for line in source_unit._file_source.splitlines(keepends=True):
                source_unit._lines_index.append((line, prefix_sum))
                prefix_sum += len(line)
        
        lines_index = source_unit._lines_index
        
        # Line numbers are 1-based, convert to 0-based for indexing
        start_line_idx = start_line - 1
        end_line_idx = end_line - 1
        
        if start_line_idx >= len(lines_index) or end_line_idx >= len(lines_index):
            raise ValueError(f"Line numbers out of range for {source_unit.source_unit_name}")
        
        # Get byte offset for start of start_line
        start_byte = lines_index[start_line_idx][1]
        
        # Get byte offset for end of end_line
        if end_line_idx + 1 < len(lines_index):
            # Not the last line, use start of next line minus 1
            end_byte = lines_index[end_line_idx + 1][1] - 1
        else:
            # Last line, use end of file
            end_byte = len(source_unit._file_source)
        
        return (start_byte, end_byte)
    
    def create_detection(
        self,
        location: MockLocation,
        message: str,
        subdetections: Tuple[Detection, ...] = tuple(),
        lsp_range: Optional[Tuple[int, int]] = None,
        subdetections_mandatory: bool = True,
    ) -> Detection:
        """Create a Detection from a MockLocation."""
        source_unit = self._find_source_unit(location)
        if source_unit is None:
            raise ValueError(
                f"Could not find source unit for contract '{location.contract_name}'"
            )
        
        byte_location = self._lines_to_bytes(
            source_unit, 
            location.start_line, 
            location.end_line
        )
        
        # Extract source code for the range
        source = source_unit.source[byte_location[0]:byte_location[1]]
        
        mock_node = MockIrNode(
            source_unit=source_unit,
            byte_location=byte_location,
            source=source,
            contract_name=location.contract_name,
        )
        
        return Detection(
            ir_node=mock_node,
            message=message,
            subdetections=subdetections,
            lsp_range=lsp_range or byte_location,
            subdetections_mandatory=subdetections_mandatory,
        )
    
    def create_detector_result(
        self,
        location: MockLocation,
        message: str,
        impact: DetectorImpact,
        confidence: DetectorConfidence,
        subdetections: List[Tuple[MockLocation, str]] = None,
        uri: Optional[str] = None,
    ) -> DetectorResult:
        """Create a DetectorResult from MockLocation and metadata."""
        # Create main detection
        sub_detections = tuple()
        if subdetections:
            sub_detections = tuple(
                self.create_detection(sub_loc, sub_msg)
                for sub_loc, sub_msg in subdetections
            )
        
        detection = self.create_detection(
            location=location,
            message=message,
            subdetections=sub_detections,
        )
        
        return DetectorResult(
            detection=detection,
            impact=impact,
            confidence=confidence,
            uri=uri,
        )
    
    def create_detector_results_batch(
        self,
        results: List[dict],
    ) -> List[DetectorResult]:
        """
        Create multiple DetectorResults from a list of dictionaries.
        
        Each dictionary should have:
        - contract_name: str
        - start_line: int
        - end_line: Optional[int]
        - file_path: Optional[Path]
        - message: str
        - impact: str (one of: "info", "warning", "low", "medium", "high")
        - confidence: str (one of: "low", "medium", "high")
        - subdetections: Optional[List[dict]] (same format without impact/confidence)
        - uri: Optional[str]
        """
        detector_results = []
        
        for result in results:
            location = MockLocation(
                contract_name=result["contract_name"],
                start_line=result["start_line"],
                end_line=result.get("end_line"),
                file_path=result.get("file_path"),
            )
            
            subdetections = []
            if "subdetections" in result:
                for sub in result["subdetections"]:
                    sub_location = MockLocation(
                        contract_name=sub["contract_name"],
                        start_line=sub["start_line"],
                        end_line=sub.get("end_line"),
                        file_path=sub.get("file_path"),
                    )
                    subdetections.append((sub_location, sub["message"]))
            
            detector_result = self.create_detector_result(
                location=location,
                message=result["message"],
                impact=DetectorImpact(result["impact"]),
                confidence=DetectorConfidence(result["confidence"]),
                subdetections=subdetections,
                uri=result.get("uri"),
            )
            detector_results.append(detector_result)
        
        return detector_results
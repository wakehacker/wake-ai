"""Common utilities used across Wake AI."""

import enum
import sys


# Python version compatibility for StrEnum
if sys.version_info < (3, 11):
    class StrEnum(str, enum.Enum):
        """String enumeration for Python < 3.11 compatibility."""
        pass
else:
    class StrEnum(enum.StrEnum):
        """String enumeration using native StrEnum for Python >= 3.11."""
        pass
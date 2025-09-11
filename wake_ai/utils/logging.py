import logging
from typing import Optional

_debug: bool = False
_created_logger_names: set[str] = set()
_verbose_filters: Optional[set[str]] = None


def get_logger(name: str, override_level: Optional[int] = None) -> logging.Logger:
    logger = logging.getLogger(name)

    if override_level is not None:
        logger.setLevel(override_level)
    else:
        _created_logger_names.add(name)
        logger.setLevel(logging.DEBUG if _debug else logging.INFO)
    return logger


def set_debug(debug: bool) -> None:
    global _debug
    _debug = debug
    for name in _created_logger_names:
        get_logger(name).setLevel(logging.DEBUG if _debug else logging.INFO)


def get_debug() -> bool:
    return _debug


def set_verbose_filters(filters: Optional[str]) -> None:
    """Set verbose filters from comma-separated string."""
    global _verbose_filters
    if filters:
        _verbose_filters = {f.strip() for f in filters.split(',')}
    else:
        _verbose_filters = None


def should_show_tool(tool_name: str) -> bool:
    """Check if a tool should be shown based on filters."""
    if _verbose_filters is None:
        return True  # No filter = show everything

    # Direct match (e.g., "Bash", "Edit", "mcp__wake__analyze_state_variables")
    if tool_name in _verbose_filters:
        return True

    # For MCP tools, also check if the server name matches
    # e.g., "mcp__wake" filter will match "mcp__wake__analyze_state_variables"
    if tool_name.startswith("mcp__"):
        for filter_name in _verbose_filters:
            if filter_name.startswith("mcp__") and tool_name.startswith(filter_name + "__"):
                return True

    return False

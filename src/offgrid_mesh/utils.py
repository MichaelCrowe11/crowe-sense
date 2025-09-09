# SPDX-License-Identifier: MIT
# OffGrid Mesh — BLE Transport (discovery) with rotating ephemeral IDs (v2)
"""
Utility functions and logging setup for OffGrid Mesh Network
"""

import logging
import sys
from typing import Optional


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """
    Set up logging for the mesh network.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger("offgrid_mesh")
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def bytes_to_hex(data: bytes, separator: str = "", uppercase: bool = False) -> str:
    """
    Convert bytes to hex string with optional separator.
    
    Args:
        data: Bytes to convert
        separator: Optional separator between hex pairs
        uppercase: Whether to use uppercase hex
        
    Returns:
        Hex string representation
    """
    hex_str = data.hex()
    if uppercase:
        hex_str = hex_str.upper()
    
    if separator:
        # Add separator every 2 characters
        hex_str = separator.join(hex_str[i:i+2] for i in range(0, len(hex_str), 2))
    
    return hex_str


def hex_to_bytes(hex_str: str) -> bytes:
    """
    Convert hex string to bytes, handling separators.
    
    Args:
        hex_str: Hex string (with or without separators)
        
    Returns:
        Bytes object
    """
    # Remove common separators
    clean_hex = hex_str.replace(":", "").replace("-", "").replace(" ", "")
    return bytes.fromhex(clean_hex)


def truncate_hex(hex_str: str, length: int = 8) -> str:
    """
    Truncate a hex string to specified length with ellipsis.
    
    Args:
        hex_str: Hex string to truncate
        length: Maximum length
        
    Returns:
        Truncated hex string with ellipsis if needed
    """
    if len(hex_str) <= length:
        return hex_str
    return hex_str[:length] + "..."


class MeshNetworkError(Exception):
    """Base exception for mesh network errors."""
    pass


class EphemeralIDError(MeshNetworkError):
    """Errors related to ephemeral ID management."""
    pass


class BLETransportError(MeshNetworkError):
    """Errors related to BLE transport."""
    pass


class MeshRoutingError(MeshNetworkError):
    """Errors related to mesh routing."""
    pass
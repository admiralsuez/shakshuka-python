"""Disk space monitoring and management utilities

This module provides utilities for detecting and handling low disk space conditions
to prevent SQLite transaction hangs when the disk is full.
"""

import logging
import shutil
from typing import Dict

logger = logging.getLogger(__name__)


class DiskSpaceError(Exception):
    """Raised when disk space is critically low"""

    pass


def get_disk_info(path: str = "/") -> Dict[str, float]:
    """Get disk usage information for a path

    Args:
        path: Path to check (default is root directory)

    Returns:
        Dictionary with:
        - total_bytes: Total disk space in bytes
        - used_bytes: Used disk space in bytes
        - free_bytes: Free disk space in bytes
        - percent_used: Percentage used (0-100)
        - percent_free: Percentage free (0-100)

    Raises:
        Exception: If unable to determine disk usage
    """
    try:
        stat = shutil.disk_usage(path)
        total = stat.total
        used = stat.used
        free = stat.free
        percent_used = (used / total * 100) if total > 0 else 0

        return {
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "percent_used": percent_used,
            "percent_free": 100 - percent_used,
        }
    except Exception as e:
        logger.exception("Failed to get disk info for %s", path)
        raise


def is_disk_full(path: str = "/", threshold_percent: float = 90.0) -> bool:
    """Check if disk usage exceeds threshold

    Args:
        path: Path to check (default is root)
        threshold_percent: Alert threshold as percentage (default 90%)

    Returns:
        True if disk usage > threshold, False otherwise
    """
    try:
        info = get_disk_info(path)
        is_full = info["percent_used"] > threshold_percent
        if is_full:
            logger.warning(
                "Disk usage high: %.1f%% (threshold: %.1f%%) free: %.2f GB",
                info["percent_used"],
                threshold_percent,
                info["free_bytes"] / (1024**3),
            )
        return is_full
    except Exception as e:
        logger.warning("Could not check if disk is full: %s", e)
        # Default to NOT full if we can't determine (fail open)
        return False


def get_free_space_mb(path: str = "/") -> float:
    """Get available disk space in MB

    Args:
        path: Path to check (default is root)

    Returns:
        Free space in megabytes
    """
    try:
        info = get_disk_info(path)
        return info["free_bytes"] / (1024 * 1024)
    except Exception as e:
        logger.warning("Could not get free disk space: %s", e)
        # Return a safe default (assume plenty of space on error)
        return 1000.0


def is_critical_low_disk(path: str = "/", threshold_mb: float = 100.0) -> bool:
    """Check if disk space is critically low (absolute minimum)

    Args:
        path: Path to check (default is root)
        threshold_mb: Minimum required free space in MB (default 100 MB)

    Returns:
        True if free space < threshold_mb, False otherwise
    """
    free_mb = get_free_space_mb(path)
    is_critical = free_mb < threshold_mb
    if is_critical:
        logger.error(
            "CRITICAL: Disk space very low: %.2f MB free (threshold: %.2f MB)",
            free_mb,
            threshold_mb,
        )
    return is_critical


def require_minimum_disk_space(path: str = "/", min_free_mb: float = 50.0) -> None:
    """Require minimum disk space or raise error

    Args:
        path: Path to check (default is root)
        min_free_mb: Minimum required free space in MB (default 50 MB)

    Raises:
        DiskSpaceError: If insufficient space
    """
    free_mb = get_free_space_mb(path)
    if free_mb < min_free_mb:
        raise DiskSpaceError(
            f"Insufficient disk space: {free_mb:.1f} MB free, "
            f"{min_free_mb:.1f} MB required"
        )


def get_disk_usage_summary(path: str = "/") -> str:
    """Get a human-readable disk usage summary

    Args:
        path: Path to check

    Returns:
        Formatted string with disk usage information
    """
    try:
        info = get_disk_info(path)
        total_gb = info["total_bytes"] / (1024**3)
        used_gb = info["used_bytes"] / (1024**3)
        free_gb = info["free_bytes"] / (1024**3)
        percent = info["percent_used"]

        return (
            f"Disk: {used_gb:.1f}GB / {total_gb:.1f}GB "
            f"({percent:.1f}% used, {free_gb:.1f}GB free)"
        )
    except Exception as e:
        logger.warning("Could not create disk usage summary: %s", e)
        return "Disk usage unavailable"

"""Build system modules for Shakshuka"""

from .version import get_version_info, bump_version_two_part, increment_build_number
from .executable import build_executable, cleanup_build_files, install_dependencies
from .installer import find_inno_setup, build_installer, update_installer_script
from .report import generate_build_report, update_changelog

__all__ = [
    'get_version_info',
    'bump_version_two_part',
    'increment_build_number',
    'build_executable',
    'cleanup_build_files',
    'install_dependencies',
    'find_inno_setup',
    'build_installer',
    'update_installer_script',
    'generate_build_report',
    'update_changelog',
]

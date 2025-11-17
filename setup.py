#!/usr/bin/env python3
"""
Setup script for Shakshuka application.
Used by fpm to create Debian packages.
"""

from setuptools import setup, find_packages
import json
import os
import glob

# Read version from version.json
version_file = os.path.join(os.path.dirname(__file__), 'config', 'version.json')
version = "8.3"  # Default version

if os.path.exists(version_file):
    try:
        with open(version_file, 'r') as f:
            version_data = json.load(f)
            version = version_data.get('version', '8.3')
    except Exception:
        pass

# Read long description if available
long_description = "Shakshuka Task Manager - A modern task management application with web interface."

setup(
    name="shakshuka",
    version=version,
    description="Shakshuka application",
    long_description=long_description,
    author="Shakshuka Team",
    author_email="team@shakshuka.com",
    url="https://github.com/shakshuka/shakshuka",
    packages=find_packages(exclude=['tests', 'tests.*']),
    py_modules=['main'],  # Include main.py as a module
    include_package_data=True,
    package_data={
        '': [
            'assets/**/*',
            'assets/templates/**/*',
            'assets/static/**/*',
            'config/**/*',
            'config/*.json',
            'config/*.txt',
        ],
    },
    # Don't use data_files - use package_data instead
    # data_files=[
    #     ('share/shakshuka/assets', glob.glob('assets/**/*', recursive=True)),
    #     ('share/shakshuka/config', glob.glob('config/**/*', recursive=True)),
    # ] if os.path.exists('assets') else [],
    entry_points={
        'console_scripts': [
            'shakshuka=main:main',
        ],
    },
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)


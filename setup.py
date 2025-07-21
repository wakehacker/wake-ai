#!/usr/bin/env python3
"""Setup script for wake-ai package."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="wake-ai",
    version="0.1.0",
    description="AI-powered smart contract security analysis framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Ackee Blockchain",
    author_email="info@ackeeblockchain.com",
    url="https://github.com/Ackee-Blockchain/wake-ai",
    license="ISC",
    packages=find_packages(exclude=["tests", "tests.*"]),
    include_package_data=True,
    package_data={
        "flows": ["*/prompts/*.md"],
    },
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0",
        "rich>=13.3.2",
        "pyyaml>=6.0",
        "typing-extensions>=4.12; python_version<'3.10'",
    ],
    extras_require={
        "dev": [
            "black>=22.0",
            "isort>=5.0",
            "pytest>=7.0",
            "pytest-asyncio>=0.17",
            "mypy>=1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "wake-ai=wake_ai.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: ISC License (ISCL)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Security",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Testing",
    ],
    keywords="ethereum solidity security ai audit smart-contracts claude",
)
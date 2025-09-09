# SPDX-License-Identifier: MIT
# OffGrid Mesh — BLE Transport (discovery) with rotating ephemeral IDs (v2)

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="crowe-sense-offgrid-mesh",
    version="2.0.0",
    author="CroweSense Project",
    description="OffGrid Mesh — BLE Transport (discovery) with rotating ephemeral IDs (v2)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MichaelCrowe11/crowe-sense",
    project_urls={
        "Bug Tracker": "https://github.com/MichaelCrowe11/crowe-sense/issues",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers", 
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Communications",
        "Topic :: Internet", 
        "Topic :: System :: Networking",
        "Topic :: Security :: Cryptography",
    ],
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0", 
            "black>=22.0.0",
            "flake8>=5.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "offgrid-mesh=offgrid_mesh.cli:main",
        ],
    },
)
from setuptools import setup, find_packages
import pathlib

HERE = pathlib.Path(__file__).parent

# Read the contents of README file
README = (HERE / "README.md").read_text(encoding="utf-8")

# Get version from core/__init__.py or hardcode for now
VERSION = "2.0.0"

setup(
    name="product-forge",
    version=VERSION,
    description="Multi-Agent Multi-Project System - Product Forge",
    long_description=README,
    long_description_content_type="text/markdown",
    author="Product Forge Team",
    author_email="team@productforge.ai",
    url="https://github.com/productforge/productforge",
    license="MIT",
    python_requires=">=3.10",
    packages=find_packages(include=["core*", "pipeline_dashboard*"]),
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn>=0.24.0",
        "pydantic>=2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
            "mypy>=1.5.0",
        ],
        "pdf": [
            "weasyprint>=60.0",
            "playwright>=1.40.0",
        ],
        "all": [
            "weasyprint>=60.0",
            "playwright>=1.40.0",
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "productforge=core.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Documentation",
        "Topic :: Software Development :: Quality Assurance",
    ],
    project_urls={
        "Homepage": "https://github.com/productforge/productforge",
        "Repository": "https://github.com/productforge/productforge",
        "Documentation": "https://github.com/productforge/productforge/blob/main/README.md",
        "Issues": "https://github.com/productforge/productforge/issues",
    },
    include_package_data=True,
)
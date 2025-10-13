"""
Setup script for blockchain financial platform backend.
"""
from setuptools import setup, find_packages

setup(
    name="blockchain-financial-platform",
    version="0.1.0",
    description="Blockchain Financial Platform Backend",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "pydantic",
        "structlog",
        "tenacity",
        "pytest",
        "pytest-asyncio",
        "pytest-mock",
    ],
)
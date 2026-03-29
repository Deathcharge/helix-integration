from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="helix-integration",
    version="1.0.0",
    author="Helix Collective",
    author_email="dev@helix.collective",
    description="Unified orchestration across all components",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Deathcharge/helix-integration",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
    ],
    python_requires=">=3.9",
    keywords="integration,orchestration,unified,ecosystem",
)

"""Setup script for SynapticLlamas."""
from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

# Read requirements
requirements = (this_directory / "requirements.txt").read_text().splitlines()
dev_requirements = (this_directory / "requirements-dev.txt").read_text().splitlines()

setup(
    name="synaptic-llamas",
    version="0.1.0",
    author="BenevolentJoker-JohnL",
    author_email="benevolentjoker@gmail.com",
    description="Distributed Parallel AI Agent Orchestration with Intelligent Load Balancing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/BenevolentJoker-JohnL/SynapticLlamas",
    project_urls={
        "Bug Tracker": "https://github.com/BenevolentJoker-JohnL/SynapticLlamas/issues",
        "Documentation": "https://github.com/BenevolentJoker-JohnL/SynapticLlamas/blob/main/README.md",
        "Source Code": "https://github.com/BenevolentJoker-JohnL/SynapticLlamas",
    },
    packages=find_packages(exclude=["tests", "examples", "docs"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: System :: Distributed Computing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": dev_requirements,
    },
    entry_points={
        "console_scripts": [
            "synaptic-llamas=main:main",
        ],
    },
    include_package_data=True,
    keywords="ai llm distributed orchestration load-balancing ollama agents",
    zip_safe=False,
)

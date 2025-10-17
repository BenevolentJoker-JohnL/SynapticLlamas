"""Setup script for SOLLOL - Super Ollama Load Balancer."""
from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text() if (this_directory / "README.md").exists() else "SOLLOL - Super Ollama Load Balancer with Distributed Inference"

setup(
    name="sollol",
    version="0.3.0",
    author="BenevolentJoker-JohnL",
    author_email="benevolentjoker@gmail.com",
    description="Super Ollama Load Balancer with Intelligent Routing and Distributed Inference",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/BenevolentJoker-JohnL/SynapticLlamas",
    project_urls={
        "Bug Tracker": "https://github.com/BenevolentJoker-JohnL/SynapticLlamas/issues",
        "Documentation": "https://github.com/BenevolentJoker-JohnL/SynapticLlamas/blob/main/README.md",
        "Source Code": "https://github.com/BenevolentJoker-JohnL/SynapticLlamas",
    },
    packages=find_packages(where="."),
    classifiers=[
        "Development Status :: 4 - Beta",
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
    install_requires=[
        "requests>=2.31.0",
        "httpx>=0.24.0",
        "ipaddress>=1.0.23",
        "dask[distributed]>=2024.1.0",
        "rich>=13.7.0",
        "flask>=2.0.0",
        "flask-cors>=4.0.0",
        "flask-sock>=0.7.0",
        "waitress>=3.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=23.0.0",
            "isort>=5.0.0",
            "mypy>=1.0.0",
        ],
        "llama-cpp": [
            # Optional: for llama.cpp distributed inference
        ],
    },
    entry_points={
        "console_scripts": [
            "sollol=sollol.cli:main",
            "sollol-setup-llama-cpp=sollol.setup_llama_cpp:main",
        ],
    },
    py_modules=['setup_llama_cpp'],
    include_package_data=True,
    keywords="ai llm distributed ollama load-balancing inference llama-cpp distributed-inference",
    zip_safe=False,
)

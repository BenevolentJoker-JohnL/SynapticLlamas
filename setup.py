"""
Setup script for SynapticLlamas.

Distributed Parallel AI Agent Orchestration with Intelligent Load Balancing
Integrates with:
- FlockParser (>=1.0.4) for document RAG
- SOLLOL (>=0.9.31) for distributed inference and observability
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

# Read requirements
requirements = []
with open('requirements.txt', 'r') as f:
    for line in f:
        line = line.strip()
        # Skip comments and empty lines
        if line and not line.startswith('#'):
            requirements.append(line)

dev_requirements = []
if Path('requirements-dev.txt').exists():
    with open('requirements-dev.txt', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                dev_requirements.append(line)

setup(
    name="synaptic-llamas",
    version="0.1.0",
    author="BenevolentJoker-JohnL",
    author_email="benevolentjoker@gmail.com",
    description="Distributed Parallel AI Agent Orchestration with Intelligent Load Balancing - integrates with FlockParser for RAG and SOLLOL for distributed inference",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/BenevolentJoker-JohnL/SynapticLlamas",
    project_urls={
        "Bug Tracker": "https://github.com/BenevolentJoker-JohnL/SynapticLlamas/issues",
        "Documentation": "https://github.com/BenevolentJoker-JohnL/SynapticLlamas/blob/main/README.md",
        "Source Code": "https://github.com/BenevolentJoker-JohnL/SynapticLlamas",
        "FlockParser": "https://github.com/BenevolentJoker-JohnL/FlockParser",
        "SOLLOL": "https://github.com/BenevolentJoker-JohnL/SOLLOL",
    },
    packages=find_packages(exclude=["tests", "examples", "docs", "sollol_backup_20251005", "build"]),
    py_modules=[
        'main',
        'orchestrator',
        'collaborative_workflow',
        'json_pipeline',
        'quality_assurance',
        'aggregator',
        'config',
        'load_balancer',
        'adaptive_strategy',
        'input_validation',
        'error_handling',
        'sollol_adapter',
        'benchmark',
        'dask_executor',
        'content_detector',
        'node_cluster',
        'network_utils',
        'hybrid_router_sync',
        'node_registry',
        'json_to_markdown',
        'flockparser_adapter',
        'distributed_orchestrator',
        'console_theme',
        'ollama_node',
        'trustcall',
    ],
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
    package_data={
        '': ['*.md', '*.yaml', '*.yml', 'LICENSE', 'requirements.txt'],
    },
    keywords="ai llm distributed orchestration load-balancing ollama agents flockparser sollol rag multi-agent",
    zip_safe=False,
)

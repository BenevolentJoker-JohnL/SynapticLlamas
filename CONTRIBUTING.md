# Contributing to SynapticLlamas

Thank you for your interest in contributing to SynapticLlamas! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Adding New Agents](#adding-new-agents)
- [Reporting Bugs](#reporting-bugs)
- [Feature Requests](#feature-requests)

## Code of Conduct

This project adheres to a Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/SynapticLlamas.git
   cd SynapticLlamas
   ```
3. **Add the upstream repository**:
   ```bash
   git remote add upstream https://github.com/BenevolentJoker-JohnL/SynapticLlamas.git
   ```
4. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## How to Contribute

### Types of Contributions

We welcome contributions in several forms:

- **Bug fixes** - Fix issues in existing code
- **New features** - Add new functionality
- **New agents** - Create specialized agents for different tasks
- **Documentation** - Improve docs, add examples, fix typos
- **Tests** - Add unit tests, integration tests, or improve coverage
- **Performance** - Optimize existing code
- **Refactoring** - Improve code quality and structure

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Ollama installed and running locally
- Git

### Installation

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install development dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # Development tools
   ```

3. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_load_balancer.py

# Run tests in parallel
pytest -n auto
```

### Code Quality Checks

```bash
# Format code with black
black .

# Sort imports with isort
isort .

# Lint with flake8
flake8 .

# Type checking with mypy
mypy .

# Run all checks at once
./scripts/check.sh
```

## Coding Standards

### Python Style Guide

- Follow [PEP 8](https://peps.python.org/pep-0008/) style guide
- Use **black** for code formatting (line length: 100)
- Use **isort** for import sorting
- Use **type hints** (PEP 484) for all functions
- Write **docstrings** for all public modules, classes, and functions

### Code Organization

- Keep modules focused and cohesive
- Use clear, descriptive names for variables, functions, and classes
- Avoid deep nesting (max 3-4 levels)
- Extract complex logic into helper functions
- Keep functions under 50 lines when possible

### Documentation

- Add docstrings in Google style:
  ```python
  def function_name(param1: str, param2: int) -> bool:
      """
      Brief description of function.

      Longer description with more details about what the function does,
      edge cases, and important notes.

      Args:
          param1: Description of param1
          param2: Description of param2

      Returns:
          Description of return value

      Raises:
          ValueError: When invalid input is provided
          ConnectionError: When node is unreachable
      """
  ```

### Error Handling

- Use specific exception types
- Provide clear, actionable error messages
- Log errors with appropriate severity
- Fail gracefully when possible
- Clean up resources in `finally` blocks or use context managers

### Logging

- Use the `logging` module (not `print`)
- Choose appropriate log levels:
  - `DEBUG` - Detailed diagnostic information
  - `INFO` - General informational messages
  - `WARNING` - Warning messages for recoverable issues
  - `ERROR` - Error messages for failures
  - `CRITICAL` - Critical errors that may cause shutdown
- Include context in log messages

## Testing

### Writing Tests

- Write tests for all new features
- Aim for >80% code coverage
- Use descriptive test names: `test_<function_name>_<scenario>_<expected_result>`
- Use fixtures for common setup
- Mock external dependencies (Ollama API, network calls)

### Test Structure

```python
def test_load_balancer_selects_least_loaded_node():
    """Test that load balancer correctly selects node with lowest load."""
    # Arrange
    registry = NodeRegistry()
    node1 = OllamaNode("http://node1:11434")
    node1.metrics.total_requests = 10
    node2 = OllamaNode("http://node2:11434")
    node2.metrics.total_requests = 5
    registry.add_node(node1)
    registry.add_node(node2)
    balancer = OllamaLoadBalancer(registry, RoutingStrategy.LEAST_LOADED)

    # Act
    selected = balancer.get_node()

    # Assert
    assert selected == node2
    assert selected.metrics.total_requests == 5
```

## Submitting Changes

### Before Submitting

1. **Sync with upstream**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run tests**:
   ```bash
   pytest
   ```

3. **Run code quality checks**:
   ```bash
   black .
   isort .
   flake8 .
   mypy .
   ```

4. **Update documentation** if needed

5. **Commit your changes** with clear messages:
   ```bash
   git commit -m "Add feature: description of feature"
   ```

### Commit Message Guidelines

- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit first line to 72 characters
- Reference issues and pull requests when relevant
- Examples:
  - `Fix: Handle timeout errors in node discovery`
  - `Feature: Add circuit breaker for node failures`
  - `Docs: Update README with new CLI options`
  - `Test: Add integration tests for distributed mode`
  - `Refactor: Extract validation logic to separate module`

### Pull Request Process

1. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create a Pull Request** on GitHub:
   - Provide a clear title and description
   - Reference related issues
   - Describe what changed and why
   - Include screenshots for UI changes
   - List any breaking changes

3. **Address review feedback**:
   - Respond to comments
   - Make requested changes
   - Push updates to the same branch

4. **Merge requirements**:
   - All tests must pass
   - Code coverage must not decrease
   - At least one approval from maintainers
   - No merge conflicts

## Adding New Agents

To add a new agent to the system:

1. **Create agent file** in `agents/` directory:
   ```python
   # agents/summarizer.py
   from typing import Dict, Any
   from .base_agent import BaseAgent

   class Summarizer(BaseAgent):
       """
       Agent that summarizes text into concise bullet points.
       """

       def __init__(self, model: str = "llama3.2"):
           super().__init__("Summarizer", model)

       def process(self, input_data: str) -> Dict[str, Any]:
           """
           Summarize input text.

           Args:
               input_data: Text to summarize

           Returns:
               Standardized JSON output with summary
           """
           system_prompt = """You are a summarization agent.
           Extract key points and create a concise summary."""

           prompt = f"Summarize the following:\n\n{input_data}"

           return self.call_ollama(prompt, system_prompt)
   ```

2. **Register in orchestrator** (`orchestrator.py`):
   ```python
   from agents.summarizer import Summarizer

   agents = [
       Researcher(model),
       Critic(model),
       Editor(model),
       Summarizer(model)  # Add here
   ]
   ```

3. **Add tests**:
   ```python
   # tests/test_summarizer.py
   def test_summarizer_produces_valid_output():
       agent = Summarizer()
       result = agent.process("Long text to summarize...")
       assert result["agent"] == "Summarizer"
       assert "data" in result
   ```

4. **Update documentation** with agent description

## Reporting Bugs

When reporting bugs, please include:

- **Clear title** describing the issue
- **Steps to reproduce** the bug
- **Expected behavior**
- **Actual behavior**
- **Environment details**:
  - OS and version
  - Python version
  - SynapticLlamas version
  - Ollama version
- **Error messages** and stack traces
- **Logs** if available

Use the bug report template when creating issues.

## Feature Requests

When requesting features, please include:

- **Clear description** of the feature
- **Use case** - What problem does it solve?
- **Proposed solution** (if you have ideas)
- **Alternatives considered**
- **Additional context** or examples

Use the feature request template when creating issues.

## Questions?

If you have questions about contributing:

1. Check existing [documentation](docs/)
2. Search [existing issues](https://github.com/BenevolentJoker-JohnL/SynapticLlamas/issues)
3. Ask in [Discussions](https://github.com/BenevolentJoker-JohnL/SynapticLlamas/discussions)
4. Contact maintainers

## License

By contributing to SynapticLlamas, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to SynapticLlamas! Your efforts help make distributed AI orchestration more accessible to everyone.

# Contributing to ArbitrageAI

Thank you for your interest in contributing to ArbitrageAI! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Guidelines](#pull-request-guidelines)
- [Issue Reporting](#issue-reporting)
- [Community](#community)

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md) to maintain a welcoming and inclusive community.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/ArbitrageAI.git
   cd ArbitrageAI
   ```
3. **Set up the development environment** (see [Development Setup](#development-setup))
4. **Create a branch** for your feature or bug fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker (for sandbox features)
- Ollama (for local LLM)

### Installation

```bash
# Install Python dependencies
pip install -e ".[dev,tests]"

# Install Node.js dependencies
cd src/client_portal
npm install

# Install pre-commit hooks
pre-commit install
```

### Environment Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
```

See [README.md](README.md) for detailed setup instructions.

## How to Contribute

### Types of Contributions

We welcome various types of contributions:

- **Bug fixes**: Fix issues in the codebase
- **New features**: Implement new functionality
- **Documentation**: Improve or add documentation
- **Tests**: Add or improve test coverage
- **Performance improvements**: Optimize existing code
- **Code quality**: Refactor, improve type hints, add linting rules

### Making Changes

1. **Create an issue** (if one doesn't exist) describing the problem or feature
2. **Write tests** for your changes
3. **Make your changes** following coding standards
4. **Run tests** and ensure they pass
5. **Run linting** and fix any issues
6. **Update documentation** as needed
7. **Submit a pull request**

## Coding Standards

### Python Code Style

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use type hints for all function signatures
- Write docstrings for all public functions and classes
- Keep functions focused and small (< 50 lines preferred)

### Code Quality Tools

We use several tools to maintain code quality:

```bash
# Linting with ruff
ruff check src/ tests/

# Type checking with mypy
mypy src/

# Code formatting
ruff format src/ tests/

# Security scanning
bandit -r src/

# Dependency security
pip-audit
```

### Naming Conventions

- **Classes**: PascalCase (e.g., `WebSocketManager`)
- **Functions/Methods**: snake_case (e.g., `send_task_update`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `MAX_RETRIES`)
- **Private methods**: Prefix with underscore (e.g., `_internal_helper`)

### Documentation

- Use Google-style docstrings
- Include type hints in function signatures
- Document all parameters, returns, and exceptions
- Keep docstrings up to date with code changes

Example:
```python
def send_task_update(
    task_id: str,
    status: str,
    message: str,
    progress: Optional[float] = None
) -> bool:
    """
    Send task status update to all subscribed clients.

    Args:
        task_id: Unique identifier for the task
        status: New task status (e.g., 'PROCESSING', 'COMPLETED')
        message: Human-readable status message
        progress: Progress percentage (0-100), if applicable

    Returns:
        True if update was sent successfully, False otherwise

    Raises:
        ConnectionError: If no active WebSocket connections
    """
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_websocket_manager.py

# Run with verbose output
pytest -v
```

### Writing Tests

- Write tests for all new features and bug fixes
- Aim for >80% code coverage
- Use descriptive test names: `test_<method>_<scenario>_<expected_result>`
- Follow Arrange-Act-Assert pattern
- Mock external dependencies

Example:
```python
async def test_websocket_manager_authenticate_client_success():
    """Test successful client authentication with valid JWT token."""
    # Arrange
    manager = WebSocketManager()
    mock_websocket = AsyncMock()
    valid_token = generate_valid_token()

    # Act
    client_id = await manager.authenticate_client(mock_websocket, valid_token)

    # Assert
    assert client_id is not None
    assert client_id in manager.active_connections
```

## Pull Request Guidelines

### Before Submitting

- [ ] Tests pass locally: `pytest`
- [ ] Linting passes: `ruff check src/ tests/`
- [ ] Type checking passes: `mypy src/`
- [ ] Coverage threshold met: `pytest --cov-fail-under=80`
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (for user-facing changes)

### PR Title Format

Use conventional commits format:
- `feat: Add WebSocket reconnection logic`
- `fix: Resolve memory leak in task executor`
- `docs: Update API documentation`
- `test: Add tests for rate limiting`
- `refactor: Simplify confidence calculation`

### PR Description Template

```markdown
## Description
Brief description of changes

## Related Issue
Fixes #<issue-number>

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe testing performed:
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Tests pass locally
- [ ] Documentation updated
```

## Issue Reporting

### Bug Reports

When reporting bugs, please include:

1. **Description**: Clear description of the bug
2. **Steps to Reproduce**: Detailed steps to reproduce
3. **Expected Behavior**: What should happen
4. **Actual Behavior**: What actually happens
5. **Environment**:
   - Python version
   - OS
   - Browser (if frontend)
   - Relevant package versions
6. **Logs**: Error messages or stack traces

### Feature Requests

When requesting features, please include:

1. **Problem Statement**: What problem does this solve?
2. **Proposed Solution**: How should it work?
3. **Use Cases**: Examples of how it would be used
4. **Alternatives Considered**: Other approaches considered
5. **Additional Context**: Any other relevant information

## Community

### Communication

- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Email**: [Contact email if applicable]

### Recognition

Contributors will be recognized in:
- CHANGELOG.md
- README.md (Contributors section)
- Release notes

## License

By contributing to ArbitrageAI, you agree that your contributions will be licensed under the [MIT License](LICENSE).

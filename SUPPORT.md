# Support

This document provides information on how to get help with ArbitrageAI.

## Getting Help

There are several ways to get support when using ArbitrageAI:

### Documentation

- **[README.md](README.md)** - Project overview and quick start guide
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines and development setup
- **[ARCHITECTURE_COMPARISON.md](ARCHITECTURE_COMPARISON.md)** - Architecture documentation
- **[API_VERSIONING_STRATEGY.md](API_VERSIONING_STRATEGY.md)** - API documentation

### GitHub Issues

**For bug reports and feature requests**, please use the [GitHub Issues](https://github.com/anchapin/ArbitrageAI/issues) tracker.

Before creating a new issue:
1. Search existing issues to avoid duplicates
2. Use the appropriate issue template
3. Provide detailed information about your environment and the problem
4. Include steps to reproduce for bugs

**When reporting bugs, please include:**
- ArbitrageAI version
- Python version
- Operating system
- Steps to reproduce the issue
- Expected behavior
- Actual behavior
- Any relevant logs or error messages

### Community Support

For general questions and community discussion:
- Check if there's a community forum or discussion board
- Join relevant community channels (if available)

## Commercial Support

For commercial support, custom development, or enterprise licensing options, please contact the maintainers directly.

## Support Policy

### Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

We recommend always using the latest stable version for the best experience and security.

### Response Times

We strive to respond to all support requests in a timely manner:

- **Critical bugs**: Within 48 hours
- **Non-critical bugs**: Within 5 business days
- **Feature requests**: Within 1 week (for initial review)

### What We Support

✅ **We support:**
- Bug fixes
- Security vulnerabilities
- Documentation improvements
- Performance issues
- Compatibility with supported Python versions (3.10+)

❌ **We don't support:**
- Custom modifications to the codebase
- Third-party integrations not officially supported
- Outdated versions
- Issues caused by misconfiguration

## Additional Resources

### Tutorials and Guides

- [Distributed Tracing Quick Start](DISTRIBUTED_TRACING_QUICK_START.md)
- [Integration Guide: Redis Locks](INTEGRATION_GUIDE_REDIS_LOCKS.md)
- [Pre-commit Setup Guide](PRECOMMIT_GUIDE.md)

### API Documentation

When running the application, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Security Issues

For security vulnerabilities, please follow our [Security Policy](SECURITY.md) and **do not** create public GitHub issues.

## Version Compatibility

### Python Versions

ArbitrageAI supports Python 3.10 and above.

### Node.js Versions

The client portal requires Node.js 18 or above.

### Database Versions

- SQLite 3.x (development)
- PostgreSQL 14+ (production)

### Redis Versions

- Redis 6.x or higher (for caching and distributed locking)

## Frequently Asked Questions

### Q: How do I set up the development environment?

A: See the [CONTRIBUTING.md](CONTRIBUTING.md#development-setup) guide for detailed instructions.

### Q: How do I run the tests?

A: Run `pytest` for backend tests and `npm test` in the `src/client_portal` directory for frontend tests.

### Q: Can I use ArbitrageAI in production?

A: Yes, but ensure you follow the production deployment guide and security best practices.

### Q: How do I configure LLM providers?

A: See the configuration documentation and environment variable examples in `.env.example`.

## Contact

For other inquiries not covered above, please open a GitHub issue or contact the maintainers directly.

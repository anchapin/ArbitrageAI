# API Versioning Strategy

**Version**: 1.0
**Date**: March 2, 2026
**Status**: Implemented

---

## Overview

This document defines the API versioning strategy for the ArbitrageAI project. The strategy ensures backward compatibility while allowing for API evolution and deprecation of old endpoints.

---

## Versioning Approach

### URL Path Versioning (Primary)

We use **URL path versioning** as the primary strategy:

```
/api/v1/tasks
/api/v1/bids
/api/v1/marketplace
```

**Rationale**:
- ✅ Explicit and visible in the URL
- ✅ Easy to debug and test
- ✅ Clear separation between versions
- ✅ Browser-friendly
- ✅ Industry standard (GitHub, Stripe, etc.)

### Alternative Approaches Considered

1. **Header Versioning** (`Accept: application/vnd.arbitrageai.v1+json`)
   - ❌ Less visible, harder to debug
   - ❌ Requires custom client configuration

2. **Query Parameter Versioning** (`/api/tasks?version=1`)
   - ❌ Can be accidentally omitted
   - ❌ Less RESTful

3. **Content Negotiation** (Accept/Content-Type headers)
   - ❌ Complex for API consumers
   - ❌ Harder to cache

---

## Version Lifecycle

### Phase 1: Current (v1)
```
/api/v1/* - All current endpoints
```

### Phase 2: Future Versions
```
/api/v1/* - Supported (maintenance mode)
/api/v2/* - Current stable version
/api/v3/* - Beta/development
```

### Deprecation Timeline

| Phase | Duration | Action |
|-------|----------|--------|
| **Active** | 12+ months | Full support, new features |
| **Deprecated** | 6 months | Bug fixes only, deprecation warnings |
| **Sunset** | 3 months | Critical security fixes only |
| **Retired** | - | Endpoint removed |

**Total Minimum Support**: 21 months from deprecation announcement

---

## Implementation

### FastAPI Router Structure

```python
# src/api/routers/__init__.py
from fastapi import APIRouter

api_router = APIRouter()

# Version 1 routes
from .v1 import tasks, bids, marketplace

api_router.include_router(tasks.router, prefix="/v1/tasks", tags=["Tasks v1"])
api_router.include_router(bids.router, prefix="/v1/bids", tags=["Bids v1"])
api_router.include_router(marketplace.router, prefix="/v1/marketplace", tags=["Marketplace v1"])
```

### Version-Specific Dependencies

```python
# src/api/dependencies.py
from fastapi import Header, HTTPException, status

def get_api_version(x_api_version: str | None = Header(None)) -> str:
    """Extract API version from header or URL."""
    return x_api_version or "v1"

def validate_version(version: str) -> bool:
    """Validate that the requested version is supported."""
    supported_versions = ["v1", "v2"]
    return version in supported_versions
```

### Response Versioning

For backward-compatible changes, use response models:

```python
# src/api/v1/schemas.py
from pydantic import BaseModel, Field

class TaskResponseV1(BaseModel):
    """Task response schema for API v1."""
    id: str
    status: str
    result: str | None = None

class TaskResponseV2(BaseModel):
    """Task response schema for API v2 with additional fields."""
    id: str
    status: str
    result: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: str
    updated_at: str
```

---

## Deprecation Strategy

### Deprecation Headers

All deprecated endpoints MUST return deprecation headers:

```python
from fastapi import Response

@router.get("/tasks/{task_id}")
async def get_task(task_id: str, response: Response):
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2026-12-31"
    response.headers["Link"] = "</api/v2/tasks/{task_id}>; rel=\"successor-version\""
    
    return task
```

### Deprecation Notice Response Header

```
Deprecation: true
Sunset: 2026-12-31
Link: </api/v2/tasks>; rel="successor-version"
X-API-Deprecation-Warning: This endpoint is deprecated. Please use /api/v2/tasks instead.
```

---

## Migration Guide Template

When releasing a new API version, provide a migration guide:

### Example: v1 to v2 Migration

```markdown
# API v1 to v2 Migration Guide

## Breaking Changes

1. **Task Response Schema**
   - v1: Returns `result` field directly
   - v2: Returns `data.result` nested structure

2. **Pagination**
   - v1: `offset` and `limit` parameters
   - v2: `cursor`-based pagination

## Migration Steps

1. Update API base URL: `/api/v1` → `/api/v2`
2. Update response parsing logic
3. Update pagination handling
4. Test in staging environment
5. Deploy to production

## Support

- Migration deadline: 2027-06-30
- Support email: api-support@arbitrageai.com
```

---

## Version Discovery

### API Root Endpoint

```
GET /api/
```

**Response**:
```json
{
  "name": "ArbitrageAI API",
  "version": "v1",
  "supported_versions": ["v1", "v2"],
  "documentation": "/docs",
  "latest_stable": "v1",
  "latest_beta": "v2"
}
```

### OpenAPI Documentation

- **v1**: `/api/v1/docs` or `/docs/v1`
- **v2**: `/api/v2/docs` or `/docs/v2`

Each version has separate OpenAPI schemas.

---

## Error Handling

### Version Not Found

```json
{
  "detail": "API version 'v3' is not supported. Supported versions: v1, v2",
  "error_code": "VERSION_NOT_SUPPORTED",
  "supported_versions": ["v1", "v2"]
}
```

### Deprecated Version Warning

```json
{
  "warning": "API version 'v1' is deprecated and will be removed on 2027-06-30",
  "successor_version": "v2",
  "migration_guide": "https://docs.arbitrageai.com/migration/v1-to-v2"
}
```

---

## Testing Strategy

### Version-Specific Tests

```python
# tests/test_api_versioning.py

def test_v1_endpoint():
    response = client.get("/api/v1/tasks")
    assert response.status_code == 200
    assert "v1_schema" in response.json()

def test_v2_endpoint():
    response = client.get("/api/v2/tasks")
    assert response.status_code == 200
    assert "metadata" in response.json()

def test_unsupported_version():
    response = client.get("/api/v3/tasks")
    assert response.status_code == 400
    assert "VERSION_NOT_SUPPORTED" in response.json()["error_code"]
```

### Backward Compatibility Tests

Ensure v1 endpoints continue to work when v2 is released:

```python
def test_v1_backward_compatibility():
    """Ensure v1 API still works after v2 release."""
    response = client.get("/api/v1/tasks")
    assert response.status_code == 200
    # Verify v1 response schema
    assert "result" in response.json()
    assert "metadata" not in response.json()  # v2 field
```

---

## Documentation

### Version-Specific Documentation

Each API version MUST have:
1. **OpenAPI Schema**: Auto-generated at `/docs/v{version}`
2. **Migration Guide**: For upgrading from previous versions
3. **Changelog**: Documenting changes between versions
4. **Deprecation Timeline**: Clear sunset dates

### Documentation Location

```
docs/
├── api/
│   ├── v1/
│   │   ├── reference.md
│   │   └── examples.md
│   ├── v2/
│   │   ├── reference.md
│   │   └── examples.md
│   └── migration/
│       ├── v1-to-v2.md
│       └── deprecation-policy.md
```

---

## Security Considerations

### Authentication Across Versions

- All API versions MUST use the same authentication mechanism
- API keys should work across all supported versions
- Token format should be version-agnostic

### Rate Limiting

- Rate limits apply per API version
- Example: 1000 requests/hour for v1, 1000 requests/hour for v2

---

## Monitoring and Analytics

### Version Usage Tracking

Track API version usage to inform deprecation decisions:

```python
# Middleware to track version usage
async def track_api_version(request: Request, call_next):
    version = extract_version_from_request(request)
    metrics.increment(f"api.requests.v{version}")
    return await call_next(request)
```

### Metrics to Monitor

1. **Request Volume by Version**: `api.requests.v{version}`
2. **Error Rate by Version**: `api.errors.v{version}`
3. **Latency by Version**: `api.latency.v{version}`
4. **Deprecation Warnings**: `api.deprecation.warnings`

---

## Rollback Strategy

If a new version has critical issues:

1. **Immediate**: Disable new version, route traffic to previous version
2. **Short-term**: Fix issues in development, release as patch
3. **Long-term**: Re-evaluate version release process

### Feature Flags

Use feature flags to enable/disable API versions:

```python
if not settings.API_V2_ENABLED:
    raise HTTPException(503, "API v2 is currently under maintenance")
```

---

## Decision Log

### 2026-03-02: Initial API Versioning Strategy

**Decision**: URL path versioning (`/api/v1/`)

**Rationale**:
- Most explicit and developer-friendly
- Industry standard (GitHub, Stripe, Slack)
- Easy to implement in FastAPI
- Clear separation between versions

**Alternatives Rejected**:
- Header versioning (less visible)
- Query parameter versioning (can be omitted)
- Content negotiation (complex for consumers)

---

## References

- [GitHub API Versioning](https://docs.github.com/en/rest/overview/versioning)
- [Stripe API Versioning](https://stripe.com/docs/api/versioning)
- [FastAPI Advanced Dependencies](https://fastapi.tiangolo.com/advanced/dependencies/)
- [RFC 5988 - Web Linking](https://datatracker.ietf.org/doc/html/rfc5988)
- [Deprecation HTTP Header](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-deprecation-header)

---

**Next Review**: June 2, 2026 (Quarterly)
**Owner**: API Development Team

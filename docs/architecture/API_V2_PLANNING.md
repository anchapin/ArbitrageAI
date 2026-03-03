# API v2 Planning Document

**Status**: 📋 Planning Phase
**Created**: March 3, 2026
**Priority**: Medium
**Related Issue**: #145 (API Versioning - Complete)

---

## Executive Summary

This document outlines the planning and roadmap for API v2 of the ArbitrageAI platform. API v1 is currently stable and fully functional. API v2 will introduce breaking changes and new features while maintaining backward compatibility through the versioning middleware implemented in Issue #145.

---

## Current State: API v1

### Features
- ✅ Task management (CRUD operations)
- ✅ Client authentication (JWT-based)
- ✅ Real-time WebSocket updates
- ✅ Payment integration (Stripe)
- ✅ File upload/download
- ✅ Client dashboard
- ✅ Analytics endpoints
- ✅ Health checks

### Architecture
```
/api/v1/
├── /tasks              - Task management
├── /client             - Client operations
├── /admin              - Admin operations
├── /session            - Session management
├── /checkout           - Payment processing
├── /files              - File operations
├── /analytics          - Analytics data
├── /system             - System endpoints
└── /ws                 - WebSocket endpoint
```

### Known Limitations in v1
1. **Pagination**: Inconsistent pagination across endpoints
2. **Filtering**: Limited filtering capabilities
3. **Rate Limiting**: Basic rate limiting without granular quotas
4. **Error Responses**: Inconsistent error response format
5. **Field Selection**: No field selection (always returns all fields)
6. **Batch Operations**: No batch create/update operations
7. **Webhooks**: Limited webhook event types
8. **API Keys**: No API key management for programmatic access

---

## API v2 Goals

### Primary Objectives
1. **Backward Compatibility**: Maintain v1 while introducing v2
2. **Developer Experience**: Improve API ergonomics and documentation
3. **Performance**: Optimize payload sizes and response times
4. **Flexibility**: Add filtering, sorting, and field selection
5. **Extensibility**: Design for future enhancements

### Success Metrics
- [ ] 95% test coverage for all v2 endpoints
- [ ] <100ms average response time (p50)
- [ ] <500ms average response time (p95)
- [ ] Zero breaking changes for v1 clients
- [ ] Comprehensive OpenAPI documentation
- [ ] SDK generation support

---

## Proposed Changes

### 1. Response Format Standardization

#### v1 (Current)
```json
{
  "id": "task-123",
  "title": "Example Task",
  "status": "pending"
}
```

#### v2 (Proposed)
```json
{
  "data": {
    "id": "task-123",
    "type": "task",
    "attributes": {
      "title": "Example Task",
      "status": "pending"
    },
    "relationships": {
      "client": {
        "data": { "id": "client-456", "type": "client" }
      }
    },
    "meta": {
      "created_at": "2026-03-03T10:00:00Z",
      "updated_at": "2026-03-03T10:00:00Z"
    }
  },
  "links": {
    "self": "/api/v2/tasks/task-123"
  }
}
```

**Benefits**:
- JSON:API compliant
- Consistent structure across all resources
- Built-in relationship handling
- Easy to extend

---

### 2. Advanced Filtering & Sorting

#### v1 (Current)
```
GET /api/v1/tasks?status=pending
```

#### v2 (Proposed)
```
GET /api/v2/tasks?filter[status]=pending&filter[domain]=accounting&sort=-created_at&fields=title,status,domain
```

**Query Parameters**:
- `filter[field]`: Filter by field value
- `sort`: Sort by field (prefix with `-` for descending)
- `fields`: Comma-separated list of fields to return
- `include`: Include related resources
- `page[number]`: Page number
- `page[size]`: Page size

---

### 3. Batch Operations

#### v2 (New)
```http
POST /api/v2/tasks/batch
Content-Type: application/json

{
  "data": [
    {
      "type": "task",
      "attributes": {
        "title": "Task 1",
        "description": "Description 1"
      }
    },
    {
      "type": "task",
      "attributes": {
        "title": "Task 2",
        "description": "Description 2"
      }
    }
  ]
}
```

**Response**:
```json
{
  "data": [
    { "id": "task-1", "type": "task", ... },
    { "id": "task-2", "type": "task", ... }
  ],
  "meta": {
    "created": 2,
    "failed": 0
  }
}
```

---

### 4. Enhanced Error Handling

#### v1 (Current)
```json
{
  "error": "Invalid task ID"
}
```

#### v2 (Proposed)
```json
{
  "errors": [
    {
      "id": "error-123",
      "status": "400",
      "code": "INVALID_RESOURCE_ID",
      "title": "Invalid task ID",
      "detail": "The provided task ID 'invalid-id' does not exist",
      "source": {
        "parameter": "task_id"
      },
      "meta": {
        "timestamp": "2026-03-03T10:00:00Z",
        "trace_id": "trace-abc123"
      }
    }
  ]
}
```

**Error Codes**:
- `INVALID_RESOURCE_ID` - Resource not found
- `VALIDATION_ERROR` - Request validation failed
- `AUTHENTICATION_REQUIRED` - Missing/invalid auth
- `PERMISSION_DENIED` - Insufficient permissions
- `RATE_LIMIT_EXCEEDED` - Quota exceeded
- `INTERNAL_ERROR` - Server error

---

### 5. API Key Management

#### v2 (New)
```http
POST /api/v2/api-keys
Content-Type: application/json
Authorization: Bearer <jwt-token>

{
  "data": {
    "type": "api_key",
    "attributes": {
      "name": "Production Key",
      "scopes": ["tasks:read", "tasks:write"],
      "expires_at": "2027-03-03T00:00:00Z"
    }
  }
}
```

**Response**:
```json
{
  "data": {
    "id": "key-123",
    "type": "api_key",
    "attributes": {
      "name": "Production Key",
      "key": "sk_live_abc123...",  // Only shown once
      "scopes": ["tasks:read", "tasks:write"],
      "created_at": "2026-03-03T10:00:00Z",
      "expires_at": "2027-03-03T00:00:00Z"
    }
  }
}
```

---

### 6. Webhook Enhancements

#### v1 (Current)
- Limited to task status changes

#### v2 (Proposed)
**Event Types**:
- `task.created`
- `task.updated`
- `task.completed`
- `task.failed`
- `task.deleted`
- `payment.completed`
- `payment.failed`
- `file.uploaded`
- `api_key.created`
- `api_key.revoked`

**Webhook Payload**:
```json
{
  "id": "event-123",
  "type": "task.completed",
  "created_at": "2026-03-03T10:00:00Z",
  "data": {
    "id": "task-456",
    "type": "task",
    "attributes": { ... }
  },
  "meta": {
    "trace_id": "trace-abc123"
  }
}
```

---

### 7. GraphQL Support (Optional)

#### v2 (Potential)
```graphql
query GetTask($id: ID!) {
  task(id: $id) {
    id
    title
    status
    client {
      id
      email
    }
    createdAt
  }
}
```

**Considerations**:
- Additional infrastructure complexity
- Learning curve for team
- Better for complex queries
- Overkill for simple use cases

**Decision**: Defer to v2.1 based on user feedback

---

## Migration Strategy

### Phase 1: Foundation (Weeks 1-2)
- [ ] Set up v2 routing infrastructure
- [ ] Create response serializers
- [ ] Implement error handling framework
- [ ] Set up OpenAPI documentation

### Phase 2: Core Endpoints (Weeks 3-6)
- [ ] Migrate task endpoints
- [ ] Migrate client endpoints
- [ ] Migrate authentication endpoints
- [ ] Add filtering/sorting support

### Phase 3: Advanced Features (Weeks 7-8)
- [ ] Implement batch operations
- [ ] Add API key management
- [ ] Enhance webhook system
- [ ] Add field selection

### Phase 4: Testing & Documentation (Weeks 9-10)
- [ ] Comprehensive test coverage
- [ ] API documentation
- [ ] Migration guide for users
- [ ] SDK generation

### Phase 5: Beta & Feedback (Weeks 11-12)
- [ ] Internal beta testing
- [ ] External beta program
- [ ] Gather feedback
- [ ] Iterate on issues

### Phase 6: General Availability (Week 13+)
- [ ] Production rollout
- [ ] Monitor metrics
- [ ] Support v1 deprecation timeline

---

## Backward Compatibility

### Deprecation Timeline
- **v2.0 Launch**: Both v1 and v2 supported
- **6 Months Post-Launch**: v1 deprecation notices in responses
- **12 Months Post-Launch**: v1 sunset (with migration support)

### Deprecation Headers
```http
Deprecation: true
Sunset: Sat, 03 Mar 2027 00:00:00 GMT
Link: <https://api.arbitrageai.com/v2/tasks>; rel="successor-version"
```

---

## Technical Implementation

### File Structure
```
src/api/v2/
├── __init__.py
├── main.py              # v2 router registration
├── dependencies.py      # v2-specific dependencies
├── responses.py         # Response serializers
├── errors.py            # Error handling
├── filters.py           # Filtering logic
├── pagination.py        # Pagination utilities
└── routes/
    ├── tasks.py
    ├── clients.py
    ├── auth.py
    ├── api_keys.py
    └── webhooks.py
```

### Dependencies
- `fastapi` (existing)
- `pydantic` (existing)
- `python-multipart` (existing)
- New: `fastapi-pagination` (optional)
- New: `strawberry-graphql` (optional, for GraphQL)

---

## Testing Strategy

### Unit Tests
```python
def test_task_response_serialization():
    task = Task(id="task-123", title="Test", status="pending")
    response = TaskResponse.from_model(task)
    assert response.data.type == "task"
    assert response.data.attributes.title == "Test"
```

### Integration Tests
```python
def test_filter_tasks():
    response = client.get("/api/v2/tasks?filter[status]=pending")
    assert response.status_code == 200
    data = response.json()
    assert all(task["attributes"]["status"] == "pending" 
               for task in data["data"])
```

### Contract Tests
- OpenAPI schema validation
- Request/response contract testing
- Backward compatibility checks

---

## Documentation

### Required Documentation
1. **API Reference**: Complete endpoint documentation
2. **Migration Guide**: v1 → v2 migration steps
3. **Getting Started**: Quick start guide
4. **Authentication Guide**: Auth methods and best practices
5. **Error Handling Guide**: Error codes and handling
6. **Rate Limiting Guide**: Quotas and limits
7. **Webhooks Guide**: Event types and setup
8. **SDK Documentation**: Language-specific guides

### Documentation Tools
- **OpenAPI/Swagger**: Auto-generated from code
- **Redoc**: Enhanced API documentation
- **Postman Collection**: Interactive API testing
- **Code Samples**: Multi-language examples

---

## Risk Assessment

### Technical Risks
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Breaking changes slip through | High | Medium | Comprehensive contract testing |
| Performance regression | High | Low | Load testing before launch |
| Documentation gaps | Medium | High | Docs as code, review process |
| Migration complexity | Medium | Medium | Detailed migration guide, tools |

### Business Risks
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| User adoption slow | Medium | Medium | Clear benefits, migration support |
| Support burden increases | Medium | High | FAQ, migration guides, support docs |
| v1 maintenance burden | Low | High | Automated deprecation notices |

---

## Success Criteria

### Technical
- [ ] All v2 endpoints implemented and tested
- [ ] 95%+ test coverage
- [ ] <100ms p50 response time
- [ ] <500ms p95 response time
- [ ] Zero critical security vulnerabilities
- [ ] Complete OpenAPI documentation

### Business
- [ ] 50% of active users migrated within 6 months
- [ ] <5% support ticket increase
- [ ] Positive user feedback (NPS > 50)
- [ ] No breaking changes for v1 users
- [ ] Clear migration path documented

---

## Open Questions

1. **GraphQL Support**: Should we invest in GraphQL for v2.1?
   - Pros: Flexible queries, reduced over-fetching
   - Cons: Complexity, learning curve
   - **Decision**: Defer based on user feedback

2. **Response Format**: JSON:API vs custom format?
   - **Recommendation**: JSON:API for consistency and tooling

3. **Authentication**: Continue with JWT or add OAuth2?
   - **Recommendation**: Keep JWT, add OAuth2 for third-party apps

4. **Rate Limiting**: Per-user or per-API-key?
   - **Recommendation**: Both, with separate quotas

---

## Next Steps

1. **Review & Feedback** (Week 1)
   - Share with team for feedback
   - Incorporate suggestions
   - Finalize specification

2. **Proof of Concept** (Week 2)
   - Implement 1-2 endpoints as PoC
   - Validate approach
   - Identify issues

3. **Full Implementation** (Weeks 3-12)
   - Follow phased approach
   - Weekly progress reviews
   - Continuous testing

4. **Beta Launch** (Week 13)
   - Internal testing
   - External beta program
   - Iterate based on feedback

5. **General Availability** (Week 14+)
   - Production launch
   - Monitor and support
   - Plan v2.1 features

---

## Resources

### References
- [JSON:API Specification](https://jsonapi.org/)
- [OpenAPI Specification](https://swagger.io/specification/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [API Design Best Practices](https://docs.github.com/en/rest/overview/resources-in-the-rest-api)

### Related Documents
- [API Versioning Strategy](../../architecture/API_VERSIONING_STRATEGY.md)
- [Issue #145: API Versioning](../../features/ISSUE_145_API_VERSIONING.md)
- [Security Policy](../../security/SECURITY.md)

---

**Document Status**: Draft
**Last Updated**: March 3, 2026
**Next Review**: March 10, 2026
**Owner**: Development Team

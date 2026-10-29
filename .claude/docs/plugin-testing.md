# Plugin Testing and Checklist

Read this when you add tests for a service, operation or step, or before closing a new plugin capability. Layers: [plugin-architecture.md](plugin-architecture.md). Naming and rules: [plugin-conventions.md](plugin-conventions.md).

---

## Testing Guidelines

### ⚠️ Rule: Tests are MANDATORY for every Service

**Every time a new Service is created or a method is added, unit tests MUST be written.**

This is not optional. Services without tests are considered incomplete.

**Checklist when creating a service:**
- [ ] Create `tests/services/test_{name}_service.py`
- [ ] Test every public method (happy path + error cases)
- [ ] Mock the network layer (`mock_network.make_request` or `mock_git_network.run_command`)
- [ ] Verify `ClientSuccess` is returned on success
- [ ] Verify `ClientError` with the correct `error_code` is returned on failure

**Where to put the tests:**
```
plugins/titan-plugin-{name}/
└── tests/
    └── services/
        └── test_{name}_service.py   ← required for every service
```

### Service Tests
```python
def test_issue_service_get_success(mock_network):
    mock_network.make_request.return_value = {"key": "PROJ-1", ...}
    service = IssueService(mock_network)

    result = service.get_issue("PROJ-1")

    assert isinstance(result, ClientSuccess)
    assert result.data.key == "PROJ-1"
```

### Operation Tests
```python
def test_fetch_my_issues_filters(mock_client):
    mock_client.search_issues.return_value = ClientSuccess(data=[...])

    issues = fetch_my_pending_issues(mock_client, "user@example.com")

    assert len(issues) == 2  # Filtered
    assert all(i.status != "Done" for i in issues)
```

### Step Tests
```python
def test_get_issue_step_success(mock_context):
    mock_context.jira.get_issue.return_value = ClientSuccess(data=...)

    result = get_issue_step(mock_context)

    assert isinstance(result, Success)
```

---

## Implementation Checklist

When creating/migrating a plugin, ensure:

### Models
- [ ] Network models in `models/network/` (faithful to API)
- [ ] UI models in the view layer (pre-formatted) — either a `models/view/` package (git) or a single `models/view.py` module (jira, github); both layouts are in use
- [ ] Mappers in `models/mappers/`

### Services
- [ ] All methods return `ClientResult[UIModel]`
- [ ] Network call → Parse → Map → Wrap Result

### Client
- [ ] Simple facade delegating to services
- [ ] All methods return `ClientResult[UIModel]`

### Steps
- [ ] MANDATORY: Pattern matching for all `ClientResult`
- [ ] NO direct `.data` access
- [ ] Clear error messages

### Operations (if needed)
- [ ] Work with UI models, NOT dicts
- [ ] Pure functions
- [ ] Well-typed parameters
- [ ] NO doctest examples

### Tests
- [ ] Network layer: 90%+ coverage
- [ ] Services: 100% coverage
- [ ] Operations: 100% coverage
- [ ] Use mocks, not real API calls

---

**Last Updated**: 2026-08-04
**Version**: 3.0

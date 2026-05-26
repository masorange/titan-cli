# Project vs Plugin Architecture

Project workflow architecture:

1. workflows live in `.titan/workflows/`
2. project step entrypoints live in `.titan/steps/**`
3. supporting layers may live under `.titan/operations/`, `.titan/clients/`, `.titan/services/`

Plugin workflow architecture:

1. workflows live in the plugin package
2. steps are exposed by plugin registration
3. supporting layers live inside the plugin package
4. package structure is part of the contract for maintainers

# 001. Delegate API surface extraction entirely to sheridan-iceberg

Date: 2026-03-23
Status: Accepted

## Context

diffract needs to obtain the public API surface of a Python package at two git refs in order to compare and classify changes between them. The alternative approaches were either implementing AST walking within diffract itself, or delegating that work to an existing library.

sheridan-iceberg provides a `get_public_api(path) -> dict[str, list[str]]` function that extracts the public API surface from a Python package at a given path — mapping module names to lists of public names.

## Decision

diffract does not implement any AST logic of its own. It calls `sheridan.iceberg.get_public_api()` to extract the API surface at each commit ref, then performs only diffing and classification on the results.

## Alternatives Considered

1. **Implement AST walking in diffract:** Extract public API directly via the `ast` module or similar. This would make diffract self-contained but would duplicate effort, introduce maintenance burden for AST correctness, and couple API extraction logic to diffract's release cycle rather than to a specialized library.

2. **Delegate to sheridan-iceberg:** Use iceberg's existing `get_public_api()` function. Selected because it keeps diffract focused on its core responsibility (diffing and classification), allows AST improvements to benefit diffract automatically, and avoids code duplication.

## Consequences

**Positive:**
- diffract remains thin and focused on diffing, not extraction
- AST correctness is iceberg's responsibility, not diffract's
- Clear separation of concerns
- When iceberg improves (e.g., adds signature support, better detection of private vs public), diffract benefits automatically

**Negative:**
- diffract is constrained to what iceberg exposes — currently name lists only, no signature information
- Adds a runtime dependency on sheridan-iceberg
- Any limitations in iceberg's extraction directly limit diffract's capability

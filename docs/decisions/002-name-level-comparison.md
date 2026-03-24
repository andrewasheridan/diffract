# 002. Name-level-only API comparison (no signature diffing)

Date: 2026-03-23
Status: Accepted

## Context

iceberg's `get_public_api()` returns `dict[str, list[str]]` — module names mapped to lists of public *names* only. Signature information (parameter names, types, return types, defaults) is not available from this API.

The original design specification mentioned that signature changes should trigger `feat!` (breaking) classification. However, implementing signature comparison would require either enhancing iceberg to expose signature data, or performing signature extraction separately within diffract itself.

## Decision

diffract compares API surfaces at the name level only. Signature changes — including argument renames, type annotation changes, return type changes, or default value modifications — are not detected or classified separately.

The classification rules implemented are:
- Name removed → `feat!` (breaking)
- Name added → `feat` (feature)
- Python files changed but no name-level changes → `refactor`
- No changes → `fix`

## Alternatives Considered

1. **Implement signature-level comparison:** Extract parameter and return type information and compare signatures before and after. This would support the original specification but would require duplicating extraction logic or enhancing iceberg first, increasing complexity and maintenance burden.

2. **Name-level comparison only:** Compare only whether names (classes, functions, variables) exist or have been removed. This is what iceberg currently provides, is simple to implement correctly, and avoids false positives from imperfect signature analysis.

## Consequences

**Positive:**
- Simple and correct at the level of data available
- Consistent with what iceberg provides today
- No risk of false positives from imperfect signature parsing
- Easy to extend in the future if iceberg adds signature data

**Negative:**
- A function that changes its signature (e.g., parameter rename) without changing its name will be classified as `fix` or `refactor` instead of `feat!` — a known gap in breaking change detection
- Callers relying on signature stability are not automatically protected by diffract; they must implement additional tooling
- The classification is less precise than the original specification intended

**Future:**
If sheridan-iceberg is extended to return signature information as part of `get_public_api()`, diffract can add signature-level comparison rules without requiring architectural changes.

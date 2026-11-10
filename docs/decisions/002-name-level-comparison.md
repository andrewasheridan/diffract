# 002. Compare only names, not signatures

Date: 2026-03-23
Status: Accepted

## Context

The `get_public_api()` function of iceberg returns `dict[str, list[str]]`. This maps
module names to lists of public *names* only. This API gives no signature data:
parameter names, types, return types or default values.

The first design specification said that a signature change must give `feat!`
(breaking). To compare signatures, iceberg must give signature data, or diffract must
get the signatures itself.

## Decision

diffract compares the public APIs only at the level of names. It does not find
signature changes. Examples of signature changes are a new argument name, a new type
annotation, a new return type and a new default value.

diffract uses these rules:

- A name was removed: `feat!` (breaking)
- A name was added: `feat` (feature)
- Python files changed, but no names changed: `refactor`
- No change: `fix`

## Alternatives considered

1. **Compare signatures:** Get the parameters and the return type of each function and
   compare them. This method obeys the first specification. But diffract must copy the
   extraction logic, or iceberg must change first. Thus the method is more complex and
   needs more maintenance.

2. **Compare only names:** Compare only whether a name (a class, a function or a
   variable) is present or was removed. iceberg gives this data now. This method is
   simple to make correct. It also gives no incorrect results from a signature analysis
   that is not complete.

## Consequences

**Positive:**

- The method is simple, and it is correct for the data that diffract has.
- The method agrees with the data that iceberg gives now.
- No incorrect results come from signature parsing that is not complete.
- If iceberg gives signature data in the future, diffract can easily use it.

**Negative:**

- diffract gives `fix` or `refactor`, not `feat!`, for a function with a changed
  signature and the same name. An example is a new parameter name. This is a known gap
  in the detection of breaking changes.
- diffract does not protect callers that need stable signatures. These callers must
  use other tools.
- The classification is less precise than the first specification.

**Future:**

If `get_public_api()` of sheridan-iceberg gives signature data in the future, diffract
can add rules for signatures. The architecture does not have to change.

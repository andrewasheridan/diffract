# 001. sheridan-iceberg gets the public API for diffract

Date: 2026-03-23
Status: Accepted

## Context

diffract must get the public API of a Python package at two git refs. Then it can
compare the two APIs and give a commit type. There were two possible methods:

- diffract reads the AST itself.
- diffract uses a library that reads the AST.

sheridan-iceberg has the function `get_public_api(path) -> dict[str, list[str]]`. This
function gets the public API of a Python package at a path. The result maps each module
name to a list of public names.

## Decision

diffract has no AST logic of its own. It calls `sheridan.iceberg.get_public_api()` to
get the public API at each ref. diffract only compares the results and gives the commit
type.

## Alternatives considered

1. **Read the AST in diffract:** diffract gets the public API with the `ast` module.
   Then diffract does not need other packages. But this method copies the work of
   iceberg. diffract must also keep the AST logic correct, and each change to that
   logic needs a diffract release.

2. **Use sheridan-iceberg:** diffract calls `get_public_api()` from iceberg. We chose
   this method for these reasons:
   - diffract does only its main work: it compares APIs and gives commit types.
   - Each improvement to the AST logic in iceberg also improves diffract.
   - There is no copied code.

## Consequences

**Positive:**

- diffract stays small. It compares APIs. It does not get them.
- iceberg, not diffract, keeps the AST logic correct.
- The two packages have separate responsibilities.
- When iceberg improves, diffract also improves. Examples are support for signatures
  and better detection of private and public names.

**Negative:**

- diffract can use only the data that iceberg gives. At this time, iceberg gives only
  lists of names. It does not give signatures.
- diffract must have sheridan-iceberg at runtime.
- Each limit of iceberg is also a limit of diffract.

# API changes

diffract compares the public API at two refs. [sheridan-iceberg](https://github.com/andrewasheridan/iceberg)
gives the public names of each module and the details of each name. diffract uses these
details to find changes to the public names that are at the two refs.

## Names

- A public name that is only at the head ref is an **added name**.
- A public name that is only at the base ref is a **removed name**.
- A public member of a class (a method, a class variable or a nested class) is also a
  public name. diffract writes it with the class name in front of it, for example
  `ApiDiff.changed`.

An added name gives `feat`. A removed name gives `feat!`.

## Changes to a name

For a public name that is at the two refs, diffract compares the details below. A
**breaking** change gives `feat!`. A change that **adds** to the name gives `feat`.

| Change | Result |
|---|---|
| A positional parameter was removed | breaking |
| A positional parameter moved to a different position | breaking |
| A positional parameter became keyword-only | breaking |
| A keyword-only parameter became positional | adds |
| A keyword-only parameter was removed | breaking |
| A parameter without a default value was added | breaking |
| A parameter with a default value was added | adds |
| A parameter lost its default value | breaking |
| A parameter got a default value | adds |
| `*args` or `**kwargs` was removed | breaking |
| `*args` or `**kwargs` was added | adds |
| A function changed to `async def`, or from `async def` | breaking |
| A function changed its kind (for example, a method became a property) | breaking |
| A function became a class, or a class became a function | breaking |
| A base class or a class keyword (for example `metaclass=ABCMeta`) was removed | breaking |
| A base class or a class keyword was added | adds |

## Limits

- diffract does not compare type annotations, return annotations, decorators,
  `typing.overload` signatures or default values. A different default value is not a
  change. Only a removed or an added default value is a change.
- iceberg does not tell positional-only parameters from the other positional
  parameters. Thus a new name for a positional-only parameter is a breaking change.
- diffract does not compare an assignment or an unresolved re-export with a different
  kind of member, because the value of either one can be a class or a function.
- diffract reads only the members that a class body defines. If you move a method to
  a base class, diffract finds a removed name.
- A change to a base class expression, for example from `Generic[T]` to
  `Generic[T, U]`, is a removed base and an added base. Thus it is breaking.

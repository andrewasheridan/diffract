"""Pre-generation hook: validates cookiecutter inputs before any files are created."""

import keyword
import re
import sys

package_name: str = "[[ cookiecutter.package_name ]]"
python_version: str = "[[ cookiecutter.python_version ]]"
dagger_version: str = "[[ cookiecutter.dagger_version ]]"
initial_version: str = "[[ cookiecutter.initial_version ]]"

errors: list[str] = []

# package_name: valid lowercase Python identifier, not a keyword
if not package_name.isidentifier():
    errors.append(
        f"package_name '{package_name}' must be a valid Python identifier "
        "(letters, digits, underscores — no hyphens or spaces)."
    )
elif not package_name.islower():
    errors.append(
        f"package_name '{package_name}' must be lowercase (e.g. 'mytool', 'iceberg')."
    )
elif keyword.iskeyword(package_name):
    errors.append(
        f"package_name '{package_name}' is a Python reserved keyword and cannot be used as a package name."
    )

# python_version: X.Y format
if not re.match(r"^\d+\.\d+$", python_version):
    errors.append(
        f"python_version '{python_version}' must be in X.Y format (e.g. '3.14', '3.12')."
    )

# dagger_version: X.Y.Z format
if not re.match(r"^\d+\.\d+\.\d+$", dagger_version):
    errors.append(
        f"dagger_version '{dagger_version}' must be in X.Y.Z format (e.g. '0.20.3')."
    )

# initial_version: X.Y.Z format
if not re.match(r"^\d+\.\d+\.\d+$", initial_version):
    errors.append(
        f"initial_version '{initial_version}' must be in X.Y.Z semver format (e.g. '0.1.0')."
    )

if errors:
    print("\nERROR: Template generation aborted due to invalid inputs:\n", file=sys.stderr)
    for error in errors:
        print(f"  • {error}", file=sys.stderr)
    print(file=sys.stderr)
    sys.exit(1)

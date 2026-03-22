"""Post-generation hook: final setup."""

import datetime
import os
import sys

project_slug: str = "[[ cookiecutter.project_slug ]]"

# --- Substitute current year into LICENSE ---
license_file = os.path.join(os.getcwd(), "LICENSE")
if os.path.exists(license_file):
    year = str(datetime.date.today().year)
    with open(license_file, encoding="utf-8") as f:
        content = f.read()
    content = content.replace("YEAR_PLACEHOLDER", year)
    with open(license_file, "w", encoding="utf-8") as f:
        f.write(content)

# --- Success message ---
print(
    f"""
╔══════════════════════════════════════════════════════════════╗
║  Project '{project_slug}' generated successfully!
╚══════════════════════════════════════════════════════════════╝

Next steps:

  cd {project_slug}
  git init
  task install
  pre-commit install
  git add .
  git commit -m "feat: initial project structure"

First CI run (requires Podman or Docker):
  task ci-init   # generate ci/sdk/ (run once)
  task ci        # run all gates locally

Before your first release, register for PyPI trusted publishing:
  pypi.org → Account Settings → Publishing → Add pending publisher
    Workflow: publish.yaml  |  Environment: pypi

Happy coding!
""",
    file=sys.stdout,
)

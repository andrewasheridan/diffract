"""[[ cookiecutter.project_slug ]]: [[ cookiecutter.description ]]."""

__all__ = [
    "__version__",
]

import importlib.metadata

try:
    __version__: str = importlib.metadata.version("[[ cookiecutter.project_slug ]]")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0+unknown"

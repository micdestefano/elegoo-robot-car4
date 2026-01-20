#  Copyright (c) Michele De Stefano - 2026.

import importlib.metadata

from .car import Car


def get_pkg_version(pkg_name: str) -> str:  # pragma: no cover
    """
    Retrieves the version of an installed package.

    Args:
        pkg_name: The name of the package.

    Returns:
        The version of the installed package.
        Returns "not-installed" if the package is not installed.
    """
    try:
        version = importlib.metadata.version(pkg_name)
    except importlib.metadata.PackageNotFoundError:
        version = "not-installed"

    return version


__all__ = [Car]
__version__ = get_pkg_version("elegoo-robot-car4")

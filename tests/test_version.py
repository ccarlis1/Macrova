"""Tests for src/__version__.py — canonical package version."""

import re

from src.__version__ import __version__


def test_version_is_nonempty_string():
    assert isinstance(__version__, str)
    assert __version__.strip() == __version__
    assert __version__


def test_version_is_semver_shaped():
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__), (
        f"__version__ must be MAJOR.MINOR.PATCH, got {__version__!r}"
    )

"""Hermetic Playwright browser helper for Bazel."""

import os
from pathlib import Path
import sys
from playwright.sync_api import Browser, Playwright


def find_runfiles_dir() -> Path | None:
    """Locates the Bazel runfiles directory."""
    for env_var in ("PYTHON_RUNFILES", "RUNFILES_DIR", "TEST_SRCDIR"):
        val = os.environ.get(env_var)
        if val and Path(val).is_dir():
            return Path(val)

    current = Path(__file__).resolve()
    for parent in current.parents:
        if parent.name.endswith(".runfiles"):
            return parent

    for p in sys.path:
        p_path = Path(p).resolve()
        for parent in [p_path] + list(p_path.parents):
            if parent.name.endswith(".runfiles"):
                return parent

    return None


def get_chromium_executable() -> str:
    """Returns path to the hermetic Chromium binary from Bazel runfiles."""
    search_dirs: list[Path] = []
    runfiles = find_runfiles_dir()
    if runfiles:
        search_dirs.append(runfiles)

    search_dirs.extend([
        Path(__file__).resolve().parent,
        Path.cwd(),
    ])

    for base_dir in search_dirs:
        if not base_dir.exists():
            continue
        for p in base_dir.rglob("chrome"):
            if "playwright_chromium" in str(p) and p.is_file() and os.access(p, os.X_OK):
                return str(p)
        for p in base_dir.rglob("Google Chrome for Testing"):
            if "playwright_chromium" in str(p) and p.is_file() and os.access(p, os.X_OK):
                return str(p)
        for p in base_dir.rglob("chrome"):
            if p.is_file() and os.access(p, os.X_OK):
                return str(p)

    raise FileNotFoundError(
        "Hermetic Chromium binary not found in Bazel runfiles."
    )


def launch_browser(playwright_instance: Playwright, headless: bool = True) -> Browser:
    """Launches Playwright Chromium with hermetic executable."""
    executable_path = get_chromium_executable()
    return playwright_instance.chromium.launch(
        executable_path=executable_path,
        headless=headless,
    )

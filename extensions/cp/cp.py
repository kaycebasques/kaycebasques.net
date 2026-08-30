import fnmatch
import os
import shutil
from pathlib import Path
from sphinx.application import Sphinx


def copy_files(app: Sphinx, exception: Exception | None) -> None:
    if exception:
        return

    patterns = getattr(app.config, "cp", [])
    if not patterns:
        return

    srcdir = Path(app.srcdir)
    outdir = Path(app.outdir)

    for root, _, files in os.walk(srcdir):
        for file in files:
            file_path = Path(root) / file
            rel_path = file_path.relative_to(srcdir)
            rel_str = str(rel_path)

            should_copy = False
            for pattern in patterns:
                if pattern.startswith("."):
                    if file.endswith(pattern):
                        should_copy = True
                        break
                elif pattern.isalnum():
                    if file.endswith(f".{pattern}"):
                        should_copy = True
                        break
                else:
                    if fnmatch.fnmatch(file, pattern) or fnmatch.fnmatch(rel_str, pattern):
                        should_copy = True
                        break

            if should_copy:
                dest_path = outdir / rel_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, dest_path)


def setup(app: Sphinx) -> dict[str, bool]:
    app.add_config_value("cp", [], "html")
    app.connect("build-finished", copy_files)
    return {
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }

from pathlib import Path


def setup(app):
    app.add_html_theme("theme", Path(__file__).resolve().parent)
    return {
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }

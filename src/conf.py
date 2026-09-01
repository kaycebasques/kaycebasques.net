# General
project = "kaycebasques.net"
release = "0.0.0"
author = "Kayce Basques"
copyright = f"2026, {author}"
exclude_patterns = ["BUILD.bazel"]

# Extensions
extensions = [
    "theme",
    "dragon",
    "sitemap",
    "posts",
    "metadata2",
]

# Posts
posts = [
    "blog/**/*",
]

# HTML
html_theme = "theme"
html_baseurl = "https://kaycebasques.net"
html_permalinks_icon = "§"
html_short_title = "kaycebasques.net"
html_extra_path = ["extra"]

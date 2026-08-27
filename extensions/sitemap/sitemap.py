from sphinx.application import Sphinx


def generate_sitemap(app: Sphinx, exception: Exception | None) -> None:
    if exception:
        return
    urls = []
    base_url = (app.config.html_baseurl or "").rstrip("/")
    for docname in app.project.docnames:
        urls.append(f"{base_url}/{docname}.html")
    urls.sort()
    sitemap = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for url in urls:
        sitemap += f"  <url><loc>{url}</loc></url>\n"
    sitemap += "</urlset>\n"
    with open(f"{app.outdir}/sitemap.xml", "w", encoding="utf-8") as f:
        f.write(sitemap)


def setup(app: Sphinx) -> dict[str, bool]:
    app.connect("build-finished", generate_sitemap)
    return {
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }

import fnmatch
from datetime import datetime
from sphinx.application import Sphinx
from sphinx.errors import ExtensionError


def set_page_context(app: Sphinx, pagename: str, templatename: str, context: dict, doctree):
    meta = context.get('meta', {})
    posts_config = getattr(app.config, 'posts', [])
    patterns = [posts_config] if isinstance(posts_config, str) else list(posts_config)

    # Require :desc: metadata on all content pages (source documents)
    if pagename in app.env.found_docs:
        desc = meta.get('desc') if meta else None
        if not desc:
            raise ExtensionError(f"Page '{pagename}' is missing required ':desc:' metadata at the very top.")
        context['desc'] = desc

    # If page matches posts config and has date, configure post context and template
    if any(fnmatch.fnmatch(pagename, pat) for pat in patterns):
        date = meta.get('date') if meta else None
        if date:
            try:
                dt = datetime.fromisoformat(date)
                date_str = dt.strftime('%Y%m%d')
            except (ValueError, TypeError):
                date_str = date.replace('-', '')

            context['date'] = date_str
            return 'post.html'


def setup(app: Sphinx):
    if 'posts' not in app.config.values:
        app.add_config_value('posts', [], 'env')
    app.connect('html-page-context', set_page_context)
    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }

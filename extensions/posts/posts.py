import fnmatch
from datetime import datetime
from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx.application import Sphinx


class PostsNode(nodes.General, nodes.Element):
    pass


class PostsDirective(Directive):
    has_content = False

    def run(self):
        return [PostsNode('')]


def process_posts(app: Sphinx, doctree: nodes.document, fromdocname: str) -> None:
    posts_nodes = list(doctree.findall(PostsNode)) if hasattr(doctree, 'findall') else doctree.traverse(PostsNode)
    if not posts_nodes:
        return

    posts_config = getattr(app.config, 'posts', [])
    patterns = [posts_config] if isinstance(posts_config, str) else list(posts_config)

    env = app.env
    posts = []
    for docname, metadata in env.metadata.items():
        if any(fnmatch.fnmatch(docname, pat) for pat in patterns):
            if 'date' in metadata:
                title_node = env.titles.get(docname)
                title_text = title_node.astext() if title_node else docname
                posts.append({
                    'docname': docname,
                    'title': title_text,
                    'date': metadata.get('date', ''),
                    'desc': metadata.get('desc', ''),
                })

    # Sort posts by date descending
    posts.sort(key=lambda x: x['date'], reverse=True)

    for node in posts_nodes:
        container = nodes.container(classes=['posts'])
        for i, post in enumerate(posts):
            if i > 0:
                container += nodes.transition()

            post_item = nodes.container(classes=['post-item'])

            # Date of the post
            date_val = post['date']
            try:
                dt = datetime.fromisoformat(date_val)
                date_str = dt.strftime('%Y%m%d')
            except (ValueError, TypeError):
                date_str = date_val.replace('-', '')

            date_para = nodes.paragraph('', date_str, classes=['post-date'])
            post_item += date_para

            # Blog post title as a link
            uri = app.builder.get_relative_uri(fromdocname, post['docname'])
            title_para = nodes.paragraph('', '', classes=['post-title'])
            ref_node = nodes.reference('', post['title'], refuri=uri)
            title_para += ref_node
            post_item += title_para

            # Description
            if post['desc']:
                desc_para = nodes.paragraph('', post['desc'], classes=['post-desc'])
                post_item += desc_para

            container += post_item

        node.replace_self(container)


def setup(app: Sphinx) -> dict[str, bool | str]:
    if 'posts' not in app.config.values:
        app.add_config_value('posts', [], 'env')
    app.add_node(PostsNode)
    app.add_directive('posts', PostsDirective)
    app.connect('doctree-resolved', process_posts)
    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }

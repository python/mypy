"""Script that converts from CHANGELOG.md (markdown) to HTML suitable for a mypy blog post.

How to use:

1. Write release notes in CHANGELOG.md.
2. MAke sure the heading for the next release is of form `## Mypy X.Y`.
2. Run `misc/gen_glob_post_html.py X.Y > target.html`.
4. Manually inspect and tweak the result.

Notes:

* There are some fragile assumptions. Double check the output.
"""

import argparse
import html
import os
import re
import sys


def format_lists(h: str) -> str:
    a = h.splitlines()
    r = []
    i = 0
    while i < len(a):
        if a[i].startswith('- '):
            r.append('<ul>')
            while i < len(a) and a[i].startswith('- '):
                r.append('<li>%s' % a[i][2:])
                i += 1
            r.append('</ul>')
        else:
            r.append(a[i])
            i += 1
    return '\n'.join(r)


def format_code(h: str) -> str:
    a = h.splitlines()
    r = []
    i = 0
    while i < len(a):
        if a[i].startswith('    '):
            r.append('<pre>')
            while i < len(a) and a[i].startswith('    '):
                # Undo &gt; and &lt;
                line = a[i].replace('&gt;', '>').replace('&lt;', '<')
                r.append(html.escape(line))
                i += 1
            r.append('</pre>')
        else:
            r.append(a[i])
            i += 1
    return '\n'.join(r)


def convert(src: str) -> str:
    h = src

    ## Remove everything before the blog post
    #h = re.sub(r'^.*?(?= Blog post: Mypy)', '', h, flags=re.DOTALL)

    ## Remove do not edit note.
    #h = re.sub(r'\n\*\*NOTE: Do not.*\*\*\n', '\n', h)

    # Replace < and >.
    h = re.sub(r'<', '&lt;', h)
    h = re.sub(r'>', '&gt;', h)

    # Title
    h = re.sub(r'(?:# )?(?:Blog post: +)?(Mypy .*? Released)', r'<h1>\1</h1>', h)

    # Subheadings
    h = re.sub(r'\n## ([A-Z`].*)\n', r'\n<h2>\1</h2>\n', h)

    # Sub-subheadings
    h = re.sub(r'\n\*\*([A-Z_`].*)\*\*\n', r'\n<h3>\1</h3>\n', h)
    h = re.sub(r'\n`\*\*([A-Z_`].*)\*\*\n', r'\n<h3>`\1</h3>\n', h)

    # Translate `**`
    h = re.sub(r'`\*\*`', '<tt>**</tt>', h)

    # Paragraphs
    h = re.sub(r'\n([A-Z])', r'\n<p>\1', h)

    # Bullet lists
    h = format_lists(h)

    # Code blocks
    h = format_code(h)

    # Code fragments
    h = re.sub(r'`([^`]+)`', r'<tt>\1</tt>', h)

    # Remove **** noise
    h = re.sub(r'\*\*\*\*', '', h)

    # Bold text
    h = re.sub(r'\*\*([A-Za-z].*?)\*\*', r' <b>\1</b>', h)

    # Emphasized text
    h = re.sub(r' \*([A-Za-z].*?)\*', r' <i>\1</i>', h)

    # Remove redundant PR links to avoid double links (they will be generated below)
    h = re.sub(r'\[(#[0-9]+)\]\(https://github.com/python/mypy/pull/[0-9]+/?\)', r'\1', h)

    # Issue and PR links
    h = re.sub(r'\((#[0-9]+)\) +\(([^)]+)\)', r'(\2, \1)', h)
    h = re.sub(r'fixes #([0-9]+)', r'fixes issue <a href="https://github.com/python/mypy/issues/\1">\1</a>', h)
    h = re.sub(r'#([0-9]+)', r'PR <a href="https://github.com/python/mypy/pull/\1">\1</a>', h)
    h = re.sub(r'\) \(PR', ', PR', h)

    # Markdown links
    h = re.sub(r'\[([^]]*)\]\(([^)]*)\)', r'<a href="\2">\1</a>', h)

    # Add random links in case they are missing
    h = re.sub(r'contributors to typeshed:',
               'contributors to <a href="https://github.com/python/typeshed">typeshed</a>:', h)

    # Add missing top-level HTML tags
    h = '<html>\n<meta charset="utf-8" />\n<body>\n' + h + '</body>\n</html>'

    return h


def extract_version(src: str, version: str) -> str:
    a = src.splitlines()
    i = 0
    heading = f"## Mypy {version}"
    while i < len(a):
        if a[i].strip() == heading:
            break
        i += 1
    else:
        raise RuntimeError(f"Can't find heading {heading!r}")
    j = i + 1
    while not a[j].startswith("## "):
        j += 1
    return "\n".join(a[i:j])


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate release blog post (HTML) based on CHANGELOG.md.")
    parser.add_argument("version")
    args = parser.parse_args()
    version: str = args.version
    if not re.match(r"[0-9]+(\.[0-9]+)+$", version):
        sys.exit(f"error: Version must be of form X.Y or X.Y.Z, not {version!r}")
    changelog_path = os.path.join(os.path.dirname(__file__), os.path.pardir, "CHANGELOG.md")
    src = open(changelog_path).read()
    src = extract_version(src, version)
    dst = convert(src)
    sys.stdout.write(dst)


if __name__ == '__main__':
    main()

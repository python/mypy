"""Converter from CHANGELOG.md (Markdown) to HTML suitable for a mypy blog post.

How to use:

1. Write release notes in CHANGELOG.md.
2. Make sure the heading for the next release is of form `## Mypy X.Y`.
2. Run `misc/gen_blog_post_html.py X.Y > target.html`.
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
    bullets = ("- ", "* ", " * ")
    while i < len(a):
        if a[i].startswith(bullets):
            r.append("<p><ul>")
            while i < len(a) and a[i].startswith(bullets):
                r.append("<li>%s" % a[i][2:].lstrip())
                i += 1
            r.append("</ul>")
        else:
            r.append(a[i])
            i += 1
    return "\n".join(r)


def format_code(h: str) -> str:
    a = h.splitlines()
    r = []
    i = 0
    while i < len(a):
        if a[i].startswith("    ") or a[i].startswith("```"):
            indent = a[i].startswith("    ")
            language: str = ""
            if not indent:
                language = a[i][3:]
                i += 1
            if language:
                r.append(f'<pre><code class="language-{language}">')
            else:
                r.append("<pre><code>")
            while i < len(a) and (
                (indent and a[i].startswith("    ")) or (not indent and not a[i].startswith("```"))
            ):
                # Undo &gt; and &lt;
                line = a[i].replace("&gt;", ">").replace("&lt;", "<")
                if indent:
                    # Undo this extra level of indentation so it looks nice with
                    # syntax highlighting CSS.
                    line = line[4:]
                r.append(html.escape(line))
                i += 1
            r.append("</code></pre>")
            if not indent and a[i].startswith("```"):
                i += 1
        else:
            r.append(a[i])
            i += 1
    formatted = "\n".join(r)
    # remove empty first line for code blocks
    return re.sub(r"<code([^\>]*)>\n", r"<code\1>", formatted)


def convert(src: str) -> str:
    h = src

    # Replace < and >.
    h = re.sub(r"<", "&lt;", h)
    h = re.sub(r">", "&gt;", h)

    # Title
    h = re.sub(r"^## (Mypy [0-9.]+)", r"<h1>\1 Released</h1>", h, flags=re.MULTILINE)

    # Subheadings
    h = re.sub(r"\n### ([A-Z`].*)\n", r"\n<h2>\1</h2>\n", h)

    # Sub-subheadings
    h = re.sub(r"\n\*\*([A-Z_`].*)\*\*\n", r"\n<h3>\1</h3>\n", h)
    h = re.sub(r"\n`\*\*([A-Z_`].*)\*\*\n", r"\n<h3>`\1</h3>\n", h)

    # Translate `**`
    h = re.sub(r"`\*\*`", "<tt>**</tt>", h)

    # Paragraphs
    h = re.sub(r"\n\n([A-Z])", r"\n\n<p>\1", h)

    # Bullet lists
    h = format_lists(h)

    # Code blocks
    h = format_code(h)

    # Code fragments
    h = re.sub(r"``([^`]+)``", r"<tt>\1</tt>", h)
    h = re.sub(r"`([^`]+)`", r"<tt>\1</tt>", h)

    # Remove **** noise
    h = re.sub(r"\*\*\*\*", "", h)

    # Bold text
    h = re.sub(r"\*\*([A-Za-z].*?)\*\*", r" <b>\1</b>", h)

    # Emphasized text
    h = re.sub(r" \*([A-Za-z].*?)\*", r" <i>\1</i>", h)

    # Remove redundant PR links to avoid double links (they will be generated below)
    h = re.sub(r"\[(#[0-9]+)\]\(https://github.com/python/mypy/pull/[0-9]+/?\)", r"\1", h)

    # Issue and PR links
    h = re.sub(r"\((#[0-9]+)\) +\(([^)]+)\)", r"(\2, \1)", h)
    h = re.sub(
        r"fixes #([0-9]+)",
        r'fixes issue <a href="https://github.com/python/mypy/issues/\1">\1</a>',
        h,
    )
    # Note the leading space to avoid stomping on strings that contain #\d in the middle (such as
    # links to PRs in other repos)
    h = re.sub(r" #([0-9]+)", r' PR <a href="https://github.com/python/mypy/pull/\1">\1</a>', h)
    h = re.sub(r"\) \(PR", ", PR", h)

    # Markdown links
    h = re.sub(r"\[([^]]*)\]\(([^)]*)\)", r'<a href="\2">\1</a>', h)

    # Add random links in case they are missing
    h = re.sub(
        r"contributors to typeshed:",
        'contributors to <a href="https://github.com/python/typeshed">typeshed</a>:',
        h,
    )

    # Add top-level HTML tags and headers for syntax highlighting css/js.
    # We're configuring hljs to highlight python and bash code. We can remove
    # this configure call to make it try all the languages it supports.
    h = f"""<html>
<meta charset="utf-8" />
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/a11y-light.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script>hljs.configure({{languages:["python","bash"]}});hljs.highlightAll();</script>
<body>
{h}
</body>
</html>"""

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
    parser = argparse.ArgumentParser(
        description="Generate HTML release blog post based on CHANGELOG.md and write to stdout."
    )
    parser.add_argument("version", help="mypy version, in form X.Y or X.Y.Z")
    args = parser.parse_args()
    version: str = args.version
    if not re.match(r"[0-9]+(\.[0-9]+)+$", version):
        sys.exit(f"error: Version must be of form X.Y or X.Y.Z, not {version!r}")
    changelog_path = os.path.join(os.path.dirname(__file__), os.path.pardir, "CHANGELOG.md")
    src = open(changelog_path).read()
    src = extract_version(src, version)
    dst = convert(src)
    sys.stdout.write(dst)


if __name__ == "__main__":
    main()

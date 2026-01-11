# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
import subprocess
from sphinx.application import Sphinx
from sphinx.util.docfields import Field

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
sys.path.insert(0, os.path.abspath("../.."))

from mypy.version import __version__ as mypy_version

# -- General configuration ------------------------------------------------

extensions = [
    "sphinx.ext.intersphinx",
    "sphinx_inline_tabs",
    "docs.source.html_builder",
    "myst_parser",
]

templates_path = ["_templates"]
source_suffix = ".rst"
master_doc = "index"
project = "mypy"
copyright = "2012-%Y Jukka Lehtosalo and mypy contributors"

version = mypy_version.split("-")[0]
release = mypy_version

exclude_patterns = [
    "build",
    "Thumbs.db",
    ".DS_Store",
]

# -- Options for HTML output ----------------------------------------------

html_theme = "furo"

# --- DYNAMIC BRANCH DETECTION FOR EDIT BUTTON ---
def get_git_branch():
    try:
        # Check if running on ReadTheDocs
        if os.environ.get("READTHEDOCS") == "True":
            return os.environ.get("READTHEDOCS_GIT_IDENTIFIER", "master")
        
        # Otherwise, get the current branch from git locally
        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"]
        ).decode("utf-8").strip()
    except Exception:
        return "master"

current_branch = get_git_branch()

html_theme_options = {
    "source_repository": "https://github.com/python/mypy",
    "source_branch": current_branch,
    "source_directory": "docs/source",
}
# ------------------------------------------------

html_logo = "mypy_light.svg"
html_static_path = ['_static']

rst_prolog = ".. |...| unicode:: U+2026   .. ellipsis\n"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "attrs": ("https://www.attrs.org/en/stable/", None),
    "cython": ("https://cython.readthedocs.io/en/stable", None),
    "monkeytype": ("https://monkeytype.readthedocs.io/en/latest", None),
    "setuptools": ("https://setuptools.pypa.io/en/latest", None),
}

def setup(app: Sphinx) -> None:
    app.add_object_type(
        "confval",
        "confval",
        objname="configuration value",
        indextemplate="pair: %s; configuration value",
        doc_field_types=[
            Field("type", label="Type", has_arg=False, names=("type",)),
            Field("default", label="Default", has_arg=False, names=("default",)),
        ],
    )

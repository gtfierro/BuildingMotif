###############################################################################
# Auto-generated by `jupyter-book config`
# If you wish to continue using _config.yml, make edits to that file and
# re-generate this one.
###############################################################################
add_module_names = False
author = "NREL"
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "undoc-members": True,
    "private-members": False,
}
autosummary_generate = True
bibtex_bibfiles = ["bibliography.bib"]
comments_config = {"hypothesis": False, "utterances": False}
copyright = "2022"
exclude_patterns = ["**.ipynb_checkpoints", ".DS_Store", "Thumbs.db", "_build"]
execution_allow_errors = False
execution_excludepatterns = []
execution_in_temp = False
execution_timeout = 30
extensions = [
    "sphinx_togglebutton",
    "sphinx_copybutton",
    "myst_nb",
    "jupyter_book",
    "sphinx_thebe",
    "sphinx_comments",
    "sphinx_external_toc",
    "sphinx.ext.intersphinx",
    "sphinx_design",
    "sphinx_book_theme",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinxcontrib.bibtex",
    "sphinx_jupyterbook_latex",
]
external_toc_exclude_missing = False
external_toc_path = "_toc.yml"
html_baseurl = ""
html_favicon = ""
html_logo = ""
html_sourcelink_suffix = ""
html_theme = "sphinx_book_theme"
html_theme_options = {
    "search_bar_text": "Search this book...",
    "launch_buttons": {
        "notebook_interface": "classic",
        "binderhub_url": "https://mybinder.org",
        "jupyterhub_url": "",
        "thebe": False,
        "colab_url": "",
    },
    "path_to_docs": "docs",
    "repository_url": "https://github.com/NREL/BuildingMOTIF",
    "repository_branch": "main",
    "google_analytics_id": "",
    "extra_navbar": 'Powered by <a href="https://jupyterbook.org">Jupyter Book</a>',
    "extra_footer": "",
    "home_page_in_toc": True,
    "announcement": "⚠️ This is an ALPHA release for testing purposes only ⚠️",
    "use_repository_button": True,
    "use_edit_page_button": False,
    "use_issues_button": True,
}
html_title = "BuildingMOTIF Documentation"
jupyter_cache = ""
jupyter_execute_notebooks = "force"
latex_engine = "pdflatex"
myst_enable_extensions = [
    "colon_fence",
    "dollarmath",
    "linkify",
    "substitution",
    "tasklist",
]
myst_url_schemes = ["mailto", "http", "https"]
nb_output_stderr = "show"
numfig = True
pygments_style = "sphinx"
suppress_warnings = ["myst.domains"]
use_jupyterbook_latex = True
use_multitoc_numbering = True

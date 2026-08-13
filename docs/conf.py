# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import os
import sys

# Add the project root directory to the system path
sys.path.insert(0, os.path.abspath("../"))

# Import sphinx_rtd_theme
try:
    import sphinx_rtd_theme
except ImportError:
    print("Error: sphinx_rtd_theme is not installed. Please install it using 'pip install sphinx_rtd_theme'.")

project = "FoundationDesign"
copyright = "2024, Kunle Yusuf"
author = "Kunle Yusuf"
release = "0.0.7"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

# Sphinx extensions
extensions = [
    "sphinx.ext.autodoc",
    "sphinx_rtd_theme",  # Added theme to extensions list
]

# Paths for templates and exclusions
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# Set theme to sphinx_rtd_theme
html_theme = "sphinx_rtd_theme"

# Paths for static files (e.g., CSS)
html_static_path = ["_static"]

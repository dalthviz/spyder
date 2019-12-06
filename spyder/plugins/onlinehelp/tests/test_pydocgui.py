# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
#

"""
Tests for pydocgui.py
"""
# Standard library imports
import sys

# Test library imports
import pytest

# Local imports
from spyder.plugins.onlinehelp.widgets import PydocBrowser
from spyder.py3compat import PY3


@pytest.fixture
def pydocbrowser(qtbot):
    """Set up pydocbrowser."""
    widget = PydocBrowser(None)
    qtbot.addWidget(widget)
    return qtbot, widget


def test_pydocbrowser(pydocbrowser):
    """Run Pydoc Browser."""
    qtbot, browser = pydocbrowser
    assert browser


@pytest.mark.parametrize(
    "lib", [('str', 'class str', 1),
            ('numpy.compat', 'numpy.compat', 2)
            ])
@pytest.mark.skipif(sys.platform == 'darwin' and PY3,
                    reason="Times out on macOS with Python 3")
def test_get_pydoc(pydocbrowser, lib):
    """
    Go to the documentation by url.
    Regression test for spyder-ide/spyder#10740
    """
    qtbot, browser = pydocbrowser
    element, doc, matches = lib
    webview = browser.webview
    with qtbot.waitSignal(webview.loadFinished, timeout=6000):
        browser.initialize()
    element_url = browser.text_to_url(element)
    with qtbot.waitSignal(webview.loadFinished):
        browser.set_url(element_url)
    # Check number of matches. In Python 2 are 3 matches instead
    # of 2 for numpy.compat
    qtbot.waitUntil(
        lambda: webview.get_number_matches(doc) in [matches, matches + 1])


if __name__ == "__main__":
    pytest.main()

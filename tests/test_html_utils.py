from bs4 import BeautifulSoup, Comment

from aiselectors.html_utils import clean_html


def test_clean_html():
    # Unit test to test clean_html function
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Title</title>
        <style>.hidden { display: none; }</style>
        <script>console.log('hello');</script>
    </head>
    <body>
        <!-- Comment to be removed -->
        <div>Visible content</div>
        <div class="hidden">Hidden content</div>
        <svg><g></g></svg>
        <link href="styles.css">
    </body>
    </html>
    """
    cleaned_html = clean_html(html)
    soup = BeautifulSoup(cleaned_html, "html.parser")

    assert not soup.find_all(string=lambda text: isinstance(text, Comment))
    assert not soup.head
    assert not soup.script
    assert not soup.style
    assert not soup.svg
    assert not soup.link
    assert "Hidden content" not in cleaned_html
    assert "Visible content" in cleaned_html
    assert soup.find("div", text="Visible content")

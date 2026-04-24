from src.html_parser import extract_visible_text, html_to_tokens, tokenize


def test_tokenize_lowercases_words():
    assert tokenize("Good FRIENDS") == ["good", "friends"]


def test_tokenize_removes_punctuation():
    assert tokenize("Hello, world!") == ["hello", "world"]


def test_extract_visible_text_removes_script_and_style():
    html = """
    <html>
        <head><style>.hidden { color: red; }</style></head>
        <body>
            <script>alert("bad")</script>
            <p>Hello world</p>
        </body>
    </html>
    """

    text = extract_visible_text(html)

    assert "Hello world" in text
    assert "alert" not in text
    assert "color" not in text


def test_html_to_tokens_extracts_clean_tokens():
    html = "<html><body><p>Good friends, good books.</p></body></html>"

    assert html_to_tokens(html) == ["good", "friends", "good", "books"]

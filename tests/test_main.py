from unittest.mock import patch

from src.main import main


@patch("src.main.SearchCLI")
def test_main_creates_and_runs_cli(mock_cli):
    instance = mock_cli.return_value

    with patch(
        "sys.argv",
        [
            "main.py",
            "--start-url",
            "https://quotes.toscrape.com/",
            "--index-path",
            "data/index.json",
            "--politeness-window",
            "0",
        ],
    ):
        main()

    mock_cli.assert_called_once()

    instance.run.assert_called_once()

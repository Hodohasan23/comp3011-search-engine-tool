install:
	python -m pip install -r requirements.txt

test:
	python -m pytest

coverage:
	python -m pytest --cov=src --cov-report=term-missing

lint:
	python -m ruff check src tests

format:
	python -m ruff format src tests
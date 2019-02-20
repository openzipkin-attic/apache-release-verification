.PHONY: lint

lint:
	black src/*.py
	isort src/*.py
	flake8 src/*.py
	mypy src/*.py

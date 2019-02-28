PRECOMMIT_SRC=.githooks/pre-commit
PRECOMMIT_DST=.git/hooks/pre-commit

${PRECOMMIT_DST}: ${PRECOMMIT_SRC}
	cp $< $@

.PHONY: upgrade-dependencies
upgrade-dependencies: venv
	./venv/bin/pip-compile --upgrade requirements.txt
	./venv/bin/pip-compile --upgrade requirements-dev.txt

.PHONY: venv
venv:
	[ -d ./venv ] || virtualenv --python=python3 venv
	[ -e ./venv/bin/pip-sync ] || ./venv/bin/pip install pip-tools
	./venv/bin/pip-sync requirements.txt requirements-dev.txt

.PHONY: setup-dev
setup-dev: venv ${PRECOMMIT_DST}

.DEFAULT_GOAL := lint
.PHONY: lint
lint: setup-dev
	black src/*.py
	isort src/*.py
	flake8 src/*.py
	mypy src/*.py

.PHONY: clean
clean:
	rm -rf src/*.pyc src/__pycache__ .mypy_cache ./venv

PYTHON := .venv/bin/python

.PHONY: setup test demo lint bench

setup:
	$(PYTHON) -m pip install --disable-pip-version-check -e '.[dev]'

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check src examples tests benchmarks

demo:
	$(PYTHON) -m src.cli record --output runs/recorded.json
	$(PYTHON) -m src.cli replay examples/traces/success.json --output runs/replayed.json
	$(PYTHON) -m src.cli inject examples/traces/success.json --fault examples/faults/retry.json --output runs/retry.json
	$(PYTHON) -m src.cli inject examples/traces/success.json --fault examples/faults/fallback.json --output runs/fallback.json
	$(PYTHON) -m src.cli inject examples/traces/success.json --fault examples/faults/fail_fast.json --output runs/fail_fast.json
	$(PYTHON) -m src.cli report runs/

bench:
	$(PYTHON) -m benchmarks.run_benchmarks --runs 100

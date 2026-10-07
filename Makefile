PYTHON ?= python3

.PHONY: setup test study verify

setup:
	$(PYTHON) -m pip install -r requirements-dev.txt

test:
	$(PYTHON) -m pytest -q

study:
	$(PYTHON) nerc.py
	$(PYTHON) datagen.py --samples 1000 --seed 42
	$(PYTHON) train_model.py
	$(PYTHON) verify_evidence.py

verify:
	$(PYTHON) verify_evidence.py

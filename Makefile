# SPDX-License-Identifier: MIT
PYTHON ?= python3
VENV   ?= .venv

.PHONY: help install build serve lighthouse clean

help:
	@echo "make install    - create venv and install dependencies"
	@echo "make build      - build public/ from essays/ + src/"
	@echo "make serve      - build and serve public/ on http://localhost:8000"
	@echo "make lighthouse - run a local Lighthouse audit (needs npx)"
	@echo "make clean      - remove public/ and venv"

$(VENV)/bin/python:
	$(PYTHON) -m venv $(VENV) || (which uv && uv venv $(VENV))
	$(VENV)/bin/python -m pip install -U pip || $(VENV)/bin/python -m ensurepip --upgrade
	$(VENV)/bin/python -m pip install -r requirements.txt

install: $(VENV)/bin/python

build: install
	$(VENV)/bin/python scripts/build.py

serve: build
	@echo "Serving public/ on http://localhost:8000"
	$(PYTHON) -m http.server 8000 -d public

lighthouse: build
	@echo "Running Lighthouse on built public/"
	npx --yes lhci autorun

clean:
	rm -rf public $(VENV) lighthouse-*.html .lighthouseci

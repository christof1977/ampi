.PHONY: run env install clean 
# .SILENT:

## 
## Makefile for ampi
## -------------------------
## ⁣
## This file contains various targets for the Ampi things bums.

ENV?=env
VENV?=venv
PYTHON?=python3

SRC:=gui
ENV_BIN:=$(ENV)/bin
ENV_PYTHON:=$(ENV_BIN)/$(PYTHON)

## ⁣
## Deployment:

run:		## run to the hills 
run: env
	$(ENV_PYTHON) main.py

env: $(ENV_BIN)/activate install
#env:
$(ENV_BIN)/activate: requirements.txt
	test -d $(ENV) || $(PYTHON) -m $(VENV) --system-site-packages $(ENV)
	$(ENV_PYTHON) -m ensurepip --upgrade
	$(ENV_PYTHON) -m pip install -qq --upgrade pip
	$(ENV_PYTHON) -m pip install -qq -r requirements.txt
	touch ./$(ENV_BIN)/activate

install:	## install project in editable mode
	$(ENV_PYTHON) -m pip install -qq -e .

## ⁣
## Helpers:

doc:
	./makedocs.sh 

clean:		## Remove generated files (env, docs, ...)
	rm -rf $(ENV)
	rm -rf docs/_build/*.*
	rm -rf docs/coverage/*.*


help:		## Show this help
	@sed -ne '/@sed/!s/## //p' $(MAKEFILE_LIST)

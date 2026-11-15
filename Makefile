NAME     := ft_otp
VENV     := .venv
PYTHON   := $(VENV)/bin/python
REQS     := requirements.txt
# Marker file: rebuilt (pip install re-run) whenever requirements.txt changes.
STAMP    := $(VENV)/.installed

all: $(STAMP)
	@chmod +x $(NAME)
	@echo "Virtual environment ready. Activate it with: source $(VENV)/bin/activate (or run: make shell)"

# make cannot activate the venv in the calling terminal (each recipe runs in a
# child shell), so open a new shell with the venv active. Leave it with `exit`.
shell: all
	@echo "Entering $(VENV) shell. Type 'exit' to leave."
	@VIRTUAL_ENV="$(abspath $(VENV))" PATH="$(abspath $(VENV))/bin:$$PATH" exec $${SHELL:-/bin/bash}

# Create the virtual environment only if it does not exist yet.
$(PYTHON):
	python3 -m venv $(VENV)

# `| $(PYTHON)`: order-only, so an existing venv is never recreated.
$(STAMP): $(REQS) | $(PYTHON)
	$(PYTHON) -m pip install -r $(REQS)
	@touch $@

test: all
	$(PYTHON) -m pytest

clean:
	find . -path ./$(VENV) -prune -o -name __pycache__ -type d -exec rm -rf {} +
	rm -rf .pytest_cache

fclean: clean
	rm -rf $(VENV)

# Separate make call: this one would still believe the deleted venv exists.
re: fclean
	$(MAKE) all

.PHONY: all shell test clean fclean re

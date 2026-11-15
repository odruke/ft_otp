# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

42 Cybersecurity Piscine project `ft_otp` (full subject: `en.subject.pdf`). Implement a TOTP generator (RFC 6238) built on HOTP (RFC 4226), in Python.

Mandatory requirements from the subject:
- Executable must be named `ft_otp`.
- `-g <file>`: read a hex key of **at least 64 hex characters** from the file, store it **encrypted** in `ft_otp.key`, print `Key was successfully saved in ft_otp.key.` On invalid key: `./ft_otp: error: key must be 64 hexadecimal characters.`
- `-k <file>`: read `ft_otp.key`, generate a 6-digit one-time password and print it to stdout.
- **Using a TOTP/HOTP library is forbidden.** The HMAC/truncation algorithm must be hand-written; libraries for crypto primitives (hashlib/hmac, encryption of the key file) and system time are allowed.
- Output must match the reference tool used at evaluation: `oathtool --totp $(cat key.hex)` (30 s step, SHA-1, 6 digits by default).
- Bonus (only graded if mandatory is perfect): QR code with seed generation, graphical interface.

## Commands

Use the project venv (`.venv/`, has pytest and the Python `oathtool` package from `requirements.txt`).

```bash
make                                # create .venv from requirements.txt (re-installs when it changes)
make shell                          # new shell with .venv active (`exit` to leave); make cannot activate it in the current terminal
make test | clean | fclean | re     # fclean deletes .venv
source .venv/bin/activate
./ft_otp -g key.hex                 # store encrypted key
./ft_otp -k ft_otp.key              # print OTP
./ft_otp --debug                    # verbose logging
./ft_otp -t                         # run the test suite (pytest, from the project root)
python -m pytest tests/test_cli.py::test_defaults   # single test
PYTHONPATH=src python -m ft_otp     # run as a module
```

pytest is configured in `pyproject.toml` (`testpaths = tests`, `pythonpath = src`), so no install is needed to run tests.

## Architecture

src layout: the package is `src/ft_otp/`; the root `ft_otp` file is only a launcher that puts `src/` on `sys.path` and calls `ft_otp.app.main` (the subject requires an executable with this exact name, runnable without installing).

- `app.py` — `main(argv) -> int` exit code: parse options, set up logging, run tests or open the menu. Dispatch for new actions goes here.
- `cli.py` — `build_parser()` + `parse_arguments(argv)` returning a frozen `Options` dataclass (`key_to_store` = `-g FILE`, `key_file` = `-k FILE`, `interface`, `run_tests`, `debug`). Pass an explicit `argv` list in tests.
- `menu.py` — curses menu (intended as the bonus interface). Menus are registered by name in `constants.MENUS` as `(prompt, options)`; `run_menu(name)` returns the chosen option string.
- `logging_setup.py`, `constants.py` (also `PROJECT_ROOT`).

Current state: `-g`, `-k` and `-i` are parsed but not yet acted on; `main()` always launches the menu unless `-t`.

## Memory

- At the start of a task, read `MEMORY.md`.
- At the end, update it: current state, important decisions with their why, and pitfalls. Keep it ~50 lines; summarise or drop what no longer helps.
- Propose moving permanent rules to CLAUDE.md instead of keeping them in memory.
- Never store secrets or personal data.

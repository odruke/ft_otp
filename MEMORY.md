# MEMORY.md
Last updated: 2026-11-11

## Current state
- Restructured into a src layout (`src/ft_otp/` package, `tests/`, `pyproject.toml`, `.gitignore`); behaviour unchanged.
- Skeleton only: argparse options, logging setup and a curses menu with a single "Exit" entry.
- `-g` / `-k` / `-i` are parsed but have no implementation (no HOTP/TOTP code, no key encryption yet).
- `tests/test_cli.py` covers argument parsing only.
- `.venv/` has pytest and the Python `oathtool` package (requirements.txt is a pip freeze).
- Not a git repository yet.
- `makefile` (lowercase, user-created) builds `.venv` from requirements.txt; a stamp file `.venv/.installed` re-runs pip when requirements.txt changes. `re` calls `$(MAKE) all` separately so the venv is really rebuilt.
- Pending user decisions before the constitution: passphrase→seed method, salt, `.env` location, no-args behaviour, QR content, hex input rules, dropping the Python `oathtool` package. Recommended: the app (not make) creates `.env`.

## Decisions (each with its why)
- Root `ft_otp` is a thin launcher that adds `src/` to `sys.path`: the subject requires running `./ft_otp` without installing anything.
- Options are a frozen dataclass instead of a TypedDict keyed by constants: the old TypedDict declared keys that never matched the real ones, so type checking was useless.
- `-g`/`-k` take a single value (no `nargs=1`), so they are `str | None`, not lists.
- `main()` returns an int exit code, passed to `sys.exit`, so `-t` propagates pytest's result.
- curses menu is the planned "graphical interface" bonus.

## Pitfalls to avoid
- TOTP/HOTP libraries (e.g. pyotp) are forbidden by the subject; implement HMAC truncation by hand.
- `ft_otp.key` is ignored in `.gitignore`; never commit a real key.
- The `ft_otp` launcher shebang is `/usr/bin/env python3`: without an active venv it runs system Python, which lacks venv-only dependencies (e.g. `cryptography` once added).
- `-t` runs `sys.executable -m pytest`: run it with the venv active, otherwise system Python has no pytest.

## Next step
Implement `-g` (validate ≥64 hex chars, encrypt, write `ft_otp.key`) and `-k` (decrypt, HOTP with counter = unix_time // 30, 6 digits) and compare against `oathtool --totp`.

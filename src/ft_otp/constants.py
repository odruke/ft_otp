"""Shared constants."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Menu actions
EXIT = "Exit"

# Menus: name -> (prompt, options)
MENUS: dict[str, tuple[str, list[str]]] = {
    "base": ("exit from this menu\n\n", [EXIT]),
}

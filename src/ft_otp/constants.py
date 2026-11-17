"""Shared constants."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Menu actions
EXIT = "Exit"
KEEP = "Keep the existing key and exit"
REPLACE = "Replace the existing file with the new hex input"
CANCEL = "Cancel"
ERASE = "Erase ft_otp.key and .env"
NO = "No"
YES = "Yes"

# Menus: name -> (prompt, options). The safe option is always listed first,
# so an accidental Enter never replaces or erases anything.
MENUS: dict[str, tuple[str, list[str]]] = {
    "base": ("exit from this menu\n\n", [EXIT]),
    "key_exists": (
        "ft_otp.key already exists, select an option\n\n",
        [KEEP, REPLACE],
    ),
    "reset": ("Select an option\n\n", [CANCEL, ERASE]),
    "confirm": ("Are you sure?\n\n", [NO, YES]),
}

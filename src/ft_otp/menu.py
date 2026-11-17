"""Interactive curses menu."""

import curses

from ft_otp.constants import MENUS

ENTER_KEYS = (curses.KEY_ENTER, 10, 13)


def select(stdscr: curses.window, prompt: str, options: list[str]) -> int:
    """Show options with arrow-key navigation; return the chosen index."""
    selected = 0

    while True:
        stdscr.clear()
        stdscr.addstr(prompt)
        for index, option in enumerate(options):
            marker = ">" if index == selected else " "
            stdscr.addstr(f"{marker} {option}\n")

        key = stdscr.getch()
        if key == curses.KEY_UP:
            selected = (selected - 1) % len(options)
        elif key == curses.KEY_DOWN:
            selected = (selected + 1) % len(options)
        elif key in ENTER_KEYS:
            return selected


def show_menu(stdscr: curses.window, name: str, details: str = "") -> str:
    """Display the menu registered as `name` and return the chosen option.

    `details` is shown above the registered prompt (e.g. warnings).
    """
    prompt, options = MENUS[name]
    return options[select(stdscr, details + prompt, options)]


def run_menu(name: str, details: str = "") -> str:
    """Open a curses session, show the menu `name`, return the choice."""
    return curses.wrapper(show_menu, name, details)

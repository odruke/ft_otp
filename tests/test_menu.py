"""Tests for the menus registry and run_menu (spec 001, task T7).

curses itself is only checked manually; here a fake screen replaces it.
"""

import curses

import pytest

from ft_otp import menu
from ft_otp.constants import CANCEL, ERASE, KEEP, MENUS, NO, REPLACE, YES


class FakeScreen:
    """Records what is drawn and returns the queued keys."""

    def __init__(self, keys: list[int]) -> None:
        self.keys = keys
        self.text = ""

    def clear(self) -> None:
        self.text = ""

    def addstr(self, text: str) -> None:
        self.text += text

    def getch(self) -> int:
        return self.keys.pop(0)


def run_with_keys(monkeypatch: pytest.MonkeyPatch, keys: list[int]) -> FakeScreen:
    screen = FakeScreen(keys)
    monkeypatch.setattr(curses, "wrapper", lambda func, *args: func(screen, *args))
    return screen


@pytest.mark.parametrize(
    ("name", "options"),
    [
        ("key_exists", [KEEP, REPLACE]),
        ("reset", [CANCEL, ERASE]),
        ("confirm", [NO, YES]),
    ],
)
def test_menus_list_the_safe_option_first(name: str, options: list[str]) -> None:
    assert MENUS[name][1] == options


def test_confirm_menu_asks_are_you_sure() -> None:
    assert "Are you sure?" in MENUS["confirm"][0]


def test_run_menu_shows_details_before_the_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    screen = run_with_keys(monkeypatch, [10])
    choice = menu.run_menu("reset", "Existing files: .env\n")
    assert choice == CANCEL
    assert screen.text.startswith("Existing files: .env\n")
    assert MENUS["reset"][0] in screen.text


def test_run_menu_without_details(monkeypatch: pytest.MonkeyPatch) -> None:
    screen = run_with_keys(monkeypatch, [curses.KEY_DOWN, 10])
    assert menu.run_menu("key_exists") == REPLACE
    assert screen.text.startswith(MENUS["key_exists"][0])

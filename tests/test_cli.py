import pytest

from ft_otp.cli import parse_arguments


def test_no_action_is_an_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        parse_arguments([])
    assert excinfo.value.code == 2


def test_two_actions_are_an_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        parse_arguments(["-g", "key.hex", "-k", "ft_otp.key"])
    assert excinfo.value.code == 2


def test_generate_alone() -> None:
    options = parse_arguments(["-g", "key.hex"])
    assert options.key_to_store == "key.hex"
    assert options.key_file is None


def test_key_alone() -> None:
    options = parse_arguments(["-k", "ft_otp.key"])
    assert options.key_file == "ft_otp.key"
    assert options.key_to_store is None


def test_interface_alone() -> None:
    assert parse_arguments(["-i"]).interface


def test_run_tests_alone() -> None:
    assert parse_arguments(["-t"]).run_tests


def test_debug_with_an_action() -> None:
    options = parse_arguments(["-t", "--debug"])
    assert options.run_tests and options.debug


def test_reset_alone() -> None:
    options = parse_arguments(["--reset"])
    assert options.reset
    assert options.key_to_store is None and not options.run_tests


def test_reset_with_another_action_is_an_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        parse_arguments(["--reset", "-g", "key.hex"])
    assert excinfo.value.code == 2

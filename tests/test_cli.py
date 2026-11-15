from ft_otp.cli import Options, parse_arguments


def test_defaults() -> None:
    assert parse_arguments([]) == Options(
        key_to_store=None,
        key_file=None,
        interface=False,
        run_tests=False,
        debug=False,
    )


def test_generate_and_key_take_a_single_path() -> None:
    options = parse_arguments(["-g", "key.hex", "-k", "ft_otp.key"])
    assert options.key_to_store == "key.hex"
    assert options.key_file == "ft_otp.key"


def test_flags() -> None:
    options = parse_arguments(["-i", "-t", "--debug"])
    assert options.interface and options.run_tests and options.debug

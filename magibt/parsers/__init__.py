"""One module per vendor: magibt/parsers/<name>.py exposing parse(msg, bill) -> dict.

The module name matches the bill's `name` in bills.toml; `bill` is that
bill's table from bills.toml (for fixed values such as an IBAN).
"""
import importlib


def get_parser(name):
    return importlib.import_module(f"magibt.parsers.{name}").parse

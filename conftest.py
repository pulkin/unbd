import pytest


def pytest_addoption(parser):
    parser.addoption("--runmetal", action="store_true", default=False, help="run tests for bare metal")


def pytest_configure(config):
    config.addinivalue_line("markers", "runmetal: mark tests to run on bare metal")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runmetal"):
        return
    skip_metal = pytest.mark.skip(reason="need --runmetal option to run")
    for item in items:
        if "metal" in item.keywords:
            item.add_marker(skip_metal)

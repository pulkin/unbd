import pytest


def pytest_addoption(parser):
    parser.addoption("--runmetal", action="store_true", default=False, help="run tests for bare metal")
    parser.addoption("--nbd", action="store", default="nbd-server")


nbd_server_cmd = None


def pytest_configure(config):
    config.addinivalue_line("markers", "runmetal: mark tests to run on bare metal")
    global nbd_server_cmd
    nbd_server_cmd = config.getoption("--nbd")



def pytest_collection_modifyitems(config, items):
    if config.getoption("--runmetal"):
        return
    skip_metal = pytest.mark.skip(reason="need --runmetal option to run")
    for item in items:
        if "metal" in item.keywords:
            item.add_marker(skip_metal)

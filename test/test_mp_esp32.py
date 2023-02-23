from inspect import getsource, signature
from textwrap import dedent
import socket
import sys

import pytest

from test_cp_linux import nbd_server


pytestmark = pytest.mark.metal
board = None
test_host = socket.gethostbyname(socket.gethostname())


def pipe(out, err, err_msg):
    sys.stdout.write(out.decode())
    sys.stderr.write(err.decode())
    if len(err):
        raise RuntimeError(f"MCU: {err_msg}")


def setup_module(module, imports=("from unbd import Client", )):
    from mpremote.pyboard import Pyboard
    module.board = Pyboard("/dev/ttyUSB0")
    module.board.enter_raw_repl()

    def wifi_connect():
        from credentials import wlan_login, wlan_pass
        from network import WLAN, STA_IF
        from time import sleep, time

        station = WLAN(STA_IF)
        station.active(True)
        station.disconnect()
        station.connect(wlan_login, wlan_pass)
        t = time() + 10
        while time() < t:
            if station.isconnected():
                break
            sleep(0.1)
        else:
            raise RuntimeError("still not connected after timeout")
        print(station.ifconfig())
    wifi_connect_src = dedent(getsource(wifi_connect))

    class raises:
        def __init__(self, e):
            self.e = e

        def __enter__(self):
            pass

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_val is None:
                raise RuntimeError(f"{self.e} not raised")
            if issubclass(exc_type, self.e):
                return True
    raises_src = dedent(getsource(raises))

    print("Set up mc ...")
    try:
        pipe(*module.board.exec_raw(wifi_connect_src), "error while compiling 'wifi_connect'")
        pipe(*module.board.exec_raw("wifi_connect()"), "error while executing wifi_connect()")
        pipe(*module.board.exec_raw(raises_src), "error while compiling 'raises'")
        for i in imports:
            pipe(*module.board.exec_raw(i), f"error while importing '{i}'")
    except:
        teardown_module(module)
        raise


def teardown_module(module):
    module.board.exit_raw_repl()


def _strip_decorators(source_code, until):
    source_code = source_code.split("\n")
    for i, line in enumerate(source_code):
        if line == until:
            break
    else:
        raise ValueError(f"decorator {until} not found")
    return "\n".join(source_code[i + 1:])


def runs_on_metal(func):
    sig = signature(func)
    source_code = _strip_decorators(dedent(getsource(func)), "@runs_on_metal")
    f_name = func.__name__

    def _result(port=sig.parameters["port"].default, data=sig.parameters["data"].default):
        with nbd_server(port, data) as args:
            pipe(*board.exec_raw(source_code), f"error while compiling '{f_name}'")
            pipe(*board.exec_raw(f"{f_name}(host={repr(test_host)})"),
                 f"error while running '{f_name}' host={test_host}")

    return _result


@runs_on_metal
def test_read(host, port=33567, data=b"Hello world"):
    with Client(host, port) as c:
        assert c.size == len(data)
        assert c.read(1, 3) == data[1:4]
        assert c.read(0, len(data)) == data


@runs_on_metal
def test_read_out_of_bounds(host, port=33567, data=b"Hello world"):
    with Client(host, port) as c:
        with raises(RuntimeError):
            c.read(10, 1024)
        assert c.read(10, 1) == data[10:11]


@runs_on_metal
def test_write(host, port=33567, data=b"Hello world"):
    with Client(host, port) as c:
        c.write(0, b"hola ")
        assert c.read(0, len(data)) == b"hola  world"


@runs_on_metal
def test_write_out_of_bounds(host, port=33567, data=b"Hello world"):
    with Client(host, port) as c:
        with raises(RuntimeError):
            c.write(10, b"xxx")
        assert c.read(0, len(data)) == data

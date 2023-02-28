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


def setup_module(module, imports=("from unbd import Client, BlockClient, connect", )):
    from mpremote.pyboard import Pyboard
    module.board = Pyboard("/dev/ttyUSB0")
    module.board.enter_raw_repl()

    def wifi_connect():
        from credentials import wlan_login, wlan_pass
        import network
        from network import WLAN, STA_IF, AP_IF
        from time import sleep, time

        WLAN(AP_IF).active(False)
        nic = WLAN(STA_IF)
        nic.active(False)
        nic.active(True)
        nic.connect(wlan_login, wlan_pass)

        t = time() + 30
        while time() < t:
            if nic.isconnected():
                break
            sleep(0.1)
        else:
            status = nic.status()
            for i in dir(network):
                if i.startswith("STAT_") and getattr(network, i) == status:
                    status = i
                    break
            raise RuntimeError(f"still not connected after timeout; status={status}")
        print(nic.ifconfig())
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
        if line.startswith(until):
            break
    else:
        raise ValueError(f"decorator {until} not found")
    return "\n".join(source_code[i + 1:])


def fat_image(files, size=1024):
    from pyfatfs.PyFat import PyFat
    import fs
    import tempfile

    with tempfile.NamedTemporaryFile("rb+") as f:
        image = PyFat()
        image.mkfs(f.name, 12, size * 1024, label="NO NAME", number_of_fats=1)
        image._mark_clean()
        f.flush()
        f.seek(0)

        with fs.open_fs(f"fat://{f.name}", writeable=True) as image:
            for name, contents in files.items():
                with image.open(name, "w") as image_f:
                    image_f.write(contents)
        return f.read()


def runs_on_metal(port=33567, data=b"Hello world"):
    def _wrapper(func):
        sig = signature(func)
        source_code = _strip_decorators(dedent(getsource(func)), "@runs_on_metal")
        f_name = func.__name__

        def _result():
            with nbd_server(port, data):
                pipe(*board.exec_raw(source_code), f"error while compiling '{f_name}'")
                args = {
                    "host": repr(test_host),
                    "port": repr(port),
                    "data": repr(data),
                }
                args = {k: v for k, v in args.items() if k in sig.parameters}
                args = ', '.join(f"{k}={v}" for k, v in args.items())
                call_as = f"{f_name}({args})"
                pipe(*board.exec_raw(call_as), f"error while running {call_as}")

        return _result
    return _wrapper


@runs_on_metal()
def test_read(host, port, data):
    with Client(host, port) as c:
        assert c.size == len(data)
        assert c.read(1, 3) == data[1:4]
        assert c.read(0, len(data)) == data


@runs_on_metal()
def test_read_out_of_bounds(host, port, data):
    with Client(host, port) as c:
        with raises(RuntimeError):
            c.read(10, 1024)
        assert c.read(10, 1) == data[10:11]


@runs_on_metal()
def test_write(host, port, data):
    with Client(host, port) as c:
        c.write(0, b"hola ")
        assert c.read(0, len(data)) == b"hola  world"


@runs_on_metal()
def test_write_out_of_bounds(host, port, data):
    with Client(host, port) as c:
        with raises(RuntimeError):
            c.write(10, b"xxx")
        assert c.read(0, len(data)) == data


@runs_on_metal(data=fat_image({"/hello.txt": "Hello world"}))
def test_mount(host, port):
    import os
    os.mount(connect(host, port, 512), "/mount")
    try:
        with open("/mount/hello.txt", 'r') as f:
            assert f.read() == "Hello world"
    finally:
        os.umount("/mount")


@runs_on_metal(data=fat_image({}))
def test_mount_rw(host, port):
    import os
    os.mount(connect(host, port, 512), "/mount")
    try:
        with open("/mount/hello.txt", 'w') as f:
            f.write("Hello world")
        with open("/mount/hello.txt", 'r') as f:
            assert f.read() == "Hello world"
    finally:
        os.umount("/mount")

import subprocess
import sys
from contextlib import contextmanager
from tempfile import NamedTemporaryFile
from time import sleep
import os

import pytest
from conftest import nbd_server_cmd

from unbd import Client


@contextmanager
def nbd_server(port, data, delay=0.01):
    with NamedTemporaryFile("wb+") as f:
        f.write(data)
        f.flush()
        f.seek(0)
        os.chmod(f.name, 0o666)  # in case nbd-server runs as a different user
        p = subprocess.Popen([*nbd_server_cmd.split(), str(port), f.name, "-d"], stdout=sys.stdout, stderr=sys.stderr)
        try:
            sleep(delay)
            yield p, f
        finally:
            p.terminate()
            p.kill()  # enforce kill


def test_read(port=33567, data=b"Hello world"):
    with nbd_server(port, data):
        with Client('localhost', port) as c:
            assert c.size == len(data)
            assert c.read(1, 3) == data[1:4]
            assert c.read(0, len(data)) == data


def test_read_out_of_bounds(port=33567, data=b"Hello world"):
    with nbd_server(port, data):
        with Client('localhost', port) as c:
            with pytest.raises(RuntimeError):
                c.read(10, 1024)
            assert c.read(10, 1) == b"d"


def test_write(port=33567, data=b"Hello world"):
    with nbd_server(port, data) as (_, file):
        with Client('localhost', port) as c:
            c.write(0, b"hola ")
        assert file.read() == b"hola  world"


def test_write_out_of_bounds(port=33567, data=b"Hello world"):
    with nbd_server(port, data) as (_, file):
        with Client('localhost', port) as c:
            with pytest.raises(RuntimeError):
                c.write(10, b"xxx")
        assert file.read() == data

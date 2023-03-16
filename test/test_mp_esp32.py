from inspect import getsource
from textwrap import dedent
import socket
import sys
from scripts.snapmount import mounted
import pytest


pytestmark = pytest.mark.metal
board = None
test_host = socket.gethostbyname(socket.gethostname())


def pipe(out, err, err_msg):
    sys.stdout.write(out.decode())
    sys.stderr.write(err.decode())
    if len(err):
        raise RuntimeError(f"MCU: {err_msg}")


def _strip_decorators(source_code, until):
    source_code = source_code.split("\n")
    for i, line in enumerate(source_code):
        if line.startswith(until):
            break
    else:
        raise ValueError(f"decorator {until} not found")
    return "\n".join(source_code[i + 1:])


def runs_on_metal(mount, **kwargs):
    def _wrapper(func):
        source_code = _strip_decorators(dedent(getsource(func)), "@runs_on_metal")
        f_name = func.__name__

        def _result():
            with mounted(mount, **kwargs) as board:
                pipe(*board.exec_raw(source_code), f"error while compiling '{f_name}'")
                call_as = f"{f_name}()"
                pipe(*board.exec_raw(call_as, timeout=60), f"error while invoking {f_name}")

        return _result
    return _wrapper


@runs_on_metal({"/hello.txt": "Hello world"}, fs="lfs")
def test_mount_littlefs():
    with open("/mount/hello.txt", 'r') as f:
        assert f.read() == "Hello world"


@runs_on_metal({"/hello.txt": "Hello world"}, fs="fat")
def test_mount_fat():
    with open("/mount/hello.txt", 'r') as f:
        assert f.read() == "Hello world"


@runs_on_metal({}, fs="lfs")
def test_mount_littlefs_rw():
    with open("/mount/hello.txt", 'w') as f:
        f.write("Hello world")
    with open("/mount/hello.txt", 'r') as f:
        assert f.read() == "Hello world"


@runs_on_metal({}, fs="fat")
def test_mount_fat_rw():
    with open("/mount/hello.txt", 'w') as f:
        f.write("Hello world")
    with open("/mount/hello.txt", 'r') as f:
        assert f.read() == "Hello world"


@runs_on_metal({"test.txt": b"abcdefgh" * 12800}, block_size=512, fs="fat")
def test_perf_fat_512():
    from time import ticks_ms, ticks_diff
    t = ticks_ms()
    with open("/mount/test.txt", "rb") as f:
        size = len(f.read())
    dt = ticks_diff(ticks_ms(), t)
    print(f"fat 512 read {size * 0.001}k in {dt * 0.001}s at {size / dt:.1f}k/s")

    chunk = bytearray(size)
    t = ticks_ms()
    with open("/mount/test.txt", "wb") as f:
        f.write(chunk)
    dt = ticks_diff(ticks_ms(), t)
    print(f"fat 512 write {size * 0.001}k in {dt * 0.001}s at {size / dt:.1f}k/s")


@runs_on_metal({"test.txt": b"abcdefgh" * 12800}, block_size=1024, fs="fat")
def test_perf_fat_1k():
    from time import ticks_ms, ticks_diff
    t = ticks_ms()
    with open("/mount/test.txt", "rb") as f:
        size = len(f.read())
    dt = ticks_diff(ticks_ms(), t)
    print(f"fat 1k read {size * 0.001}k in {dt * 0.001}s at {size / dt:.1f}k/s")

    chunk = bytearray(size)
    t = ticks_ms()
    with open("/mount/test.txt", "wb") as f:
        f.write(chunk)
    dt = ticks_diff(ticks_ms(), t)
    print(f"fat 1k write {size * 0.001}k in {dt * 0.001}s at {size / dt:.1f}k/s")


@runs_on_metal({"test.txt": b"abcdefgh" * 12800}, block_size=2048, fs="fat")
def test_perf_fat_2k():
    from time import ticks_ms, ticks_diff
    t = ticks_ms()
    with open("/mount/test.txt", "rb") as f:
        size = len(f.read())
    dt = ticks_diff(ticks_ms(), t)
    print(f"fat 2k read {size * 0.001}k in {dt * 0.001}s at {size / dt:.1f}k/s")

    chunk = bytearray(size)
    t = ticks_ms()
    with open("/mount/test.txt", "wb") as f:
        f.write(chunk)
    dt = ticks_diff(ticks_ms(), t)
    print(f"fat 2k write {size * 0.001}k in {dt * 0.001}s at {size / dt:.1f}k/s")


@runs_on_metal({"test.txt": b"abcdefgh" * 12800}, block_size=4096, fs="fat")
def test_perf_fat_4k():
    from time import ticks_ms, ticks_diff
    t = ticks_ms()
    with open("/mount/test.txt", "rb") as f:
        size = len(f.read())
    dt = ticks_diff(ticks_ms(), t)
    print(f"fat 4k read {size * 0.001}k in {dt * 0.001}s at {size / dt:.1f}k/s")

    chunk = bytearray(size)
    t = ticks_ms()
    with open("/mount/test.txt", "wb") as f:
        f.write(chunk)
    dt = ticks_diff(ticks_ms(), t)
    print(f"fat 4k write {size * 0.001}k in {dt * 0.001}s at {size / dt:.1f}k/s")

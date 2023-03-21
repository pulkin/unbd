#!/usr/bin/env python
import argparse
from pathlib import Path
import tempfile
from inspect import getsource
from textwrap import dedent
import sys
import subprocess
import os
import socket
from contextlib import closing, contextmanager
from time import sleep
import logging
import serial.tools.list_ports

from mpremote.pyboard import Pyboard, PyboardError

import unbd


def collect_path(src: str) -> (dict[str, bytes], int):
    """
    Collects paths in the specified location.

    Parameters
    ----------
    src
        Root folder to collect from.

    Returns
    -------
    A dictionary `{file_name: file_content}` and
    the cumulative size of all files collected.
    """
    src = Path(src)
    result = {}
    size = 0
    for item in src.glob("**/*"):
        item_ = str(item.relative_to(src))
        if item.is_dir():
            result[item_] = None
        elif item.is_file():
            with open(item, 'rb') as f:
                result[item_] = f.read()
            size += item.stat().st_size
    if len(result) == 0:
        raise ValueError(f"not a directory: {src}")
    return result, size


def expand_path_items(src: dict) -> dict[str, str]:
    result = {}
    for path, content in src.items():
        for i in Path(path).parents[::-1]:
            i = str(i)
            if i != "/" and i != "." and i not in result:
                result[i] = None
        result[path] = content
    return result


def pipe(out: bytes, err: bytes, err_msg: str, silent=False):
    """
    Pipes output and err to stdout and stderr.
    Raises a `RuntimeError` if `err` is not empty.

    Parameters
    ----------
    out
    err
        Streams to pipe.
    err_msg
        Error message.
    silent
        If True, does not output stdout if no stderr avail.
    """
    if not silent:
        sys.stdout.write(out.decode())
    if len(err):
        sys.stderr.write(err.decode())
    if len(err) and err_msg is not None:
        raise RuntimeError(f"MCU error: {err_msg}")


def free_tcp_port() -> int:
    # source: stackoverflow
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def pretty_memory(num, suffix="B"):
    for unit in "", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi":
        if abs(num) < 1024:
            return f"{num:3.1f} {unit}{suffix}"
        num /= 1024
    return f"{num:.1f} Yi{suffix}"


def parse_size(s):
    s = s.lower()
    if s[-1] in "kmgt":
        return int(float(s[:-1]) * (0x400 << ("kmgt".index(s[-1]) * 10)))
    else:
        return int(s)


@contextmanager
def mounted(src: str, device: str = None, block_size: int = 512, size: int = None,
            image_fn: str = None, fs: str = "lfs", ssid: str = None, passphrase: str = None,
            nbd_server="nbd-server", endpoint="/mount", soft_reset: bool = True,
            unmount: bool = True, baud_rate: int = 115200):
    """
    Mount and unmount a copy of the provided folder.

    Parameters
    ----------
    src
        Folder to mount.
    device
        The micropython device.
    block_size
        The size of the block.
    size
        Total image size.
    image_fn
        File name of the image composed.
    fs
        File system: FAT or littlefs.
    ssid
        Wireless network to employ.
    passphrase
        Wireless passphrase.
    nbd_server
        Local executable for network block device server.
    endpoint
        Where to mount to.
    soft_reset
        If True, soft-resets the board.
    unmount
        If True, unmounts automatically.
    baud_rate
        Baud rate for serial communications.
    """
    if isinstance(src, str):
        copy_items, copy_size = collect_path(src)
        logging.info(f"path {src} contains {len(copy_items)} items; total size {pretty_memory(copy_size)}")
    else:
        copy_items = expand_path_items(src)
        copy_size = sum(len(i) for i in copy_items.values() if i is not None)

    estimated_size = 2 * (len(copy_items) + 1) * block_size + 1.5 * copy_size
    logging.info(f"  estimated image size {pretty_memory(estimated_size)}")
    if size is not None and size > estimated_size:
        estimated_size = size
        logging.info(f"  requested a larger image size {pretty_memory(size)}")

    if image_fn is None:
        out_file = tempfile.NamedTemporaryFile("wb")
    else:
        out_file = open(image_fn, "wb")
    image_fn = str(Path(out_file.name).absolute())
    logging.info(f"writing image to {image_fn}")

    if fs == "lfs":
        logging.info("using littlefs")
        from littlefs import LittleFS

        block_count = estimated_size // block_size + 1
        logging.info(f"  args: {block_size=} {block_count=}")
        image = LittleFS(block_size=block_size, block_count=block_count)
        image.makedir = image.makedirs

    elif fs == "fat":
        logging.info("using FAT")
        from pyfatfs.PyFat import PyFat
        from pyfatfs.PyFatFS import PyFatFS

        # create empty image
        image = PyFat()
        image_size = max(estimated_size, block_size * 0x4000)
        logging.info(f"  args: image_size={pretty_memory(image_size)} sector_size={block_size}")
        image.mkfs(out_file.name, 16, image_size, sector_size=block_size)
        image._mark_clean()
        out_file.flush()

        # copy
        image = PyFatFS(out_file.name)
    else:
        raise ValueError(f"unknown {fs=}")

    for name, content in copy_items.items():
        if content is None:
            image.makedir(name)
        else:
            with image.open(name, 'wb' if isinstance(content, bytes) else 'w') as f_dst:
                f_dst.write(content)

    if fs == "lfs":
        out_file.write(image.context.buffer)
    elif fs == "fat":
        image.fs._mark_clean()

    out_file.flush()

    # communicate with the board
    logging.info("connecting to board and checking network capabilities")
    if device is None:
        # copy-paste from mpremote
        # Auto-detect and auto-connect to the first available device.
        logging.info("no device specified")
        for p in sorted(serial.tools.list_ports.comports()):
            logging.info(f"trying {p.device}")
            try:
                board = Pyboard(p.device, baudrate=baud_rate)
                logging.info("  success")
                break
            except PyboardError as er:
                if not er.args[0].startswith("failed to access"):
                    raise er
        else:
            raise PyboardError("no device found")
    else:
        board = Pyboard(device, baudrate=baud_rate)

    board.enter_raw_repl(soft_reset=soft_reset)

    try:
        # determine network
        pipe(*board.exec_raw("import network"), "no 'network' module or import error")

        network_connected = False
        if ssid is None:
            out, err = board.exec_raw("print(network.WLAN(network.STA_IF).ifconfig()[0] == '0.0.0.0')")
            pipe(out, err, "network test error", silent=True)
            network_connected = not eval(out)

        if not network_connected:
            if ssid is None:
                # figure out host wlan
                # dummy check through nmcli assuming SSID
                # and passphrase are simple alphanumeric strings
                data = subprocess.check_output(["nmcli", "dev", "wifi", "show-password"], text=True)
                passphrase = None
                for line in data.split("\n"):
                    if line.startswith("SSID: "):
                        ssid = line[6:]
                    if line.startswith("Password: "):
                        passphrase = line[10:]
            if ssid is None:
                raise ValueError("no wifi ssid or password specified; board is not connected to wlan either")
            logging.info(f"connecting to wifi {repr(ssid)} (passphrase {repr(passphrase)})")

            def wlan_resilient_connect(wlan_login, wlan_pass, timeout=30_000, tick=500):
                from network import WLAN, STA_IF, AP_IF, STAT_CONNECTING
                from time import ticks_ms, ticks_diff, sleep_ms

                WLAN(AP_IF).active(False)
                nic = WLAN(STA_IF)
                nic.active(True)
                nic.disconnect()
                nic.connect(wlan_login, wlan_pass)
                sleep_ms(tick)

                if (status := nic.status()) != STAT_CONNECTING:
                    raise RuntimeError(f"connection not initiated; status={status}")

                t = ticks_ms()
                while ticks_diff(ticks_ms(), t) < timeout:
                    if nic.ifconfig()[0] != '0.0.0.0':
                        break
                    sleep_ms(tick)
                else:
                    raise RuntimeError(f"still not connected after timeout; status={nic.status()}")

            pipe(*board.exec_raw(dedent(getsource(wlan_resilient_connect))),
                 "failed to inject the code (wifi connect)")
            pipe(*board.exec_raw(f"wlan_resilient_connect({repr(ssid)}, {repr(passphrase)})"),
                 "failed to connect to wifi")
        else:
            logging.info("skip network setup (already connected)")

        # chmod: in case nbd-server complains
        os.chmod(out_file.name, 0o666)
        # determine server host and port
        host = socket.gethostbyname(socket.gethostname())
        port = free_tcp_port()
        logging.info(f"using {host}:{port} as nbd server")
        # start NBD server
        nbd_process = subprocess.Popen([*nbd_server.split(), str(port), image_fn, "-d"],
                                       stdout=sys.stdout, stderr=sys.stderr)
        sleep(0.1)

        logging.info("mounting")
        pipe(*board.exec_raw(getsource(unbd)), "error while injecting 'unbd.py'")
        if fs == "fat":
            _what = f"os.VfsFat(connect({repr(host)}, {repr(port)}, {repr(block_size)}))"
        elif fs == "lfs":
            _what = f"os.VfsLfs2(connect({repr(host)}, {repr(port)}, {repr(block_size)}), readsize={repr(block_size)})"
        pipe(*board.exec_raw(f"import os; os.mount({_what}, {repr(endpoint)})"), "error while mounting")

        if not unmount:
            logging.info("no unmount requested, releasing REPL")
            board.exit_raw_repl()
            board.close()
        logging.info("ready")
        try:
            yield board
        finally:
            logging.info("done")
            nbd_process.terminate()
            nbd_process.kill()
            logging.info("NBD server terminated")
    finally:
        if unmount:
            logging.info("unmounting")
            pipe(*board.exec_raw(f"import os; os.umount({repr(endpoint)})"), None)
            board.exit_raw_repl()
            board.close()


def main():
    arg_parser = argparse.ArgumentParser(description="Mounts a folder on a micropython device")
    arg_parser.add_argument("src", help="source directory on the host", metavar="FOLDER")
    arg_parser.add_argument("--device", help="target device")
    arg_parser.add_argument("--image-fn", help="temporary image file name on the host", metavar="IMAGE", default=None)
    arg_parser.add_argument("--block-size", help="block size", metavar="SIZE", type=int,
                            default=512, choices=[0x200, 0x400, 0x800, 0x1000])
    arg_parser.add_argument("--size", help="total image size", metavar="SIZE")
    arg_parser.add_argument("--fs", help="fs choice", metavar="FS", choices=["fat", "lfs"], default="lfs")
    arg_parser.add_argument("--ssid", help="SSID to connect to", default=None)
    arg_parser.add_argument("--passphrase", help="wifi network passphrase", default=None)
    arg_parser.add_argument("--addr", help="address of the NBD host", default=None)
    arg_parser.add_argument("--nbd-server", help="NBD server to use", metavar="COMMAND", default="nbd-server")
    arg_parser.add_argument("--endpoint", help="mount remote endpoint", metavar="PATH", default="/mount")
    arg_parser.add_argument("--soft-reset", help="soft-resets the board", action="store_true")
    arg_parser.add_argument("--payload", help="payload on the micropython device")
    arg_parser.add_argument("--baud-rate", help="serial baud rate", metavar="N", type=int, default=115200)
    arg_parser.add_argument("--verbose", help="verbose printing", action="store_true")
    args = arg_parser.parse_args()

    logging.basicConfig(
        format="[%(levelname)s] %(asctime)s %(message)s",
        datefmt="%H:%M:%S",
        level=logging.INFO if args.verbose else logging.ERROR
    )

    with mounted(args.src, device=args.device, block_size=args.block_size,
                 size=None if args.size is None else parse_size(args.size),
                 image_fn=args.image_fn, fs=args.fs, ssid=args.ssid, passphrase=args.passphrase,
                 nbd_server=args.nbd_server, endpoint=args.endpoint, soft_reset=args.soft_reset,
                 unmount=args.payload is not None, baud_rate=args.baud_rate) as board:
        if args.payload is None:
            while True:
                sleep(10_000)
        else:
            pipe(*board.exec_raw(
                args.payload,
                data_consumer=lambda d: sys.stdout.write(d.decode()),
                timeout=None,
            ), "payload error", silent=True)


if __name__ == "__main__":
    main()

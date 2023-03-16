[![build](https://github.com/pulkin/unbd/actions/workflows/test.yml/badge.svg)](https://github.com/pulkin/unbd/actions)
[![pypi](https://img.shields.io/pypi/v/unbd)](https://pypi.org/project/unbd/)

unbd
====

uNBD - micro implementation of
[network block device](https://en.wikipedia.org/wiki/Network_block_device)
in python.

What for?
---------

Network block device is a protocol to communicate block storage devices
or files over the network.
This package implements a client to the NBD suitable to run on
network-enabled micropython devices such as `ESP8266` and `ESP32`.
It is also compatible with regular cpython setups.

How to use
----------

Install `nbd` on your Linux machine and start the server

```shell
nbd-server 33567 /full/path/to/fs.img -d
```

Install `unbd` on your micropython device

```shell
mpremote mip install github:pulkin/unbd
```

Mount the remote device

```python
from unbd import connect
import os
os.mount(connect('192.168.0.123', 33567, open=True), "/mount")
```

`fs.img` located on the Linux machine contains FAT image.

Command-line tools
------------------

### `snapmount.py`

For host machines, this package includes `snapmount.py` script
which builds an image of a local folder and mounts it on your
micropython device using `unbd`.
The primary purpose of `snapmount.py` is to streamline the
development of large many-file applications for micropython and
to eliminate the need of using flash memory when deploying test
builds.

Key features:
- mounts an image of a folder with a single command
- integrates with tests: mount, run and unmount
- faster than `mpremote mount`
- no micropython setup needed (provided enough RAM)
- tiny footprint

Example
```bash
snapmount.py src --verbose --payload="print(os.listdir('/mount'))" --block-size=4096 --size=4m
```

Performance
-----------

The mounted filesystem speeds range from several Kbps up to
100 Kbps in read and write. The final throughput is roughly the
ratio `block_size / network_latency`. Thus, to achieve maximal
performance:

- increase `block_size` (4096 is about the saturated maximum)
- ensure the wireless connection is stable

FAT filesystem is, in general, twice as fast as `littlefs` for
reading large files.

Examples
--------

Simply mount the partition with default values (micropython)

```python
from unbd import connect
os.mount(connect(host, port, open=True), "/mount")
```

Mount `littlefs` with a large block size

```python
os.mount(os.VfsLfs2(connect(host, port, block_size=4096), readsize=4096), "/mount")
```

Mount FAT with a large block size

```python
os.mount(os.VfsFat(connect(host, port, block_size=4096)), "/mount")
```

License
-------

[LICENSE.md](LICENSE.md)

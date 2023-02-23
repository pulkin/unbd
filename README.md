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

How to use
----------

Install `nbd` on your Linux machine and start the server

```shell
nbd-server 33567 fs.img -d
```

Install `unbd` on your micropython device and mount the remote device

```python
from unbd import connect
import uos
uos.mount(connect('192.168.0.123', 33567), "/mount_point")
```

`fs.img` located on the Linux machine contains FAT image.

License
-------

[LICENSE.md](LICENSE.md)

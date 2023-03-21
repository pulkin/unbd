[![build](https://github.com/pulkin/unbd/actions/workflows/test.yml/badge.svg)](https://github.com/pulkin/unbd/actions)
[![pypi](https://img.shields.io/pypi/v/unbd)](https://pypi.org/project/unbd/)

unbd
====

`unbd` - micro implementation of a
[network block device](https://en.wikipedia.org/wiki/Network_block_device)
in python.

What for?
---------

Use this package for mounting folders on wifi-enabled micropython
devices such as `ESP8266` and `ESP32`.

Install
-------

If you want to use `unbd` directly install it on
your micropython device through `mpremote`

```shell
mpremote mip install github:pulkin/unbd
```

To use `unbd` with cpython and/or in command-line
environment use `pip`

```shell
pip install git+https://github.com/pulkin/unbd
```

How to use
----------

First, install `nbd` server on your host computer: it will
serve file system images over your local network.
Then, use the `snapmount` script on the host or the `unbd`
module on the micropython device directly.

- using `snapmount`

  1. Install cpython package on your host computer
     ```bash
     pip install git+https://github.com/pulkin/unbd
     ```
  2. Connect your wifi-enabled micropython device to a serial port
     on your host computer
  3. Mount your source folder `src` with
     ```bash
     snapmount src
     ```

  Note that `snapmount` uses wifi to communicate host your
  micropython device in station mode with the host computer.
  It will attempt to deduce network credentials through
  Network Manager on Linux (`nmcli`). You may explicitly supply
  credentials through `--ssid` and `--passphrase`.

- manually

  1. Start NBD server on the host machine
    
     ```shell
     nbd-server 33567 /full/path/to/fs.img -d
     ```
    
  2. Connect and install `unbd` on your micropython device
    
     ```shell
     mpremote mip install github:pulkin/unbd
     ```
    
  3. Mount the remote device
    
     ```python
     from unbd import connect
     import os
     os.mount(connect('host-ip-address', 33567, open=True), "/mount")
     ```

  Note that `fs.img` located on the host machine contains FAT image.

Key features
------------

- fully virtual file system over wifi
- relatively high performance
- minimal setup needed
- tiny footprint
- no flash storage used (and no performance degradation
  for intensive IO)

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

### Real-world benchmarks

| Case                              | LittleFS 512 | FAT 512 | FAT 4096 |
|-----------------------------------|--------------|---------|----------|
| App: ~100Kb, tens of source files | 33s          | 12s     | 9s       | 

Examples
--------

### `unbd`

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

### Develop and test with `snapmount`

See also [bare-metal tests for this package](test/test_mp_esp32.py).

Running a test script `test.py` from `src`

```python
from snapmount import mounted

with mounted('src', endpoint="/", **kwargs) as board:
    out, err = board.exec_raw("import test")
    assert len(err) == 0
```

Same with `snapmount` in command line

```bash
snapmount src --ssid="ssid" --passphrase="secret" --endpoint=/ --payload="import test"
```

More options

```bash
snapmount src --verbose \
  --ssid="ssid" \
  --passphrase="secret" \
  --soft-reset \ 
  --endpoint=/ \
  --fs=fat \
  --block-size=4096 \
  --payload="import test"
```

License
-------

[LICENSE.md](LICENSE.md)

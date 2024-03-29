from struct import pack, pack_into, unpack
import socket


def _rq_message(t, offset, length, _work=bytearray(b"\x25\x60\x95\x13" + b"\x00" * 24)):
    # pack(">IHHQQI", 0x25609513, 0, t, _handle, offset, len(buf))
    _work[7] = t
    pack_into(">QI", _work, 16, offset, length)
    return _work


class Client:
    def __init__(self, host, port, name=b"", open=False, timeout=3):
        self.host = host
        self.port = port
        self.name = name
        self.socket_timeout = timeout

        self._socket = self._readinto = self._write = self.size = None

        if open:
            self.open()

    def open(self):
        self._socket = s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.socket_timeout)
        s.connect((self.host, self.port))
        f = s.makefile('br')
        self._readinto, self._write = f.readinto, s.sendall

        self.hello()
        self.size = self.select_export(self.name)

    def hello(self):
        buf = bytearray(18)
        if self._readinto(buf) != 18 or buf != b'NBDMAGICIHAVEOPT\x00\x03':
            raise RuntimeError(f"unexpected hello: {buf}")
        self._write(b'\x00\x00\x00\x03')

    def select_export(self, name: bytes):
        w = self._write
        w(pack(">8sII", b"IHAVEOPT", 1, len(name)))
        if len(name):
            w(name)
        buf = bytearray(10)
        if self._readinto(buf) < 10:
            raise RuntimeError("probably a non-existing export name")
        size, flags = unpack(">QH", buf)
        return size

    def _assert_response(self, handle=0, _buffer=bytearray(16)):
        self._readinto(_buffer)
        if _buffer[:8] != b"\x67\x44\x66\x98\x00\x00\x00\x00":
            raise RuntimeError(f"failed response header or request error: {_buffer}")
        r_handle = int.from_bytes(_buffer[8:], "big")
        if r_handle != handle:
            raise RuntimeError(f"unexpected response handle: {r_handle} != {handle}")

    def readinto(self, offset, buf):
        self._write(_rq_message(0, offset, len(buf)))
        self._assert_response()
        return self._readinto(buf)

    def write(self, offset, buf):
        w = self._write
        w(_rq_message(1, offset, len(buf)))
        w(buf)
        self._assert_response()

    def read(self, offset, length):
        result = bytearray(length)
        self.readinto(offset, result)
        return result

    def close(self):
        try:
            self._write(_rq_message(2, 0, 0))
        finally:
            self._socket.close()
            self._socket = self._readinto = self._write = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.close()
        except:
            pass
        return False


class BlockClient:
    def __init__(self, client, block_size=512):
        self.client = client
        self.block_size = block_size

    def readblocks(self, block_num, buf, offset=0):
        self.client.readinto(self.block_size * block_num + offset, buf)

    def writeblocks(self, block_num, buf, offset=0):
        self.client.write(self.block_size * block_num + offset, buf)

    def ioctl(self, op, arg):
        if op == 1:
            if self.client._socket is None:
                self.client.open()
        elif op == 2:
            try:
                if self.client._socket is not None:
                    self.client.close()
            except:
                pass
        if op == 4:
            return self.client.size // self.block_size
        elif op == 5:
            return self.block_size
        elif op == 6:
            return 0


def connect(host, port, block_size=512, name=b"", open=False):
    return BlockClient(Client(host, port, name, open=open), block_size)

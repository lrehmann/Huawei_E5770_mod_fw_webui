"""Read-only Huawei Balong container/newc inspection. Nothing here flashes a device.

Header layout is documented by forth32/balongflash (ptable.h). CRC16 is the
reflected CCITT polynomial, initialized to 0xffff, with a final XOR of 0xffff.
"""
from dataclasses import dataclass
from pathlib import PurePosixPath
import struct
import zlib
import lzma

HEADER = struct.Struct('<III8sII16s16s32sHI')
NAMES = {0x110000:'fastboot', 0x200000:'m3boot', 0x10000:'ptable',
         0x90000:'kernel', 0x220000:'vxworks', 0x230000:'m3image',
         0x240000:'dsp', 0x250000:'nvdload', 0x590000:'system',
         0x5a0000:'app', 0x5b0000:'web', 0xa0000:'oeminfo', 0xb0000:'cdrom'}


def crc_table():
    table = []
    for byte in range(256):
        value = byte
        for _ in range(8):
            value = (value >> 1) ^ (0x8408 if value & 1 else 0)
        table.append(value)
    return table


CRC_TABLE = crc_table()


def crc16(data):
    value = 0xffff
    for byte in data:
        value = CRC_TABLE[(byte ^ value) & 255] ^ (value >> 8)
    return value ^ 0xffff


@dataclass
class Partition:
    name: str
    code: int
    offset: int
    data: bytes
    header_crc_ok: bool
    block_crc_ok: bool
    version: str


def partitions(data, verify_blocks=True):
    if len(data) < 92 + HEADER.size or data[92:96] != bytes.fromhex('55aa5aa5'):
        raise ValueError('Not a supported raw Huawei Balong update container')
    pos = 92
    result = []
    while data[pos:pos+4] == bytes.fromhex('55aa5aa5'):
        if pos + HEADER.size > len(data):
            raise ValueError('Truncated partition header')
        fields = HEADER.unpack_from(data, pos)
        _, hsize, _, _, code, size, _, _, version, checksum, blocksize = fields
        if hsize < HEADER.size or hsize > 131072 or (hsize-HEADER.size) % 2 or pos+hsize+size > len(data):
            raise ValueError('Invalid partition bounds')
        payload = data[pos+hsize:pos+hsize+size]
        header = bytearray(data[pos:pos+HEADER.size])
        header[92:94] = b'\0\0'
        header_ok = crc16(header) == checksum
        block_ok = None
        if verify_blocks:
            if not blocksize:
                raise ValueError('Invalid CRC block size')
            expected = [crc16(payload[i:i+blocksize]) for i in range(0, size, blocksize)]
            crcdata = data[pos+HEADER.size:pos+hsize]
            actual = list(struct.unpack('<' + 'H'*(len(crcdata)//2), crcdata))
            block_ok = expected == actual
        result.append(Partition(NAMES.get(code,f'unknown-{code:08x}'),code,pos,payload,
                                header_ok,block_ok,version.rstrip(b'\0').decode(errors='replace')))
        pos += hsize + size
        pos = (pos + 3) & ~3
    return result


def decoded(data, limit=128*1024*1024):
    if data[:2] in (b'\x78\xda', b'\x78\x9c'):
        z = zlib.decompressobj()
        result = z.decompress(data, limit+1)
        if len(result)>limit or not z.eof:
            raise ValueError('Compressed partition is too large or incomplete')
        return result
    if data[:1] == b'\x5d' and data[5:13] == b'\xff'*8:
        z = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE, memlimit=256*1024*1024)
        result = z.decompress(data,max_length=limit+1)
        if len(result)>limit or not z.eof:
            raise ValueError('Compressed partition is too large or incomplete')
        return result
    return data


def cpio_entries(data, start=0):
    pos = start
    while True:
        if data[pos:pos+6] != b'070701' or pos+110>len(data):
            raise ValueError('Invalid or truncated newc archive')
        fields = [int(data[pos+6+i*8:pos+14+i*8],16) for i in range(13)]
        size, nsize = fields[6], fields[11]
        if nsize<1 or nsize>4096 or pos+110+nsize>len(data):
            raise ValueError('Invalid newc name')
        rawname = data[pos+110:pos+110+nsize]
        if not rawname.endswith(b'\0'):
            raise ValueError('Unterminated newc name')
        name = rawname[:-1].decode('utf-8')
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Unsafe newc name')
        begin = pos+110+nsize
        begin += (-(begin-start)) % 4
        if begin+size>len(data):
            raise ValueError('Truncated newc payload')
        payload = data[begin:begin+size]
        pos = begin+size
        pos += (-(pos-start)) % 4
        if name == 'TRAILER!!!':
            return pos
        yield {'name':name,'mode':fields[1],'uid':fields[2],'gid':fields[3],
               'size':size,'data':payload}

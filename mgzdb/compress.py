"""Compress and Decompress MGZ files.

Excellent compression can be achieved by decompressing the
zlib-compressed header, re-compressing it with lzma, and
then compressing the body separately with lzma.

Reverse the process by decompressing the lzma-compressed
header, re-compressing it with zlib, and then decompressing
the lzma-compressed body.
"""

import logging
import lzma
import struct
import time
import zlib


PREFIX_SIZE = 8
LOGGER = logging.getLogger(__name__)
ZLIB_WBITS = -15
LZMA_DICT_SIZE = 64 * 1024 * 1024
LZMA_FILTERS = [
    {
        'id': lzma.FILTER_LZMA2,
        'preset': 7 | lzma.PRESET_EXTREME,
        'dict_size': LZMA_DICT_SIZE
    }
]


def compress(data):
    """Compress from file."""
    start = time.time()
    header_len, _ = struct.unpack('<II', data.read(PREFIX_SIZE))
    zlib_header = data.read(header_len - PREFIX_SIZE)
    header = zlib.decompress(zlib_header, wbits=ZLIB_WBITS)
    lzma_header = lzma.compress(header, filters=LZMA_FILTERS)

    body = data.read()
    lzma_body = lzma.compress(body, filters=LZMA_FILTERS)

    size = PREFIX_SIZE + len(zlib_header) + len(body)
    new_size = PREFIX_SIZE + len(lzma_header) + len(lzma_body)

    LOGGER.info("compressed input to %.1f%% of original size (%d->%d) in %.2f seconds",
                (new_size / size) * 100, size, new_size, time.time() - start)
    return struct.pack('<II', len(lzma_header) + PREFIX_SIZE, 0) + lzma_header + lzma_body


def decompress(data):
    """Decompress from file."""
    start = time.time()

    header_len, _ = struct.unpack('<II', data.read(PREFIX_SIZE))
    lzma_header = data.read(header_len - PREFIX_SIZE)
    header = lzma.decompress(lzma_header)
    zlib_header = zlib.compress(header)[2:]

    body = lzma.decompress(data.read())

    LOGGER.info("decompressed in %.2f seconds", time.time() - start)
    return struct.pack('<II', len(zlib_header) + PREFIX_SIZE, 0) + zlib_header + body

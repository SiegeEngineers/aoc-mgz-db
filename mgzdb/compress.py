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

from mgz.util import Version


REVISION = 2
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


def compress_rev_1(data, version=None):
    """Compress from file."""
    start = time.time()
    if version == Version.AOK:
        prefix_size = 4
        header_len, = struct.unpack('<I', data.read(prefix_size))
    else:
        prefix_size = 8
        header_len, next_header = struct.unpack('<II', data.read(prefix_size))
    zlib_header = data.read(header_len - prefix_size)
    header = zlib.decompress(zlib_header, wbits=ZLIB_WBITS)
    lzma_header = lzma.compress(header, filters=LZMA_FILTERS)

    body = data.read()
    lzma_body = lzma.compress(body, filters=LZMA_FILTERS)

    size = prefix_size + len(zlib_header) + len(body)
    new_size = prefix_size + len(lzma_header) + len(lzma_body)

    LOGGER.info("compressed input to %.1f%% of original size (%d->%d) in %.2f seconds, rev 1",
                (new_size / size) * 100, size, new_size, time.time() - start)
    if version == Version.AOK:
        prefix = struct.pack('<I', len(lzma_header) + prefix_size)
    else:
        prefix = struct.pack('<II', len(lzma_header) + prefix_size, next_header)
    return prefix + lzma_header + lzma_body


def compress(data, version=None):
    """Compress from file."""
    start = time.time()
    if version == Version.AOK:
        prefix_size = 4
        header_len, = struct.unpack('<I', data.read(prefix_size))
    else:
        prefix_size = 8
        header_len, next_header = struct.unpack('<II', data.read(prefix_size))
    zlib_header = data.read(header_len - prefix_size)
    header = zlib.decompress(zlib_header, wbits=ZLIB_WBITS)

    lzma_header = lzma.compress(header, filters=LZMA_FILTERS)

    body = data.read()
    lzma_body = lzma.compress(body, filters=LZMA_FILTERS)

    size = prefix_size + len(zlib_header) + len(body)
    new_size = prefix_size + len(lzma_header) + len(lzma_body)

    LOGGER.info("compressed input to %.1f%% of original size (%d->%d) in %.2f seconds, rev %d",
                (new_size / size) * 100, size, new_size, time.time() - start, REVISION)
    if version == Version.AOK:
        prefix = struct.pack('<III', REVISION, len(lzma_header), header_len)
    else:
        prefix = struct.pack('<IIII', REVISION, len(lzma_header), header_len, next_header)
    return prefix + lzma_header + lzma_body


def decompress_rev_1(data, version=None):
    """Decompress from file."""
    start = time.time()

    if version == Version.AOK:
        prefix_size = 4
        header_len, = struct.unpack('<I', data.read(prefix_size))
    else:
        prefix_size = 8
        header_len, next_header = struct.unpack('<II', data.read(prefix_size))

    lzma_header = data.read(header_len - prefix_size)
    header = lzma.decompress(lzma_header)
    zlib_header = zlib.compress(header)[2:]

    body = lzma.decompress(data.read())

    LOGGER.info("decompressed in %.2f seconds", time.time() - start)
    if version == Version.AOK:
        prefix = struct.pack('<I', len(zlib_header) + prefix_size)
    else:
        prefix = struct.pack('<II', len(zlib_header) + prefix_size, next_header)
    return prefix + zlib_header + body


def decompress(data, version=None):
    """Decompress from file."""
    start = time.time()

    if version == Version.AOK:
        prefix_size = 4
        revision, lzma_len, header_len = struct.unpack('<III', data.read(12))
    else:
        prefix_size = 8
        revision, lzma_len, header_len, next_header = struct.unpack('<IIII', data.read(16))

    if revision > REVISION:
        data.seek(0)
        LOGGER.info("legacy compression, falling back to rev 1")
        return decompress_rev_1(data, version)
    LOGGER.info("using compression rev %d", revision)

    lzma_header = data.read(lzma_len)
    header = lzma.decompress(lzma_header)
    zlib_header = zlib.compress(header)[2:]
    diff = header_len - prefix_size - len(zlib_header)
    zlib_header += b'0' * diff

    body = lzma.decompress(data.read())

    LOGGER.info("decompressed in %.2f seconds", time.time() - start)
    if version == Version.AOK:
        prefix = struct.pack('<I', header_len)
    else:
        prefix = struct.pack('<II', header_len, next_header)
    return prefix + zlib_header + body


def compress_tiles(tiles):
    """Compress map tiles."""
    data = b''
    for tile in tiles:
        data += struct.pack('<bb', tile['terrain_id'], tile['elevation'])
    return lzma.compress(data, filters=LZMA_FILTERS)


def decompress_tiles(cdata, dimension):
    """Decompress map tiles."""
    x_coord = 0
    y_coord = 0
    tiles = []
    data = lzma.decompress(cdata)
    while y_coord < dimension:
        offset = ((y_coord * dimension) + x_coord) * 2
        terrain_id, elevation = struct.unpack('<bb', data[offset:offset + 2])
        tiles.append({'terrain_id': terrain_id, 'elevation': elevation, 'x': x_coord, 'y': y_coord})
        x_coord += 1
        if x_coord == dimension:
            x_coord = 0
            y_coord += 1
    return tiles


def compress_objects(objects):
    """Compress objects."""
    data = b''
    for obj in objects:
        player_num = obj['player_number'] if obj['player_number'] else 0
        data += struct.pack('<bbhff', player_num, obj['class_id'], obj['object_id'], obj['x'], obj['y'])
    return lzma.compress(data, filters=LZMA_FILTERS)


def decompress_objects(odata):
    """Decompress objects."""
    objects = []
    offset = 0
    data = lzma.decompress(odata)
    while offset < len(data):
        player_number, class_id, object_id, x, y = struct.unpack('<bbhff', data[offset:offset + 12])
        player_number = player_number if player_number > 0 else None
        objects.append(dict(player_number=player_number, class_id=class_id, object_id=object_id, x=x, y=y))
        offset += 12
    return objects

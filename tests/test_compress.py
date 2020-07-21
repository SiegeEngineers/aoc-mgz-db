import io
import struct
import unittest
import zlib

from mgz.util import Version
from mgzdb.compress import (
    compress, decompress, compress_rev_1, decompress_rev_1,
    compress_tiles, decompress_tiles,
    compress_objects, decompress_objects
)


class TestCompress(unittest.TestCase):

    def test_compress_rev_1(self):
        header = zlib_header = zlib.compress(b'1' * 100)[2:]
        body = b'0' * 100
        rec = struct.pack('<II', len(header) + 8, 0) + header + body
        compressed_rec = compress_rev_1(io.BytesIO(rec))
        self.assertEqual(rec, decompress_rev_1(io.BytesIO(compressed_rec)))

    def test_compress_fallback(self):
        header = zlib_header = zlib.compress(b'1' * 100)[2:]
        body = b'0' * 100
        rec = struct.pack('<II', len(header) + 8, 0) + header + body
        compressed_rec = compress_rev_1(io.BytesIO(rec))
        self.assertEqual(rec, decompress(io.BytesIO(compressed_rec)))

    def test_compress_aok(self):
        header = zlib_header = zlib.compress(b'1' * 100)[2:]
        body = b'0' * 100
        rec = struct.pack('<I', len(header) + 4) + header + body
        compressed_rec = compress(io.BytesIO(rec), version=Version.AOK)
        self.assertEqual(rec, decompress(io.BytesIO(compressed_rec), version=Version.AOK))

    def test_compress_rev_2(self):
        header = zlib_header = zlib.compress(b'1' * 100)[2:]
        body = b'0' * 100
        rec = struct.pack('<II', len(header) + 8, 0) + header + body
        compressed_rec = compress(io.BytesIO(rec))
        self.assertEqual(rec, decompress(io.BytesIO(compressed_rec)))

    def test_compress_tiles(self):
        tiles = [
            {'terrain_id': 1, 'elevation': 0, 'x': 0, 'y': 0},
            {'terrain_id': 2, 'elevation': 1, 'x': 1, 'y': 0},
            {'terrain_id': 1, 'elevation': 2, 'x': 0, 'y': 1},
            {'terrain_id': 2, 'elevation': 3, 'x': 1, 'y': 1}
        ]
        compressed_tiles = compress_tiles(tiles)
        self.assertEqual(tiles, decompress_tiles(compressed_tiles, 2))

    def test_compress_objects(self):
        objects = [
            {'player_number': None, 'class_id': 10, 'object_id': 100, 'x': 10.5, 'y': 75},
            {'player_number': 1, 'class_id': 70, 'object_id': 500, 'x': 20.5, 'y': 23},
            {'player_number': 2, 'class_id': 80, 'object_id': 44, 'x': 80.5, 'y': 312}
        ]
        compressed_objects = compress_objects(objects)
        self.assertEqual(objects, decompress_objects(compressed_objects))

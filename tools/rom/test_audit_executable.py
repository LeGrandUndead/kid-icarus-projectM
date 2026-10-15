import struct
import unittest

from audit_executable import exefs_entries, segments


class LayoutTests(unittest.TestCase):
    def header(self):
        header = bytearray(0x400)
        for at, addr, size in [(0x10, 0x100000, 0xFFF), (0x20, 0x200000, 9), (0x30, 0x300000, 1)]:
            struct.pack_into('<III', header, at, addr, 1, size)
        return header

    def test_file_offsets_use_pages_not_logical_sizes(self):
        self.assertEqual([s['file_offset'] for s in segments(self.header(), 0x3000)], [0, 0x1000, 0x2000])

    def test_rejects_truncation(self):
        with self.assertRaisesRegex(ValueError, 'truncated'):
            segments(self.header(), 0x2FFF)

    def test_rejects_compression(self):
        header = self.header()
        header[13] = 1
        with self.assertRaisesRegex(ValueError, 'Compressed'):
            segments(header, 0x3000)

    def test_rejects_overlap(self):
        header = self.header()
        struct.pack_into('<I', header, 0x20, 0x100000)
        with self.assertRaisesRegex(ValueError, 'Overlapping'):
            segments(header, 0x3000)

    def test_rejects_oversize_segment(self):
        header = self.header()
        struct.pack_into('<I', header, 0x18, 0x1001)
        with self.assertRaisesRegex(ValueError, 'logical size'):
            segments(header, 0x3000)

    def test_reversed_exefs_hash_table(self):
        header = bytearray(512)
        header[:5] = b'.code'
        struct.pack_into('<II', header, 8, 0, 32)
        header[0x1E0:] = b'x' * 32
        self.assertEqual(exefs_entries(header)[0]['sha256'], (b'x' * 32).hex())


if __name__ == '__main__':
    unittest.main()

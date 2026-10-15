import sys
import struct
from pathlib import Path

data = Path(sys.argv[1]).read_bytes()

pos = data.find(b"darc")

if pos == -1:
    raise SystemExit("No DARC header found")

print(f"DARC header found at 0x{pos:X}")

# DARC header:
# +0x00 magic
# +0x04 endian
# +0x06 header size
# +0x08 version
# +0x0C file length
# +0x10 file table offset
# +0x14 file table length
# +0x18 file data offset

magic = data[pos:pos+4]
endian = struct.unpack_from("<H", data, pos+4)[0]
header_size = struct.unpack_from("<H", data, pos+6)[0]
version = struct.unpack_from("<I", data, pos+8)[0]
file_length = struct.unpack_from("<I", data, pos+12)[0]
table_offset = struct.unpack_from("<I", data, pos+16)[0]
table_length = struct.unpack_from("<I", data, pos+20)[0]
data_offset = struct.unpack_from("<I", data, pos+24)[0]

print(f"magic       = {magic!r}")
print(f"endian      = 0x{endian:04X}")
print(f"header size = 0x{header_size:X}")
print(f"version     = 0x{version:X}")
print(f"file length = 0x{file_length:X}")
print(f"table offset= 0x{table_offset:X}")
print(f"table length= 0x{table_length:X}")
print(f"data offset = 0x{data_offset:X}")

print()
print("First 32 bytes of DARC:")
print(data[pos:pos+32].hex(" "))

if endian != 0xFEFF:
    print("WARNING: unexpected endian marker")
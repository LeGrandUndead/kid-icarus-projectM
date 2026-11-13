# Packs one character's frames (char_M/NNNN.jpg + NNNN_a.png) into one file,
# char_M.pak, so the game reads them in one go instead of 600+ small files
# (on a hard disk, while the game also reads its ROM, the small files took
# a minute).
#
#   python3 frame_pak.py <scene-040 folder> <mode 0-3>
#
# The file:
#   b'KIUFRAM1', then the number of frames (4 bytes),
#   then per frame: index, JPEG length, PNG length (4 bytes each),
#   then each frame's JPEG bytes and PNG bytes, in the same order.
# Numbers are little-endian. Written to .tmp first, then renamed, so a
# half-written file is never used.
import os, sys, struct

def main():
    folder, mode = sys.argv[1], int(sys.argv[2])
    frames_dir = os.path.join(folder, f'char_{mode}')
    indices = sorted(int(name[:4]) for name in os.listdir(frames_dir) if name.endswith('.jpg'))
    out_path = os.path.join(folder, f'char_{mode}.pak')
    tmp_path = out_path + '.tmp'
    # read every frame first
    frames = []
    for i in indices:
        with open(os.path.join(frames_dir, f'{i:04d}.jpg'), 'rb') as f:
            jpg = f.read()
        with open(os.path.join(frames_dir, f'{i:04d}_a.png'), 'rb') as f:
            png = f.read()
        frames.append((i, jpg, png))
    # then write the table and the bytes
    with open(tmp_path, 'wb') as out:
        out.write(b'KIUFRAM1')
        out.write(struct.pack('<I', len(frames)))
        for i, jpg, png in frames:
            out.write(struct.pack('<iII', i, len(jpg), len(png)))
        for i, jpg, png in frames:
            out.write(jpg)
            out.write(png)
    os.replace(tmp_path, out_path)
    print('packed', len(frames), 'frames into', out_path, os.path.getsize(out_path) // (1 << 20), 'MB')

main()

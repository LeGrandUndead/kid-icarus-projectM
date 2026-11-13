"""python3 -m menu_pack <out folder> [--modes 0123]   (see build.py)"""
import sys

from .build import build

args = sys.argv[1:]
if not args or args[0].startswith('-'):
    sys.exit(__doc__)
modes = '0123'
if '--modes' in args:
    modes = args[args.index('--modes') + 1]
build(args[0], modes)

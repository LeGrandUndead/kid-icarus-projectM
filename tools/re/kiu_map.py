"""A map of Kid Icarus: Uprising's code, built from the user's own ROM files.

The game's 11.6 MB of ARM code keeps a lot of structure a tool can read
without a disassembler: who calls whom, which names each function uses,
the classes' method tables with the names the game gives them, the fields
each class reads by name, and the global managers (singletons) it creates
on first use. This builds that into an SQLite file and answers questions
about it. See doc/GAME_ARCHITECTURE.md.

    python tools/re/kiu_map.py build [ROM/gameFiles] [build/re/kiu-map.sqlite]
    python tools/re/kiu_map.py fn 0x00AEAD80        what a function is
    python tools/re/kiu_map.py find Warp            names, classes, fields matching
    python tools/re/kiu_map.py class anime_command::StartFade
    python tools/re/kiu_map.py callers 0x00538B34
    python tools/re/kiu_map.py flow 0x00925E70        the calls a function makes, in order
    python tools/re/kiu_map.py singletons [text]
    python tools/re/kiu_map.py dis 0x00AEAD80 [count]   (needs capstone)

The map holds addresses and the game's own names, nothing of its code; it
lives in build/ and is never committed.

How each part is recognised (ARM, little endian):
- calls: BL and BLX with an immediate target;
- names: a literal-pool load (LDR Rd, [PC, #imm]) or an ADD/SUB Rd, PC,
  #imm whose value is the address of a printable string;
- method tables: words in read-only data loaded as literals (a constructor
  stores its class's table) followed by code addresses or zeros; a table's
  class name is the "ns::Class" string its first slots' functions use
  (slot 1 is the type information, as for anime_command::StartFade);
- fields: in a function, ADD r2, rB, #offset and ADD r1, PC, #name before a
  call: the parameter visitors register each field by name that way
  (anime_command::Warp: start_ at +0x10 ... waitTime_ at +0xD0);
- singletons: LDR Rx, =global; LDR r0, [Rx]; CMP r0, #0; BNE; BL create;
  STR r0, [Rx]: the get-or-create every manager uses (the screen fader at
  0x00D63620).
"""

import os
import re
import sqlite3
import struct
import sys
from bisect import bisect_right
from collections import defaultdict

try:
    import numpy as np
except ImportError:  # pragma: no cover
    sys.exit("kiu_map needs numpy (pip install numpy)")

DEFAULT_ROM = "ROM/gameFiles"
NAMES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kiu_names.txt")
DEFAULT_DB = "build/re/kiu-map.sqlite"


# -- the code file --------------------------------------------------------

class Code:
    """code.bin with the segment layout ExHeader.bin gives."""

    def __init__(self, folder):
        self.bytes = open(os.path.join(folder, "ExeFS", "code.bin"), "rb").read()
        header = open(os.path.join(folder, "ExHeader.bin"), "rb").read()
        self.base = struct.unpack_from("<I", header, 0x10)[0]
        segments = {}
        for name, offset in (("text", 0x10), ("rodata", 0x20), ("data", 0x30)):
            address, _pages, size = struct.unpack_from("<III", header, offset)
            segments[name] = (address, address + size)
        bss = struct.unpack_from("<I", header, 0x3C)[0]
        self.text = segments["text"]
        self.rodata = segments["rodata"]
        self.data = segments["data"]
        self.globals = (self.data[0], self.data[1] + bss + 0x1000)
        self.end = self.base + len(self.bytes)

    def word(self, address):
        offset = address - self.base
        if address & 3 or not 0 <= offset <= len(self.bytes) - 4:
            return None
        return struct.unpack_from("<I", self.bytes, offset)[0]

    def is_code(self, address):
        return self.text[0] <= address < self.text[1] and address & 3 == 0

    def string(self, address, longest=96):
        """the printable string at address, or None."""
        offset = address - self.base
        if not 0 <= offset < len(self.bytes):
            return None
        end = offset
        while end < len(self.bytes) and end - offset < longest and 32 <= self.bytes[end] < 127:
            end += 1
        if end - offset < 3 or end >= len(self.bytes) or self.bytes[end] != 0:
            return None
        return self.bytes[offset:end].decode("ascii")


def rotate_immediate(word):
    value, rotation = word & 0xFF, ((word >> 8) & 0xF) * 2
    return ((value >> rotation) | (value << (32 - rotation))) & 0xFFFFFFFF


# -- building -------------------------------------------------------------

def decode(code):
    """calls, literal and PC-relative values, per instruction address."""
    start, end = code.text
    words = np.frombuffer(code.bytes, dtype="<u4", count=(end - start) // 4,
                          offset=start - code.base).astype(np.int64)
    addresses = start + 4 * np.arange(len(words), dtype=np.int64)
    cond = words >> 28

    # BL (cond != 0xF, 1011) and BLX immediate (cond == 0xF, 101H)
    branch = (words >> 25) & 7 == 5
    offset24 = words & 0xFFFFFF
    offset24 = np.where(offset24 & 0x800000, offset24 - 0x1000000, offset24)
    bl = branch & (cond != 0xF) & ((words >> 24) & 1 == 1)
    blx = branch & (cond == 0xF)
    targets = addresses + 8 + offset24 * 4 + np.where(blx, ((words >> 24) & 1) * 2, 0)
    calls = [(int(a), int(t)) for a, t in zip(addresses[bl | blx], targets[bl | blx])
             if code.text[0] <= int(t) < code.text[1]]

    # LDR Rd, [PC, #+-imm]
    literal = (words & 0x0F5F0000) == 0x051F0000
    sign = np.where((words >> 23) & 1 == 1, 1, -1)
    pools = addresses + 8 + sign * (words & 0xFFF)
    values = {}
    for address, pool, rd in zip(addresses[literal & (cond != 0xF)], pools[literal & (cond != 0xF)],
                                 ((words >> 12) & 0xF)[literal & (cond != 0xF)]):
        value = code.word(int(pool))
        if value is not None:
            values[int(address)] = (value, int(rd))

    # ADD/SUB Rd, PC, #imm
    add = (words & 0x0FFF0000) == 0x028F0000
    sub = (words & 0x0FFF0000) == 0x024F0000
    for address, word, is_add in zip(addresses[add | sub], words[add | sub], add[add | sub]):
        immediate = rotate_immediate(int(word))
        value = (int(address) + 8 + (immediate if is_add else -immediate)) & 0xFFFFFFFF
        values[int(address)] = (value, (int(word) >> 12) & 0xF)
    return words, addresses, calls, values


def find_vtables(code, values):
    """method tables: read-only words code loads as literals, followed by
    code addresses and zeros."""
    starts = sorted({v for v, _ in values.values()
                     if code.rodata[0] <= v < code.rodata[1] and v & 3 == 0})
    tables = {}
    for i, table in enumerate(starts):
        limit = starts[i + 1] if i + 1 < len(starts) else code.rodata[1]
        slots = []
        address = table
        while address < limit and len(slots) < 256:
            word = code.word(address)
            if word is None or not (word == 0 or code.is_code(word)):
                break
            slots.append(word)
            address += 4
        if sum(1 for s in slots if s) >= 2:
            tables[table] = slots
    return tables


def build(folder, path):
    code = Code(folder)
    print(f"text {code.text[0]:08X}-{code.text[1]:08X}, rodata {code.rodata[0]:08X}-{code.rodata[1]:08X}, "
          f"data {code.data[0]:08X}-{code.data[1]:08X}")
    words, addresses, calls, values = decode(code)
    print(f"{len(words)} instructions, {len(calls)} calls, {len(values)} constants")

    vtables = find_vtables(code, values)
    print(f"{len(vtables)} method tables")

    # functions: what is called, what tables point at, and what saves the
    # return address on entry (PUSH/STMDB SP!, {..., LR}), with an
    # instruction or two loading a literal allowed before it
    starts = {t for _, t in calls}
    push_lr = ((words & 0x0FFF4000) == 0x092D4000) & ((words >> 28) == 0xE)
    previous = np.concatenate(([0], words[:-1]))
    ends = ((previous & 0x0FFFFFFF) == 0x012FFF1E) | (((previous & 0x0FFF8000) == 0x08BD8000)) \
        | (((previous & 0x0F000000) == 0x0A000000) & ((previous >> 28) == 0xE)) \
        | (previous == 0xE1A00000)  # a tail call's slot reads as MOV r0, r0
    starts.update(int(a) for a in addresses[push_lr & ends])
    for slots in vtables.values():
        starts.update(s for s in slots if s)
    starts = sorted(s for s in starts if code.is_code(s))
    print(f"{len(starts)} functions")

    def owner(address):
        i = bisect_right(starts, address) - 1
        return starts[i] if i >= 0 else None

    # names each function uses
    names = defaultdict(set)
    for address, (value, _rd) in values.items():
        text = code.string(value)
        if text:
            function = owner(address)
            if function is not None:
                names[function].add(text)

    # class names of method tables: the "ns::Class" strings of their first
    # slots' functions, slot 1 first
    classes = {}
    for table, slots in vtables.items():
        found = None
        for slot in (1, 0, 2, 3):
            if slot < len(slots) and slots[slot]:
                scoped = sorted(n for n in names.get(slots[slot], ()) if "::" in n and " " not in n)
                if scoped:
                    found = min(scoped, key=len)
                    break
        classes[table] = found

    # fields registered by name: ADD r2, rB, #offset ... ADD r1, PC, #name ... BL helper
    fields = []
    call_at = dict(calls)
    text_start = code.text[0]

    class Words:
        """the instruction at an address, by index into the decoded words."""
        def get(self, address):
            index = (address - text_start) // 4
            return int(words[index]) if 0 <= index < len(words) else None

    by_address = Words()
    for address, (value, rd) in values.items():
        if rd != 1:
            continue
        name = code.string(value)
        if not name or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*_", name):
            continue
        offset = None
        for back in range(1, 4):
            word = by_address.get(address - 4 * back)
            if word is not None and (word & 0x0FF0F000) == 0x02802000:  # ADD r2, rB, #imm
                offset = rotate_immediate(word)
                break
        helper = None
        for ahead in range(1, 4):
            if address + 4 * ahead in call_at:
                helper = call_at[address + 4 * ahead]
                break
        if helper is not None:
            fields.append((owner(address), name, offset, helper))

    # singletons: LDR Rx, =global; LDR r0, [Rx]; CMP r0, #0; BNE; BL create; STR r0, [Rx]
    singletons = defaultdict(lambda: {"create": None, "uses": 0})
    for address, (value, rd) in values.items():
        if not code.globals[0] <= value < code.globals[1]:
            continue
        load = by_address.get(address + 4)
        if load is None or (load & 0x0FFFF000) != (0x05900000 | (rd << 16)):
            continue
        singletons[value]["uses"] += 1
        for ahead in range(2, 7):
            target = call_at.get(address + 4 * ahead)
            if target is not None:
                store = by_address.get(address + 4 * ahead + 4)
                if store is not None and (store & 0x0FFFF000) == (0x05800000 | (rd << 16)):
                    singletons[value]["create"] = target
                break

    # a singleton's object: the get-or-create functions are C++ statics,
    # "guard; construct once; return the instance": the instance is the
    # last literal the creator loads, the constructor the creator's call
    # that takes it, the class's method table the first the constructor
    # (or what it calls first) stores
    # the last table a function stores is its own class's: a constructor
    # runs its base's first, which stores the base's table
    table_at = {}
    for address in sorted(values):
        value = values[address][0]
        if value in vtables:
            function = owner(address)
            if function is not None:
                table_at[function] = value
    callees = defaultdict(list)
    for site, target in calls:
        function = owner(site)
        if function is not None:
            callees[function].append(target)
    function_end = {s: (starts[i + 1] if i + 1 < len(starts) else code.text[1]) for i, s in enumerate(starts)}

    def creator_parts(create):
        end = min(function_end.get(create, create + 0x80), create + 0x100)
        loads = [(a, v) for a in range(create, end, 4) for v in [values.get(a)] if v]
        instance = next((v for a, (v, rd) in reversed(loads) if rd == 0 and code.globals[0] <= v < code.globals[1] + 0x400000), None)
        constructor = None
        for target in callees.get(create, []):
            if target in table_at or any(t in table_at for t in callees.get(target, [])[:4]):
                constructor = target
                break
        if constructor is None:
            followed = [t for t in callees.get(create, []) if t != 0x003B50EC]
            constructor = followed[0] if followed else None
        table = None
        frontier = [constructor] if constructor else []
        for _ in range(2):
            following = []
            for f in frontier:
                if f in table_at:
                    table = table_at[f]
                    break
                following.extend(callees.get(f, [])[:4])
            if table:
                break
            frontier = following
        return instance, constructor, table

    def hints_of(table, constructor):
        found = []
        functions = [constructor] if constructor else []
        if table:
            functions += [f for f in vtables[table] if f][:24]
        for f in functions:
            for n in sorted(names.get(f, ())):
                if n not in found and re.fullmatch(r"[A-Za-z][A-Za-z0-9_:%. /-]{3,}", n) and re.search(r"[a-z]{3}", n):
                    found.append(n)
        return found[:8]

    # write
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    db = sqlite3.connect(path)
    db.executescript("""
        create table functions (address integer primary key, size integer);
        create table calls (site integer, caller integer, callee integer);
        create table names (function integer, name text);
        create table vtables (address integer primary key, class text, slots integer);
        create table methods (vtable integer, slot integer, function integer);
        create table fields (function integer, name text, offset integer, helper integer);
        create table singletons (global integer primary key, create_fn integer, uses integer, class text,
                                 instance integer, constructor integer, vtable integer, hints text);
        create table info (key text primary key, value text);
    """)
    sizes = [(s, (starts[i + 1] if i + 1 < len(starts) else code.text[1]) - s) for i, s in enumerate(starts)]
    db.executemany("insert into functions values (?, ?)", sizes)
    db.executemany("insert into calls values (?, ?, ?)", [(s, owner(s), t) for s, t in calls])
    db.executemany("insert into names values (?, ?)", [(f, n) for f, ns in names.items() for n in ns])
    db.executemany("insert into vtables values (?, ?, ?)", [(t, classes[t], len(s)) for t, s in vtables.items()])
    db.executemany("insert into methods values (?, ?, ?)",
                   [(t, i, f) for t, s in vtables.items() for i, f in enumerate(s) if f])
    db.executemany("insert into fields values (?, ?, ?, ?)", fields)
    rows = []
    for g, single in singletons.items():
        if not single["create"]:
            continue
        instance, constructor, table = creator_parts(single["create"])
        name = classes.get(table) if table else None
        rows.append((g, single["create"], single["uses"], name, instance, constructor, table,
                     " | ".join(hints_of(table, constructor))))
    db.executemany("insert into singletons values (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    db.executemany("insert into info values (?, ?)", [
        ("text", f"{code.text[0]:08X}-{code.text[1]:08X}"),
        ("rodata", f"{code.rodata[0]:08X}-{code.rodata[1]:08X}"),
        ("data", f"{code.data[0]:08X}-{code.data[1]:08X}"),
    ])
    for statement in ("create index calls_callee on calls (callee)", "create index calls_caller on calls (caller)",
                      "create index names_function on names (function)", "create index names_name on names (name)",
                      "create index methods_function on methods (function)", "create index fields_function on fields (function)"):
        db.execute(statement)
    db.commit()
    named = sum(1 for c in classes.values() if c)
    print(f"{named} named classes, {len(fields)} fields, "
          f"{sum(1 for s in singletons.values() if s['create'])} singletons -> {path}")


# -- asking ---------------------------------------------------------------

def curated():
    """the names we gave things as we understood them, tools/re/kiu_names.txt:
    `address  name  what it is`."""
    found = {}
    if os.path.exists(NAMES):
        for line in open(NAMES, encoding="utf-8"):
            line = line.split("#", 1)[0].strip()
            if line:
                parts = line.split(None, 2)
                found[int(parts[0], 16)] = (parts[1], parts[2] if len(parts) > 2 else "")
    return found


def hexa(value):
    return f"0x{value:08X}" if value is not None else "?"


def number(text):
    return int(text, 16) if text.lower().startswith("0x") or re.fullmatch(r"[0-9A-Fa-f]{6,8}", text) else int(text)


def containing(db, address):
    row = db.execute("select address, size from functions where address <= ? order by address desc limit 1",
                     (address,)).fetchone()
    return row


def describe_function(db, address):
    row = containing(db, address)
    if not row:
        print("not in a known function")
        return
    function, size = row
    known = curated()
    ours = known.get(function)
    print(f"function {hexa(function)}, {size} bytes" + (f" (address +0x{address - function:X})" if address != function else "")
          + (f": {ours[0]}, {ours[1]}" if ours else ""))
    for table, slot, cls in db.execute(
            "select m.vtable, m.slot, v.class from methods m join vtables v on v.address = m.vtable where m.function = ?",
            (function,)):
        print(f"  method {slot} (+0x{slot * 4:X}) of {cls or '?'} (table {hexa(table)})")
    for global_, cls in db.execute("select global, class from singletons where create_fn = ?", (function,)):
        print(f"  creates the singleton at {hexa(global_)} ({cls or '?'})")
    used = [n for (n,) in db.execute("select name from names where function = ? order by name", (function,))]
    if used:
        print("  names: " + ", ".join(used[:40]) + (" ..." if len(used) > 40 else ""))
    fields = list(db.execute("select name, offset from fields where function = ? order by offset", (function,)))
    if fields:
        print("  fields: " + ", ".join(f"{n}+0x{o:X}" if o is not None else n for n, o in fields))
    callers = [c for (c,) in db.execute("select distinct caller from calls where callee = ? limit 30", (function,))]
    callees = [c for (c,) in db.execute("select distinct callee from calls where caller = ? limit 30", (function,))]
    print(f"  called by {len(callers)}{'+' if len(callers) == 30 else ''}: " + " ".join(hexa(c) for c in callers[:12]))
    print(f"  calls {len(callees)}{'+' if len(callees) == 30 else ''}: " + " ".join(hexa(c) for c in callees[:12]))


def find(db, text):
    like = f"%{text}%"
    for address, (name, what) in curated().items():
        if text.lower() in (name + " " + what).lower():
            print(f"ours   {name}  {hexa(address)}  {what}")
    classes = list(db.execute("select address, class, slots from vtables where class like ? order by class limit 60", (like,)))
    for table, cls, slots in classes:
        print(f"class  {cls}  table {hexa(table)} ({slots} slots)")
    for global_, create, cls, uses in db.execute(
            "select global, create_fn, class, uses from singletons where class like ? limit 40", (like,)):
        print(f"single {cls}  at {hexa(global_)}  created by {hexa(create)}  used {uses}x")
    for function, name, offset in db.execute(
            "select function, name, offset from fields where name like ? limit 60", (like,)):
        print(f"field  {name} +{hexa(offset) if offset is not None else '?'}  read by {hexa(function)}")
    for function, name in db.execute("select function, name from names where name like ? limit 60", (like,)):
        print(f"name   \"{name}\"  in {hexa(function)}")


def label(db, function, known):
    """the shortest useful description of a function."""
    if function in known:
        return known[function][0]
    row = db.execute("select v.class, m.slot from methods m join vtables v on v.address = m.vtable "
                     "where m.function = ? and v.class is not null limit 1", (function,)).fetchone()
    if row:
        return f"{row[0]} method {row[1]}"
    row = db.execute("select global from singletons where create_fn = ?", (function,)).fetchone()
    if row:
        ours = known.get(row[0])
        return f"get {ours[0] if ours else 'singleton ' + hexa(row[0])}"
    used = [n for (n,) in db.execute("select name from names where function = ? limit 3", (function,))]
    return ("uses " + ", ".join(used)) if used else ""


def flow(db, address):
    """the calls a function makes, in address order, each labelled."""
    function = containing(db, address)[0]
    known = curated()
    print(f"{hexa(function)} {label(db, function, known)}")
    for site, callee in db.execute("select site, callee from calls where caller = ? order by site", (function,)):
        print(f"  {hexa(site)}  -> {hexa(callee)}  {label(db, callee, known)}")


def describe_class(db, name):
    for table, cls, slots in db.execute("select address, class, slots from vtables where class = ?", (name,)):
        print(f"{cls}: table {hexa(table)}, {slots} slots")
        for slot, function in db.execute("select slot, function from methods where vtable = ? order by slot", (table,)):
            fields = list(db.execute("select name, offset from fields where function = ?", (function,)))
            extra = (" fields: " + ", ".join(f"{n}+0x{o:X}" if o is not None else n for n, o in fields)) if fields else ""
            print(f"  {slot:2} +0x{slot * 4:02X}  {hexa(function)}{extra}")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return
    command = argv[1]
    if command == "build":
        build(argv[2] if len(argv) > 2 else DEFAULT_ROM, argv[3] if len(argv) > 3 else DEFAULT_DB)
        return
    db = sqlite3.connect(os.environ.get("KIU_MAP", DEFAULT_DB))
    if command == "fn":
        describe_function(db, number(argv[2]))
    elif command == "find":
        find(db, argv[2])
    elif command == "class":
        describe_class(db, argv[2])
    elif command == "flow":
        flow(db, number(argv[2]))
    elif command == "callers":
        function = containing(db, number(argv[2]))[0]
        for site, caller in db.execute("select site, caller from calls where callee = ? order by caller", (function,)):
            print(f"{hexa(caller)}  (call at {hexa(site)})")
    elif command == "singletons":
        like = (argv[2] if len(argv) > 2 else "").lower()
        known = curated()
        for global_, create, cls, uses, instance, constructor, table, hints in db.execute(
                "select global, create_fn, class, uses, instance, constructor, vtable, hints from singletons order by uses desc"):
            ours = known.get(global_, (None, ""))[0]
            text = " ".join(str(x) for x in (ours, cls, hints) if x)
            if like and like not in text.lower():
                continue
            print(f"{hexa(global_)} {uses:4}x  {ours or cls or '?'}")
            print(f"            instance {hexa(instance)}  constructor {hexa(constructor)}  table {hexa(table)}"
                  + (f"\n            uses: {hints}" if hints else ""))
    elif command == "dis":
        import capstone
        folder = os.environ.get("KIU_ROM", DEFAULT_ROM)
        code = Code(folder)
        address, count = number(argv[2]), int(argv[3]) if len(argv) > 3 else 40
        md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
        offset = address - code.base
        for instruction in md.disasm(code.bytes[offset:offset + 4 * count], address):
            print(f"{instruction.address:08X}: {instruction.mnemonic:8} {instruction.op_str}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)

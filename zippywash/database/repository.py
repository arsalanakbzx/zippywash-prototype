"""Repository: loads every saved object into memory with typed relationships, and saves changes back.

It holds no business rules. Typical use (one unit of work):

    world = repo.load()          # all objects, relationships rebuilt
    ... call domain methods / services ...
    repo.commit(world)           # one transaction: everything changed is saved, or nothing is

The prototype's data set is small, so loading it whole keeps the code simple and the
relationships complete. New objects are found automatically by following relationships from
known objects; objects nothing points to yet (e.g. a new time slot) are added with world.add().
"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from zippywash.common import link
from zippywash.customer_order_service.loyalty_rule import LoyaltyRule
from zippywash.database.mapping import BY_CLASS, JOIN_TABLE, MAPPINGS, SORT_KEYS, ByClassName, from_db, to_db
from zippywash.customer_order_service.time_slot import TimeSlot
from zippywash.operations_resource.machine import Machine

if TYPE_CHECKING:
    import sqlite3


class World:
    """Identity map: exactly one Python object per saved row."""

    def __init__(self):
        self.index: dict[type, dict[str, object]] = ByClassName({m.cls.__name__: {} for m in MAPPINGS})
        self._snap: dict[int, tuple] = {}          # id(obj) -> row as last saved/loaded
        self._join_snap: set[tuple[str, str]] = set()

    # ---------- access ----------
    def get(self, cls, key):
        return self.index[cls].get(key)

    def all(self, cls) -> list:
        return list(self.index[cls].values())

    def add(self, *objs) -> None:
        for obj in objs:
            m = BY_CLASS[type(obj)]
            self.index[m.cls].setdefault(getattr(obj, m.pk), obj)

    # ---------- discovery of new objects by following relationships ----------
    def discover(self) -> None:
        seen = {id(o) for d in self.index.values() for o in d.values()}
        stack = [o for d in self.index.values() for o in d.values()]
        while stack:
            obj = stack.pop()
            m = BY_CLASS[type(obj)]
            neighbours = [getattr(obj, r.attr) for r in m.refs]
            for other in MAPPINGS:   # collections that point back at this class
                for r in other.refs:
                    if r.target is m.cls and r.inverse:
                        value = getattr(obj, r.inverse, None)
                        neighbours.extend(value if isinstance(value, list) else [value])
            if type(obj).__name__ == "TimeSlot":
                neighbours.extend(obj.contributing_machines)
            if type(obj).__name__ == "Machine":
                neighbours.extend(obj.time_slots)
            for n in neighbours:
                if n is not None and type(n) in BY_CLASS and id(n) not in seen:
                    seen.add(id(n))
                    self.add(n)
                    stack.append(n)


def _row(m, obj) -> tuple:
    values = [getattr(obj, m.pk)]
    values += [to_db(c.kind, getattr(obj, c.attr)) for c in m.cols]
    for r in m.refs:
        target = getattr(obj, r.attr)
        values.append(None if target is None else getattr(target, BY_CLASS[r.target].pk))
    return tuple(values)


def _columns(m) -> list[str]:
    return [m.pk] + [c.attr for c in m.cols] + [f"{r.attr}_id" for r in m.refs]


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ------------------------------------------------------------------
    def load(self) -> World:
        world = World()
        raw: dict[type, list] = {}
        # 1. Build every object from its scalar columns
        for m in MAPPINGS:
            cols = _columns(m)
            rows = self.conn.execute(f"SELECT {', '.join(cols)} FROM {m.table} ORDER BY rowid").fetchall()
            raw[m.cls] = rows
            for row in rows:
                kwargs = {m.pk: row[0]}
                for i, c in enumerate(m.cols, start=1):
                    kwargs[c.attr] = from_db(c.kind, row[i])
                obj = m.cls(**{k: v for k, v in kwargs.items() if k in m.cls.__dataclass_fields__
                               and m.cls.__dataclass_fields__[k].init})
                for k, v in kwargs.items():          # non-init technical fields
                    if not m.cls.__dataclass_fields__[k].init:
                        object.__setattr__(obj, k, v)
                world.index[m.cls][row[0]] = obj
        # 2. Rebuild typed relationships (both ends)
        for m in MAPPINGS:
            offset = 1 + len(m.cols)
            for row in raw[m.cls]:
                obj = world.index[m.cls][row[0]]
                for j, r in enumerate(m.refs):
                    key = row[offset + j]
                    if key is None:
                        continue
                    target = world.index[r.target][key]
                    object.__setattr__(obj, r.attr, target)
                    if r.inverse is None:
                        continue
                    if r.inverse_many:
                        link(getattr(target, r.inverse), obj)
                    else:
                        object.__setattr__(target, r.inverse, obj)
        for slot_id, machine_id in self.conn.execute(f"SELECT time_slot_id, machine_id FROM {JOIN_TABLE}"):
            slot, machine = world.index[TimeSlot][slot_id], world.index[Machine][machine_id]
            link(slot.contributing_machines, machine)
            link(machine.time_slots, slot)
            world._join_snap.add((slot_id, machine_id))
        # 3. Ordering, sealing of ledger records, snapshot for change detection
        for (cls, attr), key in SORT_KEYS.items():
            for obj in world.index[cls].values():
                getattr(obj, attr).sort(key=key)
        for m in MAPPINGS:
            for obj in world.index[m.cls].values():
                if hasattr(obj, "seal") and getattr(obj, "posted", True):
                    obj.seal()
                world._snap[id(obj)] = _row(m, obj)
        LoyaltyRule.register(world.all(LoyaltyRule))
        return world

    # ------------------------------------------------------------------
    def commit(self, world: World) -> int:
        """Save every new or changed object in one transaction. Returns how many rows were written."""
        world.discover()
        written = 0
        with self.conn:
            self.conn.execute("PRAGMA defer_foreign_keys = ON")
            for m in MAPPINGS:
                cols = _columns(m)
                updates = ", ".join(f"{c} = excluded.{c}" for c in cols[1:])
                sql = (f"INSERT INTO {m.table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
                       f"ON CONFLICT({m.pk}) DO UPDATE SET {updates}")
                for obj in world.index[m.cls].values():
                    row = _row(m, obj)
                    if world._snap.get(id(obj)) != row:
                        self.conn.execute(sql, row)
                        world._snap[id(obj)] = row
                        written += 1
            pairs = {(s.time_slot_id, mc.machine_id) for s in world.all(TimeSlot) for mc in s.contributing_machines}
            for pair in pairs - world._join_snap:
                self.conn.execute(f"INSERT OR IGNORE INTO {JOIN_TABLE} VALUES (?, ?)", pair)
            for pair in world._join_snap - pairs:
                self.conn.execute(f"DELETE FROM {JOIN_TABLE} WHERE time_slot_id = ? AND machine_id = ?", pair)
            world._join_snap = pairs
        return written

    # ------------------------------------------------------------------
    def row_counts(self) -> dict[str, int]:
        counts = defaultdict(int)
        for m in MAPPINGS:
            counts[m.table] = self.conn.execute(f"SELECT COUNT(*) FROM {m.table}").fetchone()[0]
        return dict(counts)


class InMemoryRepository:
    """Same interface as Repository, but keeps one World in memory and never touches a database.

    Used by the web app, where the Python domain runs inside the visitor's browser: each visitor
    gets their own private copy of the demo data, and reloading the page starts fresh."""

    def __init__(self):
        self.world: World | None = None

    def load(self) -> World:
        if self.world is None:
            self.world = World()
        LoyaltyRule.register(self.world.all(LoyaltyRule))
        return self.world

    def commit(self, world: World) -> int:
        world.discover()          # register new objects (new orders, payments...) in the identity map
        self.world = world
        return 0

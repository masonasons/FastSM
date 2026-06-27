"""Timeline navigation by a chosen granularity ("movement unit").

Alt+Left/Right cycles the active unit; Alt+Up/Down jumps to the next item
matching it. Ported from FastSMApple (FastSMCore/Timeline/Movement.swift).
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class MovementUnit:
	kind: str  # "time" | "same_user" | "thread"
	seconds: int = 0

	@property
	def title(self) -> str:
		if self.kind == "same_user":
			return "Same user"
		if self.kind == "thread":
			return "Thread"
		if self.seconds % 86400 == 0:
			d = self.seconds // 86400
			return f"{d} day" + ("" if d == 1 else "s")
		h = self.seconds // 3600
		return f"{h} hour" + ("" if h == 1 else "s")


def _time(seconds: int) -> MovementUnit:
	return MovementUnit(kind="time", seconds=seconds)


CATALOG: List[MovementUnit] = [
	_time(3600), _time(7200), _time(14400), _time(21600), _time(43200), _time(86400),
	MovementUnit(kind="same_user"),
	MovementUnit(kind="thread"),
]

_current_index = 0


def current() -> MovementUnit:
	return CATALOG[_current_index % len(CATALOG)]


def cycle(delta: int) -> MovementUnit:
	"""Step the active unit by delta (+1 next, -1 previous) and return it."""
	global _current_index
	n = len(CATALOG)
	_current_index = (_current_index + delta) % n
	return CATALOG[_current_index]


def _ts(status):
	t = getattr(status, "created_at", None)
	if t is None:
		return None
	# Support both datetime and epoch-seconds shapes.
	if hasattr(t, "timestamp"):
		try:
			return t.timestamp()
		except (OverflowError, ValueError, OSError):
			return None
	try:
		return float(t)
	except (TypeError, ValueError):
		return None


def destination(statuses, from_index: int, unit: MovementUnit, direction: str) -> Optional[int]:
	"""Index to jump to from `from_index` by one `unit` step, or None.

	`direction` is "down" (toward higher indices) or "up" (toward lower).
	"""
	if not (0 <= from_index < len(statuses)):
		return None
	step = 1 if direction == "down" else -1

	if unit.kind == "time":
		base = _ts(statuses[from_index])
		if base is None:
			return None
		threshold = unit.seconds
		i = from_index + step
		while 0 <= i < len(statuses):
			t = _ts(statuses[i])
			if t is not None and abs(base - t) >= threshold:
				return i
			i += step
		return None

	if unit.kind == "same_user":
		uid = _author_id(statuses[from_index])
		if uid is None:
			return None
		i = from_index + step
		while 0 <= i < len(statuses):
			if _author_id(statuses[i]) == uid:
				return i
			i += step
		return None

	if unit.kind == "thread":
		keys = _thread_keys(statuses)
		key = keys[from_index]
		if key is None:
			return None
		i = from_index + step
		while 0 <= i < len(statuses):
			if keys[i] == key:
				return i
			i += step
		return None

	return None


def _author_id(status):
	a = getattr(status, "account", None)
	return getattr(a, "id", None) if a is not None else None


def _thread_keys(statuses):
	parent = {}
	for s in statuses:
		sid = getattr(s, "id", None)
		if sid is not None:
			parent[sid] = getattr(s, "in_reply_to_id", None)

	def root(sid):
		cur = sid
		for _ in range(1000):
			p = parent.get(cur)
			if p is None or p not in parent:
				break
			cur = p
		return cur

	keys = []
	for s in statuses:
		sid = getattr(s, "id", None)
		keys.append(root(sid) if sid is not None else None)
	return keys

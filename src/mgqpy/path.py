"""Compiled dotted paths and existential traversal (internal)."""

from functools import lru_cache
from typing import Any, Callable

from .utils import is_array_index


MISSING = object()
Path = tuple[tuple[str, int | None], ...]
ValueMatch = Callable[[Any, Any], bool]


@lru_cache(maxsize=1024)
def compile_path(path: str) -> Path:
    # Longer digit strings cannot index a Python list; keep their field spelling.
    return tuple((key, int(key) if is_array_index(key) and len(key) < 20 else None)
                 for key in path.split("."))


def bind_path(parts: Path, match: ValueMatch, operand, expand_leaf=True):
    """Bind a leaf test; $all supplies fresh per-call state as the operand."""
    end = len(parts)
    ends_empty = parts[-1][0] == ""

    def predicate(doc, operand=operand):
        # A list root occurs only in document-form $elemMatch. Here it is a
        # document with numeric fields, not an array to traverse implicitly.
        if isinstance(doc, list):
            _, index = parts[0]
            if index is None or index >= len(doc):
                return match(MISSING, operand)
            return _walk(doc[index], parts, 1, match, operand, expand_leaf, end, ends_empty)
        return _walk(doc, parts, 0, match, operand, expand_leaf, end, ends_empty)

    return predicate


def _walk(value, parts, offset, match, operand, expand_leaf, end, ends_empty):
    while offset < end:
        key, index = parts[offset]
        if isinstance(value, dict):
            if key not in value:
                return match(MISSING, operand)
            value = value[key]
            offset += 1
        elif isinstance(value, list):
            # Index first, then literal-field alternatives. A terminal explicit
            # index does not implicitly expand its selected array value.
            if index is not None and index < len(value):
                selected = value[index]
                if offset + 1 == end:
                    if match(selected, operand):
                        return True
                elif isinstance(selected, (dict, list)):
                    # An indexed array plus a final empty component yields
                    # its immediate members, then itself, even for array ops.
                    if ends_empty and offset + 2 == end and isinstance(selected, list):
                        if _walk(selected, parts, end, match, operand, True, end, ends_empty):
                            return True
                    elif _walk(selected, parts, offset + 1, match, operand, expand_leaf, end, ends_empty):
                        return True
            # An empty remaining suffix exhausts an array path, but objects
            # still consume literal empty keys (including repeated dots).
            if ends_empty and offset + 1 == end:
                break
            missing_checked = False
            for child in value:
                if isinstance(child, dict):
                    if key in child:
                        if _walk(child[key], parts, offset + 1, match, operand, expand_leaf, end, ends_empty):
                            return True
                    elif not missing_checked:
                        # Every child without the key reaches the same missing value.
                        if match(MISSING, operand):
                            return True
                        missing_checked = True
            return False
        else:
            return match(MISSING, operand)

    if expand_leaf and isinstance(value, list):
        # $all replays whole reached leaves for successive requirements. Its
        # leaf handler must not expand a value selected by a terminal index.
        if expand_leaf is not True:
            return expand_leaf(value, operand, True)
        for child in value:
            if match(child, operand):
                return True
    return match(value, operand)

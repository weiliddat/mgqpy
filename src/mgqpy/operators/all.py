"""Independent requirements over one lazy walk, replaying reached leaf values."""

from ..path import walk
from .eq_ne_not import _match_eq


_SIMPLE = {int, float, str}


def _matches(group, match, operand):
    value, expand, simple = group
    if simple:
        return operand in value
    if expand and match is _match_eq:
        for child in value:
            if match(child, operand):
                return True
    return match(value, operand)


def compile_all(parts, operands, match):
    # C-level membership is safe only for these exact scalar pairs. In
    # particular, bools, NaNs and native conversions need shared equality.
    simple = match is _match_eq and all(type(o) in _SIMPLE and o == o for o in operands)

    def visit(value, state, expand=False):
        current, seen = state
        fast = (simple and expand and type(value) is list
                and _SIMPLE.issuperset(map(type, value)))
        if fast and not seen:
            for current, operand in enumerate(operands):
                if operand not in value:
                    state[0] = current
                    seen.append((value, expand, fast))
                    return False
            return True
        group = value, expand, fast
        seen.append(group)
        if not _matches(group, match, operands[current]):
            return False
        while True:
            current += 1
            if current == len(operands):
                return True
            # Later requirements can match earlier leaves. Do not evaluate
            # them at all until the preceding requirement has succeeded.
            for previous in seen:
                if _matches(previous, match, operands[current]):
                    break
            else:
                state[0] = current
                return False

    def predicate(doc):
        return walk(doc, parts, visit, [0, []], visit)

    return predicate

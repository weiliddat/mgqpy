"""Independent requirements over one lazy walk, replaying reached leaf values."""

from ..comparison import _all_plain, all_plain_operands
from ..path import bind_path
from .eq_ne_not import _match_eq


def _matches(group, match, operand):
    value, expand, checked = group
    # Certified scalar prefixes use the general leaf-equality scan via C membership.
    if checked is not None:
        length = len(value)
        if checked == length:
            return operand in value
        if checked and operand in value[:checked]:
            return True
        # Certify only bounded chunks, not an unread tail. Later requirements
        # reuse the certified prefix; other values still use shared equality.
        while checked < length:
            chunk = value if length <= 128 else value[checked:checked + 32]
            if not _all_plain(map(type, chunk)):
                group[2] = None
                break
            checked += len(chunk)
            group[2] = checked
            if operand in chunk:
                return True
        else:
            return False
    if expand and match is _match_eq:
        for child in value:
            if match(child, operand):
                return True
    return match(value, operand)


def compile_all(parts, operands, match):
    # C-level membership is safe only for these exact scalar pairs. In
    # particular, bools, NaNs and native conversions need shared equality.
    simple = match is _match_eq and all_plain_operands(operands)

    def visit(value, state, expand=False):
        current, seen = state
        checked = 0 if simple and expand and type(value) is list else None
        group = [value, expand, checked]
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

    traverse = bind_path(parts, visit, None, visit)

    def predicate(doc):
        return traverse(doc, [0, []])

    return predicate

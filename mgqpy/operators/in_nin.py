from mgqpy.operators.eq_ne_not import _match_eq


from typing import List


def _match_in(doc, path: List[str], ov) -> bool:
    if not _validate_in_nin(ov):
        return False

    if len(path) == 0:
        if isinstance(doc, list) and any([_match_in(d, path, ov) for d in doc]):
            return True

        return any([_match_eq(doc, path, o) for o in ov])

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_in(doc[key], rest, ov)

    if isinstance(doc, list) and key.isdigit():
        idx = int(key)
        if idx < len(doc):
            return _match_in(doc[idx], rest, ov)

    if isinstance(doc, list):
        return any([_match_in(d, path, ov) for d in doc])

    if None in ov:
        return True

    return False


def _match_nin(doc, path: List[str], ov) -> bool:
    if not _validate_in_nin(ov):
        return False

    return not _match_in(doc, path, ov)


def _validate_in_nin(ov):
    return isinstance(ov, list)

from typing import List


def _match_all(doc, path: List[str], ov) -> bool:
    if not _validate_all(ov):
        return False

    if len(path) == 0:
        if not isinstance(doc, list):
            return False

        return all([o in doc or o == doc for o in ov])

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_all(doc[key], rest, ov)

    if isinstance(doc, list) and key.isdigit():
        idx = int(key)
        if idx < len(doc):
            return _match_all(doc[idx], rest, ov)

    if isinstance(doc, list):
        return any([_match_all(d, path, ov) for d in doc])

    return False


def _validate_all(ov) -> bool:
    return isinstance(ov, list)

from typing import List


def _match_size(doc, path: List[str], ov) -> bool:
    if len(path) == 0:
        if not isinstance(doc, list):
            return False

        if len(doc) == ov:
            return True

        return False

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_size(doc[key], rest, ov)

    if isinstance(doc, list) and key.isdigit():
        idx = int(key)
        if idx < len(doc):
            return _match_size(doc[idx], rest, ov)

    if isinstance(doc, list):
        return any([_match_size(d, path, ov) for d in doc])

    return False

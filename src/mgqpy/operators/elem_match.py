import mgqpy


from typing import List


def _match_elem_match(doc, path: List[str], ov) -> bool:
    if len(path) == 0:
        if not isinstance(doc, list):
            return False

        if any(mgqpy._match_cond(ov, d) for d in doc):
            return True

        return False

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_elem_match(doc[key], rest, ov)

    if isinstance(doc, list) and key.isdigit():
        idx = int(key)
        if idx < len(doc):
            return _match_elem_match(doc[idx], rest, ov)

    if isinstance(doc, list):
        return any([_match_elem_match(d, path, ov) for d in doc])

    return False

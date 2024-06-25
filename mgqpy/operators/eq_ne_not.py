import re
from typing import List

import mgqpy


def _match_eq(doc, path: List[str], ov) -> bool:
    if len(path) == 0:
        if isinstance(doc, list) and any([_match_eq(d, path, ov) for d in doc]):
            return True

        if isinstance(ov, re.Pattern) and isinstance(doc, str):
            if ov.search(doc):
                return True

        return doc == ov

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict) and key in doc:
        return _match_eq(doc[key], rest, ov)

    if isinstance(doc, list) and key.isdigit():
        idx = int(key)
        if idx < len(doc):
            return _match_eq(doc[idx], rest, ov)

    if isinstance(doc, list):
        return any([_match_eq(d, path, ov) for d in doc])

    if ov is None:
        return True

    return False


def _match_ne(doc, path: List[str], ov) -> bool:
    return not _match_eq(doc, path, ov)


def _match_not(doc, path, ov):
    return not mgqpy._match_cond({path: ov}, doc)

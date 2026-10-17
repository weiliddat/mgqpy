import numbers
from typing import List

from mgqpy.utils import is_array_index


def _match_exists(doc, path: List[str], ov) -> bool:
    # MongoDB reads only false, null and numeric zero as false; "", [] and {} are true
    want = not (ov is None or (isinstance(ov, numbers.Number) and ov == 0))
    return _path_exists(doc, path) == want


def _path_exists(doc, path: List[str]) -> bool:
    if len(path) == 0:
        return True

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict):
        return key in doc and _path_exists(doc[key], rest)

    if isinstance(doc, list):
        if is_array_index(key) and int(key) < len(doc) and _path_exists(doc[int(key)], rest):
            return True
        return any(_path_exists(d, path) for d in doc if isinstance(d, dict))

    return False

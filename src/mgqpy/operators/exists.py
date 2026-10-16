from typing import List


def _match_exists(doc, path: List[str], ov) -> bool:
    return _path_exists(doc, path) == bool(ov)


def _path_exists(doc, path: List[str]) -> bool:
    if len(path) == 0:
        return True

    key = path[0]
    rest = path[1:]

    if isinstance(doc, dict):
        return key in doc and _path_exists(doc[key], rest)

    if isinstance(doc, list):
        if key.isdigit() and int(key) < len(doc) and _path_exists(doc[int(key)], rest):
            return True
        return any([_path_exists(d, path) for d in doc if isinstance(d, dict)])

    return False

from typing import List

import mgqpy


def _match_all(doc, path: List[str], ov) -> bool:
    if not _validate_all(ov):
        return False

    if len(ov) == 0:
        return False

    if _is_all_elem_match(ov):
        elem_match_query = {"$and": [{".".join(path): o} for o in ov]}
        return mgqpy._match_cond(elem_match_query, doc)

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


# $all can be a list of values, or only $elemMatch if $ expression is in a list of dicts
def _validate_all(ov) -> bool:
    is_list = isinstance(ov, list)
    if is_list:
        if len(ov) == 0:
            return True
        if isinstance(ov[0], dict) and any(k.startswith("$") for k in ov[0].keys()):
            return _is_all_elem_match(ov)
    return is_list


def _is_all_elem_match(ov) -> bool:
    return all(isinstance(o, dict) and "$elemMatch" in o for o in ov)

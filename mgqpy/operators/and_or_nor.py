import mgqpy


def _match_and(doc, path: str, ov) -> bool:
    return all([mgqpy._match_cond(cond, doc) for cond in ov])


def _match_or(doc, path: str, ov) -> bool:
    return any([mgqpy._match_cond(cond, doc) for cond in ov])


def _match_nor(doc, path: str, ov) -> bool:
    return not any([mgqpy._match_cond(cond, doc) for cond in ov])

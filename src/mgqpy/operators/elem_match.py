def _match_elem_match(value, predicate) -> bool:
    if isinstance(value, list):
        for child in value:
            if isinstance(child, (dict, list)) and predicate(child):
                return True
    return False

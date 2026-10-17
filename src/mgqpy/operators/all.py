def _match_all(value, operands) -> bool:
    if not operands or not isinstance(value, list):
        return False
    for operand in operands:
        if not (operand in value or operand == value):
            return False
    return True


def _validate_all(operands) -> bool:
    if operands and isinstance(operands[0], dict):
        if any(key.startswith("$") for key in operands[0]):
            return _is_all_elem_match(operands)
    return True


def _is_all_elem_match(operands) -> bool:
    return all(isinstance(operand, dict) and "$elemMatch" in operand for operand in operands)

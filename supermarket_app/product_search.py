"""Shared product search rules for inventory and purchasing."""
import re


def matches_product(product, search):
    """Match numeric IDs exactly and product names by case-insensitive substring."""
    term = search.strip().casefold()
    if not term:
        return True
    identifier = re.fullmatch(r'(?:id\s*)?(\d+)', term)
    if identifier:
        return product['product_id'] == int(identifier.group(1))
    return term in product['product_name'].casefold()

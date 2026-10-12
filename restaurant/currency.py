from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def format_inr(value):
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return ""

    sign = "-" if amount < 0 else ""
    whole, fraction = f"{abs(amount):.2f}".split(".")
    if len(whole) > 3:
        final_group = whole[-3:]
        remaining = whole[:-3]
        groups = []
        while remaining:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        whole = ",".join([*groups, final_group])

    return f"₹{sign}{whole}.{fraction}"
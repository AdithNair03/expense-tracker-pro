"""Money and number formatting used by templates (registered as Jinja filters)."""
from decimal import ROUND_HALF_UP, Decimal

SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}


def _indian_grouping(n: int) -> str:
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups) + "," + tail


def money(value, currency="INR", decimals=2):
    """money(123456.5) -> '₹1,23,456.50' (Indian grouping for INR, western otherwise)."""
    v = Decimal(str(value or 0)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    sign = "-" if v < 0 else ""
    v = abs(v)
    symbol = SYMBOLS.get(currency, currency + " ")
    whole = int(v)
    frac = f"{v - whole:.{decimals}f}"[1:] if decimals else ""
    grouped = _indian_grouping(whole) if currency == "INR" else f"{whole:,}"
    return f"{sign}{symbol}{grouped}{frac}"


def money_short(value, currency="INR"):
    """Compact form for stat cards: ₹1.2L, ₹3.4K, $1.2M."""
    v = float(value or 0)
    symbol = SYMBOLS.get(currency, currency + " ")
    a = abs(v)
    sign = "-" if v < 0 else ""
    if currency == "INR":
        if a >= 1e7:
            return f"{sign}{symbol}{a / 1e7:.2f}Cr"
        if a >= 1e5:
            return f"{sign}{symbol}{a / 1e5:.2f}L"
    elif a >= 1e6:
        return f"{sign}{symbol}{a / 1e6:.2f}M"
    if a >= 1e3:
        return f"{sign}{symbol}{a / 1e3:.1f}K"
    return f"{sign}{symbol}{a:.0f}"

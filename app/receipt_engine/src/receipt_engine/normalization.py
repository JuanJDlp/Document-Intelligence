import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def folded(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", value.upper()) if not unicodedata.combining(c)
    )


def money(value: str) -> tuple[str | None, list[str]]:
    flags: list[str] = []
    cleaned = re.sub(r"[^0-9.,+-]", "", value)
    if "." in cleaned and "," in cleaned:
        decimal_sep = "." if cleaned.rfind(".") > cleaned.rfind(",") else ","
        cleaned = cleaned.replace("," if decimal_sep == "." else ".", "").replace(decimal_sep, ".")
    else:
        sep = "," if "," in cleaned else "."
        if cleaned.count(sep) > 1:
            cleaned = cleaned.replace(sep, "")
        elif sep in cleaned:
            if len(cleaned.rsplit(sep, 1)[1]) == 3:
                flags.append("AMBIGUOUS_AMOUNT_FORMAT")
                cleaned = cleaned.replace(sep, "")
            else:
                cleaned = cleaned.replace(sep, ".")
    try:
        amount = Decimal(cleaned)
        if not amount.is_finite():
            return None, ["FIELD_INVALID"]
        return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)), flags
    except InvalidOperation:
        return None, ["FIELD_INVALID"]


def normalized_date(value: str, current_year: int) -> tuple[str | None, list[str]]:
    flags: list[str] = []
    value = folded(value.strip()).replace(" DE ", " ")
    months = {
        "ENE": 1,
        "JAN": 1,
        "FEB": 2,
        "MAR": 3,
        "ABR": 4,
        "APR": 4,
        "MAY": 5,
        "JUN": 6,
        "JUL": 7,
        "AGO": 8,
        "AUG": 8,
        "SEP": 9,
        "OCT": 10,
        "NOV": 11,
        "DIC": 12,
        "DEC": 12,
    }
    try:
        if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", value):
            year, month, day = map(int, value.split("-"))
        elif re.fullmatch(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{4}", value):
            day, month, year = map(int, re.split(r"[/.-]", value))
            if day <= 12 and month <= 12:
                flags.append("DATE_FORMAT_ASSUMED")
        else:
            day_s, month_s, year_s = value.split()
            day, month, year = int(day_s), months[month_s[:3]], int(year_s)
            if len(year_s) != 4:
                return None, ["FIELD_INVALID"]
        if not 2000 <= year <= current_year + 1:
            return None, ["FIELD_INVALID"]
        return date(year, month, day).isoformat(), flags
    except (ValueError, KeyError):
        return None, ["FIELD_INVALID"]


def nit(value: str) -> tuple[str | None, bool]:
    digits = re.sub(r"\D", "", value)
    if not 7 <= len(digits) <= 11:
        return None, False
    base, check = digits[:-1], int(digits[-1])
    weights = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)
    remainder = sum(int(v) * weights[i] for i, v in enumerate(reversed(base))) % 11
    expected = remainder if remainder < 2 else 11 - remainder
    return f"{base}-{check}", expected == check

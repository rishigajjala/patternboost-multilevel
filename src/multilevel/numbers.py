from __future__ import annotations

from fractions import Fraction
from typing import Any


def parse_number(value: Any) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, float):
        return Fraction(str(value))
    if isinstance(value, str):
        return Fraction(value)
    raise TypeError(f"unsupported numeric value: {value!r}")


def parse_box(row: list[Any]) -> tuple[Fraction, Fraction, Fraction, Fraction]:
    if len(row) != 4:
        raise ValueError(f"box must have four coordinates, got {row!r}")
    return tuple(parse_number(x) for x in row)  # type: ignore[return-value]


def parse_point(row: list[Any]) -> tuple[Fraction, Fraction]:
    if len(row) != 2:
        raise ValueError(f"point must have two coordinates, got {row!r}")
    return parse_number(row[0]), parse_number(row[1])


def json_number(value: Fraction) -> int | str:
    return value.numerator if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def json_box(box: tuple[Fraction, Fraction, Fraction, Fraction]) -> list[int | str]:
    return [json_number(x) for x in box]


def json_point(point: tuple[Fraction, Fraction]) -> list[int | str]:
    return [json_number(x) for x in point]


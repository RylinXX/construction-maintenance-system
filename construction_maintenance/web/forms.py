from __future__ import annotations

from werkzeug.datastructures import ImmutableMultiDict


def text_value(form: ImmutableMultiDict[str, str], key: str) -> str:
    return (form.get(key) or "").strip()


def required_text(form: ImmutableMultiDict[str, str], key: str, label: str) -> str:
    value = text_value(form, key)
    if not value:
        raise ValueError(f"{label}不能为空")
    return value


def optional_int(
    form: ImmutableMultiDict[str, str], key: str, label: str
) -> int | None:
    value = text_value(form, key)
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{label}必须是整数") from exc

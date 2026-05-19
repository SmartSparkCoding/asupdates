import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"

environment = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def default_timetable():
    return {str(period): {"subject": "", "room": ""} for period in range(1, 8)}


def parse_timetable(raw_value):
    if not raw_value:
        return default_timetable()

    if isinstance(raw_value, dict):
        timetable = default_timetable()
        for period, data in raw_value.items():
            period_key = str(period)
            if period_key in timetable and isinstance(data, dict):
                timetable[period_key]["subject"] = str(data.get("subject", "")).strip()
                timetable[period_key]["room"] = str(data.get("room", "")).strip()
        return timetable

    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError):
        return default_timetable()

    return parse_timetable(parsed)


def serialize_timetable(form_data, prefix):
    timetable = default_timetable()
    for period in timetable:
        timetable[period]["subject"] = form_data.get(f"{prefix}_{period}_subject", "").strip()
        timetable[period]["room"] = form_data.get(f"{prefix}_{period}_room", "").strip()
    return timetable


def timetable_rows(timetable):
    rows = []
    for period, data in timetable.items():
        subject = (data or {}).get("subject", "").strip()
        room = (data or {}).get("room", "").strip()
        if subject or room:
            rows.append({"period": period, "subject": subject, "room": room})
    return rows


def render_email_html(context):
    template = environment.get_template("email.html")
    return template.render(**context)
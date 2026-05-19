import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"

environment = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
SCHEDULE_FIELDS = ["before_school", "break_time", "lunch_time", "after_school"]

PERIOD_TIMES = {
    "1": "08:40 - 09:25",
    "2": "09:30 - 10:15",
    "3": "10:20 - 11:05",
    "Break": "11:05 - 11:20",
    "4": "11:25 - 12:10",
    "5a": "12:15 - 13:00",
    "5b / Lunch": "13:00 - 13:45",
    "6": "14:10 - 15:00",
    "7": "15:05 - 15:50",
}

MENU_FIELDS = ["main", "sides", "pasta_bar", "street_food", "potatoes", "soup", "vegetarian", "dessert"]


def default_timetable():
    return {str(period): {"subject": "", "room": ""} for period in range(1, 8)}


def default_week_schedule():
    return {
        day: {field: "" for field in SCHEDULE_FIELDS}
        for day in WEEKDAYS
    }


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


def parse_week_schedule(raw_value):
    if not raw_value:
        return default_week_schedule()

    if isinstance(raw_value, dict):
        schedule = default_week_schedule()
        for day in WEEKDAYS:
            day_value = raw_value.get(day, {})
            if isinstance(day_value, dict):
                for field in SCHEDULE_FIELDS:
                    schedule[day][field] = str(day_value.get(field, "")).strip()
        return schedule

    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError):
        return default_week_schedule()

    return parse_week_schedule(parsed)


def serialize_timetable(form_data, prefix):
    timetable = default_timetable()
    for period in timetable:
        timetable[period]["subject"] = form_data.get(f"{prefix}_{period}_subject", "").strip()
        timetable[period]["room"] = form_data.get(f"{prefix}_{period}_room", "").strip()
    return timetable


def serialize_week_schedule(form_data, prefix):
    schedule = default_week_schedule()
    for day in WEEKDAYS:
        slug = day.lower()
        for field in SCHEDULE_FIELDS:
            schedule[day][field] = form_data.get(f"{prefix}_{slug}_{field}", "").strip()
    return schedule


def timetable_rows(timetable):
    rows = []
    for period, data in timetable.items():
        subject = (data or {}).get("subject", "").strip()
        room = (data or {}).get("room", "").strip()
        if subject or room:
            rows.append({"period": period, "subject": subject, "room": room})
    return rows


def schedule_day_row(schedule, day_name):
    day_value = (schedule or {}).get(day_name, {})
    return {
        "day": day_name,
        "before_school": day_value.get("before_school", ""),
        "break_time": day_value.get("break_time", ""),
        "lunch_time": day_value.get("lunch_time", ""),
        "after_school": day_value.get("after_school", ""),
    }


def schedule_rows(schedule):
    return [schedule_day_row(schedule, day) for day in WEEKDAYS]


def render_email_html(context):
    template = environment.get_template("email_original.html")
    return template.render(**context)
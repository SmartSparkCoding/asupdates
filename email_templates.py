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
DAY_TIMETABLE_FIELDS = ["before_school", "after_school", "lunch_clubs"]  # User-facing daily timetable
PERIOD_ORDER = ["1", "2", "3", "4", "5a", "5b / Lunch", "6", "7"]

PERIOD_TIMES = {
    "1": "08:40 - 09:25",
    "2": "09:30 - 10:15",
    "3": "10:20 - 11:05",
    "Break": "11:05 - 11:20",
    "4": "11:25 - 12:10",
    "5a": "12:15 - 13:00",
    "5b / Lunch": "13:00 - 13:45",
    "6": "14:15 - 15:00",
    "7": "15:05 - 15:50",
}

MENU_FIELDS = ["main", "sides", "pasta_bar", "street_food", "potatoes", "soup", "vegetarian", "dessert"]


def _period_form_slug(period):
    return str(period).lower().replace(" / ", "_").replace(" ", "_")


def _empty_period_entry():
    return {"subject": "", "room": ""}


def default_timetable():
    return {
        day: {period: _empty_period_entry() for period in PERIOD_ORDER}
        for day in WEEKDAYS
    }


def default_week_schedule():
    return {
        day: {field: "" for field in SCHEDULE_FIELDS}
        for day in WEEKDAYS
    }


def default_day_timetable():
    """User timetable for a single day with before/after school and lunch clubs."""
    return {day: {field: "" for field in DAY_TIMETABLE_FIELDS} for day in WEEKDAYS}


def default_week_menu():
    return {
        day: {field: "" for field in MENU_FIELDS}
        for day in WEEKDAYS
    }


def parse_timetable(raw_value):
    if not raw_value:
        return default_timetable()

    if isinstance(raw_value, dict):
        timetable = default_timetable()
        if any(day in raw_value for day in WEEKDAYS):
            for day in WEEKDAYS:
                day_value = raw_value.get(day, {})
                if not isinstance(day_value, dict):
                    continue
                for period in PERIOD_ORDER:
                    period_value = day_value.get(period, {})
                    if isinstance(period_value, dict):
                        timetable[day][period]["subject"] = str(period_value.get("subject", "")).strip()
                        timetable[day][period]["room"] = str(period_value.get("room", "")).strip()
            return timetable

        legacy_timetable = {period: _empty_period_entry() for period in PERIOD_ORDER}
        for period, data in raw_value.items():
            period_key = str(period)
            if period_key in legacy_timetable and isinstance(data, dict):
                legacy_timetable[period_key]["subject"] = str(data.get("subject", "")).strip()
                legacy_timetable[period_key]["room"] = str(data.get("room", "")).strip()

        for day in WEEKDAYS:
            for period in PERIOD_ORDER:
                timetable[day][period]["subject"] = legacy_timetable[period]["subject"]
                timetable[day][period]["room"] = legacy_timetable[period]["room"]
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


def parse_week_menu(raw_value):
    if not raw_value:
        return default_week_menu()

    if isinstance(raw_value, dict):
        menu = default_week_menu()
        for day in WEEKDAYS:
            day_value = raw_value.get(day, {})
            if isinstance(day_value, dict):
                for field in MENU_FIELDS:
                    menu[day][field] = str(day_value.get(field, "")).strip()
        return menu

    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError):
        menu = default_week_menu()
        menu[WEEKDAYS[0]]["main"] = str(raw_value).strip()
        return menu

    return parse_week_menu(parsed)


def serialize_timetable(form_data, prefix):
    timetable = default_timetable()
    for day in WEEKDAYS:
        day_slug = day.lower()
        for period in PERIOD_ORDER:
            period_slug = _period_form_slug(period)
            timetable[day][period]["subject"] = form_data.get(f"{prefix}_{day_slug}_{period_slug}_subject", "").strip()
            timetable[day][period]["room"] = form_data.get(f"{prefix}_{day_slug}_{period_slug}_room", "").strip()
    return timetable


def timetable_day_rows(timetable, day_name):
    day_value = (timetable or {}).get(day_name, {})
    rows = []
    for period in PERIOD_ORDER:
        period_value = day_value.get(period, {})
        rows.append({
            "period": period,
            "time": PERIOD_TIMES.get(period, ""),
            "subject": (period_value or {}).get("subject", ""),
            "room": (period_value or {}).get("room", ""),
        })
    return rows


def serialize_week_schedule(form_data, prefix):
    schedule = default_week_schedule()
    for day in WEEKDAYS:
        slug = day.lower()
        for field in SCHEDULE_FIELDS:
            schedule[day][field] = form_data.get(f"{prefix}_{slug}_{field}", "").strip()
    return schedule


def serialize_week_menu(form_data, prefix):
    menu = default_week_menu()
    for day in WEEKDAYS:
        slug = day.lower()
        for field in MENU_FIELDS:
            menu[day][field] = form_data.get(f"{prefix}_{slug}_{field}", "").strip()
    return menu


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


def render_template_html(template_name, context):
    template = environment.get_template(template_name)
    return template.render(**context)


def render_mailing_list_email_html(context):
    return render_template_html("mailing_list_email.html", context)

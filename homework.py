from __future__ import annotations

from datetime import date, datetime, timedelta


def _row_to_dict(row):
    if not row:
        return {}
    return {key: row[key] for key in row.keys()}


def fetch_homework_items(conn, user_id: int):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, user_id, subject, title, details, due_date, due_time, completed, created_at
        FROM homework_items
        WHERE user_id=?
        ORDER BY due_date ASC, due_time ASC, created_at DESC
        """,
        (user_id,),
    )
    return [_row_to_dict(row) for row in cursor.fetchall()]


def parse_due_date(raw_value):
    if not raw_value:
        return None
    try:
        return date.fromisoformat(str(raw_value))
    except ValueError:
        return None


def _homework_sort_key(item):
    due_date = parse_due_date(item.get("due_date")) or date.max
    due_time = item.get("due_time") or "23:59"
    return (due_date, due_time)


def split_homework(items, today=None):
    today = today or date.today()
    tomorrow = today + timedelta(days=1)

    due_today = []
    due_tomorrow = []
    overdue = []
    upcoming = []

    for item in sorted(items, key=_homework_sort_key):
        due_date = parse_due_date(item.get("due_date"))
        if not due_date:
            continue

        if due_date < today and not item.get("completed"):
            overdue.append(item)
        elif due_date == today:
            due_today.append(item)
        elif due_date == tomorrow:
            due_tomorrow.append(item)
        else:
            upcoming.append(item)

    next_homework = None
    for item in sorted(items, key=_homework_sort_key):
        if not item.get("completed"):
            next_homework = item
            break

    return {
        "due_today": due_today,
        "due_tomorrow": due_tomorrow,
        "overdue": overdue,
        "upcoming": upcoming,
        "next_homework": next_homework,
        "pending_count": sum(1 for item in items if not item.get("completed")),
    }


def homework_email_summary(items, today=None):
    sections = split_homework(items, today=today)
    return {
        "due_today": sections["due_today"],
        "due_tomorrow": sections["due_tomorrow"],
        "overdue": sections["overdue"],
        "next_homework": sections["next_homework"],
        "pending_count": sections["pending_count"],
    }

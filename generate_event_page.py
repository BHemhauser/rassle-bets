"""
Generate a clean HTML event page from wrestling CSV data.

This script:
1) Loads the CSV file
2) Asks for an EventID
3) Filters rows for that EventID
4) Groups rows by Match
5) Builds a responsive HTML page
6) Saves the output to event.html
"""

from collections import OrderedDict
import csv
from datetime import datetime
import html
from pathlib import Path
from string import Template
from typing import Optional


CSV_FILE = Path("data.csv")
FALLBACK_CSV_FILE = Path("WrestleGame_db - Sheet1.csv")
TEMPLATE_FILE = Path("template.html")
OUTPUT_FILE = Path("event.html")
BELT_DEFAULT_IMAGE = "assets/belts/default.png"
BELT_IMAGE_BY_MATCH = {
    "World Heavyweight Championship": "assets/belts/world_heavyweight.png",
    "Women's Intercontinental Championship": "assets/belts/womens_ic.png",
    "Women's Intercontinental Champion": "assets/belts/womens_ic.png",
}


def normalize(value: str) -> str:
    """Return a trimmed, lowercase version of text for safer comparisons."""
    return (value or "").strip().lower()


def pick_first_key(row: dict, possible_keys: list[str]) -> str:
    """
    Return the first matching key name from possible_keys that exists in row.
    Returns an empty string if none are found.
    """
    for key in possible_keys:
        if key in row:
            return key
    return ""


def load_rows(csv_path: Path) -> list[dict]:
    """Read all rows from a CSV file and return them as a list of dictionaries."""
    with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def get_available_event_ids(rows: list[dict], event_id_key: str) -> list[str]:
    """Collect unique EventIDs in the order they first appear."""
    seen = OrderedDict()
    for row in rows:
        event_id = (row.get(event_id_key) or "").strip()
        if event_id:
            seen[event_id] = True
    return list(seen.keys())


def is_current_champion(value: str) -> bool:
    """Interpret several common yes/true values as champion markers."""
    return normalize(value) in {"y", "yes", "true", "1"}


def parse_american_odds(odds_text: str) -> Optional[int]:
    """Convert odds text to an integer (e.g., '150', '+150', '-200') or None."""
    cleaned = (odds_text or "").strip()
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def format_odds(odds_text: str) -> str:
    """
    Return display-friendly odds text.
    - Positive odds are shown with a '+' sign (150 -> +150)
    - Missing/invalid odds are shown as TBD
    """
    odds_value = parse_american_odds(odds_text)
    if odds_value is None:
        return "TBD"

    if odds_value > 0:
        return f"+{odds_value}"
    return str(odds_value)


def format_start_time(time_text: str) -> str:
    """
    Convert HH:MM (24-hour) to h:mmam/pm EST.
    Example: 19:00 -> 7:00pm EST
    """
    raw = (time_text or "").strip()
    if not raw:
        return "Unknown"

    parts = raw.split(":")
    if len(parts) < 2:
        return raw

    try:
        hour_24 = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return raw

    suffix = "am" if hour_24 < 12 else "pm"
    hour_12 = hour_24 % 12
    if hour_12 == 0:
        hour_12 = 12
    return f"{hour_12}:{minute:02d}{suffix} EST"


def day_ordinal(day: int) -> str:
    """Return day number with ordinal suffix (1st, 2nd, 3rd, etc.)."""
    if 11 <= day % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def format_event_date(date_text: str) -> str:
    """
    Convert date values like 2/28/2026 into:
    Saturday, February 28th, 2026
    """
    raw = (date_text or "").strip()
    if not raw:
        return "Unknown Date"

    parsed = None
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw, fmt)
            break
        except ValueError:
            continue

    if not parsed:
        return raw

    weekday = parsed.strftime("%A")
    month = parsed.strftime("%B")
    return f"{weekday}, {month} {day_ordinal(parsed.day)}, {parsed.year}"


def load_template(template_path: Path) -> Template:
    """Load HTML template file and return a Template object."""
    with template_path.open("r", encoding="utf-8") as f:
        return Template(f.read())


def find_logo_path(event_id: str) -> Optional[str]:
    """
    Find a logo by EventID in assets/logos using:
    1) assets/logos/<EventID>.png
    2) assets/logos/<eventid_lower>.png
    Returns a relative path string, or None if not found.
    """
    cleaned = (event_id or "").strip()
    if not cleaned:
        return None

    candidates = [
        Path("assets/logos") / f"{cleaned}.png",
        Path("assets/logos") / f"{cleaned.lower()}.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.as_posix()
    return None


def belt_image_for_match(match_name: str) -> str:
    """
    Return belt image path for a match, with default fallback.
    """
    mapped = BELT_IMAGE_BY_MATCH.get((match_name or "").strip())
    if mapped:
        return mapped
    return BELT_DEFAULT_IMAGE


def build_event_html(event_rows: list[dict], keys: dict[str, str]) -> str:
    """
    Build a full HTML document for one event.
    The page includes event details and match sections with wrestler cards.
    """
    first = event_rows[0]
    raw_event_name = (first.get(keys["event"]) or "Unknown Event").strip()
    raw_event_id = (first.get(keys["event_id"]) or "").strip()
    event_name = html.escape(raw_event_name)
    event_id = html.escape(raw_event_id)
    event_date = html.escape(format_event_date(first.get(keys["date"]) or ""))
    start_time = html.escape(format_start_time(first.get(keys["start_time"]) or ""))
    country = html.escape((first.get(keys["country"]) or "").strip())
    location = html.escape((first.get(keys["location"]) or "").strip())
    venue = html.escape((first.get(keys["venue"]) or "").strip())
    logo_path = find_logo_path(raw_event_id)

    if logo_path:
        event_header = (
            f'<img class="event-logo" src="{html.escape(logo_path)}" '
            f'alt="{html.escape(raw_event_name)} logo">'
        )
    else:
        event_header = f"<h1>{event_name}</h1>"

    # Group rows by match while preserving order.
    matches = OrderedDict()
    for row in event_rows:
        match_name = (row.get(keys["match"]) or "Unknown Match").strip()
        matches.setdefault(match_name, []).append(row)

    match_sections = []
    for match_name, rows in matches.items():
        safe_match_name = html.escape(match_name)
        wrestler_items = []
        for row in rows:
            wrestler_name = html.escape((row.get(keys["wrestler"]) or "Unknown Wrestler").strip())
            raw_odds = row.get(keys["odds"]) or ""
            odds_value = parse_american_odds(raw_odds)
            odds = html.escape(format_odds(raw_odds))
            champ_raw = row.get(keys["champion"]) or ""
            champ = is_current_champion(champ_raw)

            champ_class = " wrestler champion" if champ else " wrestler"
            belt_icon = ""
            if champ:
                belt_path = html.escape(belt_image_for_match(match_name))
                belt_icon = (
                    f'<img class="belt-icon" src="{belt_path}" '
                    f'alt="{html.escape(match_name)} belt">'
                )
            odds_data = html.escape(str(odds_value) if odds_value is not None else "")
            wager_disabled = " disabled" if odds_value is None else ""
            wager_placeholder = "TBD" if odds_value is None else "0"

            wrestler_items.append(
                f"""
                <div class="{champ_class}" data-match="{safe_match_name}" data-odds="{odds_data}">
                    <div class="wrestler-main">
                        <span class="name">{wrestler_name}{belt_icon}</span>
                    </div>
                    <div class="odds">Odds: {odds}</div>
                    <div class="wager-row">
                        <label class="wager-label">Wager (pts)</label>
                        <input class="wager-input" type="number" min="0" step="1" value="0" placeholder="{wager_placeholder}"{wager_disabled}>
                    </div>
                </div>
                """
            )
        match_sections.append(
            f"""
            <section class="match-card">
                <button class="match-toggle" type="button" aria-expanded="true">
                    <h2>{safe_match_name}</h2>
                    <span class="toggle-icon" aria-hidden="true">▾</span>
                </button>
                <div class="match-body">
                    {"".join(wrestler_items)}
                </div>
            </section>
            """
        )

    template = load_template(TEMPLATE_FILE)
    return template.safe_substitute(
        page_title=f"{event_name} ({event_id})",
        event_header=event_header,
        event_id_plain=event_id,
        event_name_plain=event_name,
        event_name=event_name,
        start_time=start_time,
        event_date=event_date,
        country=country,
        location=location,
        venue=venue,
        match_sections="".join(match_sections),
    )


def main() -> None:
    """Program entry point."""
    csv_path = CSV_FILE if CSV_FILE.exists() else FALLBACK_CSV_FILE
    if not csv_path.exists():
        print(f"Error: Could not find '{CSV_FILE}' (or fallback '{FALLBACK_CSV_FILE}').")
        return
    if not TEMPLATE_FILE.exists():
        print(f"Error: Could not find '{TEMPLATE_FILE}'.")
        return

    rows = load_rows(csv_path)
    if not rows:
        print("Error: CSV file is empty.")
        return

    sample_row = rows[0]

    # Support both the user's listed headers and the current CSV headers.
    keys = {
        "event_id": pick_first_key(sample_row, ["EventID"]),
        "event": pick_first_key(sample_row, ["Event"]),
        "date": pick_first_key(sample_row, ["Date"]),
        "start_time": pick_first_key(sample_row, ["StartTime", "Start Time"]),
        "country": pick_first_key(sample_row, ["Country"]),
        "location": pick_first_key(sample_row, ["Location"]),
        "venue": pick_first_key(sample_row, ["Venue"]),
        "match": pick_first_key(sample_row, ["Match"]),
        "wrestler": pick_first_key(sample_row, ["Wrestler"]),
        "champion": pick_first_key(sample_row, ["CurrentChamp", "Current Champ (Y/N)"]),
        "odds": pick_first_key(sample_row, ["Odds"]),
    }

    missing = [name for name, key in keys.items() if not key]
    if missing:
        print("Error: Missing required CSV columns for:", ", ".join(missing))
        print("Please check the header row in your CSV.")
        return

    available_event_ids = get_available_event_ids(rows, keys["event_id"])
    if not available_event_ids:
        print("Error: No EventID values found.")
        return

    print("Available EventIDs:", ", ".join(available_event_ids))
    selected_event_id = input("Enter EventID to generate (example: EC2026): ").strip()

    event_rows = [
        row for row in rows
        if normalize(row.get(keys["event_id"]) or "") == normalize(selected_event_id)
    ]
    if not event_rows:
        print(f"Error: No rows found for EventID '{selected_event_id}'.")
        return

    detected_matches = list(OrderedDict.fromkeys(
        (row.get(keys["match"]) or "Unknown Match").strip() for row in event_rows
    ))
    print("Detected Match names:")
    for match_name in detected_matches:
        print(f" - {match_name}")

    html_text = build_event_html(event_rows, keys)
    OUTPUT_FILE.write_text(html_text, encoding="utf-8")
    print(f"Success! Created '{OUTPUT_FILE}'.")


if __name__ == "__main__":
    main()

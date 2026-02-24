"""
Generate a clean HTML event page from wrestling CSV data.

This script:
1) Loads the CSV file
2) Generates one page per EventID: event_<EventID>.html
3) Builds an index.html linking all generated event pages
"""

from collections import OrderedDict
import csv
from datetime import datetime, timezone
import html
from pathlib import Path
import re
from string import Template
from typing import Optional


CSV_FILE = Path("data/EC2026.csv")
FALLBACK_CSV_FILE = Path("data.csv")
LEGACY_FALLBACK_CSV_FILE = Path("WrestleGame_db - Sheet1.csv")
TEMPLATE_FILE = Path("template.html")
INDEX_FILE = Path("index.html")
LEGACY_EVENT_FILE = Path("event.html")
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


def sanitize_event_id(event_id: str) -> str:
    """Convert EventID into a file-safe value."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", (event_id or "").strip())


def event_output_file(event_id: str) -> Path:
    """Build output filename for one event page."""
    return Path(f"event_{sanitize_event_id(event_id)}.html")


def parse_event_date_for_sort(date_text: str) -> datetime:
    """Parse event date for index sorting (newest first)."""
    raw = (date_text or "").strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return datetime.min


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
    last_updated = datetime.now(timezone.utc).strftime("%B %d, %Y %H:%M UTC")

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
            raw_result = ""
            if keys.get("result"):
                raw_result = (row.get(keys["result"]) or "").strip().upper()
            result_value = raw_result if raw_result in {"W", "L"} else ""

            champ_class = " wrestler champion" if champ else " wrestler"
            if result_value == "L":
                champ_class += " result-lost"
            belt_icon = ""
            if champ:
                belt_path = html.escape(belt_image_for_match(match_name))
                belt_icon = (
                    f'<img class="belt-icon" src="{belt_path}" '
                    f'alt="{html.escape(match_name)} belt">'
                )
            result_indicator = ""
            if result_value == "W":
                result_indicator = '<span class="result-pill winner">Winner</span>'
            elif result_value == "L":
                result_indicator = '<span class="result-pill lost">Lost</span>'
            odds_data = html.escape(str(odds_value) if odds_value is not None else "")
            result_data = html.escape(result_value)
            wager_disabled = " disabled" if odds_value is None else ""
            wager_placeholder = "TBD" if odds_value is None else "0"

            wrestler_items.append(
                f"""
                <div class="{champ_class}" data-match="{safe_match_name}" data-odds="{odds_data}" data-result="{result_data}">
                    <div class="wrestler-main">
                        <span class="name">{wrestler_name}{belt_icon}{result_indicator}</span>
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
        last_updated=last_updated,
        match_sections="".join(match_sections),
    )


def load_leaderboard_rows(event_id: str) -> list[dict]:
    """
    Load optional leaderboard CSV for an event.
    Expected path: data/<EventID>_leaderboard.csv
    Columns: Player, Score, PendingWager, MaxPossiblePoints, Wins, Losses
    """
    leaderboard_path = Path("data") / f"{event_id}_leaderboard.csv"
    if not leaderboard_path.exists():
        return []
    with leaderboard_path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return []

    valid_rows = []
    for row in rows:
        player = (row.get("Player") or "").strip()
        if not player:
            continue
        try:
            score = int(float((row.get("Score") or row.get("Net") or "0").strip() or "0"))
        except ValueError:
            score = 0
        score = max(0, score)
        try:
            pending_wager = int(float((row.get("PendingWager") or "0").strip() or "0"))
        except ValueError:
            pending_wager = 0
        try:
            max_possible_points = int(float((row.get("MaxPossiblePoints") or "0").strip() or "0"))
        except ValueError:
            max_possible_points = 0
        try:
            wins = int(float((row.get("Wins") or "0").strip() or "0"))
        except ValueError:
            wins = 0
        try:
            losses = int(float((row.get("Losses") or "0").strip() or "0"))
        except ValueError:
            losses = 0
        valid_rows.append(
            {
                "Player": player,
                "Score": score,
                "PendingWager": pending_wager,
                "MaxPossiblePoints": max_possible_points,
                "Wins": wins,
                "Losses": losses,
            }
        )
    valid_rows.sort(key=lambda item: item["Score"], reverse=True)
    return valid_rows


def format_whole(value: int) -> str:
    """Format integer-like values as whole numbers."""
    return str(int(value))


def build_live_html(event_rows: list[dict], keys: dict[str, str], leaderboard_rows: list[dict]) -> str:
    """Build live tracker page HTML for one event."""
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
    last_updated = datetime.now(timezone.utc).strftime("%B %d, %Y %H:%M UTC")

    if logo_path:
        event_header = (
            f'<img class="event-logo" src="{html.escape(logo_path)}" '
            f'alt="{html.escape(raw_event_name)} logo">'
        )
    else:
        event_header = f"<h1>{event_name}</h1>"

    matches = OrderedDict()
    for row in event_rows:
        match_name = (row.get(keys["match"]) or "Unknown Match").strip()
        matches.setdefault(match_name, []).append(row)

    total_matches = len(matches)
    completed_matches = 0
    match_sections = []
    any_pending = False

    for match_name, rows in matches.items():
        winner_count = 0
        wrestler_items = []
        for row in rows:
            wrestler_name_raw = (row.get(keys["wrestler"]) or "Unknown Wrestler").strip()
            wrestler_name = html.escape(wrestler_name_raw)
            raw_odds = row.get(keys["odds"]) or ""
            odds = html.escape(format_odds(raw_odds))
            champ_raw = row.get(keys["champion"]) or ""
            champ = is_current_champion(champ_raw)
            result_raw = (row.get(keys.get("result", "")) or "").strip().upper() if keys.get("result") else ""
            result_value = result_raw if result_raw in {"W", "L"} else ""

            champ_class = " wrestler champion" if champ else " wrestler"
            if result_value == "L":
                champ_class += " result-lost"

            belt_icon = ""
            if champ:
                belt_path = html.escape(belt_image_for_match(match_name))
                belt_icon = (
                    f'<img class="belt-icon" src="{belt_path}" '
                    f'alt="{html.escape(match_name)} belt">'
                )

            result_indicator = ""
            if result_value == "W":
                result_indicator = '<span class="result-pill winner">Winner</span>'
                winner_count += 1
            elif result_value == "L":
                result_indicator = '<span class="result-pill lost">Lost</span>'

            wrestler_items.append(
                f"""
                <div class="{champ_class}">
                    <div class="wrestler-main">
                        <span class="name">{wrestler_name}{belt_icon}{result_indicator}</span>
                    </div>
                    <div class="odds">Odds: {odds}</div>
                </div>
                """
            )

        match_status = "Final" if winner_count >= 1 else "Pending"
        match_status_class = "final" if winner_count >= 1 else "pending"
        if winner_count >= 1:
            completed_matches += 1
        else:
            any_pending = True

        safe_match_name = html.escape(match_name)
        match_sections.append(
            f"""
            <section class="match-card">
                <button class="match-toggle" type="button" aria-expanded="true">
                    <div class="match-toggle-meta">
                        <h2>{safe_match_name}</h2>
                        <span class="match-status {match_status_class}">Status: {match_status}</span>
                    </div>
                    <span class="toggle-icon" aria-hidden="true">▾</span>
                </button>
                <div class="match-body">
                    {"".join(wrestler_items)}
                </div>
            </section>
            """
        )

    if completed_matches == 0:
        live_status = "Pending"
    elif any_pending:
        live_status = "Live"
    else:
        live_status = "Final"

    if leaderboard_rows:
        top_score = max((row["Score"] for row in leaderboard_rows), default=0)
        leaderboard_body = []
        for row in leaderboard_rows:
            player = html.escape(row["Player"])
            score = html.escape(format_whole(max(0, row["Score"])))
            wins = html.escape(format_whole(row["Wins"]))
            losses = html.escape(format_whole(row["Losses"]))
            pending_wager = html.escape(format_whole(row["PendingWager"]))
            max_possible = html.escape(format_whole(row["MaxPossiblePoints"]))
            max_output = html.escape(format_whole(max(0, row["Score"]) + row["MaxPossiblePoints"]))
            leader_class = " leader-row" if row["Score"] == top_score else ""
            leaderboard_body.append(
                f"""
                <tr class="{leader_class.strip()}">
                  <td>{player}</td>
                  <td class="score-cell">{score}</td>
                  <td class="stat-cell">{wins}-{losses}</td>
                  <td class="num-cell">{pending_wager}</td>
                  <td class="num-cell">{max_possible}</td>
                  <td class="num-cell">{max_output}</td>
                </tr>
                """
            )
        leaderboard_html = f"""
        <section class="summary-panel leaderboard-panel">
          <h3 class="summary-title">Leaderboard</h3>
          <div class="table-wrap">
            <table class="leaderboard-table">
              <thead>
                <tr>
                  <th>Player</th>
                  <th class="score-head">Score</th>
                  <th>W-L</th>
                  <th>Pending Wager</th>
                  <th>Max Possible Points</th>
                  <th>Max Output</th>
                </tr>
              </thead>
              <tbody>
                {"".join(leaderboard_body)}
              </tbody>
            </table>
          </div>
        </section>
        """
    else:
        leaderboard_html = """
        <section class="summary-panel leaderboard-panel">
          <h3 class="summary-title">Leaderboard</h3>
          <div class="validation-message">Leaderboard data not found yet. Add the event leaderboard CSV in the data folder to show standings.</div>
        </section>
        """

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{event_name} Live Tracker ({event_id})</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main class="container">
    <header class="event-header" data-event-name="{event_name}">
      {event_header}
      <div class="event-time"><strong>Start Time:</strong> {start_time}</div>
      <div class="event-meta">
        <div><strong>Date:</strong> {event_date}</div>
        <div><strong>Country:</strong> {country}</div>
        <div><strong>Location:</strong> {location}</div>
        <div><strong>Venue:</strong> {venue}</div>
      </div>
      <div class="live-status-line"><strong>Status:</strong> {html.escape(live_status)} | <strong>Matches completed:</strong> {completed_matches} / {total_matches}</div>
    </header>

    <nav class="page-nav" aria-label="Page navigation">
      <a class="copy-btn btn-secondary" href="event_{sanitize_event_id(raw_event_id)}.html">Make Picks</a>
      <a class="copy-btn btn-primary" href="live_{sanitize_event_id(raw_event_id)}.html">Live Tracker</a>
    </nav>

    {leaderboard_html}

    <section class="match-controls" aria-label="Match controls">
      <button id="expand-all" class="copy-btn btn-secondary" type="button">Expand all</button>
      <button id="collapse-all" class="copy-btn btn-secondary" type="button">Collapse all</button>
    </section>

    <section class="matches">
      {"".join(match_sections)}
    </section>

    <footer class="site-footer">
      Last updated: {html.escape(last_updated)}
    </footer>
  </main>
  <script>
  document.addEventListener("DOMContentLoaded", function () {{
    const cards = Array.from(document.querySelectorAll(".match-card"));
    function setExpanded(card, expanded) {{
      const toggle = card.querySelector(".match-toggle");
      const body = card.querySelector(".match-body");
      if (!toggle || !body) return;
      toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
      body.hidden = !expanded;
    }}
    cards.forEach(function (card) {{
      const toggle = card.querySelector(".match-toggle");
      setExpanded(card, true);
      if (toggle) {{
        toggle.addEventListener("click", function () {{
          const expanded = toggle.getAttribute("aria-expanded") === "true";
          setExpanded(card, !expanded);
        }});
      }}
    }});
    const expandAll = document.getElementById("expand-all");
    const collapseAll = document.getElementById("collapse-all");
    if (expandAll) expandAll.addEventListener("click", function () {{ cards.forEach(function (c) {{ setExpanded(c, true); }}); }});
    if (collapseAll) collapseAll.addEventListener("click", function () {{ cards.forEach(function (c) {{ setExpanded(c, false); }}); }});
  }});
  </script>
</body>
</html>
"""


def main() -> None:
    """Program entry point."""
    if CSV_FILE.exists():
        csv_path = CSV_FILE
    elif FALLBACK_CSV_FILE.exists():
        csv_path = FALLBACK_CSV_FILE
    else:
        csv_path = LEGACY_FALLBACK_CSV_FILE
    if not csv_path.exists():
        print(
            "Error: Could not find a source CSV. Checked: "
            f"'{CSV_FILE}', '{FALLBACK_CSV_FILE}', '{LEGACY_FALLBACK_CSV_FILE}'."
        )
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
        "result": pick_first_key(sample_row, ["Result"]),
    }

    required_keys = ["event_id", "event", "date", "start_time", "country", "location", "venue", "match", "wrestler", "champion", "odds"]
    missing = [name for name in required_keys if not keys.get(name)]
    if missing:
        print("Error: Missing required CSV columns for:", ", ".join(missing))
        print("Please check the header row in your CSV.")
        return

    available_event_ids = get_available_event_ids(rows, keys["event_id"])
    if not available_event_ids:
        print("Error: No EventID values found.")
        return

    print("Available EventIDs:", ", ".join(available_event_ids))

    event_summaries = []
    for event_id in available_event_ids:
        event_rows = [
            row for row in rows
            if normalize(row.get(keys["event_id"]) or "") == normalize(event_id)
        ]
        if not event_rows:
            continue

        detected_matches = list(OrderedDict.fromkeys(
            (row.get(keys["match"]) or "Unknown Match").strip() for row in event_rows
        ))
        print(f"Detected Match names for {event_id}:")
        for match_name in detected_matches:
            print(f" - {match_name}")

        output_file = event_output_file(event_id)
        html_text = build_event_html(event_rows, keys)
        output_file.write_text(html_text, encoding="utf-8")
        print(f"Created '{output_file.name}'.")
        live_output_file = Path(f"live_{sanitize_event_id(event_id)}.html")
        leaderboard_rows = load_leaderboard_rows(event_id)
        live_html = build_live_html(event_rows, keys, leaderboard_rows)
        live_output_file.write_text(live_html, encoding="utf-8")
        print(f"Created '{live_output_file.name}'.")

        first = event_rows[0]
        event_summaries.append(
            {
                "event_id": (first.get(keys["event_id"]) or "").strip(),
                "event_name": (first.get(keys["event"]) or "Unknown Event").strip(),
                "date": (first.get(keys["date"]) or "").strip(),
                "location": (first.get(keys["location"]) or "Unknown Location").strip() or "Unknown Location",
                "file_name": output_file.name,
            }
        )

    event_summaries.sort(
        key=lambda item: parse_event_date_for_sort(item["date"]),
        reverse=True,
    )

    index_items = []
    for item in event_summaries:
        event_name = html.escape(item["event_name"])
        event_id = html.escape(item["event_id"])
        date_text = html.escape(format_event_date(item["date"]))
        location = html.escape(item["location"])
        href = html.escape(item["file_name"])
        live_href = html.escape(f"live_{sanitize_event_id(item['event_id'])}.html")
        index_items.append(
            f"""
            <section class="match-card">
              <h2>{event_name}</h2>
              <div class="event-meta">
                <div><strong>EventID:</strong> {event_id}</div>
                <div><strong>Date:</strong> {date_text}</div>
                <div><strong>Location:</strong> {location}</div>
              </div>
              <p style="margin: 12px 0 0;"><a href="{href}">Make Picks</a> | <a href="{live_href}">Live Tracker</a></p>
            </section>
            """
        )

    index_updated = datetime.now(timezone.utc).strftime("%B %d, %Y %H:%M UTC")
    index_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Event Index</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main class="container">
    <header class="event-header">
      <h1>Event Pages</h1>
      <div class="event-meta"><div>Generated from {html.escape(csv_path.name)}</div></div>
    </header>
    <section class="matches">
      {"".join(index_items)}
    </section>
    <footer class="site-footer">
      Last updated: {html.escape(index_updated)}
    </footer>
  </main>
</body>
</html>
"""
    INDEX_FILE.write_text(index_html, encoding="utf-8")
    print(f"Created '{INDEX_FILE.name}'.")
    if LEGACY_EVENT_FILE.exists():
        print(
            f"Note: '{LEGACY_EVENT_FILE.name}' already exists but is not generated anymore. "
            "Use event_<EventID>.html files and index.html."
        )


if __name__ == "__main__":
    main()

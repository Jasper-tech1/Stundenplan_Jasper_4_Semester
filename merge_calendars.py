import re
import requests
from icalendar import Calendar

FEED_URLS = [
    "https://sked.lin.hs-osnabrueck.de/sked/grp/24BTS-MAS-4.ics",
    "https://sked.lin.hs-osnabrueck.de/sked/grp/24BTS-EAT-4.ics",
]

EXCLUDE_KEYWORDS = [
    "Entwurfsberechnung statischer Systeme",
    "englisch",
    "Fluidmechanik",
    "Konstruktion technischer Baugruppen",
    "elektrotechnik",
    "metallbau",
]

OUTPUT_FILE = "Stundenplan.ics"


def normalize_encoding(s: str) -> str:
    if not s:
        return ""

    replacements = {
        "Ã¼": "ü",
        "Ã¶": "ö",
        "Ã¤": "ä",
        "Ãœ": "Ü",
        "Ã–": "Ö",
        "Ã„": "Ä",
        "ÃŸ": "ß",
        "â€“": "–",
        "â€”": "—",
        "â€ž": "„",
        "â€œ": "“",
        "â€š": "‚",
        "â€™": "’",
    }

    for wrong, right in replacements.items():
        s = s.replace(wrong, right)

    return s


def clean_text(s: str) -> str:
    if not s:
        return ""
    s = str(s)
    s = normalize_encoding(s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def normalize_summary(summary: str) -> str:
    s = clean_text(summary)
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def should_keep_event(summary: str) -> bool:
    normalized = clean_text(summary).lower()
    for bad in EXCLUDE_KEYWORDS:
        if bad.lower() in normalized:
            print(f"Filtere Event wegen Keyword '{bad}': {summary}")
            return False
    return True


def sanitize_component_text_fields(component) -> None:
    for field in ["summary", "description", "location"]:
        value = component.get(field)
        if value is not None:
            component[field] = clean_text(str(value))


def fetch_calendar(url: str):
    try:
        print(f"Lade {url} ...")
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()

        print("HTTP Status:", resp.status_code)
        print("Erste 100 Bytes:", resp.content[:100])

        cal = Calendar.from_ical(resp.content)
        return cal

    except Exception as e:
        print(f"Fehler beim Laden oder Parsen von {url}: {e}")
        return None


def build_merged_calendar() -> Calendar:
    print("Baue zusammengeführten Kalender ...")

    merged_cal = Calendar()
    merged_cal.add("prodid", "-//Merged Uni Plan//DE")
    merged_cal.add("version", "2.0")
    merged_cal.add("X-WR-CALNAME", "Uni Stundenplan")
    merged_cal.add("X-WR-TIMEZONE", "Europe/Berlin")
    merged_cal.add("CALSCALE", "GREGORIAN")
    merged_cal.add("METHOD", "PUBLISH")

    seen = set()
    total_events = 0
    kept_events = 0

    for url in FEED_URLS:
        src_cal = fetch_calendar(url)
        if src_cal is None:
            continue

        for component in src_cal.walk():
            if component.name != "VEVENT":
                continue

            total_events += 1

            summary = str(component.get("summary", ""))
            summary_clean = clean_text(summary)

            print("Gefundenes Event:", summary_clean)

            if not should_keep_event(summary_clean):
                continue

            dtstart_field = component.get("dtstart")
            dtend_field = component.get("dtend")

            if not dtstart_field:
                print(f"Überspringe Event ohne DTSTART: {summary_clean}")
                continue

            dtstart = dtstart_field.dt
            dtend = dtend_field.dt if dtend_field else None
            norm_title = normalize_summary(summary_clean)

            dedup_key = (dtstart, dtend, norm_title)

            if dedup_key in seen:
                print(f"Duplikat, überspringe: {summary_clean} @ {dtstart}")
                continue

            seen.add(dedup_key)

            sanitize_component_text_fields(component)
            merged_cal.add_component(component)
            kept_events += 1

    print(f"Fertig: {kept_events} von {total_events} Events übernommen.")
    return merged_cal


def save_calendar(cal: Calendar, output_path: str) -> None:
    ics_data = cal.to_ical()

    print("Ausgabedatei:", output_path)
    print("Anzahl Bytes:", len(ics_data))
    print("Vorschau:", ics_data[:200])

    with open(output_path, "wb") as f:
        f.write(ics_data)

    print(f"Kalender-Datei gespeichert unter: {output_path}")


def main():
    print("Starte Skript ...")
    cal = build_merged_calendar()
    save_calendar(cal, OUTPUT_FILE)
    print("Skript fertig.")


if __name__ == "__main__":
    main()

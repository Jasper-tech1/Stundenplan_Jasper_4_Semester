import re
import requests
from icalendar import Calendar

# ==============================
# KONFIGURATION
# ==============================

FEED_URLS = [
    "https://sked.lin.hs-osnabrueck.de/sked/grp/24BTS-MAS-4.ics",
    "https://sked.lin.hs-osnabrueck.de/sked/grp/24BTS-EAT-4.ics",
]

# Module, die NICHT im Kalender erscheinen sollen
EXCLUDE_KEYWORDS = [
    "Entwurfsberechnung statischer Systeme",
    "englisch",
    "Fluidmechanik",
    "Konstruktion technischer Baugruppen",
    "elektrotechnik",
    "metallbau",
]

OUTPUT_FILE = "Stundenplan.ics"

# ==============================
# HILFSFUNKTIONEN
# ==============================

def normalize_encoding(s: str) -> str:
    """
    Behebt typische Mojibake-/Encoding-Probleme wie:
    'Ã¼' -> 'ü'
    """
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
    """
    Vereinheitlicht Text für Vergleiche:
    - Encoding korrigieren
    - trimmen
    - Mehrfach-Leerzeichen entfernen
    """
    if not s:
        return ""

    s = str(s)
    s = normalize_encoding(s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def normalize_summary(summary: str) -> str:
    """
    Normalisiert Veranstaltungstitel für Dubletten-Erkennung:
    - Encoding korrigieren
    - Klammerzusätze entfernen
    - Leerzeichen vereinheitlichen
    - in Kleinbuchstaben umwandeln
    """
    s = clean_text(summary)
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def should_keep_event(summary: str) -> bool:
    """
    Prüft, ob ein Event behalten werden soll.
    """
    normalized = clean_text(summary).lower()

    for bad in EXCLUDE_KEYWORDS:
        if bad.lower() in normalized:
            print(f"Filtere Event wegen Keyword '{bad}': {summary}")
            return False

    return True


def sanitize_component_text_fields(component) -> None:
    """
    Bereinigt wichtige Textfelder innerhalb eines VEVENT.
    Dadurch erscheinen Umlaute später auch sauber im exportierten Kalender.
    """
    text_fields = [
        "summary",
        "description",
        "location",
    ]

    for field in text_fields:
        value = component.get(field)
        if value is not None:
            cleaned = clean_text(str(value))
            component[field] = cleaned


def fetch_calendar(url: str):
    """
    Lädt einen ICS-Feed herunter und gibt ein Calendar-Objekt zurück.
    """
    try:
        print(f"Lade {url} ...")
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()

        # Direkt mit Bytes arbeiten, damit Encoding-Probleme minimiert werden
        return Calendar.from_ical(resp.content)

    except Exception as e:
        print(f"Fehler beim Laden oder Parsen von {url}: {e}")
        return None


# ==============================
# HAUPT-LOGIK
# ==============================

def build_merged_calendar() -> Calendar:
    print("Baue zusammengeführten Kalender ...")

    merged_cal = Calendar()
    merged_cal.add("prodid", "-//Merged Uni Plan//DE")
    merged_cal.add("version", "2.0")

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

            # Robuster Dubletten-Schlüssel:
            # Startzeit + Endzeit + normalisierter Titel
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
    """
    Speichert den Kalender als ICS-Datei.
    """
    ics_data = cal.to_ical()

    with open(output_path, "wb") as f:
        f.write(ics_data)

    print(f"Kalender-Datei gespeichert unter: {output_path}")


def main():
    cal = build_merged_calendar()
    save_calendar(cal, OUTPUT_FILE)


if __name__ == "__main__":
    main()

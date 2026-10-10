#!/usr/bin/env python3
"""Törésvonalak | Baltic Hybrid Intelligence Brief PDF.
Creates dated archive + latest. Uses AI only if dashboard timestamp matches;
otherwise produces a clearly labelled rule-based fallback report.
No automatic WordPress publication.
"""
import html
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak,
    NextPageTemplate, Table, TableStyle, KeepTogether, HRFlowable
)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "docs/data/baltic_dashboard.json"
AI_FILE = ROOT / "docs/data/baltic_ai_analysis.json"
ARCHIVE = ROOT / "docs/reports/archive"
LATEST = ROOT / "docs/reports/latest-baltic-hybrid-threat-report.pdf"
NAVY = colors.HexColor("#082D49")
BLUE = colors.HexColor("#0B83C9")
CYAN = colors.HexColor("#83D5FA")
INK = colors.HexColor("#243D51")
MUTED = colors.HexColor("#637C8D")
PALE = colors.HexColor("#EEF5F9")
LINE = colors.HexColor("#D8E6EF")
WHITE = colors.white
CW, CH = A4

def font_setup():
    options = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    ]
    for regular, bold in options:
        if Path(regular).is_file() and Path(bold).is_file():
            pdfmetrics.registerFont(TTFont("TVRegular", regular))
            pdfmetrics.registerFont(TTFont("TVBold", bold))
            pdfmetrics.registerFontFamily("TVRegular", normal="TVRegular", bold="TVBold")
            return
    raise RuntimeError("Hiányoznak a magyar ékezeteket támogató TTF betűkészletek.")

def e(value):
    return html.escape(str(value if value is not None else "—"), quote=True)

def plain(value):
    return e(value).replace("\n", "<br/>")

def valid_url(value):
    try:
        parsed = urlparse(str(value or ""))
        return parsed.scheme in ("https", "http") and bool(parsed.netloc)
    except ValueError:
        return False

def date_of(value):
    return str(value or "")[:10] or "dátum nélkül"

def number(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

def decimal(value):
    try:
        return f"{float(value):.2f}".replace(".", ",")
    except (TypeError, ValueError):
        return "—"

def cname(code):
    return {"Estonia": "Észtország", "Latvia": "Lettország",
            "Lithuania": "Litvánia", "Poland": "Lengyelország",
            "Regional": "Regionális"}.get(code, str(code or "—"))

def catname(code):
    return {"sabotage": "szabotázs", "cyber": "kibertevékenység",
            "drone_incident": "drónincidensek", "disinformation": "dezinformáció",
            "espionage": "kémkedés", "gps_interference": "GPS-zavarás",
            "gnss_interference": "GNSS-zavarás",
            "critical_infrastructure": "kritikus infrastruktúra"}.get(
                code, str(code or "—").replace("_", " "))

def read_json(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)

def get_ai(data):
    if not AI_FILE.is_file():
        return None
    try:
        ai = read_json(AI_FILE)
        if ai.get("source_dashboard_generated_at") != data.get("generated_at"):
            print("AI fájl más adatállapothoz tartozik: szabályalapú tartalék jelentés.")
            return None
        if not all(isinstance(ai.get(k), str) and ai[k].strip() for k in (
                "lead", "english_summary", "executive_summary",
                "regional_assessment", "conclusion", "limitations")):
            return None
        if not isinstance(ai.get("sources"), list):
            return None
        return ai
    except (OSError, ValueError, TypeError):
        return None

def styles():
    return {
        "body": ParagraphStyle("TVBody", fontName="TVRegular", fontSize=9.1,
            leading=15.1, textColor=INK, spaceAfter=10, allowWidows=0, allowOrphans=0),
        "small": ParagraphStyle("TVSmall", fontName="TVRegular", fontSize=7.8,
            leading=12.2, textColor=MUTED, spaceAfter=7),
        "heading": ParagraphStyle("TVHeading", fontName="TVBold", fontSize=15,
            leading=21, textColor=NAVY, spaceBefore=16, spaceAfter=12,
            keepWithNext=True),
        "subheading": ParagraphStyle("TVSubHeading", fontName="TVBold", fontSize=10.3,
            leading=15, textColor=BLUE, spaceBefore=12, spaceAfter=7,
            keepWithNext=True),
        "cover_brand": ParagraphStyle("TVCoverBrand", fontName="TVBold", fontSize=15,
            leading=21, textColor=CYAN, spaceAfter=13),
        "cover_title": ParagraphStyle("TVCoverTitle", fontName="TVBold", fontSize=29,
            leading=39, textColor=WHITE, spaceAfter=13),
        "cover_sub": ParagraphStyle("TVCoverSub", fontName="TVRegular", fontSize=12,
            leading=19, textColor=colors.HexColor("#D6E8F2"), spaceAfter=20),
        "cover_info": ParagraphStyle("TVCoverInfo", fontName="TVRegular", fontSize=10,
            leading=17, textColor=WHITE),
        "toc": ParagraphStyle("TVTOC", fontName="TVRegular", fontSize=10,
            leading=18, textColor=INK, leftIndent=7, firstLineIndent=-7,
            spaceBefore=4),
        "source": ParagraphStyle("TVSource", fontName="TVRegular", fontSize=8,
            leading=13.4, textColor=INK, spaceAfter=7, wordWrap="CJK"),
        "note": ParagraphStyle("TVNote", fontName="TVRegular", fontSize=8.1,
            leading=13, textColor=INK, spaceAfter=8),
        "center": ParagraphStyle("TVCenter", fontName="TVBold", fontSize=10,
            leading=15, textColor=NAVY, alignment=TA_CENTER),
    }

def page_cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, CW, CH, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#0B496C"))
    canvas.rect(0, 0, 0.30*cm, CH, fill=1, stroke=0)
    canvas.setStrokeColor(colors.HexColor("#205D7F"))
    canvas.setLineWidth(0.6)
    for y in (6, 8, 10, 12, 14, 16, 18, 20, 22):
        canvas.line(1.2*cm, y*cm, CW-1.2*cm, y*cm)
    canvas.setFillColor(CYAN)
    canvas.rect(1.6*cm, CH-3.15*cm, 2.3*cm, 0.09*cm, fill=1, stroke=0)
    canvas.setFont("TVRegular", 8)
    canvas.setFillColor(colors.HexColor("#BDD8E8"))
    canvas.drawString(1.65*cm, 1.55*cm, "TÖRÉSVONALAK · OSINT INTELLIGENCE SERIES")
    canvas.drawRightString(CW-1.65*cm, 1.55*cm, "SZERKESZTŐI ELLENŐRZÉSRE")
    canvas.restoreState()

def page_body(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(.55)
    canvas.rect(1.10*cm, 1.0*cm, CW-2.20*cm, CH-2.0*cm, fill=0, stroke=1)
    canvas.setFillColor(NAVY)
    canvas.rect(1.10*cm, CH-1.55*cm, CW-2.20*cm, .55*cm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("TVBold", 8.1)
    canvas.drawString(1.42*cm, CH-1.36*cm, "TÖRÉSVONALAK")
    canvas.setFont("TVRegular", 7.3)
    canvas.drawRightString(CW-1.42*cm, CH-1.36*cm, "BALTIC HYBRID INTELLIGENCE BRIEF")
    canvas.setStrokeColor(LINE)
    canvas.line(1.42*cm, 1.68*cm, CW-1.42*cm, 1.68*cm)
    canvas.setFont("TVRegular", 7.3)
    canvas.setFillColor(MUTED)
    canvas.drawString(1.42*cm, 1.39*cm, getattr(doc, "report_date", ""))
    canvas.drawCentredString(CW/2, 1.39*cm, "AI-TÁMOGATOTT · NEM ELLENŐRZÖTT")
    canvas.drawRightString(CW-1.42*cm, 1.39*cm, f"{doc.page}. oldal")
    canvas.restoreState()

class BriefDoc(BaseDocTemplate):
    def __init__(self, filename, report_date):
        super().__init__(str(filename), pagesize=A4,
                         leftMargin=1.7*cm, rightMargin=1.7*cm,
                         topMargin=2.2*cm, bottomMargin=2.1*cm,
                         title=f"Baltic Hybrid Intelligence Brief – {report_date}",
                         author="Törésvonalak")
        self.report_date = report_date
        self.heading_number = 0
        cover = Frame(1.75*cm, 2.4*cm, CW-3.5*cm, CH-5.7*cm,
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        normal = Frame(1.75*cm, 2.05*cm, CW-3.5*cm, CH-4.45*cm,
                       leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([
            PageTemplate(id="Cover", frames=[cover], onPage=page_cover),
            PageTemplate(id="Normal", frames=[normal], onPage=page_body),
        ])

    def beforeDocument(self):
        self.heading_number = 0

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and getattr(flowable, "_tv_heading", False):
            self.heading_number += 1
            key = f"section-{self.heading_number}"
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (0, flowable.getPlainText(), self.page, key))

def main():
    font_setup()
    if not DASH.is_file():
        raise FileNotFoundError(DASH)
    data = read_json(DASH)
    summary = data.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("A dashboard JSON summary mezője hiányzik.")
    ai = get_ai(data)
    st = styles()
    report_date = date_of(data.get("latest_update") or data.get("generated_at"))
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    filename = ARCHIVE / f"baltic-hybrid-threat-report-{report_date}.pdf"
    doc = BriefDoc(filename, report_date)
    story = []

    def p(value, kind="body"):
        story.append(Paragraph(plain(value), st[kind]))

    def h(value):
        item = Paragraph(e(value), st["heading"])
        item._tv_heading = True
        story.append(item)

    def sh(value):
        story.append(Paragraph(e(value), st["subheading"]))

    def new_section(value):
        story.append(PageBreak())
        h(value)

    def card_row(items):
        cells = []
        for title, value in items:
            cells.append(Paragraph(
                f'<font color="#637C8D" size="7">{e(title)}</font><br/>'
                f'<font color="#082D49" size="12"><b>{e(value)}</b></font>',
                st["note"]))
        width = (CW-3.5*cm)/len(cells)
        table = Table([cells], colWidths=[width]*len(cells), hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), PALE),
            ("BOX", (0,0), (-1,-1), .6, LINE),
            ("INNERGRID", (0,0), (-1,-1), .5, WHITE),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING", (0,0), (-1,-1), 12),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ]))
        story.append(table)
        story.append(Spacer(1, 12))

    # 1 – Cover
    story.append(Spacer(1, 3.6*cm))
    story.append(Paragraph("TÖRÉSVONALAK", st["cover_brand"]))
    story.append(Paragraph("BALTIC HYBRID<br/>INTELLIGENCE<br/>BRIEF", st["cover_title"]))
    story.append(Paragraph(
        "Hibrid fenyegetések és regionális biztonsági helyzetkép<br/>"
        "Észtország · Lettország · Litvánia · Lengyelország", st["cover_sub"]))
    story.append(Spacer(1, .9*cm))
    story.append(Paragraph(f"JELENTÉS DÁTUMA: {e(report_date)}", st["cover_info"]))
    story.append(Spacer(1, .25*cm))
    story.append(Paragraph(
        "14 napos gördülő monitoradatok · AI-támogatott elemzői tervezet"
        if ai else "14 napos gördülő monitoradatok · szabályalapú tartalék jelentés",
        st["cover_info"]))
    story.append(NextPageTemplate("Normal"))
    story.append(PageBreak())

    # 2 – TOC
    h("Tartalom")
    p("A fejezetcímek kattinthatók a PDF-olvasóban.", "small")
    toc = TableOfContents()
    toc.levelStyles = [st["toc"]]
    story.append(toc)
    story.append(Spacer(1, 1*cm))
    p("A jelentés a monitor által gyűjtött hírcímek és metaadatok alapján készül. "
      "A publikálás előtt a források és az elemzői állítások emberi ellenőrzése szükséges.", "note")

    # 3 – Lead and English
    new_section("Lead | Bevezetés")
    if ai:
        p(ai["lead"])
    else:
        p(f"A Baltic Hybrid Monitor {report_date} dátumú adatállapota a balti államok és "
          f"Lengyelország hibrid fenyegetéseit követi. A 14 napos gördülő "
          f"mintában {number(summary.get('event_count'))} esemény szerepel, "
          f"köztük {number(summary.get('incident_count'))} incidensnek minősített tétel. "
          f"A fenyegetési index {decimal(summary.get('threat_index'))}, amely a monitor "
          f"saját módszertani mutatója, nem hatósági kockázatértékelés. "
          "Az események hírcímekből és metaadatokból származnak, így az állítások "
          "ellenőrzést igényelnek. A jelentés a jelenlegi adatállapotot ismerteti, "
          "nem állít bizonyított trendváltozást.")
    sh("English Summary")
    if ai:
        p(ai["english_summary"])
    else:
        p(f"This brief describes the Baltic Hybrid Monitor's rolling 14-day dataset "
          f"as of {report_date}. The dataset contains {number(summary.get('event_count'))} "
          f"events, including {number(summary.get('incident_count'))} entries classified "
          "as incidents. These are monitoring classifications, not independently "
          "verified incidents. The threat index is a model-derived indicator. "
          "News titles and metadata require manual source verification before publication.")

    # 4 – Report
    new_section("A jelentés | Vezetői összefoglaló")
    card_row([
        ("THREAT INDEX", decimal(summary.get("threat_index"))),
        ("BESOROLÁS", str(summary.get("threat_level") or "—").upper()),
        ("14 NAP / ESEMÉNY", number(summary.get("event_count"))),
        ("INCIDENS-BESOROLÁS", number(summary.get("incident_count"))),
    ])
    if ai:
        p(ai["executive_summary"])
    else:
        p(f"A 14 napos gördülő adatállományban {number(summary.get('event_count'))} esemény, "
          f"{number(summary.get('indicator_count'))} korai indikátor és "
          f"{number(summary.get('assessment_count'))} háttérértékelés szerepel. "
          "Az események osztályozása és pontszáma nem igazolja önmagában "
          "az állítások tényszerűségét vagy a szereplők felelősségét.")
    sh("Regionális helyzetértékelés")
    if ai:
        p(ai["regional_assessment"])
    else:
        drivers = data.get("category_drivers") or []
        if drivers:
            p("A monitorban leggyakrabban megjelenő kategóriák: " +
              "; ".join(f"{catname(x.get('category'))} ({number(x.get('event_count'))} tétel)"
                        for x in drivers[:4]) + ". "
              "Ezek monitor szerinti kategóriák, nem megerősített események vagy "
              "bizonyított fenyegetésnövekedések.")
        else:
            p("A regionális értékeléshez nem áll rendelkezésre elegendő kategóriaadat.")

    sh("Országonkénti helyzetkép")
    country_cards = {x.get("country"): x for x in data.get("country_cards") or []}
    ai_countries = {x.get("country"): x.get("assessment") for x in
                    (ai.get("country_assessments") or [])} if ai else {}
    for code in ("Estonia", "Latvia", "Lithuania", "Poland"):
        sh(cname(code))
        card = country_cards.get(code, {})
        p(f"Monitoradat (14 nap): {number(card.get('event_count'))} esemény; "
          f"{number(card.get('incident_count'))} incidens-besorolás; "
          f"legmagasabb pontszám: {number(card.get('highest_score'))}.", "small")
        if ai_countries.get(code):
            p(ai_countries[code])
        else:
            cats = card.get("top_categories") or []
            p("A kiemelt monitorozási kategóriák: " +
              (", ".join(catname(x.get("name")) for x in cats[:3]) if cats else
               "nincs elegendő kategóriaadat") +
              ". A megfigyelt hírjelzések független ellenőrzést igényelnek.")

    # Event assessment with traceable references
    new_section("Kiemelt események | Forrásalapú áttekintés")
    source_events = {str(x.get("event_id")): x for x in (ai.get("sources") or [])} if ai else {}
    if ai:
        event_notes = ai.get("event_assessments") or []
        for idx, item in enumerate(event_notes, 1):
            ev = source_events.get(str(item.get("event_id")))
            if not ev:
                continue
            sh(f"{idx}. {ev.get('title') or 'Esemény'}")
            p(f"Ország: {cname(ev.get('primary_country'))} · "
              f"publikálás: {date_of(ev.get('published_at'))} · "
              f"monitor-bizonyosság: {ev.get('confidence') or 'ismeretlen'} · "
              f"pontszám: {number(ev.get('hybrid_threat_score'))}", "small")
            p(item.get("assessment") or "")
            p(f"Kapcsolódó hivatkozások: lásd a forrásjegyzék [{idx}] eseménycsoportját. "
              "A hivatkozások száma nem jelenti a független megerősítések számát.", "small")
    else:
        seen = set()
        items = []
        for item in (data.get("top_events") or []) + (data.get("recent_events") or []):
            key = item.get("event_id")
            if key and key not in seen and valid_url(item.get("url")):
                seen.add(key)
                items.append(item)
        items = sorted(items, key=lambda x: number(x.get("hybrid_threat_score")), reverse=True)[:6]
        for idx, ev in enumerate(items, 1):
            sh(f"{idx}. {ev.get('title') or 'Esemény'}")
            p(f"Monitor szerinti ország: {cname(ev.get('primary_country'))}. "
              f"Pontszám: {number(ev.get('hybrid_threat_score'))}. "
              f"Bizonyosság: {ev.get('confidence') or 'ismeretlen'}. "
              "A hírcím állítása további ellenőrzést igényel.", "small")
            source_events[str(ev.get("event_id"))] = {
                **ev, "linked_articles": [{"title": ev.get("title"), "url": ev.get("url")}]}

    sh("További figyelési szempontok")
    if ai:
        for point in ai.get("watchpoints") or []:
            p("• " + str(point))
    else:
        p("A következő adatfrissítésekben különösen fontos az új események forrásainak "
          "ellenőrzése, az esetleges független megerősítések keresése és "
          "a korai indikátorok elkülönítése a tényleges incidensektől.")

    # 5 – Conclusion
    new_section("Zárás | Elemzői következtetések")
    if ai:
        p(ai["conclusion"])
    else:
        p("A monitor a balti térség és Lengyelország hibrid fenyegetéseinek "
          "rendszerezett követését támogatja. A számszerű mutatók "
          "jelzések, nem önmagukban igazolt biztonságpolitikai tények. "
          "A publikálás előtt minden lényeges állítást a kapcsolódó "
          "források alapján ellenőrizni kell.")
    sh("Módszertani korlátok")
    if ai:
        p(ai["limitations"])
    else:
        p("A jelentés szabályalapú tartalék változat, mert az aktuális "
          "dashboard-adatállapothoz nem áll rendelkezésre érvényes AI-tervezet.")
    review = data.get("manual_review_queue") or {}
    p(f"Manuális ellenőrzésre váró tételek: {number(review.get('pending_count'))}. "
      f"Az adatállomány frissítése: {data.get('generated_at') or 'ismeretlen'}. "
      "A publikálási időpont nem feltétlenül egyezik az esemény tényleges időpontjával.",
      "small")

    # 6 – Sources
    new_section("Forrásjegyzék")
    p("A linkek kattinthatók. A forráscímek és URL-ek a monitor adatállományából "
      "származnak. A több kapcsolódó cikk nem feltétlenül jelent egymástól "
      "független forrásokat; az átvételek és az eredeti beszámolók elkülönítése "
      "emberi ellenőrzést igényel.", "small")
    if ai:
        ordered_ids = [x.get("event_id") for x in ai.get("event_assessments") or []
                     if x.get("event_id") in source_events]
        ordered_ids += [eid for eid in source_events if eid not in ordered_ids]
    else:
        ordered_ids = list(source_events)
    used = set()
    for idx, eid in enumerate(ordered_ids, 1):
        if eid in used:
            continue
        used.add(eid)
        ev = source_events[eid]
        sh(f"[{idx}] {ev.get('title') or 'Esemény'}")
        p(f"Eseményazonosító: {eid} · monitor-bizonyosság: "
          f"{ev.get('confidence') or 'ismeretlen'} · "
          f"publikálás: {date_of(ev.get('published_at'))}", "small")
        links = ev.get("linked_articles") or []
        if not links and valid_url(ev.get("url")):
            links = [{"title": ev.get("title"), "url": ev.get("url")}]
        if not links:
            p("Nincs ellenőrizhető URL a bemeneti adatokban.", "small")
        for j, link in enumerate(links, 1):
            url = str(link.get("url") or "")
            if not valid_url(url):
                continue
            title = str(link.get("title") or "Kapcsolódó cikk")
            story.append(Paragraph(
                f'{idx}.{j}. <link href="{e(url)}" color="#0B83C9">'
                f'{e(title)}</link><br/>'
                f'<font color="#637C8D">{e(url[:115])}'
                f'{"…" if len(url)>115 else ""}</font>',
                st["source"]))
    sh("AI-használat és kötelező elemzői ellenőrzés")
    warning = (
        "AI-ALAPÚ ELEMZÉS – ELEMZŐI ELLENŐRZÉS SZÜKSÉGES. "
        "A jelentés mesterséges intelligencia támogatásával, automatizált "
        "OSINT-adatgyűjtés és forrásfeldolgozás alapján készülhet. "
        "A bemutatott információk eltérő megbízhatóságú nyílt forrásokból "
        "származhatnak. Az AI által készített értékelések nem tekinthetők "
        "önállóan igazolt ténymegállapításnak. A források hitelességének, "
        "az események időpontjának, a szereplők azonosításának és az "
        "elemzői következtetéseknek az egyéni, emberi ellenőrzése "
        "kiemelten fontos. A publikálás külön szerkesztői döntés."
    )
    box = Table([[Paragraph(e(warning), st["note"])]], colWidths=[CW-3.5*cm])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), PALE),
        ("BOX", (0,0), (-1,-1), 1, BLUE),
        ("LEFTPADDING", (0,0), (-1,-1), 14),
        ("RIGHTPADDING", (0,0), (-1,-1), 14),
        ("TOPPADDING", (0,0), (-1,-1), 13),
        ("BOTTOMPADDING", (0,0), (-1,-1), 11),
    ]))
    story.append(box)
    story.append(Spacer(1, 12))
    p("Törésvonalak · https://toresvonalak.blog/ · Baltic Hybrid Monitor", "small")

    doc.multiBuild(story)
    LATEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(filename, LATEST)
    print(f"PDF elkészült: {filename}")
    print(f"Legfrissebb PDF: {LATEST}")
    print("Tartalom:", "AI-elemzés" if ai else "szabályalapú tartalék")
    print("Blogpublikálás: nincs; kizárólag kézi döntés alapján.")

if __name__ == "__main__":
    main()

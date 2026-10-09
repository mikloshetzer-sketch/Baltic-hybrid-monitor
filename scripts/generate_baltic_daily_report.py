#!/usr/bin/env python3
"""Baltic Hybrid Intelligence Brief: source-bound, Hungarian, daily PDF.
Only dashboard JSON is used; no invented facts or external LLM dependency.
"""
import json, shutil, re, html
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable

ROOT=Path(__file__).resolve().parents[1] if Path(__file__).resolve().parent.name == 'scripts' else Path(__file__).resolve().parent
DATA_PATH=ROOT/'docs/data/baltic_dashboard.json'
REPORT_DIR=ROOT/'docs/reports'
ARCHIVE_DIR=REPORT_DIR/'archive'
LATEST_REPORT=REPORT_DIR/'latest-baltic-hybrid-threat-report.pdf'
NAVY=colors.HexColor('#083a54'); BLUE=colors.HexColor('#0b83c9'); TEXT=colors.HexColor('#28485d'); MUTED=colors.HexColor('#607b8d'); LIGHT=colors.HexColor('#edf5f9')

def fonts():
    candidates=[('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),('/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf','/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf')]
    for normal,bold in candidates:
        if Path(normal).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont('BriefRegular',normal));pdfmetrics.registerFont(TTFont('BriefBold',bold));pdfmetrics.registerFontFamily('BriefRegular',normal='BriefRegular',bold='BriefBold');return 'BriefRegular','BriefBold'
    raise RuntimeError('Unicode TTF fonts missing; cannot reliably render Hungarian accents.')

def esc(x):return html.escape(str(x if x is not None else '—'))
def num(x):
    try:return int(x or 0)
    except (ValueError,TypeError):return 0

def fmt(x):
    try:return f'{float(x):.2f}'.replace('.',',')
    except (ValueError,TypeError):return '—'

def short_date(x):return str(x or '')[:10] or 'ismeretlen dátum'

def country(x):return {'Estonia':'Észtország','Latvia':'Lettország','Lithuania':'Litvánia','Poland':'Lengyelország','Regional':'regionális / több országot érintő'}.get(x,str(x or 'nem meghatározott'))

def category(x):return {'sabotage':'szabotázs','cyber':'kiberműveletek','drone_incident':'drónincidensek','disinformation':'dezinformáció','espionage':'hírszerzés / kémkedés','migration_pressure':'migrációs nyomás','gnss_interference':'GNSS-zavarás'}.get(str(x),str(x).replace('_',' '))

def link_url(url):
    p=urlparse(str(url or ''))
    return str(url) if p.scheme in ('https','http') and p.netloc else None

def unique_events(data):
    found={}
    for event in list(data.get('top_events') or [])+list(data.get('recent_events') or []):
        if not isinstance(event,dict):continue
        key=event.get('event_id') or event.get('url') or event.get('title')
        if key and key not in found:found[key]=event
    return list(found.values())

def paragraph(text,style):return Paragraph(text,style)

def footer(canvas,doc):
    canvas.saveState();w,h=A4;canvas.setStrokeColor(colors.HexColor('#d8e5ed'));canvas.line(1.65*cm,1.5*cm,w-1.65*cm,1.5*cm)
    canvas.setFont('BriefRegular',8);canvas.setFillColor(MUTED);canvas.drawString(1.65*cm,1.17*cm,'TÖRÉSVONALAK · Baltic Hybrid Intelligence Platform');canvas.drawRightString(w-1.65*cm,1.17*cm,f'{doc.page}. oldal');canvas.restoreState()

def build_report(data,output):
    regular,bold=fonts()
    summary=data.get('summary') or {};events=unique_events(data);countries=data.get('country_cards') or [];drivers=data.get('category_drivers') or []
    generated=data.get('latest_update') or data.get('generated_at') or datetime.now(timezone.utc).isoformat();date=short_date(generated)
    title=ParagraphStyle('title',fontName=bold,fontSize=20,leading=27,textColor=NAVY,spaceAfter=11)
    subtitle=ParagraphStyle('sub',fontName=regular,fontSize=10,leading=15,textColor=MUTED,spaceAfter=15)
    h2=ParagraphStyle('h2',fontName=bold,fontSize=12,leading=17,textColor=BLUE,spaceBefore=17,spaceAfter=8,keepWithNext=True)
    body=ParagraphStyle('body',fontName=regular,fontSize=9.5,leading=15.3,textColor=TEXT,spaceAfter=9,alignment=TA_LEFT)
    small=ParagraphStyle('small',parent=body,fontSize=8,leading=12,textColor=MUTED,spaceAfter=6)
    eventstyle=ParagraphStyle('event',parent=body,fontSize=9,leading=14,spaceAfter=5)
    story=[]
    def add(text,style=body):story.append(paragraph(text,style))
    add('BALTIC HYBRID INTELLIGENCE BRIEF',title)
    add(f'Napi regionális biztonságpolitikai helyzetértékelés · {esc(date)} · Észtország, Lettország, Litvánia és Lengyelország',subtitle)
    score=fmt(summary.get('threat_index'));level=esc(summary.get('threat_level','—')).upper();n=num(summary.get('event_count'));inc=num(summary.get('incident_count'));ind=num(summary.get('indicator_count'));ass=num(summary.get('assessment_count'))
    cards=[('THREAT INDEX',score),('BESOROLÁS',level),('ESEMÉNYEK',str(n)),('INCIDENSEK',str(inc)),('INDIKÁTOROK',str(ind))]
    table=Table([[Paragraph(f'<font color="#607b8d">{a}</font><br/><font size="13" color="#083a54"><b>{b}</b></font>',small) for a,b in cards]],colWidths=[3.45*cm]*5)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LIGHT),('BOX',(0,0),(-1,-1),.6,colors.HexColor('#cbdde8')),('INNERGRID',(0,0),(-1,-1),.4,colors.white),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),8)]));story.append(table)
    story.append(Spacer(1,10))
    add('Vezetői összefoglaló',h2)
    main=drivers[0] if drivers else None
    dominant=f"A feldolgozott kategóriák közül a {category(main.get('category'))} szerepel a leggyakrabban ({num(main.get('event_count'))} esemény)." if main else 'A kategóriák rangsora a rendelkezésre álló adatokból nem állapítható meg.'
    add(f'A Baltic Hybrid Monitor {esc(date)}-i adatállapotában a regionális Threat Index <b>{score}</b>, a modell besorolása <b>{level}</b>. A 14 napos gördülő helyzetképben <b>{n} esemény</b> szerepel, köztük <b>{inc} incidens</b>, <b>{ind} korai figyelmeztető indikátor</b> és <b>{ass} háttérértékelés</b>. {esc(dominant)} A mutatók nem azt jelentik, hogy ennyi esemény történt az adott naptári napon: a jelentés a legfrissebb rendelkezésre álló, gördülő adatállomány értelmezése.')
    add('A fenyegetési index önmagában nem azonos a katonai eszkaláció valószínűségével. A magasabb pontszám több vagy erősebb jelzést jelent a monitor módszertana szerint, de nem bizonyítja az események közötti koordinációt, sem az elkövető kilétét. Az alacsony bizonyosságú és ellenőrzésre váró tételek értékelését ezért külön kezeljük.')
    add('A helyzet értelmezése',h2)
    if drivers:
        ds=drivers[:3];bits=[f'{category(x.get("category"))}: {num(x.get("event_count"))} esemény' for x in ds]
        add('A megfigyelt fenyegetési kép fő témái: <b>'+esc('; '.join(bits))+'</b>. Ez a megoszlás a monitor kategorizálását tükrözi, és nem feltétlenül az incidensek tényleges súlyossági sorrendje. Egyetlen hír több fenyegetési kategóriához is tartozhat.')
    else:add('Nem áll rendelkezésre elegendő kategóriaadat a fenyegetési összetétel megállapításához.')
    if inc==0:add('A jelenlegi mintában nincs incidensként besorolt esemény. Ez nem bizonyítja az incidensek teljes hiányát a térségben.')
    else:add(f'A rendszer {inc} incidensnek minősített tételt különít el. Az incidens-besorolás nem azonos a hatósági megerősítéssel; az egyes események forrását és bizonyossági szintjét külön szükséges vizsgálni.')
    add('Országonkénti helyzetkép',h2)
    for c in countries:
        code=c.get('country');cnt=num(c.get('event_count'));cats=c.get('top_categories') or []
        catphrase=', '.join(category(x.get('name')) for x in cats[:2]) if cats else 'nincs kiemelkedő kategória a rendelkezésre álló adatokban'
        intro='A regionális besorolás nem egyetlen országban történt eseményt jelent.' if code=='Regional' else 'A számszerű országos eloszlás nem pontos eseménykoordináták alapján készült.'
        add(f'<b>{esc(country(code))}.</b> A monitor {cnt} ide sorolt eseményt tart nyilván, ebből {num(c.get("incident_count"))} incidens és {num(c.get("indicator_count"))} indikátor. Jellemző témák: {esc(catphrase)}. Legmagasabb eseménypontszám: {num(c.get("highest_score"))}. {esc(intro)}')
    add('Kiemelt események – forrással és bizonyossággal',h2)
    top=sorted(events,key=lambda x:num(x.get('hybrid_threat_score')),reverse=True)[:6]
    if not top:add('Nem érhető el eseménykivonat.');
    for i,e in enumerate(top,1):
        title_text=esc(e.get('title','Cím nélküli esemény'))
        link=link_url(e.get('url'))
        title_markup=f'<link href="{esc(link)}" color="#0b83c9">{title_text}</link>' if link else title_text
        add(f'<b>[{i}] {title_markup}</b><br/>{esc(country(e.get("primary_country")))} · pontszám: {num(e.get("hybrid_threat_score"))} · besorolás: {esc(e.get("event_subtype","—"))} · bizonyosság: {esc(e.get("confidence","nem jelölt"))} ({num(e.get("confidence_score"))}/100) · publikálás: {esc(short_date(e.get("published_at")))}.',eventstyle)
    add('Mit figyeljünk a következő időszakban?',h2)
    add('Az új, megerősített incidensek számát; a szabotázs-, kiber- és drónjelzések területi koncentrációját; az azonos eseményről érkező független források számát; valamint azt, hogy a korai indikátorokból tényleges operatív esemény lesz-e. Ezek figyelési szempontok, nem előrejelzett történések.')
    review=data.get('manual_review_queue') or {};p=review.get('priority_counts') or {}
    add('Adatminőség és elemzői fenntartások',h2)
    add(f'A kézi ellenőrzésre váró tételek száma: <b>{num(review.get("pending_count"))}</b>; ebből aktuális: <b>{num(review.get("current_pending_count"))}</b>, történeti: <b>{num(review.get("historical_pending_count"))}</b>. Prioritások: P1 {num(p.get("P1"))}, P2 {num(p.get("P2"))}, P3 {num(p.get("P3"))}. Ezek a tételek nem tekinthetők automatikusan bizonyított eseményeknek. A jelentés a JSON-ban szereplő publikálási dátumot ismerheti, amely nem feltétlenül egyezik az esemény tényleges időpontjával.')
    add('Módszertan és források',h2)
    add('Forrás: Baltic Hybrid Intelligence Platform, <i>baltic_dashboard.json</i> aktuális automatikus adatállománya. A kiemelt eseményekhez kattintható forráshivatkozások tartoznak. A jelentés szabályalapú, ellenőrizhető szöveges összefoglaló; nem állít önállóan igazolt tényként olyan körülményt, amelyet a monitor csak hírcím vagy pontszám alapján ismer.')
    add(f'Adatfrissítés: {esc(generated)}. A 14 napos fenyegetési ablak és az egynapos eseményértékelés nem keverendő össze. Az index változásáról nem teszünk állítást korábbi, összehasonlítható napi érték nélkül.',small)
    output.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(output),pagesize=A4,leftMargin=1.65*cm,rightMargin=1.65*cm,topMargin=1.7*cm,bottomMargin=1.9*cm,title=f'Baltic Hybrid Intelligence Brief - {date}',author='Törésvonalak Monitor Network')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return date

def make_report():
    if not DATA_PATH.exists():raise FileNotFoundError(f'Missing dashboard data: {DATA_PATH}')
    data=json.loads(DATA_PATH.read_text(encoding='utf-8'))
    if not isinstance(data.get('summary'),dict):raise ValueError('Missing summary in dashboard JSON')
    date=short_date(data.get('latest_update') or data.get('generated_at'))
    archive=ARCHIVE_DIR/f'baltic-hybrid-threat-report-{date}.pdf'
    build_report(data,archive)
    LATEST_REPORT.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(archive,LATEST_REPORT)
    print(f'Archived: {archive}\nLatest: {LATEST_REPORT}')

if __name__=='__main__':make_report()

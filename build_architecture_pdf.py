import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable, Preformatted
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from datetime import datetime

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(40, 755, "Orbita - IQ  |  Technical & Architecture Report")
            self.drawRightString(572, 755, "Ground Operations System")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.75)
            self.line(40, 748, 572, 748)

        # Footer (all pages)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.75)
        self.line(40, 42, 572, 42)
        
        self.drawString(40, 30, f"Orbita - IQ Ground Operations Dashboard — orbita-iq.vercel.app")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(572, 30, page_text)
        self.restoreState()

def generate_pdf(output_path="ORBITA_IQ_TECHNICAL_ARCHITECTURE_REPORT.pdf"):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=50,
        bottomMargin=50
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Palette
    C_PRIMARY = colors.HexColor("#0F172A")    # Slate 900
    C_SECONDARY = colors.HexColor("#1E293B")  # Slate 800
    C_ACCENT = colors.HexColor("#0284C7")     # Sky 600
    C_ACCENT_DARK = colors.HexColor("#0369A1")
    C_MUTED = colors.HexColor("#475569")      # Slate 600
    C_LIGHT_BG = colors.HexColor("#F8FAFC")   # Slate 50
    C_CARD_BG = colors.HexColor("#F1F5F9")    # Slate 100
    C_BORDER = colors.HexColor("#E2E8F0")     # Slate 200
    
    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=C_PRIMARY,
        alignment=TA_LEFT
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=C_ACCENT,
        alignment=TA_LEFT
    )

    badge_style = ParagraphStyle(
        'Badge',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=C_MUTED,
        alignment=TA_LEFT
    )
    
    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=C_PRIMARY,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=C_SECONDARY,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.2,
        leading=13.5,
        textColor=C_SECONDARY,
        alignment=TA_LEFT,
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'BulletText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=C_SECONDARY,
        leftIndent=12,
        firstLineIndent=-12,
        spaceAfter=4
    )
    
    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=C_SECONDARY
    )
    
    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11.5,
        textColor=C_PRIMARY
    )
    
    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.white
    )

    code_block_style = ParagraphStyle(
        'CodeBlock',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.8,
        leading=10.5,
        textColor=colors.HexColor("#0F172A")
    )

    story = []
    
    # ----------------------------------------------------
    # Header Banner Box
    # ----------------------------------------------------
    header_content = [
        [
            Paragraph("<b>Orbita - IQ</b> — Technical & Architecture Report", title_style),
            Paragraph("<b>LIVE SYSTEM</b><br/><font color='#0284C7'>orbita-iq.vercel.app</font>", ParagraphStyle('RBadge', parent=badge_style, alignment=TA_RIGHT))
        ],
        [
            Paragraph("Ground Operations · Conjunction Intelligence Dashboard", subtitle_style),
            Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", ParagraphStyle('RDate', parent=badge_style, alignment=TA_RIGHT))
        ]
    ]
    header_table = Table(header_content, colWidths=[380, 152])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=2, color=C_ACCENT, spaceBefore=4, spaceAfter=10))

    # ----------------------------------------------------
    # Section 1: Project Overview
    # ----------------------------------------------------
    story.append(Paragraph("1. Project Overview", h1_style))
    p_overview = (
        "<b>Orbita - IQ</b> is a satellite operations and conjunction-intelligence dashboard built for a ground-ops-style "
        "workflow: track an operational fleet of satellites, screen them for close approaches against both each other and the broader "
        "tracked space object catalog, and surface actionable risk alerts to an operator — modeled loosely on real-world Conjunction "
        "Data Message (CDM) screening as performed by organizations such as the 18th Space Defense Squadron.<br/><br/>"
        "The system covers the full operational loop: <b>catalog ingestion &rarr; fleet tracking &rarr; orbit propagation &rarr; "
        "conjunction screening &rarr; risk classification &rarr; alerting &rarr; operator review</b>, complemented by a CesiumJS 3D "
        "visualization digital twin and an LLM-assisted advisory tool for qualitative conjunction assessment."
    )
    story.append(Paragraph(p_overview, body_style))
    story.append(Spacer(1, 4))

    # ----------------------------------------------------
    # Section 2: Tech Stack
    # ----------------------------------------------------
    story.append(Paragraph("2. Tech Stack", h1_style))
    stack_data = [
        [Paragraph("Layer", table_header), Paragraph("Technology & Implementations", table_header)],
        [Paragraph("Frontend", table_cell_bold), Paragraph("React 18, Vite, TypeScript, Tailwind CSS, Lucide Icons", table_cell)],
        [Paragraph("Frontend Hosting", table_cell_bold), Paragraph("Vercel (Static Single Page Application)", table_cell)],
        [Paragraph("Backend", table_cell_bold), Paragraph("Python 3.11, FastAPI, SQLAlchemy (async, <code>asyncpg</code> driver)", table_cell)],
        [Paragraph("Backend Hosting", table_cell_bold), Paragraph("Render (Managed Web Service)", table_cell)],
        [Paragraph("Database / Auth", table_cell_bold), Paragraph("Supabase (Managed PostgreSQL, GoTrue Auth, Realtime Subscriptions, RLS)", table_cell)],
        [Paragraph("Orbit Propagation", table_cell_bold), Paragraph("SGP4 / SDP4 (via <code>python-sgp4</code>, vectorized with NumPy arrays)", table_cell)],
        [Paragraph("Scheduling", table_cell_bold), Paragraph("APScheduler (<code>AsyncIOScheduler</code> background tasks)", table_cell)],
        [Paragraph("Numerics / TCA", table_cell_bold), Paragraph("NumPy, SciPy (<code>scipy.optimize.minimize_scalar</code> for TCA refinement)", table_cell)],
        [Paragraph("3D Digital Twin", table_cell_bold), Paragraph("CesiumJS (Cartesian3 transformations, orbital paths, camera track)", table_cell)],
        [Paragraph("Live Updates", table_cell_bold), Paragraph("Supabase Realtime + dedicated <code>/ws/orbit</code> WebSocket with 20s polling fallback", table_cell)],
        [Paragraph("External Data", table_cell_bold), Paragraph("CelesTrak (Automated TLE / space catalog ingestion)", table_cell)],
    ]
    t_stack = Table(stack_data, colWidths=[130, 402])
    t_stack.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_PRIMARY),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [C_LIGHT_BG, colors.white]),
        ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
    ]))
    story.append(t_stack)
    story.append(Spacer(1, 4))
    story.append(Paragraph("<i>Note: Frontend and backend are deployed and scaled independently — Vercel serves the static SPA build, and all client calls communicate directly with the Render FastAPI service.</i>", ParagraphStyle('Foot', parent=body_style, fontSize=8, textColor=C_MUTED)))
    story.append(Spacer(1, 4))

    # ----------------------------------------------------
    # Section 3: Data Model
    # ----------------------------------------------------
    story.append(Paragraph("3. Data Model", h1_style))
    story.append(Paragraph("Core tables in the Supabase PostgreSQL database:", body_style))
    
    data_models = [
        "<b><code>satellites</code></b> — The operator's tracked fleet ('My Satellites'). Stores NORAD ID, name, international designator, object type, status, owning organization, and orbital state.",
        "<b><code>catalog_satellites</code></b> — Global space catalog (~5,000+ objects spanning payloads, debris, and rocket bodies across LEO/MEO/GEO/HEO), searchable and filterable.",
        "<b><code>tle_records</code></b> — Stored two-line element sets backing SGP4 propagation for every tracked and cataloged object.",
        "<b><code>orbit_state</code></b> — Current propagated position/velocity per satellite, refreshed on schedule and pushed to clients in real time.",
        "<b><code>conjunction_alerts</code> / <code>conjunction_events</code></b> — Single source of truth for screening results: satellite pair, scope, time of closest approach (TCA), miss distance, relative velocity, collision probability (Pc), risk level, and alert status.",
        "<b><code>profiles</code></b> — Operator identity (employee ID, full name, role, department), backed by Supabase Auth and strict RLS policies."
    ]
    for dm in data_models:
        story.append(Paragraph(f"• {dm}", bullet_style))
    
    story.append(Spacer(1, 2))
    story.append(Paragraph("<b>Schema Integrity:</b> Several fields use native Postgres enum types (<code>satellite_status</code>, <code>object_type</code>, <code>risk_level</code>, <code>alert_status</code>, <code>alert_state</code>), strictly enforced at database DDL level.", ParagraphStyle('EnumNote', parent=body_style, fontSize=8.5, textColor=C_MUTED)))
    story.append(Spacer(1, 4))

    # ----------------------------------------------------
    # Section 4: Core Features
    # ----------------------------------------------------
    story.append(Paragraph("4. Core Features", h1_style))
    features = [
        ("Dashboard", "Fleet-wide summary KPI cards (tracked count, active alerts, high-risk alerts, next upcoming conjunction), fleet altitude trend charts, and real-time live conjunction activity feed."),
        ("My Satellites", "Operator's active fleet (611 satellites in current dataset), each with live altitude, lat/long coordinates, velocity, and health status, refreshed via scheduled SGP4 propagation."),
        ("All Satellites (Catalog)", "Global catalog (~5,028 objects), filterable by orbital regime (LEO/MEO/GEO/HEO) and type (Payloads, Debris, Rocket Bodies), searchable by NORAD/COSPAR ID, with 'Sync Catalog' & 1-click 'Track' capabilities."),
        ("Alerts (CDM Screening)", "Conjunction Data Message-style screening results sorted by TCA, filterable by risk level (Critical/High/Medium/Low) and scope (Fleet vs Fleet, Fleet vs Catalog), with full vector detail modals & operator status workflow (Monitor/Resolve)."),
        ("Orbit Viewer (3D Twin)", "CesiumJS-based 3D digital twin rendering live satellite positions and full orbital tracks, offering imagery layer switching, time-warp simulation controls (1x–60x), and live/global fleet toggles."),
        ("AI Assistant", "LLM-driven qualitative conjunction analysis and maneuver advisory generator, designed as an operational decision-support layer with cached advisories per conjunction event."),
        ("Settings", "Operator profile preferences, notification alert thresholds, and security controls.")
    ]
    for title, desc in features:
        story.append(Paragraph(f"• <b>{title}</b> — {desc}", bullet_style))
    
    story.append(Spacer(1, 4))

    # ----------------------------------------------------
    # Section 5: Conjunction Screening Engine
    # ----------------------------------------------------
    story.append(Paragraph("5. Conjunction Screening Engine", h1_style))
    story.append(Paragraph(
        "The screening engine is the computational core of Orbita - IQ. It operates across two screening scopes — "
        "<b>Fleet vs. Fleet</b> and <b>Fleet vs. Catalog</b> — over a rolling <b>5-day (120-hour)</b> look-ahead horizon using a high-performance two-stage pipeline:",
        body_style
    ))
    
    engine_stages = [
        "<b>Stage 1 — Coarse Orbital Filter:</b> For every candidate pair, perigee/apogee altitude envelopes (with safety margins) are checked for overlap. Pairs whose orbital shells geometrically cannot intersect are discarded before any propagation. This eliminates <b>>99%</b> of raw pairs at virtually zero computational cost.",
        "<b>Stage 2 — Vectorized Ephemeris Propagation:</b> For all surviving unique satellites, a 5-day state trajectory is precomputed once using vectorized SGP4. Relative distance between pairs across the entire 120-hour timeline is evaluated in a single NumPy array pass. When a local minimum is detected, the true Time of Closest Approach (TCA) is refined via <code>scipy.optimize.minimize_scalar</code>. Per-pair scan cost is reduced to sub-millisecond speeds."
    ]
    for stg in engine_stages:
        story.append(Paragraph(f"• {stg}", bullet_style))
    
    story.append(Spacer(1, 4))
    story.append(Paragraph("Risk Classification Thresholds", h2_style))
    
    risk_data = [
        [Paragraph("Miss Distance", table_header), Paragraph("Risk Level", table_header), Paragraph("Collision Probability ($P_c$)", table_header), Paragraph("Operator Action / Notification", table_header)],
        [Paragraph("&lt; 1.0 km", table_cell_bold), Paragraph("<font color='#DC2626'><b>CRITICAL</b></font>", table_cell), Paragraph("Evaluated per event", table_cell), Paragraph("<b>Active Urgent Alert</b> + Banner", table_cell)],
        [Paragraph("1.0 – 5.0 km", table_cell_bold), Paragraph("<font color='#EA580C'><b>HIGH</b></font>", table_cell), Paragraph("Evaluated per event", table_cell), Paragraph("<b>Active Alert</b> (Top Priority)", table_cell)],
        [Paragraph("5.0 – 25.0 km", table_cell_bold), Paragraph("<font color='#D97706'><b>MEDIUM</b></font>", table_cell), Paragraph("Evaluated per event", table_cell), Paragraph("Stored & Visible in Alerts table", table_cell)],
        [Paragraph("25.0 – 50.0 km", table_cell_bold), Paragraph("<font color='#2563EB'><b>LOW</b></font>", table_cell), Paragraph("Evaluated per event", table_cell), Paragraph("Stored & Visible for situational awareness", table_cell)],
        [Paragraph("&gt; 50.0 km", table_cell_bold), Paragraph("Not Reported", table_cell), Paragraph("N/A", table_cell), Paragraph("Filtered out (noise suppression)", table_cell)],
    ]
    t_risk = Table(risk_data, colWidths=[90, 85, 130, 227])
    t_risk.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_PRIMARY),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [C_LIGHT_BG, colors.white]),
        ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
    ]))
    story.append(t_risk)
    story.append(Spacer(1, 4))
    
    story.append(Paragraph("<b>Scheduled Engine Automation:</b>", h2_style))
    jobs = [
        "<b>Orbit Propagation (5 min):</b> Computes real-time satellite state vectors and updates <code>orbit_state</code> table.",
        "<b>Conjunction Screening (20 min):</b> Executes Stage 1 & Stage 2 screening across Fleet-vs-Fleet and Fleet-vs-Catalog.",
        "<b>Catalog Synchronization (12 hours):</b> Fetches fresh TLE ephemerides from CelesTrak to prevent propagation drift."
    ]
    for j in jobs:
        story.append(Paragraph(f"• {j}", bullet_style))
    
    story.append(Spacer(1, 6))

    # ----------------------------------------------------
    # Section 6: Real-Time Data Flow
    # ----------------------------------------------------
    story.append(Paragraph("6. Real-Time Data Flow & WebSocket Architecture", h1_style))
    flow_box = (
        "                     +----------------------+\n"
        "                     |  conjunction_alerts  |  (Single Source of Truth)\n"
        "                     +----------+-----------+\n"
        "                                |\n"
        "        +-----------------------+-----------------------+\n"
        "        |                       |                       |\n"
        "        v                       v                       v\n"
        "GET /api/v1/dashboard   GET /api/v1/alerts       Supabase Realtime\n"
        " - Active Alerts         - Filtered/sorted rows    - Live push to clients\n"
        " - High Risk Alerts      - Status updates          - 20s polling fallback\n"
        " - Next Conjunction      - Horizon / TCA badges\n"
    )
    
    t_flow = Table([[Preformatted(flow_box, code_block_style)]], colWidths=[532])
    t_flow.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), C_LIGHT_BG),
        ('BOX', (0,0), (-1,-1), 1, C_BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(t_flow)
    story.append(Spacer(1, 4))
    story.append(Paragraph("Live orbit positions follow a dedicated path: the scheduled propagation job writes updated coordinates to <code>orbit_state</code> and broadcasts over the <code>/ws/orbit</code> WebSocket channel, feeding the My Satellites table and CesiumJS 3D globe simultaneously.", body_style))
    story.append(Spacer(1, 4))

    # ----------------------------------------------------
    # Section 7: Deployment Architecture
    # ----------------------------------------------------
    story.append(Paragraph("7. Deployment Architecture", h1_style))
    deploy_box = (
        " Vercel (React/Vite SPA)  ==== HTTP ====>  Render (FastAPI)  ==== asyncpg ====>  Supabase (PostgreSQL)\n"
        "                                               |                                       |\n"
        "                                               +-- APScheduler background jobs         +-- Supabase Auth\n"
        "                                               +-- /ws/orbit WebSocket stream          +-- Realtime Push\n"
        "                                               \n"
        " CelesTrak  === (Catalog Sync Job) ===>  Render (FastAPI)  ========>  Supabase (catalog_satellites)\n"
    )
    t_deploy = Table([[Preformatted(deploy_box, code_block_style)]], colWidths=[532])
    t_deploy.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), C_LIGHT_BG),
        ('BOX', (0,0), (-1,-1), 1, C_BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_deploy)
    story.append(Spacer(1, 6))

    # ----------------------------------------------------
    # Section 8: Notable Engineering Considerations
    # ----------------------------------------------------
    story.append(Paragraph("8. Notable Engineering Considerations", h1_style))
    considerations = [
        "<b>Schema / Migration Discipline:</b> Native PostgreSQL enum types stay strictly synchronized between SQLAlchemy data models and database DDL through structured Alembic migrations, failing loudly on schema drift rather than attempting risky runtime auto-mutations.",
        "<b>SGP4 Accuracy Over 5-Day Horizons:</b> Numerical propagation error accumulates over time elapsed since TLE epoch. A high-frequency 12-hour CelesTrak TLE sync cadence maintains positional fidelity.",
        "<b>Alert Fatigue Suppression:</b> With global screening encompassing both fleet-internal and catalog objects, lower-risk approaches vastly outnumber critical events. The system strictly isolates 'stored/cataloged data' from 'active high-risk notifications' to keep operator workflows focused and actionable."
    ]
    for c in considerations:
        story.append(Paragraph(f"• {c}", bullet_style))
        
    story.append(Spacer(1, 4))

    # ----------------------------------------------------
    # Section 9: Next Steps & Roadmap
    # ----------------------------------------------------
    story.append(Paragraph("9. Next Steps & Technical Roadmap", h1_style))
    roadmap = [
        "<b>Blended Probability Classification:</b> Integrate collision probability ($P_c$) calculations directly into the primary risk tiering metric alongside miss distance.",
        "<b>Time-Series Conjunction Trends:</b> Transition dashboard altitude/conjunction trend graphs from static views to persistent historical time-series analytics.",
        "<b>Covariance-Based Conjunction Assessment:</b> Incorporate full state covariance matrices for high-precision probability volumes beyond standard TLE-derived point state vectors."
    ]
    for r in roadmap:
        story.append(Paragraph(f"• {r}", bullet_style))

    # Build Document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated PDF at: {output_path}")

if __name__ == "__main__":
    generate_pdf()

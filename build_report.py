"""Build the Pine Meadow Brolay season report PDF.

Usage:  python build_report.py            -> writes Brolay_<season>.pdf next to this file
"""
from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from brolay_stats import HIT, MISS, PUSH, Season, fmt_american

HERE = Path(__file__).parent
DATA = HERE / "brolay_data.json"
LOGO = HERE / "nfl_logo.png"
NAME = "Pine Meadow Brolay"

# ---------------------------------------------------------------- palette
INK = colors.HexColor("#0b0b0b")
INK2 = colors.HexColor("#52514e")
MUTED = colors.HexColor("#8a8985")
RULE = colors.HexColor("#e3e2dd")
PANEL = colors.HexColor("#f4f4f1")
BLUE = colors.HexColor("#2a78d6")
ORANGE = colors.HexColor("#eb6834")
GOOD = colors.HexColor("#008300")
GOOD_BG = colors.HexColor("#e4f3e4")
BAD = colors.HexColor("#c93a39")
BAD_BG = colors.HexColor("#fbe7e7")
PEND_BG = colors.HexColor("#ededea")

PAGE_W = letter[0] - 1.5 * inch  # usable width at 0.75in margins

# ---------------------------------------------------------------- styles
def style(name, **kw):
    base = dict(fontName="Helvetica", fontSize=10, leading=13, textColor=INK)
    base.update(kw)
    return ParagraphStyle(name, **base)

S = dict(
    title=style("title", fontName="Helvetica-Bold", fontSize=30, leading=34),
    subtitle=style("subtitle", fontSize=16, leading=20, textColor=INK2),
    tag=style("tag", fontSize=10.5, leading=14, textColor=INK2),
    h1=style("h1", fontName="Helvetica-Bold", fontSize=22, leading=26),
    h2=style("h2", fontName="Helvetica-Bold", fontSize=13, leading=16, spaceBefore=6),
    body=style("body"),
    small=style("small", fontSize=8.5, leading=11, textColor=INK2),
    muted=style("muted", fontSize=9, leading=12, textColor=MUTED),
    kpi_label=style("kpi_label", fontSize=8, leading=10, textColor=INK2),
    kpi_value=style("kpi_value", fontName="Helvetica-Bold", fontSize=22, leading=26),
    kpi_sub=style("kpi_sub", fontSize=8.5, leading=11, textColor=MUTED),
    cell=style("cell", fontSize=9.5, leading=12),
    cell_b=style("cell_b", fontName="Helvetica-Bold", fontSize=9.5, leading=12),
    cell_c=style("cell_c", fontSize=9.5, leading=12, alignment=TA_CENTER),
    verdict=style("verdict", fontSize=11, leading=15),
)

def P(text, st="body"):
    return Paragraph(text, S[st])


def money(x: float | None, signed=False) -> str:
    if x is None:
        return "-"
    s = f"${abs(x):,.2f}"
    if signed and x > 0:
        return "+" + s
    if x < 0:
        return "-" + s
    return s


def pct(x: float | None) -> str:
    return "-" if x is None else f"{100 * x:.0f}%"


def base_table(data, col_widths, header=True):
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0, hAlign="LEFT")
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, RULE),
    ]
    if header:
        cmds += [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("TEXTCOLOR", (0, 0), (-1, 0), INK2),
            ("LINEBELOW", (0, 0), (-1, 0), 1, INK),
        ]
    t.setStyle(TableStyle(cmds))
    return t


# ---------------------------------------------------------------- charts
def _fig_to_image(fig, width=PAGE_W, height=None):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    img = Image(buf)
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth = width
    img.drawHeight = height or width * ratio
    return img


def _style_axes(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c9c8c2")
    ax.tick_params(colors="#52514e", labelsize=9, length=0)
    ax.grid(axis="y", color="#e3e2dd", linewidth=0.8)
    ax.set_axisbelow(True)


def chart_cumulative_net(points):
    weeks = [w for w, _ in points]
    vals = [v for _, v in points]
    fig, ax = plt.subplots(figsize=(7, 2.6))
    ax.axhline(0, color="#9a9a94", linewidth=1)
    ax.plot(weeks, vals, color="#2a78d6", linewidth=2, marker="o", markersize=6,
            markerfacecolor="#2a78d6", markeredgecolor="white", markeredgewidth=1.5)
    ax.annotate(money(vals[-1], signed=True), (weeks[-1], vals[-1]),
                textcoords="offset points", xytext=(8, 0), va="center",
                fontsize=9, color="#0b0b0b", fontweight="bold")
    ax.set_xticks(weeks)
    ax.set_xlabel("Week", fontsize=9, color="#52514e")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_xlim(min(weeks) - 0.5, max(weeks) + 1.2)
    _style_axes(ax)
    return _fig_to_image(fig)


def chart_implied_vs_actual(rows):
    names = [r["person"] for r in rows]
    implied = [100 * (r["avg_implied"] or 0) for r in rows]
    actual = [100 * (r["rate"] or 0) for r in rows]
    x = range(len(names))
    w = 0.28
    fig, ax = plt.subplots(figsize=(7, 2.8))
    b1 = ax.bar([i - w / 2 - 0.02 for i in x], implied, w, color="#eb6834", label="Book's implied hit %")
    b2 = ax.bar([i + w / 2 + 0.02 for i in x], actual, w, color="#2a78d6", label="Actual hit %")
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5,
                    f"{b.get_height():.0f}%", ha="center", va="bottom", fontsize=8.5, color="#0b0b0b")
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, fontsize=10)
    ax.set_ylim(0, 110)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.legend(frameon=False, fontsize=9, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.15))
    _style_axes(ax)
    return _fig_to_image(fig)


# ---------------------------------------------------------------- sections
def status_label(status: str) -> tuple[str, colors.Color, colors.Color]:
    return {
        "won": ("CASHED", GOOD, GOOD_BG),
        "lost": ("LOST", BAD, BAD_BG),
        "pending": ("IN PROGRESS", INK2, PEND_BG),
        "void": ("VOID", INK2, PEND_BG),
    }[status]


def kpi_row(season: Season):
    r = season.record()
    rec = f"{r['wins']}-{r['losses']}"
    open_note = f"{r['pending']} open" if r["pending"] else "no open bets"
    net_color = GOOD if r["net"] > 0 else BAD if r["net"] < 0 else INK
    cells = [
        ("PARLAY RECORD", rec, open_note, INK),
        ("WAGERED", money(r["wagered"]), f"{money(r['at_risk'])} at risk", INK),
        ("PAID OUT", money(r["paid_out"]), f"{len(season.settled_weeks)} settled", INK),
        ("NET", money(r["net"], signed=True), "settled weeks", net_color),
    ]
    row = []
    for label, val, sub, col in cells:
        vs = ParagraphStyle("kv", parent=S["kpi_value"], textColor=col)
        row.append([[Paragraph(label, S["kpi_label"])], [Paragraph(val, vs)], [Paragraph(sub, S["kpi_sub"])]])
    t = Table([[Table(c, colWidths=[PAGE_W / 4 - 12]) for c in row]], colWidths=[PAGE_W / 4] * 4)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LINEAFTER", (0, 0), (-2, -1), 0.75, colors.white),
    ]))
    return t


def leaderboard_table(season: Season):
    head = ["#", "Name", "Hits", "Miss", "Push", "Open", "Hit %", "Avg odds", "Streak", "Best run"]
    data = [head]
    for i, r in enumerate(season.leaderboard(), 1):
        data.append([str(i), Paragraph(r["person"], S["cell_b"]), r["hits"], r["misses"], r["pushes"],
                     r["pending"], pct(r["rate"]),
                     fmt_american(r["avg_odds"]) if r["avg_odds"] is not None else "-",
                     r["current_streak"], f"{r['longest_hit_streak']}W" if r["longest_hit_streak"] else "-"])
    widths = [0.3, 1.2, 0.55, 0.55, 0.55, 0.55, 0.65, 0.8, 0.65, 0.75]
    t = base_table(data, [w * inch for w in widths])
    t.setStyle(TableStyle([("ALIGN", (2, 0), (-1, -1), "CENTER"), ("FONTSIZE", (0, 1), (-1, -1), 9.5)]))
    return t


def risk_table(season: Season):
    rows = sorted((season.person_stats(p) for p in season.members),
                  key=lambda r: r["avg_implied"] if r["avg_implied"] is not None else 1)
    data = [["Name", "Avg implied", "Actual", "Edge", "Risk rank"]]
    for i, r in enumerate(rows, 1):
        edge = None if r["rate"] is None or r["avg_implied"] is None else r["rate"] - r["avg_implied"]
        edge_s = "-" if edge is None else f"{100 * edge:+.0f} pts"
        data.append([Paragraph(r["person"], S["cell_b"]), pct(r["avg_implied"]), pct(r["rate"]), edge_s,
                     f"{i} of {len(rows)}" + ("  (biggest swings)" if i == 1 else "")])
    t = base_table(data, [1.2 * inch, 1.1 * inch, 0.9 * inch, 0.9 * inch, 2.2 * inch])
    t.setStyle(TableStyle([("ALIGN", (1, 0), (3, -1), "CENTER")]))
    return t


def awards_tally(season: Season):
    data = [["Name", "MVP", "Blown Layup", "Sole anchor"]]
    for p in season.members:
        r = season.person_stats(p)
        data.append([Paragraph(p, S["cell_b"]), r["mvps"], r["blown_layups"], r["sole_anchors"]])
    t = base_table(data, [1.2 * inch, 0.9 * inch, 0.9 * inch, 1.1 * inch])
    t.setStyle(TableStyle([("ALIGN", (1, 0), (-1, -1), "CENTER")]))
    return t


def awards_log(season: Season):
    data = [["Week", "Result", "MVP", "Blown Layup", "Anchor"]]
    for w in season.weeks:
        label, _, _ = status_label(w.status)
        mvp = f"{w.mvp.person} ({fmt_american(w.mvp.odds)})" if w.mvp else "-"
        layup = f"{w.blown_layup.person} ({fmt_american(w.blown_layup.odds)})" if w.blown_layup else "-"
        anchor = ", ".join(a.person for a in w.anchors) if w.status == "lost" else "-"
        data.append([str(w.week), label.title(), mvp, layup, anchor])
    t = base_table(data, [0.6 * inch, 1.0 * inch, 1.6 * inch, 1.6 * inch, 1.6 * inch])
    return t


def week_page(w, season: Season):
    label, fg, bg = status_label(w.status)
    header = Table([[Paragraph(f"Week {w.week}", S["h1"]),
                     Paragraph(f'<font color="{fg.hexval()}"><b>{label}</b></font>',
                               ParagraphStyle("pill", parent=S["cell_c"], fontSize=9))]],
                   colWidths=[PAGE_W - 1.3 * inch, 1.3 * inch])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (1, 0), (1, 0), bg),
        ("TOPPADDING", (1, 0), (1, 0), 6), ("BOTTOMPADDING", (1, 0), (1, 0), 6),
    ]))
    story = [header, P(w.date.strftime("%A, %B %d, %Y").replace(" 0", " "), "tag"), Spacer(1, 10)]

    data = [["Who", "Pick", "Game", "Type", "Odds", "Implied", "Result"]]
    cmds = [("ALIGN", (4, 0), (-1, -1), "CENTER")]
    for i, l in enumerate(w.legs, 1):
        res = {HIT: "HIT", MISS: "MISS", PUSH: "PUSH", None: "OPEN"}[l.result]
        game = (f'{l.opponent or "-"}<br/><font size="8.5" color="{INK2.hexval()}">'
                f'{l.score or "Not final"}</font>')
        data.append([Paragraph(l.person, S["cell_b"]), Paragraph(l.pick, S["cell"]),
                     Paragraph(game, S["cell"]), l.type.title(),
                     fmt_american(l.odds), pct(l.implied), res])
        col = {HIT: (GOOD, GOOD_BG), MISS: (BAD, BAD_BG)}.get(l.result, (INK2, PEND_BG))
        cmds += [("TEXTCOLOR", (6, i), (6, i), col[0]), ("BACKGROUND", (6, i), (6, i), col[1]),
                 ("FONTNAME", (6, i), (6, i), "Helvetica-Bold"), ("FONTSIZE", (6, i), (6, i), 8.5)]
    t = base_table(data, [0.65 * inch, 1.95 * inch, 1.8 * inch, 0.6 * inch, 0.55 * inch,
                          0.7 * inch, 0.75 * inch])
    t.setStyle(TableStyle(cmds))
    story += [t, Spacer(1, 14)]

    to_win = w.potential_payout - w.stake
    box = [[Paragraph("Parlay", S["kpi_label"]),
            Paragraph(f"<b>{fmt_american(w.combined_american)}</b>", S["cell"]),
            Paragraph("Stake", S["kpi_label"]), Paragraph(f"<b>{money(w.stake)}</b>", S["cell"]),
            Paragraph("Pays", S["kpi_label"]),
            Paragraph(f"<b>{money(w.potential_payout)}</b>  <font color='#8a8985'>(to win {money(to_win)})</font>", S["cell"])]]
    bt = Table(box, colWidths=[0.6 * inch, 0.9 * inch, 0.6 * inch, 0.9 * inch, 0.6 * inch, 3.4 * inch])
    bt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PANEL), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story += [bt, Spacer(1, 14)]

    if w.status == "won":
        v = (f"Cashed. {money(w.stake)} became <b>{money(w.payout)}</b>, {money(w.payout / len(season.members))} each. "
             f"MVP: {w.mvp.person} with {w.mvp.pick} at {fmt_american(w.mvp.odds)}.")
    elif w.status == "lost":
        names = [f"{a.person} ({a.pick})" for a in w.anchors]
        who = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        hits = [l for l in w.legs if l.result == HIT]
        v = f"Sunk by {who}. {money(w.stake)} gone."
        if len(names) == 1 and len(hits) == len(w.legs) - 1:
            v += f" The other {len(hits)} legs all hit, so this one stings."
        if w.blown_layup:
            v += f" Blown Layup: {w.blown_layup.person}, whose {fmt_american(w.blown_layup.odds)} pick was the safest miss."
    elif w.status == "void":
        v = "Every leg pushed. Stake refunded."
    else:
        open_n = sum(l.result is None for l in w.legs)
        v = f"Games in progress. {open_n} of {len(w.legs)} legs still open. Pays {money(w.potential_payout)} if the rest hit."
    story.append(P(v, "verdict"))
    if w.note:
        story += [Spacer(1, 8), P(w.note, "small")]
    return story


def title_block(season: Season):
    """NFL logo beside the report name; text only if the logo file is missing."""
    text = [Paragraph(NAME.upper(), S["title"]), Paragraph(f"{season.year} Season", S["subtitle"])]
    if not LOGO.exists():
        return KeepTogether(text)
    size = 1.0 * inch
    t = Table([[Image(str(LOGO), width=size, height=size), text]],
              colWidths=[size + 0.15 * inch, PAGE_W - size - 0.15 * inch])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


# ---------------------------------------------------------------- document
def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.75 * inch, 0.5 * inch, f"{NAME} {doc.season_year}")
    canvas.drawRightString(letter[0] - 0.75 * inch, 0.5 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build(data_path: Path = DATA, out_path: Path | None = None) -> Path:
    season = Season.load(data_path)
    out_path = out_path or HERE / f"Brolay_{season.year}.pdf"
    doc = SimpleDocTemplate(str(out_path), pagesize=letter, leftMargin=0.75 * inch,
                            rightMargin=0.75 * inch, topMargin=0.75 * inch, bottomMargin=0.8 * inch,
                            title=f"{NAME} {season.year}", author=f"The {NAME} Group")
    doc.season_year = season.year
    names = " · ".join(season.members)
    story = []

    # ---- page 1: season summary
    story += [title_block(season), Spacer(1, 4),
              P(f"{names}. ${season.stake_per_person:.0f} each, one leg each, every Sunday.", "tag"),
              P(f"Through Week {season.weeks[-1].week if season.weeks else 0}. "
                f"Updated {date.today().strftime('%B %d, %Y').replace(' 0', ' ')}.", "muted"),
              Spacer(1, 16), kpi_row(season), Spacer(1, 18),
              Paragraph("Season leaderboard", S["h2"]), Spacer(1, 4), leaderboard_table(season),
              P("Ranked by hit rate on settled legs. Streak is current run of hits (W) or misses (L). "
                "Avg odds is the average price each person takes.", "small"), Spacer(1, 18),
              Paragraph("Bankroll", S["h2"]), Spacer(1, 4)]
    pts = season.cumulative_net()
    if pts:
        story.append(chart_cumulative_net(pts))
        story.append(P("Cumulative net after each settled week.", "small"))
    else:
        story.append(P("Bankroll chart appears once the first parlay settles.", "muted"))

    # ---- page 2: who picks well
    story += [PageBreak(), Paragraph("Who picks well", S["h1"]), Spacer(1, 4),
              P("The book's implied hit rate is what the odds say should happen. Actual is what did. "
                "Beating your implied rate means you're finding value; taking long shots is fine if you cash them.", "tag"),
              Spacer(1, 12)]
    rows = [season.person_stats(p) for p in season.members]
    if any(r["rate"] is not None for r in rows):
        story += [chart_implied_vs_actual(rows), Spacer(1, 8)]
    else:
        story += [P("Implied vs. actual chart appears once legs settle.", "muted"), Spacer(1, 8)]
    story += [Paragraph("Risk appetite", S["h2"]), Spacer(1, 4), risk_table(season),
              P("Lower implied probability means longer odds. Edge is actual minus implied, in percentage points.", "small"),
              Spacer(1, 18)]
    story += [Paragraph("Awards", S["h2"]), Spacer(1, 4),
              P("<b>MVP</b>: longest-odds leg that hit. <b>Blown Layup</b>: safest-odds leg that missed. "
                "<b>Sole anchor</b>: the only miss in a losing week.", "small"), Spacer(1, 6),
              awards_tally(season), Spacer(1, 14),
              KeepTogether([Paragraph("Week by week", S["h2"]), Spacer(1, 4), awards_log(season)])]

    # ---- one page per week, newest first
    for w in reversed(season.weeks):
        story.append(PageBreak())
        story += week_page(w, season)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return out_path


if __name__ == "__main__":
    print("wrote", build())

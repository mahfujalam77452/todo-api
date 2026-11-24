"""Draw a team summary (from reports.build_team_summary) as a PDF."""
import io
import os
from xml.sax.saxutils import escape

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PRIMARY = colors.HexColor("#2563eb")
INK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#526078")
LINE = colors.HexColor("#dfe5f0")
SOFT = colors.HexColor("#f4f7fd")
GOOD = colors.HexColor("#15803d")
WARN = colors.HexColor("#b45309")
BAD = colors.HexColor("#b91c1c")


def _fonts():
    """(regular, bold, unicode?). Helvetica unless a Unicode TTF is configured."""
    regular, bold = settings.PDF_FONT_PATH, settings.PDF_FONT_BOLD_PATH
    if regular and os.path.exists(regular):
        pdfmetrics.registerFont(TTFont("ReportFont", regular))
        if bold and os.path.exists(bold):
            pdfmetrics.registerFont(TTFont("ReportFont-Bold", bold))
            return "ReportFont", "ReportFont-Bold", True
        return "ReportFont", "ReportFont", True
    return "Helvetica", "Helvetica-Bold", False


class _Pdf:
    def __init__(self, summary):
        self.s = summary
        self.font, self.bold, self.unicode = _fonts()
        self.styles = self._styles()

    # ---------------------------------------------------------------- helpers
    def t(self, value):
        """Safe text for a Paragraph: escaped, and without characters the font cannot draw."""
        text = "" if value is None else str(value)
        if not self.unicode:
            text = text.encode("cp1252", "replace").decode("cp1252")
        return escape(text)

    def p(self, value, style="cell"):
        return Paragraph(self.t(value), self.styles[style])

    def _styles(self):
        f, b = self.font, self.bold
        return {
            "title": ParagraphStyle("title", fontName=b, fontSize=20, leading=24, textColor=colors.white),
            "subtitle": ParagraphStyle("subtitle", fontName=f, fontSize=10.5, leading=14, textColor=colors.HexColor("#dbe7ff")),
            "h2": ParagraphStyle("h2", fontName=b, fontSize=12.5, leading=16, textColor=INK, spaceBefore=14, spaceAfter=6, keepWithNext=1),
            "body": ParagraphStyle("body", fontName=f, fontSize=9.5, leading=13, textColor=INK),
            "bullet": ParagraphStyle("bullet", fontName=f, fontSize=9.5, leading=13.5, textColor=INK, leftIndent=10, bulletIndent=0),
            "cell": ParagraphStyle("cell", fontName=f, fontSize=8.5, leading=11, textColor=INK),
            "cellb": ParagraphStyle("cellb", fontName=b, fontSize=8.5, leading=11, textColor=INK),
            "head": ParagraphStyle("head", fontName=b, fontSize=8, leading=10, textColor=MUTED),
            "num": ParagraphStyle("num", fontName=b, fontSize=17, leading=20, textColor=INK, alignment=TA_CENTER),
            "numlabel": ParagraphStyle("numlabel", fontName=f, fontSize=7.5, leading=9, textColor=MUTED, alignment=TA_CENTER),
            "muted": ParagraphStyle("muted", fontName=f, fontSize=9, leading=12, textColor=MUTED),
        }

    def table(self, header, rows, widths, align_right=()):
        data = [[self.p(h, "head") for h in header]] + rows
        table = Table(data, colWidths=widths, repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), SOFT),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, PRIMARY),
            ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]
        for col in align_right:
            style.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
        table.setStyle(TableStyle(style))
        return table

    def stat_row(self, items, width):
        """A row of number boxes: [(value, label, colour), ...]."""
        cells = [
            [Paragraph(self.t(value), ParagraphStyle("n", parent=self.styles["num"], textColor=color)),
             self.p(label, "numlabel")]
            for value, label, color in items
        ]
        table = Table([[c for c in cells]], colWidths=[width / len(items)] * len(items))
        table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, LINE),
            ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE),
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        return table

    # ---------------------------------------------------------------- content
    def build(self):
        s, st, snap = self.s, self.s["day_stats"], self.s["snapshot"]
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
            topMargin=14 * mm, bottomMargin=16 * mm,
            title=f"Daily summary - {s['team']} - {s['day']:%d %b %Y}",
            author="Todo Workspace",
        )
        width = doc.width
        story = []

        banner = Table(
            [[Paragraph("Daily Team Summary", self.styles["title"])],
             [self.p(f"{s['team']}  |  {s['day']:%A, %d %B %Y}", "subtitle")]],
            colWidths=[width],
        )
        banner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PRIMARY),
            ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (0, 0), 12), ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
        ]))
        story += [banner, Spacer(1, 10)]

        story.append(self.p("Highlights", "h2"))
        for line in s["highlights"]:
            story.append(Paragraph(self.t(line), self.styles["bullet"], bulletText="•"))

        story.append(self.p("The day in numbers", "h2"))
        story.append(self.stat_row([
            (st["total"], "ACTIONS", INK),
            (st["created"], "TODOS CREATED", INK),
            (st["completed"], "COMPLETED", GOOD),
            (st["accepted"], "ACCEPTED", GOOD),
            (st["rejected"], "REJECTED", BAD if st["rejected"] else INK),
            (st["deleted"], "DELETED", INK),
        ], width))

        story.append(self.p("Where the team stands now", "h2"))
        story.append(self.stat_row([
            (snap["active"], "ACTIVE TODOS", INK),
            (snap["overdue"], "OVERDUE", BAD if snap["overdue"] else INK),
            (snap["awaiting"], "AWAITING ANSWER", WARN if snap["awaiting"] else INK),
            (snap["stale"], f"WAITING > {s['stale_hours']}H", WARN if snap["stale"] else INK),
        ], width))
        story.append(Spacer(1, 3))
        story.append(self.p("Counts cover the todos that belong to this team. Rejected and completed todos are not 'active'.", "muted"))

        story += self.attention_section(width)
        story += self.members_section(width)
        story += self.timeline_section(width)
        story.append(Spacer(1, 12))
        story.append(self.p(f"Generated {s['generated_at']:%d %b %Y, %H:%M} (Asia/Dhaka). Automatic report from Todo Workspace.", "muted"))

        doc.build(story, canvasmaker=lambda *a, **k: _NumberedCanvas(*a, font=self.font, **k))
        return buffer.getvalue()

    def attention_section(self, width):
        s = self.s
        parts = [self.p("Needs attention", "h2")]
        if not (s["overdue_items"] or s["stale_items"] or s["rejected"]):
            parts.append(self.p("Nothing needs attention: no overdue todos, no unanswered assignments, no rejections.", "body"))
            return parts

        if s["overdue_items"]:
            rows = [[self.p(i["title"]), self.p(i["assignee"]), self.p(i["due"]), self.p(f"{i['days']} d", "cellb")] for i in s["overdue_items"]]
            parts.append(KeepTogether([
                self.p(f"Overdue todos ({s['snapshot']['overdue']})", "cellb"), Spacer(1, 3),
                self.table(["Todo", "Assignee", "Was due", "Late by"], rows, [width * .46, width * .22, width * .18, width * .14]),
            ]))
            if s["snapshot"]["overdue"] > len(s["overdue_items"]):
                parts.append(self.p(f"... and {s['snapshot']['overdue'] - len(s['overdue_items'])} more.", "muted"))
            parts.append(Spacer(1, 8))

        if s["stale_items"]:
            rows = [[self.p(i["title"]), self.p(i["assignee"]), self.p(i["since"]), self.p(f"{i['hours']} h", "cellb")] for i in s["stale_items"]]
            parts.append(KeepTogether([
                self.p(f"Assignments with no answer for more than {s['stale_hours']} hours ({s['snapshot']['stale']})", "cellb"), Spacer(1, 3),
                self.table(["Todo", "Assigned to", "Assigned at", "Waiting"], rows, [width * .46, width * .22, width * .18, width * .14]),
            ]))
            parts.append(Spacer(1, 8))

        if s["rejected"]:
            rows = [[self.p(i["todo"]), self.p(i["actor"]), self.p(i["reason"] or "No reason given")] for i in s["rejected"]]
            parts.append(KeepTogether([
                self.p(f"Rejected during the day ({len(s['rejected'])})", "cellb"), Spacer(1, 3),
                self.table(["Todo", "Rejected by", "Reason"], rows, [width * .40, width * .22, width * .38]),
            ]))
        return parts

    def members_section(self, width):
        rows = [
            [self.p(m["name"], "cellb"), self.p(m["role"]), self.p(m["actions"]), self.p(m["completed"]), self.p(m["open"]), self.p(m["overdue"], "cellb" if m["overdue"] else "cell")]
            for m in self.s["members"]
        ]
        table = self.table(
            ["Member", "Role", "Actions", "Completed", "Active todos", "Overdue"], rows,
            [width * .28, width * .20, width * .12, width * .14, width * .14, width * .12],
            align_right=(2, 3, 4, 5),
        )
        return [self.p("Member overview", "h2"), table]

    def timeline_section(self, width):
        s = self.s
        parts = [self.p("Activity timeline", "h2")]
        if not s["timeline"]:
            parts.append(self.p("No activity was recorded on this day.", "body"))
            return parts
        rows = [
            [self.p(r["time"], "cellb"), self.p(r["actor"]), self.p(r["action"]), self.p(r["todo"]), self.p(r["detail"])]
            for r in s["timeline"]
        ]
        parts.append(self.table(
            ["Time", "Who", "Action", "Todo", "Details"], rows,
            [width * .08, width * .16, width * .17, width * .29, width * .30],
        ))
        if s["timeline_hidden"]:
            parts.append(Spacer(1, 4))
            parts.append(self.p(f"... and {s['timeline_hidden']} more actions (the timeline shows the first {len(s['timeline'])}).", "muted"))
        return parts


class _NumberedCanvas(canvas.Canvas):
    """Adds 'Page x of y' to every page (the total is known only at the end)."""

    def __init__(self, *args, font="Helvetica", **kwargs):
        super().__init__(*args, **kwargs)
        self._font = font
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self.setFont(self._font, 8)
            self.setFillColor(MUTED)
            self.drawRightString(A4[0] - 16 * mm, 9 * mm, f"Page {self._pageNumber} of {total}")
            super().showPage()
        super().save()


def render_summary_pdf(summary):
    """Return the PDF (bytes) for a summary built by reports.build_team_summary()."""
    return _Pdf(summary).build()
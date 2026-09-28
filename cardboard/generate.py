#!/usr/bin/env python3
"""Generate printable cardboard build plans for the Supercade arcade cabinet.

Geometry is taken from the original Supercade CAD exports in
github.com/MikSaint/supercade:

  3D Files/Arcade-Panels.pdf  (3/4" = 1', side-panel polygon + panel list)
  3D Files/Arcade-Mockup.pdf  (3/4" = 1', side/front/top views)
  Flats/SuperCade_Controls_v3_27x11.3in.ai  (1:1 control panel flat)

The numbers were read from the vector paths in those files (scale x16 for the
3/4" = 1' drawings) and are hard-coded below so this script runs on its own.

Each entry in BUILDS is one plan set. The cabinet body scales; arcade
buttons and joysticks don't, so each build carries its own control layout.

Usage:
  pip install pymupdf
  python3 generate.py            # writes into ./<build key>/
"""

import base64
import json
import math
import os
from collections import Counter
from dataclasses import dataclass, field

import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
PT = 72.0  # points per inch
MM = 1 / 25.4
LETTER = pymupdf.paper_rect("letter")

# ---------------------------------------------------------------------------
# Source geometry (inches, full size)
# ---------------------------------------------------------------------------

# Side panel profile. h = height from the floor, d = depth from the back.
# Read from Arcade-Panels.pdf path #121/#122 (outline of the side panel).
SIDE = {
    "A": (0.00, 0.00),    # floor, back
    "B": (73.73, 0.00),   # top, back
    "C": (73.73, 14.84),  # top, front
    "D": (40.80, 9.85),   # bottom of screen slope / back of control deck
    "E": (39.00, 24.49),  # control deck, front edge
    "F": (34.81, 24.49),  # bottom of control-panel front lip
    "G": (34.31, 9.26),   # under the control deck, meets the kick panel
    "H": (0.00, 15.62),   # floor, front
}
SIDE_ORDER = "ABCDEFGH"
LOWER_SHELF_H = 9.5   # Arcade-Mockup.pdf side view, 10" shelf
INNER_WIDTH = 29.0    # every cross panel in the original is 29" wide
SPEAKER_W, SPEAKER_H = 5.25, 4.0  # Arcade-Panels.pdf speaker ovals

# The screen sits back in a recess behind the front frame (Arcade-Mockup.pdf
# side view, same h/d axes as SIDE). Speakers are in the recess ceiling,
# pointing down; the screen leans back 5 degrees.
RECESS = {
    "S1": (69.39, 6.74),   # speaker shelf underside, back
    "S2": (70.72, 14.34),  # speaker shelf underside, front (meets the frame)
    "M1": (46.52, 8.71),   # screen face, bottom
    "M2": (69.63, 6.70),   # screen face, top
    "R1": (46.52, 6.46),   # recess floor top, back
}
FRAME_BORDER = 1.0     # frame edge left beside the opening, each side


@dataclass
class Hole:
    x: float     # inches from the template's left edge
    y: float     # inches from the template's top edge (players at the bottom)
    dia_mm: float
    kind: str    # button / stick / start / coin / aux / mount
    label: str = ""


@dataclass
class ControlLayout:
    width: float
    height: float
    holes: list
    source: str
    octagon: tuple = None       # (cx, cy, w, h, chamfer) inches
    player_labels: tuple = ()   # ((x, y, text), ...)
    note: str = ""


def original_controls():
    """SuperCade_Controls_v3_27x11.3in.ai, hole centres in inches."""
    holes = [Hole(x, y, 30.0, "button") for x, y in [
        (5.372, 8.022), (5.659, 6.431), (6.683, 7.455), (6.987, 5.864),
        (8.138, 7.455), (8.442, 5.864), (9.602, 7.533), (9.905, 5.942),
        (20.335, 8.022), (20.622, 6.431), (21.646, 7.455), (21.950, 5.864),
        (23.102, 7.455), (23.406, 5.864), (24.565, 7.533), (24.869, 5.942),
    ]]
    holes += [
        Hole(2.781, 7.276, 25.0, "stick"), Hole(17.756, 7.276, 25.0, "stick"),
        Hole(6.393, 2.263, 24.0, "start", "P1 START"), Hole(7.912, 2.263, 24.0, "coin", "COIN 1"),
        Hole(21.351, 2.263, 24.0, "start", "P2 START"), Hole(22.870, 2.263, 24.0, "coin", "COIN 2"),
        Hole(1.655, 2.249, 19.0, "aux"),
    ]
    holes += [Hole(x, y, 5.0, "mount") for x, y in [
        (1.918, 5.675), (3.654, 5.675), (1.918, 8.872), (3.643, 8.872),
        (16.893, 5.675), (18.629, 5.675), (16.893, 8.872), (18.618, 8.872),
        (0.529, 0.536), (26.462, 0.536), (0.529, 10.760), (26.462, 10.760),
    ]]
    holes += [Hole(x, y, 4.0, "mount") for x, y in [
        (11.466, 1.593), (11.466, 2.907), (15.855, 1.593), (15.855, 2.907),
    ]]
    return ControlLayout(
        27.0, 11.3, holes, "SuperCade_Controls_v3 (27\" x 11.3\")",
        octagon=(13.658, 2.249, 117 * MM, 39 * MM, 0.30),
        player_labels=((7.6, 10.2, "PLAYER 1"), (22.6, 10.2, "PLAYER 2")),
        note="Template is 27\" wide: centre it on the 29\" deck.",
    )


def compact_controls(width, height):
    """2 players x (stick + 6 buttons) squeezed onto a small deck.

    Same arrangement as the original (stick left, 3 x 2 buttons right, start
    and coin above), with 24 mm action buttons at 30 mm pitch so both players
    fit. Laid out in mm from the deck's top-left corner.
    """
    w_mm = width / MM
    half = w_mm / 2
    holes = []
    for p, x0 in ((1, 0.0), (2, half)):
        sx, sy = x0 + 44, 118  # plate clears the side flange by ~10 mm
        holes.append(Hole(sx * MM, sy * MM, 25.0, "stick"))
        # 4 bolts for the stick's mounting plate (same 44 x 81 mm pattern as
        # the original drawing; check it against your own joystick)
        for dx in (-22, 22):
            for dy in (-40.5, 40.5):
                holes.append(Hole((sx + dx) * MM, (sy + dy) * MM, 5.0, "mount"))
        for i, bx in enumerate((100, 130, 160)):
            drop = 8 if i == 0 else 0  # first column sits a little lower, like the original
            holes.append(Hole((x0 + bx) * MM, (102 + drop) * MM, 24.0, "button"))
            holes.append(Hole((x0 + bx) * MM, (135 + drop) * MM, 24.0, "button"))
        holes.append(Hole((x0 + 112) * MM, 42 * MM, 24.0, "start", f"P{p} START"))
        holes.append(Hole((x0 + 146) * MM, 42 * MM, 24.0, "coin", f"COIN {p}"))
    holes.append(Hole(half * MM, 42 * MM, 19.0, "aux", "MENU"))
    m = 10
    for x, y in ((m, m), (w_mm - m, m), (m, height / MM - m), (w_mm - m, height / MM - m)):
        holes.append(Hole(x * MM, y * MM, 5.0, "mount"))
    return ControlLayout(
        width, height, holes, "compact 2-player layout for the scaled deck",
        player_labels=((half / 2 * MM + 0.6, height - 0.25, "PLAYER 1"),
                       ((half * 1.5) * MM + 0.6, height - 0.25, "PLAYER 2")),
        note="Template is the whole deck: line its edges up with P5.",
    )


@dataclass
class Build:
    key: str                 # output folder
    title: str               # e.g. "Half scale"
    scale: float
    lower: float = 0.0       # inches trimmed off the bottom, after scaling
    flange: float = 2.0
    controls: ControlLayout = None
    screen: str = ""
    screen_window: str = ""
    material: str = ""
    deck_note: str = ""
    deck_extra: tuple = ()   # extra cut-list row for the deck
    ballast: str = ""
    cover: bool = True       # acrylic screen cover row
    shopping: list = field(default_factory=list)
    stock_note: str = ""
    nest_note: str = ""
    filename: str = ""
    control_box: bool = False  # also make the standalone control-box plans

    @property
    def inner_width(self):
        return INNER_WIDTH * self.scale

    @property
    def blank_width(self):
        return self.inner_width + 2 * self.flange

    @property
    def shelf_h(self):
        return LOWER_SHELF_H * self.scale - self.lower

    @property
    def screw_pitch(self):
        return max(3.5, 6 * self.scale)

    def side_points(self):
        pts = {k: (h * self.scale, d * self.scale) for k, (h, d) in SIDE.items()}
        if self.lower:
            # Trim the floor end: the kick slope H->G keeps its angle, so H
            # slides up that slope and everything else drops by `lower`.
            (hh, hd), (gh, gd) = pts["H"], pts["G"]
            t = self.lower / (gh - hh)
            new_hd = hd + (gd - hd) * t
            pts = {k: (h - self.lower, d) for k, (h, d) in pts.items()}
            pts["A"], pts["H"] = (0.0, 0.0), (0.0, new_hd)
        return pts

    def frame_note(self):
        s0, s1, b = self.frame_opening()
        return (f"ONE continuous flat piece. Cut an opening {frac(self.inner_width - 2 * b)} wide, "
                f"from {frac(s0)} to {frac(s1)} down from the top (C) edge. The recess sits behind it.")

    def beam(self):
        """Box-beam shelf strips (top, front, bottom, back, glue tab)."""
        top = round(10 * self.scale * 2) / 2
        side = max(1.5, round(3 * self.scale * 2) / 2)
        tab = 1.0 if self.scale >= 0.75 else 0.75
        return top, side, tab

    def front_d(self, h):
        """Depth of the front edge C-D at height h."""
        p = self.side_points()
        (ch, cd), (dh, dd) = p["C"], p["D"]
        return dd + (cd - dd) * (h - dh) / (ch - dh)

    def recess_points(self):
        pts = {k: (h * self.scale - self.lower, d * self.scale) for k, (h, d) in RECESS.items()}
        h = pts["R1"][0]
        pts["R2"] = (h, self.front_d(h))    # recess floor meets the frame
        return pts

    def frame_opening(self):
        """Opening in P4, as distances along C-D measured from C, plus side border."""
        p, r = self.side_points(), self.recess_points()
        (ch, cd), (dh, dd) = p["C"], p["D"]
        L = math.hypot(ch - dh, cd - dd)
        along = lambda h: (ch - h) / (ch - dh) * L
        return along(r["S2"][0]), along(r["R1"][0]), max(0.75, FRAME_BORDER * self.scale)

    def inner_panels(self):
        """Recess parts: id, name, (a, b) face line, length, note, visible-face normal (dh, dd)."""
        r = self.recess_points()
        L = lambda a, b: math.hypot(r[b][0] - r[a][0], r[b][1] - r[a][1])
        sw = SPEAKER_W * self.scale
        return [
            ("P4a", "Speaker shelf", ("S1", "S2"), L("S1", "S2"),
             f"Recess ceiling. Two {frac(sw)} x {frac(SPEAKER_H * self.scale)} speaker holes, pointing DOWN at the players.", (-1, 0)),
            ("P4b", "Screen board", ("M1", "M2"), L("M1", "M2"),
             self.screen_window + " Leans back 5 degrees; the monitor bolts or straps on behind it.", (0, 1)),
            ("P4c", "Recess floor", ("R1", "R2"), L("R1", "R2"),
             "Bottom of the recess, level with the top of the frame's lower lip.", (1, 0)),
        ]

    def cross_panels(self):
        p = self.side_points()
        L = lambda a, b: edge_len(p, a, b)
        return [
            # id, name, edge, length, notes
            ("P2", "Back", "A-B", L("A", "B"),
             f"Cut a {frac(12 * self.scale)} x {frac(20 * self.scale)} service door low down (optional)."),
            ("P3", "Top", "B-C", L("B", "C"), ""),
            ("P4", "Front frame", "C-D", L("C", "D"), self.frame_note()),
            ("P5", "Control deck", "D-E", L("D", "E"), self.deck_note),
            ("P6", "Control lip", "E-F", L("E", "F"), "Front face under the players' wrists."),
            ("P7", "Under-deck", "F-G", L("F", "G"), ""),
            ("P8", "Kick panel", "G-H", L("G", "H"), "Leg room slope. Optional access door."),
            ("P9", "Floor", "H-A", L("H", "A"), "Double layer. This carries the ballast."),
        ]


def edge_len(p, a, b):
    (h1, d1), (h2, d2) = p[a], p[b]
    return math.hypot(h2 - h1, d2 - d1)


def frac(v):
    """Inches to the nearest 1/8 as a tape-measure friendly string."""
    eighths = round(v * 8)
    whole, rem = divmod(eighths, 8)
    if rem == 0:
        return f'{whole}"'
    g = math.gcd(rem, 8)
    f = f"{rem // g}/{8 // g}"
    return f'{whole} {f}"' if whole else f'{f}"'


# ---------------------------------------------------------------------------
# The builds
# ---------------------------------------------------------------------------

FULL_SHOPPING = [
    ("CARDBOARD + FASTENING", [
        ("Double-wall corrugated sheets, 48\" x 96\"", "5-6 sheets. Or appliance boxes (free from appliance/moving stores)."),
        ("Kids' cardboard construction kit (screws + nuts)", "Plastic screws, punch/driver tool, safe saw. Get one whose screws come with nuts."),
        ("Extra plastic screws (refill pack)", "Plan on ~150. Each cross panel uses ~10, shelves and deck add more."),
        ("PVA / white glue + hot glue gun", "Glue laminations and flanges; screws clamp while it dries."),
        ("Nylon nuts + bolts, M4/M5 x 25-30 mm, fender washers", "For the joysticks and anything heavy."),
        ("Wide packing tape / gaffer tape", "Edge-protecting the corners and the bottom edge."),
    ]),
    ("CONTROLS + ELECTRONICS", [
        ("\"Zero delay\" 2-player arcade kit (joysticks + 30 mm buttons + USB encoders)", "Pick one with SCREW-IN buttons, 20+ buttons to cover start/coin."),
        ("Screen", "Sized for a 27\" monitor. An old 22-27\" monitor or a light TV is fine."),
        ("Computer", "Raspberry Pi 4/5 running an arcade front-end, or any old laptop/mini PC."),
        ("Speakers", "Two small speakers that fit a 5 1/4\" x 4\" oval cut-out."),
        ("Power strip with a switch", "One switch for everything; mount it on the lower shelf."),
        ("Weight for the base", "2 x 10 lb sandbags or bags of rice/gravel on the lower shelf."),
    ]),
    ("TOOLS", [
        ("Long metal straightedge (4 ft) + carpenter's square", "For drawing the side panels."),
        ("Box cutter / utility knife + self-healing mat", "Adults do the long cuts. Kids use the kit's safe saw."),
        ("Scoring tool", "The kit's crease roller, a blunt butter knife or an empty ballpoint pen."),
        ("Drill with 1 3/16\" (30 mm) and 1\" (25 mm) hole saws (optional)", "Clean control-panel holes. Otherwise a compass + craft knife."),
    ]),
]

HALF_SHOPPING = [
    ("CARDBOARD + FASTENING", [
        ("Big cardboard boxes", "4-5 large ones (TV, bike or wardrobe boxes). The longest parts are 37\" long."),
        ("Kids' cardboard construction kit with screws + nuts", "e.g. a 400-piece kit with safe saw + crease roller. ~80 screws get used, so one kit is plenty."),
        ("5 mm PVC foam board (\"Foamex\"), A3 / 12 x 18\" is enough", "For the control deck top plate. Cuts with a craft knife, holds buttons firmly."),
        ("PVA / white glue + hot glue gun", "Glue the laminations and the box-beam shelves."),
        ("Nylon or steel M4/M5 x 20 mm bolts + nuts + washers", "8 for the joysticks, 4 for the deck plate corners."),
        ("Wide packing tape / gaffer tape", "Edge-protecting the corners and the bottom edge."),
    ]),
    ("CONTROLS + ELECTRONICS", [
        ("\"Zero delay\" 2-player arcade kit with 24 mm buttons", "Needs 2 sticks + 16 x 24 mm buttons (12 action + 2 start + 2 coin). If the kit only has 30 mm, buy a 24 mm pack. SCREW-IN type."),
        ("13.3\" portable USB-C monitor", "~0.7 kg. Built-in speakers are common, so check and skip separate ones."),
        ("Computer", "Raspberry Pi 4/5 with an arcade front-end, or an old laptop behind the cabinet."),
        ("Small USB speakers (optional)", "Only if the monitor has none. Two 2 5/8\" x 2\" oval cut-outs are in the templates."),
        ("Weight for the base", "A 2 kg bag of rice or a couple of books on the lower shelf."),
    ]),
    ("TOOLS", [
        ("Metal ruler (1 m / 40\") + set square", "For drawing the side panels."),
        ("Craft knife + cutting mat", "Adults do the long cuts and the Foamex. Kids use the kit's safe saw."),
        ("Crease roller (in the kit) or a blunt butter knife", "For scoring fold lines."),
        ("Compass, pencil, tape measure", "Or a drill with 24 mm + 25 mm hole saws / a step bit for neat holes."),
    ]),
]

HALF_DECK = compact_controls(INNER_WIDTH * 0.5, edge_len({k: (h * 0.5, d * 0.5) for k, (h, d) in SIDE.items()}, "D", "E"))

BUILDS = [
    Build(
        key="half-scale", title="Half scale", scale=0.5, flange=1.5,
        controls=HALF_DECK, filename="SuperCade-Half-Plans.pdf", control_box=True,
        screen='13.3" portable USB-C monitor',
        screen_window='Centred window 11 5/8" x 6 1/2" (13.3" monitor visible area; measure yours).',
        material="cardboard body, 5 mm Foamex deck plate",
        deck_note="1 layer of cardboard + the Foamex plate (P12) on top. Under each joystick, cut an opening in the cardboard just bigger than the stick's mounting plate, so the stick bolts to the Foamex only.",
        deck_extra=("P12", "Deck top plate", "1", None, "-",
                    "5 mm Foamex (PVC foam board). Tape the 1:1 template to it, cut every hole, then drill through into P5."),
        ballast="a 2 kg bag of rice on the lower shelf",
        cover=False,
        shopping=HALF_SHOPPING,
        stock_note="Cardboard: 4-5 big boxes. The longest parts (sides + back) are about 37\" long, so you need at least one box with a panel that long - TV, bike and wardrobe boxes are.",
        nest_note="Each side is 36 7/8\" x 12 1/4\". Trace the second from the first, flipped over.",
    ),
    Build(
        key="full-size", title="Full size (original)", scale=1.0,
        controls=original_controls(), filename="SuperCade-Full-Plans.pdf",
        screen='27" monitor (original), lighter is better',
        screen_window="Centred window cut to YOUR monitor's visible area (about 23 1/2\" x 13 1/4\" for a 27\").",
        material="double-wall corrugated cardboard",
        deck_note="Laminate 2-3 layers. Tape the 1:1 control-panel template on, centred.",
        deck_extra=("P12", "Deck doubler", "2", None, "-",
                    "Glued under P5 so the controls don't flex. Cut holes through all layers together."),
        ballast="20 lb of sandbags or rice on the lower shelf",
        shopping=FULL_SHOPPING,
        stock_note="Cardboard: roughly five 48\" x 96\" double-wall sheets, six if you double the sides. A refrigerator box gets you the two sides and the back.",
        nest_note="Fitting on a 4x8 sheet: both sides fit on one 48 x 96 sheet if the second is turned end-for-end so the control-deck tongues sit side by side (see Arcade-Sheets.pdf, sheet 2).",
    ),
    Build(
        key="full-size", title="Full size, kid height (8 in lower)", scale=1.0, lower=8.0,
        controls=original_controls(), filename="SuperCade-Full-KidHeight-Plans.pdf",
        screen='27" monitor (original), lighter is better',
        screen_window="Centred window cut to YOUR monitor's visible area (about 23 1/2\" x 13 1/4\" for a 27\").",
        material="double-wall corrugated cardboard",
        deck_note="Laminate 2-3 layers. Tape the 1:1 control-panel template on, centred.",
        deck_extra=("P12", "Deck doubler", "2", None, "-",
                    "Glued under P5 so the controls don't flex. Cut holes through all layers together."),
        ballast="20 lb of sandbags or rice on the lower shelf",
        shopping=FULL_SHOPPING,
        stock_note="Cardboard: roughly five 48\" x 96\" double-wall sheets. A refrigerator box gets you the two sides and the back.",
        nest_note="Both sides fit on one 48 x 96 sheet with the second turned end-for-end.",
    ),
]

# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

BLACK, GREY, LIGHT, RED, BLUE = (0, 0, 0), (0.45, 0.45, 0.45), (0.82, 0.82, 0.82), (0.8, 0.1, 0.1), (0.1, 0.3, 0.75)
TAN = (0.96, 0.93, 0.86)


def text(page, x, y, s, size=9, font="helv", color=BLACK, rotate=0):
    page.insert_text((x, y), s, fontsize=size, fontname=font, color=color, rotate=rotate)


def box(page, rect, s, size=9, font="helv", color=BLACK, align=0):
    rc = page.insert_textbox(rect, s, fontsize=size, fontname=font, color=color, align=align)
    if rc < 0:
        raise ValueError(f"text overflow ({rc:.0f}pt) in box {rect}: {s[:40]!r}")
    return rc


def header(page, title, sub=""):
    text(page, 36, 50, title, 18, "hebo")
    if sub:
        text(page, 36, 68, sub, 9, color=GREY)
    page.draw_line((36, 76), (LETTER.width - 36, 76), color=BLACK, width=0.8)


def footer(page, n, total, label):
    text(page, 36, LETTER.height - 24, f"SUPERCADE cardboard edition  -  {label}", 7, color=GREY)
    text(page, LETTER.width - 80, LETTER.height - 24, f"page {n} / {total}", 7, color=GREY)


def dim_line(page, p1, p2, label, off=12, size=7, color=BLUE):
    """Dimension line between p1 and p2 (points), offset perpendicular by `off`."""
    (x1, y1), (x2, y2) = p1, p2
    dx, dy = x2 - x1, y2 - y1
    ln = math.hypot(dx, dy) or 1
    nx, ny = -dy / ln * off, dx / ln * off
    a, b = (x1 + nx, y1 + ny), (x2 + nx, y2 + ny)
    page.draw_line(p1, a, color=LIGHT, width=0.4)
    page.draw_line(p2, b, color=LIGHT, width=0.4)
    page.draw_line(a, b, color=color, width=0.5)
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    w = pymupdf.get_text_length(label, "helv", size)
    page.draw_rect(pymupdf.Rect(mx - w / 2 - 1.5, my - size / 2 - 1.5, mx + w / 2 + 1.5, my + size / 2 + 1.5),
                   color=None, fill=(1, 1, 1))
    text(page, mx - w / 2, my + size / 2 - 1, label, size, color=color)


# ---------------------------------------------------------------------------
# Plan set (letter, scaled drawings)
# ---------------------------------------------------------------------------


def fit_scale(b, max_h_pt, max_w_pt):
    pts = b.side_points()
    return min(max_h_pt / pts["B"][0], max_w_pt / pts["E"][1])


def draw_side(page, pts, origin, scale, labels=True):
    ox, oy = origin
    pp = {k: pymupdf.Point(ox + d * scale, oy - h * scale) for k, (h, d) in pts.items()}
    poly = [pp[k] for k in SIDE_ORDER] + [pp["A"]]
    page.draw_polyline(poly, color=BLACK, fill=TAN, width=1.0, closePath=True)
    if labels:
        for k in SIDE_ORDER:
            text(page, pp[k].x + 3, pp[k].y - 3, k, 8, "hebo", RED)
            page.draw_circle(pp[k], 1.6, color=RED, fill=RED)
    return pp


def draw_recess(page, b, origin, scale, labels=True):
    """Recess parts inside the side panel, and the opening in the front frame."""
    ox, oy = origin
    P = lambda hd: pymupdf.Point(ox + hd[1] * scale, oy - hd[0] * scale)
    r = b.recess_points()
    # the frame opening: the part of edge C-D the player looks through
    top_h, bot_h = r["S2"][0], r["R1"][0]
    page.draw_line(P((top_h, b.front_d(top_h))), P((bot_h, b.front_d(bot_h))), color=(1, 1, 1), width=2.4)
    page.draw_line(P((top_h, b.front_d(top_h))), P((bot_h, b.front_d(bot_h))), color=BLACK, width=0.6, dashes="[1 2] 0")
    for pid, name, (a, c), ln, _, _ in b.inner_panels():
        page.draw_line(P(r[a]), P(r[c]), color=(0.15, 0.15, 0.15), width=2.2)
        if labels:
            m = (P(r[a]) + P(r[c])) / 2
            text(page, m.x + 4, m.y + (9 if pid == "P4a" else -3 if pid == "P4c" else 3), pid, 6, "hebo", BLUE)


def page_overview(doc, b):
    page = doc.new_page(width=LETTER.width, height=LETTER.height)
    pts = b.side_points()
    total_h = pts["B"][0]
    deck_h = (pts["D"][0] + pts["E"][0]) / 2
    header(page, "SUPERCADE - cardboard edition", f"{b.title}. Printable plan set, built from the original Supercade CAD files.")

    scale = fit_scale(b, 590, 150)
    origin = (90, 700)
    pp = draw_side(page, pts, origin, scale)
    draw_recess(page, b, origin, scale)
    for pid, name, edge, ln, _ in b.cross_panels():
        a, c = edge.split("-")
        m = (pp[a] + pp[c]) / 2
        v = pp[c] - pp[a]
        n = pymupdf.Point(v.y, -v.x) / (abs(v) or 1)  # outward for this winding
        lab = f"{pid} {name}"
        w = pymupdf.get_text_length(lab, "hebo", 7)
        tx = m.x + n.x * 8 - (w if n.x < -0.3 else (w / 2 if abs(n.x) <= 0.3 else 0))
        ty = m.y + n.y * 8 + 3 + (4 if n.y > 0.3 else 0)
        text(page, tx, ty, lab, 7, "hebo", BLUE)
    if b.shelf_h > 1.5:
        y = origin[1] - b.shelf_h * scale
        page.draw_line((origin[0] + 2 * b.scale * scale, y), (origin[0] + 12 * b.scale * scale, y),
                       color=GREY, width=1.5, dashes="[3 2] 0")
        text(page, origin[0] + 2 * b.scale * scale, y - 3, "P11 lower shelf", 6, color=GREY)
    text(page, origin[0], origin[1] + 28, "P1 SIDE PANEL (x2) - side view, back on the left", 8, "hebo")
    dim_line(page, pp["A"], pp["B"], frac(total_h), off=-20)

    x0 = 330
    rows = [
        ("Overall height", frac(total_h)),
        ("Overall depth", frac(pts["E"][1])),
        ("Inside width", frac(b.inner_width)),
        ("Outside width", f'{frac(b.inner_width)} + 2 x side thickness'),
        ("Control deck height", f"~{frac(deck_h)} (7 deg tilt)"),
        ("Screen", b.screen),
        ("Material", b.material),
        ("Fasteners", "kids' plastic cardboard screws + glue"),
    ]
    y = 110
    text(page, x0, y, "AT A GLANCE", 10, "hebo"); y += 16
    for k, v in rows:
        text(page, x0, y, k, 8, color=GREY); text(page, x0 + 90, y, v, 8); y += 13

    y += 14
    text(page, x0, y, "WHAT'S IN THIS PACKET", 10, "hebo"); y += 6
    box(page, pymupdf.Rect(x0, y, LETTER.width - 36, y + 170),
        "1  This overview\n"
        "2  Side panel - measure-and-mark drawing\n"
        "3  Cut list (every part, every size)\n"
        "4  Cross panels - fold-flange layout\n"
        "5  Control panel layout + hole schedule\n"
        "6  Shopping list\n"
        "7  Assembly steps\n\n"
        f"1:1 print-and-tape templates in {b.key}/templates/:\n"
        "  control-panel-1to1.pdf\n"
        "  speaker-cutouts-1to1.pdf\n"
        f"  side-panel-1to1{suffix(b)}.pdf", 8)

    y += 185
    text(page, x0, y, "HOW THE CARDBOARD VERSION WORKS", 10, "hebo"); y += 6
    box(page, pymupdf.Rect(x0, y, LETTER.width - 36, y + 220),
        "The original is 1/2\" plywood held together with wood screws "
        "driven into panel edges. Cardboard edges can't hold a screw, so "
        f"every cross panel (P2-P9) gets a {frac(b.flange)} flange folded down on each "
        "end. The flange lies flat against the inside of the side panel "
        "and a plastic screw + nut goes through both layers, face to face. "
        "That's exactly the joint kids' cardboard screw kits are made for.\n\n"
        + (f"Everything is the original at {b.scale:.0%} - except the controls. "
           "Arcade buttons and joysticks don't shrink, so the deck has its own "
           "compact 2-player layout (page 5)." if b.scale != 1 else
           "Side panel shape, panel lengths and control layout are the "
           "original's. Only the joinery changes."), 8)
    return page


def suffix(b):
    return "-kid" if b.lower else ""


def page_side(doc, b):
    page = doc.new_page(width=LETTER.width, height=LETTER.height)
    pts = b.side_points()
    header(page, "P1  Side panel  (make 2)", "Draw it straight onto the cardboard with a tape measure and a long straightedge. Every edge is a straight line.")
    scale = fit_scale(b, 560, 200)
    origin = (70, 700)
    pp = draw_side(page, pts, origin, scale)
    draw_recess(page, b, origin, scale)
    dim_line(page, pp["A"], pp["B"], frac(pts["B"][0]), off=-18)
    dim_line(page, pp["H"], pp["A"], frac(pts["H"][1]), off=-16)
    dim_line(page, pp["B"], pp["C"], frac(pts["C"][1]), off=-16)
    dim_line(page, pp["E"], pp["F"], frac(edge_len(pts, "E", "F")), off=-14)
    if b.shelf_h > 1.5:
        y = origin[1] - b.shelf_h * scale
        page.draw_line((origin[0] + 1.9 * b.scale * scale, y), (origin[0] + 11.9 * b.scale * scale, y),
                       color=GREY, width=1.2, dashes="[3 2] 0")
        text(page, origin[0] + 2 * b.scale * scale, y - 3, f"lower shelf, {frac(b.shelf_h)} up", 6, color=GREY)

    x0 = 330
    y = 100
    text(page, x0, y, "MARK THESE POINTS", 11, "hebo"); y += 6
    box(page, pymupdf.Rect(x0, y, LETTER.width - 36, y + 70),
        "Lay the sheet flat. Draw the BACK edge first as a long straight line "
        "(A to B). Every point is measured UP from the floor end along that "
        "line, then OUT square to it (use a set square or a big book).", 8)
    y += 72
    cols = [x0, x0 + 40, x0 + 115, x0 + 190]
    for c, h in zip(cols, ["Pt", "Up from floor", "Out from back", "Is"]):
        text(page, c, y, h, 8, "hebo")
    y += 4
    page.draw_line((x0, y), (LETTER.width - 36, y), color=GREY, width=0.4)
    y += 12
    what = {
        "A": "floor, back corner", "B": "top, back corner", "C": "top, front corner",
        "D": "screen meets deck", "E": "deck, front edge", "F": "lip, bottom",
        "G": "under deck, inner", "H": "floor, front corner",
    }
    for k in SIDE_ORDER:
        h, d = pts[k]
        text(page, cols[0], y, k, 9, "hebo", RED)
        text(page, cols[1], y, f"{frac(h)}  ({h:.2f})", 8)
        text(page, cols[2], y, f"{frac(d)}  ({d:.2f})", 8)
        text(page, cols[3], y, what[k], 7, color=GREY)
        y += 14
    y += 4
    text(page, x0, y + 6, "INSIDE LINES (pencil only - where the recess parts go)", 7, "hebo"); y += 18
    inner = {"S1": "P4a speaker shelf, back", "S2": "P4a speaker shelf, front", "M1": "P4b screen board, bottom",
             "M2": "P4b screen board, top", "R1": "P4c recess floor, back", "R2": "P4c recess floor, front"}
    r = b.recess_points()
    for k, label in inner.items():
        h, d = r[k]
        text(page, cols[0], y, k, 9, "hebo", BLUE)
        text(page, cols[1], y, f"{frac(h)}  ({h:.2f})", 8)
        text(page, cols[2], y, f"{frac(d)}  ({d:.2f})", 8)
        text(page, cols[3], y, label, 7, color=GREY)
        y += 13
    y += 6
    box(page, pymupdf.Rect(x0, y, LETTER.width - 36, y + 280),
        "Join the dots in order A-B-C-D-E-F-G-H-A with straight lines. Draw the "
        "inside lines S1-S2, M1-M2 and R1-R2 on the INSIDE face: the recess parts' "
        "flanges line up on them.\n\n"
        f"Check your work: D-E should be {frac(edge_len(pts, 'D', 'E'))} long and "
        f"C-D {frac(edge_len(pts, 'C', 'D'))}. If not, a point is off.\n\n"
        "Second side: cut the first one out, flip it over, and trace it. "
        "The two sides are mirror images, so tracing the flipped panel "
        "gives you the correct other hand automatically.\n\n"
        "Flutes UP AND DOWN (parallel to A-B): that direction carries the screen.\n\n"
        "Stiffness: glue a second layer to each side (flutes crossed), "
        f"OR glue {frac(max(1.5, 3 * b.scale))} wide ribs of cardboard on the inside, keeping the "
        f"{frac(b.flange)} strip along every edge free for the flanges. See the "
        "screw-length note on page 6 before you pick.\n\n" + b.nest_note, 8)
    return page


def page_cutlist(doc, b):
    page = doc.new_page(width=LETTER.width, height=LETTER.height)
    header(page, "Cut list", f'Cross panels are {frac(b.inner_width)} between the sides + a {frac(b.flange)} fold flange each end = {frac(b.blank_width)} wide blanks.')
    cols = [36, 66, 150, 180, 290, 330]
    y = 100
    for c, h in zip(cols, ["Part", "Name", "Qty", "Cut size (L x W)", "Edge", "Notes"]):
        text(page, c, y, h, 8, "hebo")
    y += 4
    page.draw_line((36, y), (LETTER.width - 36, y), width=0.5)
    y += 12
    pts = b.side_points()
    deck = edge_len(pts, "D", "E")
    top, side, tab = b.beam()
    beam_len = 2 * top + 2 * side + tab
    bw = f"{frac(beam_len)} x {frac(b.blank_width)}"
    rows = [("P1", "Side panel", "2", f"{frac(pts['B'][0])} x {frac(pts['E'][1])}", "-",
             "Shape on page 2. Mirror pair.")]
    for pid, name, edge, ln, note in b.cross_panels():
        rows.append((pid, name, "1", f"{frac(ln)} x {frac(b.blank_width)}", edge, note))
        if pid == "P4":
            for ipid, iname, (a, c), iln, inote, _ in b.inner_panels():
                rows.append((ipid, iname, "1", f"{frac(iln)} x {frac(b.blank_width)}", f"{a}-{c}", inote))
    rows += [
        ("P10", "Screen shelf", "1", bw, "-",
         f"Folds into a {frac(top)} deep x {frac(side)} thick box beam (page 4). Sits under the monitor; set its height on the dry-run."),
        ("P11", "Lower shelf", "1", bw, "-",
         (f"Same box beam, at {frac(b.shelf_h)} up. " if b.shelf_h > 1.5 else "Same box beam, low down. ")
         + "Holds the computer and the ballast."),
    ]
    pid, name, qty, _, edge, note = b.deck_extra
    rows.append((pid, name, qty, f"{frac(deck)} x {frac(b.inner_width)}", edge, note))
    rows.append(("P13", "Corner strips", "8", f'{frac(max(1.5, 2 * b.scale))} x {frac(b.inner_width)}', "-",
                 "Folded into L-angles and glued into inside corners that feel loose."))
    if b.cover:
        rows.append(("P14", "Screen cover", "1", f'{frac(23.21 * b.scale)} x {frac(b.inner_width)}', "-",
                     "Optional. Original is 1/4\" dark-tint acrylic. Clear PET sheet works."))
    for r in rows:
        text(page, cols[0], y, r[0], 8, "hebo", RED)
        text(page, cols[1], y, r[1], 8)
        text(page, cols[2], y, r[2], 8)
        text(page, cols[3], y, r[3], 8)
        text(page, cols[4], y, r[4], 8, color=GREY)
        rc = box(page, pymupdf.Rect(cols[5], y - 8, LETTER.width - 36, y + 40), r[5], 7, color=GREY)
        y += max(18, 48 - rc + 6)
        page.draw_line((36, y - 9), (LETTER.width - 36, y - 9), color=LIGHT, width=0.3)

    y += 6
    box(page, pymupdf.Rect(36, y, LETTER.width - 36, y + 150),
        b.stock_note + "\n\n"
        "Every size is measured on the CAD edge. Cut cross panels 1/4\" long and "
        "trim during the dry fit: cardboard is thicker than the pencil line, so "
        "corners will need a nibble.\n\n"
        f"Flutes: on the cross panels, run them ACROSS the {frac(b.blank_width)} width so the "
        "flange fold goes along the flutes (cleaner fold, stiffer span).", 8)
    return page


def page_flanges(doc, b):
    page = doc.new_page(width=LETTER.width, height=LETTER.height)
    header(page, "Cross panels - fold-flange layout", "The same pattern for P2-P9. Score, fold 90 degrees, screw to the side panels.")
    W, F = b.blank_width, b.flange
    s = 200 / W
    x, y = 60, 110
    Lp = 250 / s  # diagram length, inches
    r = pymupdf.Rect(x, y, x + W * s, y + Lp * s)
    page.draw_rect(r, color=BLACK, width=1, fill=TAN)
    for fx in (F, W - F):
        page.draw_line((x + fx * s, y), (x + fx * s, y + Lp * s), color=RED, width=0.8, dashes="[4 2] 0")
    n = max(2, int(Lp // b.screw_pitch))
    for fx in (F / 2, W - F / 2):
        for i in range(n):
            cy = y + (Lp / n * (i + 0.5)) * s
            page.draw_circle((x + fx * s, cy), 2.5, color=BLUE, width=0.8)
    dim_line(page, (r.x0, r.y0), (r.x1, r.y0), f'{frac(W)} blank', off=-12)
    dim_line(page, (r.x0 + F * s, r.y1), (r.x1 - F * s, r.y1), f'{frac(b.inner_width)} between folds', off=12)
    dim_line(page, (r.x0, r.y1), (r.x0 + F * s, r.y1), frac(F), off=24)
    dim_line(page, (r.x1, r.y0), (r.x1, r.y1), "length = cut list", off=-14)
    box(page, pymupdf.Rect(r.x0 + F * s + 6, r.y0 + 20, r.x1 - F * s - 6, r.y0 + 120),
        "panel face (outside of the cabinet)\n\n"
        "red dashed = score + fold line\n\n"
        f"blue = screw + nut every ~{frac(b.screw_pitch)}, {frac(F / 2)} in from the edge", 7, color=GREY)

    # Section sketch
    sx, sy = 330, 130
    text(page, sx, sy - 12, "SECTION (looking down)", 8, "hebo")
    t = 5
    page.draw_rect(pymupdf.Rect(sx, sy, sx + t, sy + 90), fill=(0.8, 0.7, 0.55), color=BLACK, width=0.5)
    page.draw_rect(pymupdf.Rect(sx + 150, sy, sx + 150 + t, sy + 90), fill=(0.8, 0.7, 0.55), color=BLACK, width=0.5)
    page.draw_rect(pymupdf.Rect(sx + t, sy + 80, sx + 150, sy + 85), fill=(0.9, 0.85, 0.7), color=BLACK, width=0.5)
    page.draw_rect(pymupdf.Rect(sx + t, sy + 55, sx + t + 5, sy + 80), fill=(0.9, 0.85, 0.7), color=BLACK, width=0.5)
    page.draw_rect(pymupdf.Rect(sx + 145, sy + 55, sx + 150, sy + 80), fill=(0.9, 0.85, 0.7), color=BLACK, width=0.5)
    for ex in (sx - 6, sx + 150 + t - 2):
        page.draw_line((ex, sy + 67), (ex + 18, sy + 67), color=BLUE, width=1.5)
    text(page, sx - 8, sy + 105, "side", 7); text(page, sx + 140, sy + 105, "side", 7)
    text(page, sx + 50, sy + 98, "cross panel", 7)
    text(page, sx + 12, sy + 50, "flange", 7)
    text(page, sx + 30, sy + 64, "screw + nut (blue)", 7, color=BLUE)

    # Box-beam shelf: top (with end flanges) / front / bottom / back / glue tab
    top, side, tab = b.beam()
    beam_len = 2 * top + 2 * side + tab
    y2 = r.y1 + 60
    text(page, 60, y2, "P10 / P11  BOX-BEAM SHELF", 11, "hebo")
    y2 += 12
    s2 = 170 / beam_len
    rr = pymupdf.Rect(60, y2, 60 + W * s2, y2 + beam_len * s2)
    page.draw_rect(rr, color=BLACK, width=1, fill=TAN)
    for fx in (F, W - F):
        page.draw_line((rr.x0 + fx * s2, rr.y0), (rr.x0 + fx * s2, rr.y0 + top * s2), color=RED, width=0.8, dashes="[4 2] 0")
    folds = [top, top + side, 2 * top + side, 2 * top + 2 * side]
    for fy in folds:
        page.draw_line((rr.x0 + F * s2, rr.y0 + fy * s2), (rr.x1 - F * s2, rr.y0 + fy * s2), color=RED, width=0.8, dashes="[4 2] 0")
    for fx0 in (0, W - F):
        page.draw_rect(pymupdf.Rect(rr.x0 + fx0 * s2, rr.y0 + top * s2, rr.x0 + (fx0 + F) * s2, rr.y1),
                       color=BLACK, fill=(0.75, 0.75, 0.75), width=0.5)
    edges = [0] + folds + [beam_len]
    for (a, c), lab in zip(zip(edges, edges[1:]), ("top", "front", "bottom", "back", "glue tab")):
        if (c - a) * s2 >= 9:
            text(page, rr.x0 + F * s2 + 6, rr.y0 + (a + c) / 2 * s2 + 3, lab, 7, color=GREY)
        dim_line(page, (rr.x1, rr.y0 + a * s2), (rr.x1, rr.y0 + c * s2), frac(c - a), off=-14)
    box(page, pymupdf.Rect(60, rr.y1 + 14, LETTER.width - 36, rr.y1 + 150),
        f"A {frac(beam_len)} x {frac(W)} blank. Cut away the two grey strips "
        f"({frac(F)} x {frac(beam_len - top)}) so the end flanges only remain on the "
        f"{frac(top)} top. Score every red line. Fold the rest under into a closed "
        f"{frac(top)} x {frac(side)} tube and glue the tab to the underside of the top. "
        "A closed tube is what makes a cardboard shelf stiff enough to hold a "
        "monitor. The end flanges screw to the side panels.\n\n"
        "Screen shelf: set its height so the monitor sits centred behind the "
        "P4b window. Stand the monitor on it with its own stand removed, and strap "
        "the monitor back to the shelf or to P2 so it can't slide forward.", 8)
    return page


def draw_cp(page, cp, ox, oy, s, labels=False, crosshair=False):
    page.draw_rect(pymupdf.Rect(ox, oy, ox + cp.width * s, oy + cp.height * s), color=BLACK, width=0.8)
    for h in cp.holes:
        c = pymupdf.Point(ox + h.x * s, oy + h.y * s)
        rad = h.dia_mm * MM / 2 * s
        col = {"button": BLACK, "stick": RED, "mount": BLUE}.get(h.kind, BLACK)
        page.draw_circle(c, rad, color=col, width=0.8)
        if crosshair:
            k = min(rad * 0.6, 0.15 * s)
            page.draw_line(c - (k, 0), c + (k, 0), color=col, width=0.4)
            page.draw_line(c - (0, k), c + (0, k), color=col, width=0.4)
            if h.kind != "mount":
                lab = f"{h.dia_mm:g}mm"
                w = pymupdf.get_text_length(lab, "helv", 6)
                text(page, c.x - w / 2, c.y + rad + 7, lab, 6, color=GREY)
        if labels and h.label:
            size = max(4, min(6, 0.08 * s))
            w = pymupdf.get_text_length(h.label, "helv", size)
            text(page, c.x - w / 2, c.y - rad - 2, h.label, size, color=GREY)
    if cp.octagon:
        cx, cy, w, hh, ch = cp.octagon
        oct_pts = [(-w / 2 + ch, -hh / 2), (w / 2 - ch, -hh / 2), (w / 2, -hh / 2 + ch), (w / 2, hh / 2 - ch),
                   (w / 2 - ch, hh / 2), (-w / 2 + ch, hh / 2), (-w / 2, hh / 2 - ch), (-w / 2, -hh / 2 + ch)]
        poly = [pymupdf.Point(ox + (cx + a) * s, oy + (cy + c) * s) for a, c in oct_pts]
        page.draw_polyline(poly + [poly[0]], color=BLACK, width=0.8)
    if labels or crosshair:
        for px, py, lab in cp.player_labels:
            size = 0.2 * s
            wl = pymupdf.get_text_length(lab, "hebo", size)
            text(page, ox + px * s - wl / 2, oy + py * s, lab, size, "hebo", LIGHT)


def page_control(doc, b):
    page = doc.new_page(width=LETTER.width, height=LETTER.height)
    cp = b.controls
    header(page, "P5  Control panel layout", f"{cp.source}. Print templates/control-panel-1to1.pdf for the real-size version.")
    deck_len = edge_len(b.side_points(), "D", "E")
    s = min((LETTER.width - 72) / b.inner_width, 300 / deck_len)
    dx, dy = 36 + (LETTER.width - 72 - b.inner_width * s) / 2, 96
    ox = dx + (b.inner_width - cp.width) / 2 * s
    oy = dy + (deck_len - cp.height) / 2 * s
    page.draw_rect(pymupdf.Rect(dx, dy, dx + b.inner_width * s, dy + deck_len * s), color=GREY, width=0.5, dashes="[2 2] 0")
    draw_cp(page, cp, ox, oy, s, labels=True)
    text(page, 36, dy + deck_len * s + 12,
         f"dashed = full deck P5 ({frac(b.inner_width)} x {frac(deck_len)}). {cp.note} Players stand at the bottom edge.", 7, color=GREY)

    y = dy + deck_len * s + 34
    text(page, 36, y, "HOLE SCHEDULE", 11, "hebo"); y += 14
    what = {
        "button": "Action buttons. Use SCREW-IN buttons with a plastic nut - snap-in buttons only grip thin metal/acrylic.",
        "stick": "Joystick shafts. The stick's plate bolts on underneath the deck.",
        "start": "Player Start buttons.",
        "coin": "Coin buttons (Select on most emulators).",
        "aux": "Aux: menu / exit / volume.",
        "mount": "Bolt holes: joystick plates (4 per stick - CHECK against your own stick, spacing varies) and deck corners.",
    }
    counts = Counter((h.kind, h.dia_mm) for h in cp.holes)
    for (kind, dia), q in sorted(counts.items(), key=lambda kv: (-kv[0][1], kv[0][0])):
        text(page, 36, y, str(q), 8, "hebo"); text(page, 60, y, f"{dia:g} mm", 8, "hebo")
        desc = "Screws around the centre window." if (kind, dia) == ("mount", 4.0) else what[kind]
        rc = box(page, pymupdf.Rect(130, y - 8, LETTER.width - 36, y + 30), desc, 8)
        y += max(14, (38 - rc) + 5)
    if cp.octagon:
        text(page, 36, y, "1", 8, "hebo"); text(page, 60, y, "117 x 39 mm", 8, "hebo")
        box(page, pymupdf.Rect(130, y - 8, LETTER.width - 36, y + 30), "Centre octagon window: logo plate, USB port, or a small display.", 8)
        y += 14
    y += 10
    text(page, 36, y, "CUTTING ROUND HOLES", 11, "hebo"); y += 6
    box(page, pymupdf.Rect(36, y, LETTER.width - 36, y + 200),
        "Tape the 1:1 template down. Push an awl (or the screw kit's punch "
        "tool) through every crosshair. Remove the paper, draw each circle "
        "with a compass, then cut with a sharp craft knife in several light "
        "passes. Faster and neater: a hole saw or step drill bit of the right "
        "size, run by a grown-up.\n\n"
        "Cut small first and open up: the button should need a firm push, "
        "and the plastic nut does the rest. Keep the deck thin where the "
        "controls go (about 10 mm max): screw-in buttons and joysticks are "
        "made for thin panels.", 8)
    return page


def page_shopping(doc, b):
    page = doc.new_page(width=LETTER.width, height=LETTER.height)
    header(page, "Shopping list", "Search terms, not specific listings - check sizes and reviews before you buy.")
    y = 100
    for title, items in b.shopping:
        text(page, 36, y, title, 11, "hebo"); y += 14
        for name, note in items:
            page.draw_rect(pymupdf.Rect(36, y - 7, 43, y), color=BLACK, width=0.6)
            h1 = 38 - box(page, pymupdf.Rect(50, y - 8, 300, y + 30), name, 8, "hebo")
            h2 = 38 - box(page, pymupdf.Rect(305, y - 8, LETTER.width - 36, y + 30), note, 8, color=GREY)
            y += max(h1, h2) + 6
        y += 10
    y += 4
    text(page, 36, y, "SCREW LENGTH - READ BEFORE YOU LAMINATE", 10, "hebo", RED); y += 6
    box(page, pymupdf.Rect(36, y, LETTER.width - 36, y + 90),
        "Kids' plastic cardboard screws are short: they're made to join two layers of "
        "ordinary box cardboard. Before cutting anything, screw a scrap of your flange "
        "cardboard to a scrap of your side-panel cardboard, nut on. If it won't reach "
        "through a laminated (2-layer) side, keep the sides single-layer and stiffen them "
        "with glued ribs instead (page 2), or use nylon nuts and bolts at those joints.", 8)
    return page


def page_assembly(doc, b):
    page = doc.new_page(width=LETTER.width, height=LETTER.height)
    header(page, "Assembly steps", "Dry-fit with screws only, glue once everything lines up.")
    deck_step = ("Build the control deck (P5 + P12)",
                 "Glue the doublers under P5. When dry, tape on the 1:1 template and cut all the holes. Mount joysticks and buttons now - much easier on the bench."
                 if b.scale == 1 else
                 "Cut every hole in the Foamex plate from the 1:1 template, lay it on P5 and mark through. Cut P5's holes plus a bigger opening under each stick. Bolt plate + P5 together at the corners, then mount sticks and buttons on the bench.")
    steps = [
        ("Test the screws", "Screw scrap to scrap in the exact layers you'll use (page 6 note)."),
        ("Draw + cut the sides (P1)", "Page 2. Cut one, flip it, trace the second. Laminate or rib them. Label the insides 'LEFT' and 'RIGHT'."),
        ("Cut + score cross panels (P2-P9)", "Page 3 sizes, page 4 flanges. Score with the flutes, fold every flange to 90 deg."),
        deck_step,
        ("Stand the back up (P2)", "Lay one side flat, inside face up. Place P2 along edge A-B, flanges down against the side. Punch + screw."),
        ("Floor + top (P9, P3)", "Add P9 on H-A and P3 on B-C. You now have a rigid 'C'. Add the second side on top and screw all three."),
        ("Stand it up + add the front", "Stand the cabinet up. Screw in P8, P7, P6 and P5 (control deck, pre-wired). Then the recess, painted black first: P4c floor, P4b screen board, P4a speaker shelf. Last, P4 - the front frame - as one flat piece over the lot."),
        ("Shelves (P10, P11)", "Fold the box beams, screw their flanges in: lower shelf at the marked line, screen shelf so the monitor centres in the window."),
        ("Weight + anchor", f"Put {b.ballast} BEFORE the monitor goes in." + (" Strap the top to a wall stud with an anti-tip furniture strap." if b.scale >= 0.75 else "")),
        ("Electronics", "Computer on the lower shelf, encoder under the deck, monitor on its shelf. Run cables out through the service door."),
        ("Glue + finish", "Once it all works, back out one screw at a time, run glue into the joint, re-screw. Tape the edges, then paint or wrap it. Put Supercade art on the sides!"),
    ]
    y = 100
    for i, (t, d) in enumerate(steps, 1):
        page.draw_circle((46, y - 3), 9, color=BLACK, fill=BLACK)
        lab = str(i)
        w = pymupdf.get_text_length(lab, "hebo", 9)
        text(page, 46 - w / 2, y, lab, 9, "hebo", (1, 1, 1))
        text(page, 64, y, t, 10, "hebo")
        rc = box(page, pymupdf.Rect(64, y + 4, LETTER.width - 36, y + 50), d, 8, color=(0.2, 0.2, 0.2))
        y += 4 + (46 - rc) + 16
    y += 6
    safety = ("SAFETY. This is a tall, narrow box with a screen near the top: it WILL tip if "
              "it isn't weighted and strapped. Keep it strapped to the wall whenever kids are around "
              "it. Box-cutter work is for adults. Keep the power strip off the floor and don't block "
              "the monitor's vents." if b.scale >= 0.75 else
              "SAFETY. Small, but still top-heavy with the monitor in: weight the lower shelf, and "
              "stand it against a wall. Knife and Foamex cutting is for adults; kids use the kit's "
              "safe saw. Don't block the monitor's or computer's vents.")
    page.draw_rect(pymupdf.Rect(36, y, LETTER.width - 36, y + 62), color=RED, width=1)
    box(page, pymupdf.Rect(46, y + 8, LETTER.width - 46, y + 58), safety, 8, "hebo", RED)
    return page


def build_plans(b):
    doc = pymupdf.open()
    for fn in (page_overview, page_side, page_cutlist, page_flanges, page_control, page_shopping, page_assembly):
        fn(doc, b)
    for i, page in enumerate(doc, 1):
        footer(page, i, len(doc), b.title)
    doc.set_metadata({"title": f"Supercade cardboard plans - {b.title}", "author": "Super Labs"})
    out = os.path.join(HERE, b.key, b.filename)
    doc.save(out, garbage=4, deflate=True)
    return out


# ---------------------------------------------------------------------------
# 1:1 tiled templates
# ---------------------------------------------------------------------------

MARGIN = 0.4    # in, unprintable edge
OVERLAP = 0.5   # in, shared strip between neighbouring tiles


def tiled(out, title, width_in, height_in, draw, landscape=False):
    """Tile a width_in x height_in drawing at 1:1 across letter pages.

    `draw(page, ox, oy)` draws the artwork with its (0, 0) at page point
    (ox, oy), 72 pt per inch. Each tile gets a global 1" grid so neighbouring
    pages line up on the grid lines. A drawing that fits on one page is
    printed on one page, without a map.
    """
    pw, ph = (LETTER.height, LETTER.width) if landscape else (LETTER.width, LETTER.height)
    aw, ah = pw / PT - 2 * MARGIN, ph / PT - 2 * MARGIN - 0.3  # 0.3" for the label strip
    sx, sy = aw - OVERLAP, ah - OVERLAP
    single = width_in <= aw and height_in <= ah
    cols = 1 if single else max(1, math.ceil((width_in - OVERLAP) / sx))
    rows = 1 if single else max(1, math.ceil((height_in - OVERLAP) / sy))
    doc = pymupdf.open()

    if not single:
        mp = doc.new_page(width=pw, height=ph)
        text(mp, 36, 50, title, 16, "hebo")
        text(mp, 36, 68, f"1:1 template, {cols} x {rows} = {cols * rows} pages. Print at 100% / 'Actual size' - NOT 'fit to page'.", 9)
        scale = min((pw - 72) / width_in, (ph - 260) / height_in)
        mx, my = 36, 90
        mpr = pymupdf.Rect(mx, my, mx + width_in * scale, my + height_in * scale)
        tmp = pymupdf.open()
        tp = tmp.new_page(width=width_in * PT, height=height_in * PT)
        draw(tp, 0, 0)
        mp.show_pdf_page(mpr, tmp, 0)
        for r in range(rows):
            for c in range(cols):
                tr = pymupdf.Rect(mx + c * sx * scale, my + r * sy * scale,
                                  mx + min(c * sx + aw, width_in) * scale, my + min(r * sy + ah, height_in) * scale)
                mp.draw_rect(tr, color=BLUE, width=0.5)
                text(mp, tr.x0 + 3, tr.y0 + 10, f"{chr(65 + r)}{c + 1}", 8, "hebo", BLUE)
        y = mpr.y1 + 24
        box(mp, pymupdf.Rect(36, y, pw - 36, y + 150),
            "1. Print every page at 100% scale. Measure the 2\" check bar on any page - if it isn't "
            "exactly 2\", fix your printer's scaling and print again.\n"
            "2. Lay the pages out by their labels (A1 top-left). Neighbouring pages overlap by 1/2\": "
            "trim the RIGHT and BOTTOM margins of each page along the dashed trim line, lay it over "
            "the next page so the grey 1\" grid lines match, and tape.\n"
            "3. Tape the finished template to the material, then transfer: prick every corner / "
            "crosshair with an awl, or cut straight through paper and cardboard together.", 8)

    for r in range(rows):
        for c in range(cols):
            page = doc.new_page(width=pw, height=ph)
            x0_in, y0_in = c * sx, r * sy
            ox = MARGIN * PT - x0_in * PT
            oy = MARGIN * PT - y0_in * PT
            area = pymupdf.Rect(MARGIN * PT, MARGIN * PT, MARGIN * PT + aw * PT, MARGIN * PT + ah * PT)
            gx = math.ceil(x0_in)
            while gx <= min(x0_in + aw, width_in):
                X = ox + gx * PT
                page.draw_line((X, area.y0), (X, min(area.y1, oy + height_in * PT)), color=(0.88, 0.88, 0.88), width=0.3)
                gx += 1
            gy = math.ceil(y0_in)
            while gy <= min(y0_in + ah, height_in):
                Y = oy + gy * PT
                page.draw_line((area.x0, Y), (min(area.x1, ox + width_in * PT), Y), color=(0.88, 0.88, 0.88), width=0.3)
                gy += 1
            draw(page, ox, oy)
            white = (1, 1, 1)
            page.draw_rect(pymupdf.Rect(0, 0, pw, area.y0), color=None, fill=white)
            page.draw_rect(pymupdf.Rect(0, area.y1, pw, ph), color=None, fill=white)
            page.draw_rect(pymupdf.Rect(0, 0, area.x0, ph), color=None, fill=white)
            page.draw_rect(pymupdf.Rect(area.x1, 0, pw, ph), color=None, fill=white)
            if not single:
                page.draw_rect(area, color=GREY, width=0.3)
            if c < cols - 1:
                X = area.x1 - OVERLAP * PT
                page.draw_line((X, area.y0), (X, area.y1), color=RED, width=0.5, dashes="[4 3] 0")
                text(page, X + 2, area.y0 + 10, "trim", 6, color=RED)
            if r < rows - 1:
                Y = area.y1 - OVERLAP * PT
                page.draw_line((area.x0, Y), (area.x1, Y), color=RED, width=0.5, dashes="[4 3] 0")
                text(page, area.x0 + 2, Y - 2, "trim", 6, color=RED)
            ly = area.y1 + 13
            if single:
                text(page, area.x0, ly, f"{title}  -  1:1, print at 100% / 'Actual size'", 8, color=GREY)
            else:
                text(page, area.x0, ly, f"{chr(65 + r)}{c + 1}", 14, "hebo", BLUE)
                text(page, area.x0 + 34, ly - 2, f"{title}  -  row {chr(65 + r)}, column {c + 1} of {cols}", 7, color=GREY)
                text(page, area.x0 + 34, ly + 7, "right: " + (f"{chr(65 + r)}{c + 2}" if c < cols - 1 else "-") +
                     "   below: " + (f"{chr(66 + r)}{c + 1}" if r < rows - 1 else "-"), 7, color=GREY)
            sq = pymupdf.Rect(area.x1 - 2 * PT, area.y1 + 4, area.x1, area.y1 + 4 + 0.2 * PT)
            page.draw_line((sq.x0, sq.y0 + 4), (sq.x1, sq.y0 + 4), color=BLACK, width=0.8)
            page.draw_line((sq.x0, sq.y0), (sq.x0, sq.y0 + 8), color=BLACK, width=0.8)
            page.draw_line((sq.x1, sq.y0), (sq.x1, sq.y0 + 8), color=BLACK, width=0.8)
            text(page, sq.x0 + 0.6 * PT, sq.y0 + 16, 'check: 2" exactly', 6)
    doc.set_metadata({"title": title, "author": "Super Labs"})
    doc.save(out, garbage=4, deflate=True)
    return out, len(doc)


def cp_drawer(cp):
    def draw(page, ox, oy):
        draw_cp(page, cp, ox, oy, PT, labels=True, crosshair=True)
    return draw


def speaker_drawer(b):
    w, h = SPEAKER_W * b.scale, SPEAKER_H * b.scale

    def draw(page, ox, oy):
        for i in range(2):
            cx, cy = ox + (w / 2 + 0.5) * PT, oy + (h / 2 + 0.3 + i * (h + 0.5)) * PT
            r = pymupdf.Rect(cx - w / 2 * PT, cy - h / 2 * PT, cx + w / 2 * PT, cy + h / 2 * PT)
            page.draw_oval(r, color=BLACK, width=1)
            page.draw_line((cx - 8, cy), (cx + 8, cy), color=GREY, width=0.5)
            page.draw_line((cx, cy - 8), (cx, cy + 8), color=GREY, width=0.5)
            lab = f"speaker {frac(w)} x {frac(h)}"
            text(page, cx - pymupdf.get_text_length(lab, "helv", 8) / 2, cy + 20, lab, 8, color=GREY)
        text(page, ox + 0.2 * PT, oy + (2 * h + 1.2) * PT, "Cut 2 in P4a, the speaker shelf, so they point down at the players. Skip if your monitor has speakers.", 7, color=GREY)
    return draw, w + 1.0, 2 * h + 1.5


def side_drawer(b):
    pts = b.side_points()
    H = pts["B"][0]
    big = 14 * b.scale + 4

    def draw(page, ox, oy):
        P = {k: pymupdf.Point(ox + d * PT, oy + (H - h) * PT) for k, (h, d) in pts.items()}
        poly = [P[k] for k in SIDE_ORDER] + [P["A"]]
        page.draw_polyline(poly, color=BLACK, width=1.4, closePath=True)
        for k in SIDE_ORDER:
            page.draw_circle(P[k], 4, color=RED, width=0.8)
            text(page, P[k].x + 6, P[k].y - 6, k, big, "hebo", RED)
        if b.shelf_h > 1.5:
            y = oy + (H - b.shelf_h) * PT
            page.draw_line((ox + 1.9 * b.scale * PT, y), (ox + 11.9 * b.scale * PT, y), color=GREY, width=1, dashes="[6 4] 0")
            text(page, ox + 2 * b.scale * PT, y - 4, "lower shelf (top face)", 9, color=GREY)
        r = b.recess_points()
        Q = lambda k: pymupdf.Point(ox + r[k][1] * PT, oy + (H - r[k][0]) * PT)
        for pid, _, (ka, kc), _, _, _ in b.inner_panels():
            page.draw_line(Q(ka), Q(kc), color=BLUE, width=1.2, dashes="[8 4] 0")
            for k in (ka, kc):
                page.draw_circle(Q(k), 3, color=BLUE, width=0.8)
                text(page, Q(k).x + 5, Q(k).y + 12, k, 11, "hebo", BLUE)
            m = (Q(ka) + Q(kc)) / 2
            text(page, m.x + 6, m.y - 6, f"{pid} line (inside face)", 9, color=BLUE)
        text(page, ox + 0.8 * PT, oy + 2 * PT, "TOP", big, "hebo", GREY)
        text(page, ox + 0.8 * PT, oy + (H - 1.2) * PT, "FLOOR", big, "hebo", GREY)
        text(page, ox + 0.5 * PT, oy + H / 2 * PT, "BACK edge", 12, "hebo", GREY, rotate=90)
        text(page, ox + 2 * PT, oy + (H * 0.8) * PT, "flutes run up and down", 10, color=GREY)
    return draw, pts["E"][1], H


# ---------------------------------------------------------------------------
# Standalone control box (try the controls before building the cabinet)
# ---------------------------------------------------------------------------

BOX_BACK_H, BOX_FRONT_H = 4.0, 3.0   # wedge: ~7.7 deg, close to the cabinet's 7
BOX_SKIRT = 1.0                      # lid skirt that folds down over the tray
BOX_TAB = 0.9                        # corner tabs on the tray's front/back walls
BOX_CLEAR = 0.125                    # tray is this much smaller per side than the lid


def box_dims(b):
    lw, ld = b.controls.width, b.controls.height   # lid top = the deck plate
    tw, td = lw - 2 * BOX_CLEAR, ld - 2 * BOX_CLEAR  # tray outside
    return lw, ld, tw, td


def draw_poly(page, pts, ox, oy, s, fill=TAN, color=BLACK, width=1.0, dashes=None):
    P = [pymupdf.Point(ox + x * s, oy + y * s) for x, y in pts]
    page.draw_polyline(P + [P[0]], color=color, fill=fill, width=width, dashes=dashes, closePath=True)


def fold(page, a, c, ox, oy, s):
    page.draw_line((ox + a[0] * s, oy + a[1] * s), (ox + c[0] * s, oy + c[1] * s), color=RED, width=0.8, dashes="[4 2] 0")


def box_page_overview(doc, b):
    page = doc.new_page(width=LETTER.width, height=LETTER.height)
    lw, ld, tw, td = box_dims(b)
    header(page, "SUPERCADE control box", "Try the controls first: a tabletop box you plug into a laptop or TV. The deck plate moves into the cabinet later.")

    # side section
    s = 28
    ox, oy = 70, 295
    text(page, ox, 108, "SIDE SECTION (players on the right)", 9, "hebo")
    tray = [(0, 0), (td, 0), (td, -BOX_FRONT_H), (0, -BOX_BACK_H)]
    draw_poly(page, tray, ox, oy, s)
    k = BOX_FRONT_H - BOX_BACK_H
    lid_top = [(0 - 0.12, -BOX_BACK_H - 0.12), (td + 0.12, -BOX_FRONT_H - 0.12 - 0 * k)]
    page.draw_line((ox + lid_top[0][0] * s, oy + lid_top[0][1] * s), (ox + lid_top[1][0] * s, oy + lid_top[1][1] * s), color=BLUE, width=4)
    for x, h in ((-0.12, BOX_BACK_H), (td + 0.12, BOX_FRONT_H)):
        page.draw_line((ox + x * s, oy - (h + 0.12) * s), (ox + x * s, oy - (h + 0.12 - BOX_SKIRT) * s), color=BLUE, width=1.5)
    # joystick + buttons (schematic)
    stick_y = min(hh.y for hh in b.controls.holes if hh.kind == "stick")
    xs = stick_y / ld * td
    top_at = lambda x: BOX_BACK_H + (BOX_FRONT_H - BOX_BACK_H) * x / td
    ht = top_at(xs)
    page.draw_rect(pymupdf.Rect(ox + (xs - 0.9) * s, oy - (ht - 0.2) * s, ox + (xs + 0.9) * s, oy - (ht - 2.4) * s), color=RED, width=0.8, fill=(1, 0.93, 0.93))
    page.draw_line((ox + xs * s, oy - ht * s), (ox + xs * s, oy - (ht + 1.2) * s), color=RED, width=2)
    page.draw_circle((ox + xs * s, oy - (ht + 1.35) * s), 0.35 * s, color=RED, fill=(1, 0.6, 0.6))
    dim_line(page, (ox, oy), (ox, oy - BOX_BACK_H * s), frac(BOX_BACK_H), off=14)
    dim_line(page, (ox + td * s, oy), (ox + td * s, oy - BOX_FRONT_H * s), frac(BOX_FRONT_H), off=-14)
    dim_line(page, (ox, oy), (ox + td * s, oy), frac(td), off=-14)
    text(page, ox, oy + 30, "tan = tray (B1)   blue = lid (B2) + Foamex plate (P12)   red = joystick", 7, color=GREY)

    x0 = 360
    y = 108
    text(page, x0, y, "PARTS", 10, "hebo"); y += 14
    parts = [
        ("B1", "Tray", f"{frac(tw + 2 * BOX_BACK_H)} x {frac(td + BOX_BACK_H + BOX_FRONT_H)} cardboard, one piece (page 2)"),
        ("B2", "Lid", f"{frac(lw + 2 * BOX_SKIRT)} x {frac(ld + 2 * BOX_SKIRT)} cardboard, one piece (page 3)"),
        ("P12", "Deck plate", f"{frac(lw)} x {frac(ld)} 5 mm Foamex - the same plate the cabinet uses"),
    ]
    for pid, name, what in parts:
        text(page, x0, y, pid, 8, "hebo", RED); text(page, x0 + 28, y, name, 8, "hebo")
        rc = box(page, pymupdf.Rect(x0 + 28, y + 2, LETTER.width - 36, y + 30), what, 7, color=GREY)
        y += 30 - rc + 10
    y += 8
    text(page, x0, y, "ALSO NEED", 10, "hebo"); y += 6
    box(page, pymupdf.Rect(x0, y, LETTER.width - 36, y + 120),
        "- The 2-player zero-delay kit (2 sticks, 16 x 24 mm buttons, 2 encoders)\n"
        "- 4 x M4/M5 bolts + nuts for the plate corners, 8 for the sticks\n"
        "- ~10 kit screws + nuts, glue, tape\n"
        "- 1 kg of weight inside (bag of rice) + a non-slip mat underneath, "
        "so the box doesn't walk when someone yanks a stick\n"
        "- A laptop, or a TV + Raspberry Pi", 8)

    y = 372
    text(page, 36, y, "WHY THIS SHAPE", 10, "hebo"); y += 6
    box(page, pymupdf.Rect(36, y, LETTER.width - 36, y + 90),
        "It's a shoebox with a sloped top. The lid is the control deck, and its skirts fold DOWN over "
        "the outside of the tray, so nothing folds inward into the space the joysticks and buttons "
        "need. The slope (back 4\", front 3\") gives the same ~7 degree tilt as the cabinet's deck. The "
        "Foamex plate is exactly the cabinet's P12, and the template is the same one: if the kids "
        "love it, unbolt the plate with everything still wired and drop it into the cabinet.", 8)
    y += 80
    text(page, 36, y, "CHECK FIRST", 10, "hebo", RED); y += 6
    box(page, pymupdf.Rect(36, y, LETTER.width - 36, y + 90),
        "Measure your joystick from the underside of its mounting plate to the bottom of its "
        "microswitches / connector. The box leaves about 2 3/4\" at the stick. If yours needs more, add "
        "the same amount to BOTH wall heights (and to the side walls) before cutting.", 8)
    return page


def box_page_tray(doc, b):
    page = doc.new_page(width=LETTER.width, height=LETTER.height)
    lw, ld, tw, td = box_dims(b)
    bh, fh, T = BOX_BACK_H, BOX_FRONT_H, BOX_TAB
    header(page, "B1  Tray - one piece", "Cut on the black lines, score + fold UP on the red dashed lines. Measurements in inches.")
    W = tw + 2 * bh
    H = td + bh + fh
    s = min((LETTER.width - 110) / W, 330 / H)
    ox = 55 + bh * s
    oy = 120 + bh * s
    # bottom, walls, side walls (trapezoids), corner tabs
    draw_poly(page, [(0, 0), (tw, 0), (tw, td), (0, td)], ox, oy, s)
    draw_poly(page, [(0, -bh), (tw, -bh), (tw, 0), (0, 0)], ox, oy, s)
    draw_poly(page, [(0, td), (tw, td), (tw, td + fh), (0, td + fh)], ox, oy, s)
    draw_poly(page, [(0, 0), (-bh, 0), (-fh, td), (0, td)], ox, oy, s)
    draw_poly(page, [(tw, 0), (tw + bh, 0), (tw + fh, td), (tw, td)], ox, oy, s)
    c = 0.25
    for x0, sgn in ((0, -1), (tw, 1)):
        draw_poly(page, [(x0, -bh + c), (x0 + sgn * T, -bh + c + T * 0.4), (x0 + sgn * T, -c - T * 0.2), (x0, -c)], ox, oy, s, fill=(0.9, 0.86, 0.76))
        draw_poly(page, [(x0, td + c), (x0 + sgn * T, td + c + T * 0.2), (x0 + sgn * T, td + fh - c - T * 0.4), (x0, td + fh - c)], ox, oy, s, fill=(0.9, 0.86, 0.76))
    for a, cc in (((0, 0), (tw, 0)), ((0, td), (tw, td)), ((0, 0), (0, td)), ((tw, 0), (tw, td)),
                  ((0, -bh + c), (0, -c)), ((tw, -bh + c), (tw, -c)), ((0, td + c), (0, td + fh - c)), ((tw, td + c), (tw, td + fh - c))):
        fold(page, a, cc, ox, oy, s)
    # cable slot in the back wall
    sw, sh = 1.5, 1.0
    r = pymupdf.Rect(ox + (tw / 2 - sw / 2) * s, oy - (0.75 + sh) * s, ox + (tw / 2 + sw / 2) * s, oy - 0.75 * s)
    page.draw_rect(r, color=BLACK, width=0.8, fill=(1, 1, 1), radius=0.3)
    text(page, r.x0, r.y0 - 3, f"USB slot {frac(sw)} x {frac(sh)}, {frac(0.75)} up", 6, color=GREY)
    # labels
    for (x, y), lab in (((tw / 2, td / 2), "BOTTOM"), ((tw / 2, -bh / 2 - 0.9), "BACK WALL"), ((tw / 2, td + fh / 2), "FRONT WALL (players)"),
                        ((-bh / 2 - 0.2, td / 2), "SIDE"), ((tw + bh / 2 - 0.3, td / 2), "SIDE")):
        w = pymupdf.get_text_length(lab, "hebo", 8)
        text(page, ox + x * s - w / 2, oy + y * s + 3, lab, 8, "hebo", GREY)
    # dimensions
    dim_line(page, (ox, oy - bh * s), (ox + tw * s, oy - bh * s), frac(tw), off=-12)
    dim_line(page, (ox + tw * s, oy - bh * s), (ox + tw * s, oy), frac(bh), off=-(bh * s + 14))
    dim_line(page, (ox + tw * s, oy), (ox + tw * s, oy + td * s), frac(td), off=-(bh * s + 14))
    dim_line(page, (ox + tw * s, oy + td * s), (ox + tw * s, oy + (td + fh) * s), frac(fh), off=-(bh * s + 14))
    dim_line(page, (ox - bh * s, oy), (ox, oy), frac(bh), off=-10)
    dim_line(page, (ox - fh * s, oy + td * s), (ox, oy + td * s), frac(fh), off=12)
    y = oy + (td + fh) * s + 30
    box(page, pymupdf.Rect(36, y, LETTER.width - 36, y + 220),
        f"Blank: {frac(W)} x {frac(H)}. Draw the {frac(tw)} x {frac(td)} BOTTOM first, then add the walls around it.\n\n"
        f"SIDE walls are sloped: {frac(bh)} tall at the back edge, {frac(fh)} at the front. Draw them as "
        "a line out square from each corner of the bottom, then join the ends.\n\n"
        f"Corner TABS ({frac(T)} wide, shaded) are on the front and back walls. Trim their outer corners at a slant "
        "so they clear the folds. They fold round INSIDE the side walls: glue them, then put one kit screw + nut "
        "through each tab and side wall.\n\n"
        "The USB slot takes both encoder cables out of the back. Cut it before folding.\n\n"
        "Fold order: back + front walls up, tabs in, side walls up over the tabs.", 8)
    return page


def box_page_lid(doc, b):
    page = doc.new_page(width=LETTER.width, height=LETTER.height)
    lw, ld, tw, td = box_dims(b)
    S = BOX_SKIRT
    header(page, "B2  Lid = control deck", "Cut on black, score + fold DOWN on red. The Foamex plate (P12) bolts on top, lined up with the edges.")
    W, H = lw + 2 * S, ld + 2 * S
    s = (LETTER.width - 110) / W
    ox, oy = 55 + S * s, 110 + S * s
    draw_poly(page, [(0, 0), (lw, 0), (lw, ld), (0, ld)], ox, oy, s)
    for pts in ([(0, -S), (lw, -S), (lw, 0), (0, 0)], [(0, ld), (lw, ld), (lw, ld + S), (0, ld + S)],
                [(-S, 0), (0, 0), (0, ld), (-S, ld)], [(lw, 0), (lw + S, 0), (lw + S, ld), (lw, ld)]):
        draw_poly(page, pts, ox, oy, s, fill=(0.9, 0.86, 0.76))
    for a, c in (((0, 0), (lw, 0)), ((0, ld), (lw, ld)), ((0, 0), (0, ld)), ((lw, 0), (lw, ld))):
        fold(page, a, c, ox, oy, s)
    # controls, faint, so you can see where the relief cut-outs go
    for hh in b.controls.holes:
        page.draw_circle((ox + hh.x * s, oy + hh.y * s), hh.dia_mm * MM / 2 * s, color=LIGHT, width=0.6)
    for hh in b.controls.holes:
        if hh.kind == "stick":
            rw, rh = 76 * MM, 104 * MM
            page.draw_rect(pymupdf.Rect(ox + (hh.x - rw / 2) * s, oy + (hh.y - rh / 2) * s, ox + (hh.x + rw / 2) * s, oy + (hh.y + rh / 2) * s),
                           color=RED, width=0.9, dashes="[2 2] 0")
    # screw points on the skirts
    for x in (lw * 0.25, lw * 0.75):
        for y in (-S / 2, ld + S / 2):
            page.draw_circle((ox + x * s, oy + y * s), 3, color=BLUE, width=0.9)
    for x in (-S / 2, lw + S / 2):
        page.draw_circle((ox + x * s, oy + ld / 2 * s), 3, color=BLUE, width=0.9)
    dim_line(page, (ox, oy - S * s), (ox + lw * s, oy - S * s), frac(lw), off=-12)
    dim_line(page, (ox + (lw + S) * s, oy), (ox + (lw + S) * s, oy + ld * s), frac(ld), off=-14)
    dim_line(page, (ox + lw * s, oy + (ld + S) * s), (ox + (lw + S) * s, oy + (ld + S) * s), frac(S), off=12)
    text(page, ox + 6, oy + ld * s + S * s * 0.6, "FRONT skirt (players' side)", 7, "hebo", GREY)
    text(page, ox + 6, oy - S * s * 0.4, "BACK skirt", 7, "hebo", GREY)
    y = oy + (ld + S) * s + 34
    box(page, pymupdf.Rect(36, y, LETTER.width - 36, y + 300),
        f"Blank: {frac(W)} x {frac(H)}. The top is exactly the deck plate ({frac(lw)} x {frac(ld)}); "
        f"the {frac(S)} skirts fold down and the four corner squares are cut away.\n\n"
        "Holes: tape the 1:1 control-panel template (templates/control-panel-1to1.pdf) onto the "
        "FOAMEX plate and cut every hole there. Then lay the plate on the lid, mark through, and cut the lid's "
        "button and bolt holes.\n\n"
        "Red dashed boxes: cut these right out of the lid, under each joystick. They're sized for a typical "
        "stick plate (about 3\" x 4\"); make them just bigger than YOUR plate. The stick bolts to the Foamex "
        "alone, which keeps the panel thin enough for the shaft.\n\n"
        "Blue circles: one kit screw + nut through skirt and tray wall at each (6 total). Keep the lid "
        "unglued so you can open it to fix wiring.\n\n"
        "Bolt the plate down through the 4 corner holes (plate + lid only).", 8)
    return page


def box_page_steps(doc, b):
    page = doc.new_page(width=LETTER.width, height=LETTER.height)
    header(page, "Build + wire + play", "About an afternoon. Kids can do the folding, screwing and button-pressing; adults do the knife work.")
    steps = [
        ("Cut the plate first", "Tape the 1:1 template to the 5 mm Foamex, prick every crosshair, cut the holes (hole saw / step bit, or compass + knife). This is the part that has to be neat."),
        ("Cut + fold the tray (B1)", "Page 2. Cut the USB slot, fold the walls up, glue + screw the corner tabs."),
        ("Cut the lid (B2)", "Page 3. Mark the holes through the plate, cut them and the two joystick openings, fold the skirts."),
        ("Mount the controls on the bench", "Bolt the plate onto the lid. Screw the buttons in from the top (nut underneath), bolt each stick on from below."),
        ("Wire it", "Each encoder board: joystick harness into the stick, one 2-wire lead per button. Player 1 on one board, Player 2 on the other. Stick the boards to the tray bottom with double-sided tape, and run both USB cables out of the slot."),
        ("Close it up", "Put the 1 kg weight in, drop the lid on, 6 screws through the skirts. Non-slip mat underneath."),
        ("Test", "Plug into a laptop: on Windows, 'Set up USB game controllers'; on Mac/Linux, any online gamepad tester. Every button should light up once. Swap any lead that shows up wrong."),
        ("Play", "Easiest start: a Raspberry Pi with an arcade front-end (e.g. RetroPie / Batocera) on the TV. It sees the box as two gamepads. Pick a handful of 2-player games you're happy with."),
    ]
    y = 100
    for i, (t, d) in enumerate(steps, 1):
        page.draw_circle((46, y - 3), 9, color=BLACK, fill=BLACK)
        lab = str(i)
        w = pymupdf.get_text_length(lab, "hebo", 9)
        text(page, 46 - w / 2, y, lab, 9, "hebo", (1, 1, 1))
        text(page, 64, y, t, 10, "hebo")
        rc = box(page, pymupdf.Rect(64, y + 4, LETTER.width - 36, y + 50), d, 8, color=(0.2, 0.2, 0.2))
        y += 4 + (46 - rc) + 16
    y += 6
    text(page, 36, y, "IS IT WORTH THE CABINET? A FEW WEEKS OF...", 10, "hebo"); y += 6
    box(page, pymupdf.Rect(36, y, LETTER.width - 36, y + 120),
        "- Do they ask for it, or only play when it's offered?\n"
        "- Do they play together (good sign) or fight over it (fixable: take turns by credits)?\n"
        "- Does it fit into the day without pushing out sleep, outside play or homework?\n\n"
        "Credits trick: the COIN buttons are a built-in limit - e.g. '5 credits after homework'.\n"
        "If it's a hit: unbolt the plate with everything still wired and move it to the cabinet's control deck.", 8)
    return page


def build_control_box(b):
    doc = pymupdf.open()
    for fn in (box_page_overview, box_page_tray, box_page_lid, box_page_steps):
        fn(doc, b)
    for i, page in enumerate(doc, 1):
        footer(page, i, len(doc), "control box")
    doc.set_metadata({"title": "Supercade control box", "author": "Super Labs"})
    out = os.path.join(HERE, b.key, "SuperCade-Control-Box.pdf")
    doc.save(out, garbage=4, deflate=True)
    return out


# ---------------------------------------------------------------------------
# 3D viewer data (viewer/data.js) - the same numbers the PDFs use
# ---------------------------------------------------------------------------

VIEWER_BUILDS = (
    # (id, label, build index in BUILDS, screen visible area in inches)
    ("full", "Full size", 1, (23.5, 13.25)),
    ("kid", "Kid height", 2, (23.5, 13.25)),
    ("half", "Half scale", 0, (11.625, 6.5)),
)


def viewer_panels(b, screen):
    """Every flat cross panel as a face line a->b (h, d) plus the normal of its visible face.

    The panel's thickness sits behind the visible face. Holes are measured across
    the width (x from the left side) and along the panel from a (s).
    """
    R = lambda v: [round(v[0], 3), round(v[1], 3)]
    pts, rec = b.side_points(), b.recess_points()
    W = b.inner_width
    out = []
    for pid, name, edge, ln, note in b.cross_panels():
        a, c = edge.split("-")
        (h1, d1), (h2, d2) = pts[a], pts[c]
        dh, dd = h2 - h1, d2 - d1
        item = {"id": pid, "name": name, "a": R(pts[a]), "b": R(pts[c]), "length": round(ln, 3),
                "out": [round(dd / ln, 4), round(-dh / ln, 4)], "note": note}
        if pid == "P4":
            s0, s1, border = b.frame_opening()
            item["holes"] = [{"rect": [round(border, 3), round(s0, 3), round(W - border, 3), round(s1, 3)]}]
        if pid == "P9":
            item["explode"] = [0, 1]          # slide the floor out the front, not through the mat
        out.append(item)
    sw, sh = screen
    for pid, name, (a, c), ln, note, normal in b.inner_panels():
        item = {"id": pid, "name": name, "a": R(rec[a]), "b": R(rec[c]), "length": round(ln, 3),
                "out": list(normal), "note": note, "recess": True, "explode": [0.35, 1] if pid == "P4a" else [0, 1]}
        if pid == "P4b":
            item["holes"] = [{"rect": [round((W - sw) / 2, 3), round((ln - sh) / 2, 3), round((W + sw) / 2, 3), round((ln + sh) / 2, 3)]}]
            item["screen"] = True
        if pid == "P4a":
            ow, oh = SPEAKER_W * b.scale, SPEAKER_H * b.scale
            item["holes"] = [{"oval": [round(x, 3), round(ln / 2, 3), round(ow, 3), round(oh, 3)]}
                             for x in (W * 0.22, W * 0.78)]
        out.append(item)
    return out


def export_viewer_data():
    out = {"builds": []}
    for vid, label, idx, screen in VIEWER_BUILDS:
        b = BUILDS[idx]
        pts = b.side_points()
        cp = b.controls
        top, side, _ = b.beam()
        out["builds"].append({
            "id": vid,
            "label": label,
            "title": b.title,
            "scale": b.scale,
            "innerWidth": round(b.inner_width, 3),
            "flange": b.flange,
            "side": {k: [round(h, 3), round(d, 3)] for k, (h, d) in pts.items()},
            "order": SIDE_ORDER,
            "shelfH": round(b.shelf_h, 3),
            "beam": [top, side],
            "panels": viewer_panels(b, screen),
            "screen": list(screen),
            "controls": {
                "width": round(cp.width, 3), "height": round(cp.height, 3),
                "holes": [[round(h.x, 3), round(h.y, 3), h.dia_mm, h.kind] for h in cp.holes],
                "octagon": [round(v, 3) for v in cp.octagon] if cp.octagon else None,
            },
        })
    # People for scale: CC0 bodies from Blender Studio's Human Base Meshes, packed
    # into a script so the viewer also works when opened straight from disk.
    people = {}
    for pid in ("adult", "kid8", "kid5"):
        glb = os.path.join(HERE, "viewer", "people", pid + ".glb")
        if os.path.exists(glb):
            with open(glb, "rb") as f:
                people[pid] = base64.b64encode(f.read()).decode("ascii")
    with open(os.path.join(HERE, "viewer", "people.js"), "w") as f:
        f.write("// Generated by generate.py from viewer/people/*.glb (CC0, Blender Studio Human Base Meshes).\n")
        f.write("window.SUPERCADE_PEOPLE = " + json.dumps(people) + ";\n")
    path = os.path.join(HERE, "viewer", "data.js")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("// Generated by generate.py - do not edit by hand.\n")
        f.write("window.SUPERCADE_DATA = " + json.dumps(out, separators=(",", ":")) + ";\n")
    return path


def main():
    made = []
    for b in BUILDS:
        tdir = os.path.join(HERE, b.key, "templates")
        os.makedirs(tdir, exist_ok=True)
        made.append(build_plans(b))
        if b.control_box:
            made.append(build_control_box(b))
        made.append(tiled(os.path.join(tdir, "control-panel-1to1.pdf"), "SUPERCADE control panel",
                          b.controls.width, b.controls.height, cp_drawer(b.controls), landscape=True))
        draw, w, h = speaker_drawer(b)
        made.append(tiled(os.path.join(tdir, "speaker-cutouts-1to1.pdf"), "SUPERCADE speaker cut-outs", w, h, draw))
        draw, w, h = side_drawer(b)
        made.append(tiled(os.path.join(tdir, f"side-panel-1to1{suffix(b)}.pdf"),
                          f"SUPERCADE side panel ({b.title.lower()})", w, h, draw))
    made.append(export_viewer_data())
    for m in made:
        print(m)


if __name__ == "__main__":
    main()

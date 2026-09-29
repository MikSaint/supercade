"""Cut files and parts lists for every build, in every material it can be made from.

generate.py works out the geometry (side profile, panel lengths, holes); this
module turns it into flat parts, nests them onto stock sheets, and writes:

  cad/supercade-<build>-<material>.svg   1:1, units = inches (lasers, Cricut, printing)
  cad/supercade-<build>-<material>.dxf   1:1, inches, R12 (CNC, laser, Fusion, Illustrator)

plus the cut list and shopping list the builder shows for the selected build.

Materials:
  cardboard  cross panels are blanks with fold flanges, shelves are folded box beams
  plastic    PVC foam board, panels cut to the inside width and glued/bolted to angle
  wood       plywood, panels cut to the inside width, glued + screwed to battens
"""

import math

GAP = 0.375            # between nested parts, inches (kerf + a margin)
MM = 1 / 25.4

# name, thickness (in), stock sheet (w x h in), per scale
STOCK = {
    ("cardboard", "small"): ("Cardboard (box panels)", 0.28, (36, 48)),
    ("plastic", "small"): ('6 mm PVC foam board, 2 x 4 ft', 6 * MM, (24, 48)),
    ("wood", "small"): ('6 mm birch plywood, 2 x 4 ft', 6 * MM, (24, 48)),
    ("plastic", "large"): ('10 mm PVC foam board, 4 x 8 ft', 10 * MM, (48, 96)),
    ("wood", "large"): ('1/2" (12 mm) plywood, 4 x 8 ft', 12 * MM, (48, 96)),
}


def materials_for(b):
    """Cardboard only for the bartop; the full-size cabinets are plastic or wood."""
    return ("cardboard", "plastic", "wood") if b.table else ("plastic", "wood")


def size_class(b):
    return "large" if b.scale >= 1 else "small"


# ---------------------------------------------------------------- parts

def _rect(w, h, x=0.0, y=0.0):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def _circle_or_oval(cx, cy, w, h):
    if abs(w - h) < 1e-6:
        return ("circle", cx, cy, w / 2)
    n = 48
    return ("poly", [(cx + w / 2 * math.cos(2 * math.pi * i / n), cy + h / 2 * math.sin(2 * math.pi * i / n)) for i in range(n)])


def build_parts(b, panels, material, frac):
    """Flat parts for one build in one material.

    Each part: id, name, qty, outline (closed polygon), holes, folds (lines),
    stock ("body" = the main sheets, "deck" = the 5 mm Foamex plate), note.
    """
    card = material == "cardboard"
    W = b.inner_width
    F = b.flange if card else 0.0
    parts = []

    pts = b.side_points()
    side = dict(id="P1", name="Side panel", qty=1, stock="body",
                outline=[(pts[k][1], pts[k][0]) for k in b.order], holes=[], folds=[],
                note="Mirror pair: cut two, turn one over.")
    # both sides nest together, the second turned end-for-end
    a, c = pair_sides(side)
    x0, y0, _, _ = bbox(a + c)
    shift = lambda poly: [(x - x0, y - y0) for x, y in poly]
    parts.append(dict(side, qty=2, pair=True, outline=shift(a), extra=[shift(c)]))

    cp = b.controls
    for item in panels:
        L = item["length"]
        holes = []
        for h in item.get("holes", []):
            if "rect" in h:
                x0, s0, x1, s1 = h["rect"]
                holes.append(("poly", _rect(x1 - x0, s1 - s0, x0 + F, s0)))
            else:
                cx, cs, ow, oh = h["oval"]
                holes.append(_circle_or_oval(cx + F, cs, ow, oh))
        if item["id"] == "P5" and not card and not b.table:
            # plywood / foam board is stiff enough to take the controls directly
            ox, oy = (W - cp.width) / 2, (L - cp.height) / 2
            holes += [("circle", ox + h.x, oy + h.y, h.dia_mm * MM / 2) for h in cp.holes]
        folds = [((F, 0), (F, L)), ((F + W, 0), (F + W, L))] if card else []
        parts.append(dict(id=item["id"], name=item["name"], qty=1, stock="body",
                          outline=_rect(W + 2 * F, L), holes=holes, folds=folds, note=""))

    # shelves
    top, side, tab = b.beam()
    if b.recess:
        sd, ss = b.screen_shelf_depth(), b.screen_shelf_side()
        if card:
            for pid, name, d, s_ in (("P10", "Screen shelf", sd, ss), ("P11", "Lower shelf", top, side)):
                if pid == "P11" and not b.shelf:
                    continue
                ln = 2 * d + 2 * s_ + tab
                ys = [d, d + s_, 2 * d + s_, 2 * d + 2 * s_]
                parts.append(dict(id=pid, name=name + " (box beam)", qty=1, stock="body",
                                  outline=_rect(W + 2 * F, ln), holes=[],
                                  folds=[((F, y), (F + W, y)) for y in ys], note="Fold into a closed tube."))
        else:
            parts.append(dict(id="P10", name="Screen shelf", qty=1, stock="body", outline=_rect(W, sd),
                              holes=[], folds=[], note="Sits on battens under the monitor."))
            if b.shelf:
                parts.append(dict(id="P11", name="Lower shelf", qty=1, stock="body", outline=_rect(W, top),
                                  holes=[], folds=[], note="Sits on battens; carries the computer and ballast."))
    else:
        lg = b.ledge()
        if card:
            parts.append(dict(id="P10", name="Monitor ledge", qty=2, stock="body",
                              outline=_rect(lg["width"], 2 * lg["leg"]), holes=[],
                              folds=[((0, lg["leg"]), (lg["width"], lg["leg"]))],
                              note="Two layers glued, flutes crossed, folded into an L."))
        else:
            parts.append(dict(id="P10", name="Monitor ledge", qty=2, stock="body",
                              outline=_rect(lg["width"], lg["leg"]), holes=[], folds=[],
                              note="Glue the two strips into an L."))

    # the control plate: always 5 mm Foamex on the bartop (it's the control box's plate)
    if b.table:
        parts.append(dict(id="P12", name="Deck plate (5 mm Foamex)", qty=1, stock="deck",
                          outline=_rect(cp.width, cp.height),
                          holes=[("circle", h.x, h.y, h.dia_mm * MM / 2) for h in cp.holes], folds=[],
                          note="Same plate as the control box."))
    return parts


def bbox(poly):
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


# ---------------------------------------------------------------- nesting

def _segments_cross(p1, p2, q1, q2):
    d = lambda a, b, c: (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return (d(p1, p2, q1) * d(p1, p2, q2) < 0) and (d(q1, q2, p1) * d(q1, q2, p2) < 0)


def _inside(pt, poly):
    x, y, c = pt[0], pt[1], False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def _overlap(a, b):
    ea, eb = list(zip(a, a[1:] + a[:1])), list(zip(b, b[1:] + b[:1]))
    if any(_segments_cross(p1, p2, q1, q2) for p1, p2 in ea for q1, q2 in eb):
        return True
    return _inside(a[0], b) or _inside(b[0], a)


def _pt_seg(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _clearance(a, b):
    """Smallest distance between two polygons' outlines."""
    ea, eb = list(zip(a, a[1:] + a[:1])), list(zip(b, b[1:] + b[:1]))
    return min(min(_pt_seg(p, q1, q2) for p in a for q1, q2 in eb),
               min(_pt_seg(p, q1, q2) for p in b for q1, q2 in ea))


def pair_sides(side):
    """Both side panels as one part: the second turned end-for-end and slid in
    until the control-deck tongues sit side by side, as in the original sheet
    layout. Returns the pair's two outlines, packed as tight as they go."""
    poly = side["outline"]
    x0, y0, x1, y1 = bbox(poly)
    w, h = x1 - x0, y1 - y0
    turned = [(x0 + x1 - x, y0 + y1 - y) for x, y in poly]
    best = None
    for k in range(0, 41):
        dy = (k - 20) / 40 * h * 0.5
        lo, hi = 0.0, w + GAP
        while hi - lo > 0.02:                   # smallest slide that doesn't touch
            mid = (lo + hi) / 2
            moved = [(x + mid, y + dy) for x, y in turned]
            if _overlap(poly, moved) or _clearance(poly, moved) < GAP:
                lo = mid
            else:
                hi = mid
        moved = [(x + hi, y + dy) for x, y in turned]
        bx0, by0, bx1, by1 = bbox(poly + moved)
        area = (bx1 - bx0) * (by1 - by0)
        if best is None or area < best[0]:
            best = (area, moved)
    return poly, best[1]


def nest(parts, sheet):
    """Skyline packing onto sheets of `sheet` (w, h), biggest parts first. Each
    part goes wherever it ends lowest, turned 90 degrees if that's better, so
    long panels fill the sheet's length and narrow ones fill the strips beside
    them. Returns a list of sheets, each a list of (part, x, y, rotated)."""
    sw, sh = sheet
    items = []
    for p in parts:
        x0, y0, x1, y1 = bbox(outlines(p))
        items += [(p, x1 - x0, y1 - y0)] * (1 if p.get("pair") else p["qty"])
    items.sort(key=lambda it: -(it[1] * it[2]))

    def try_place(sky, w, h):
        best = None
        for i, (sx, _, _) in enumerate(sky):
            if sx + w > sw + 1e-6:
                break
            y = max(ty for tx, ty, tw in sky if tx < sx + w - 1e-9 and tx + tw > sx + 1e-9)
            if y + h <= sh + 1e-6 and (best is None or (y + h, sx) < (best[0] + h, best[1])):
                best = (y, sx)
        return best

    def add(sky, x, y, w, h):
        new = []
        for tx, ty, tw in sky:
            # keep the parts of each segment outside [x, x + w)
            if tx < x:
                new.append((tx, ty, min(tw, x - tx)))
            if tx + tw > x + w:
                nx = max(tx, x + w)
                new.append((nx, ty, tx + tw - nx))
        new.append((x, y + h, w))
        new.sort()
        merged = []
        for seg in new:
            if merged and abs(merged[-1][1] - seg[1]) < 1e-9 and abs(merged[-1][0] + merged[-1][2] - seg[0]) < 1e-9:
                merged[-1] = (merged[-1][0], seg[1], merged[-1][2] + seg[2])
            else:
                merged.append(seg)
        return merged

    sheets = []
    for p, w, h in items:
        opts = [(w, h, False), (h, w, True)]
        if not any(ww + 2 * GAP <= sw and hh + 2 * GAP <= sh for ww, hh, _ in opts):
            raise ValueError(f"{p['id']} ({w:.1f} x {h:.1f}) doesn't fit a {sw} x {sh} sheet")
        done = False
        for s in sheets:
            cands = []
            for ww, hh, rot in opts:
                spot = try_place(s["sky"], ww + GAP, hh + GAP)
                if spot:
                    cands.append((spot[0] + hh, spot[1], spot, ww, hh, rot))
            if cands:
                _, _, (y, x), ww, hh, rot = min(cands)
                s["parts"].append((p, x + GAP, y + GAP, rot))
                s["sky"] = add(s["sky"], x, y, ww + GAP, hh + GAP)
                done = True
                break
        if not done:
            s = {"parts": [], "sky": [(0.0, 0.0, sw)]}
            sheets.append(s)
            cands = []
            for ww, hh, rot in opts:
                spot = try_place(s["sky"], ww + GAP, hh + GAP)
                if spot:
                    cands.append((spot[0] + hh, spot[1], spot, ww, hh, rot))
            _, _, (y, x), ww, hh, rot = min(cands)
            s["parts"].append((p, x + GAP, y + GAP, rot))
            s["sky"] = add(s["sky"], x, y, ww + GAP, hh + GAP)
    return [s["parts"] for s in sheets]


def outlines(p):
    """Every outline point of a part (a paired part has two outlines)."""
    return p["outline"] + [q for e in p.get("extra", []) for q in e]


def _place(p, x, y, rot):
    """Transform for a nested part: returns f(pt) -> sheet coordinates."""
    x0, y0, x1, y1 = bbox(outlines(p))
    h = y1 - y0
    if not rot:
        return lambda q: (x + q[0] - x0, y + q[1] - y0)
    return lambda q: (x + (h - (q[1] - y0)), y + (q[0] - x0))


# ---------------------------------------------------------------- writers

SHEET_SPACING = 4.0


def layout(groups):
    """Lay nested sheets side by side. `groups` is [(sheets, (w, h), stock name)].
    Returns drawing primitives in inches."""
    out, ox = [], 0.0
    total = sum(len(g[0]) for g in groups)
    i = 0
    for sheets, (sw, sh), stock in groups:
        for placed in sheets:
            i += 1
            out.append(("sheet", [(ox, 0), (ox + sw, 0), (ox + sw, sh), (ox, sh)]))
            out.append(("label", (ox + 0.3, sh + 1.0, f"SHEET {i}/{total}: {stock} ({sw} x {sh} in)", 0.6)))
            for p, x, y, rot in placed:
                f = _place(p, x + ox, y, rot)
                for poly in [p["outline"]] + p.get("extra", []):
                    out.append(("cut", [f(q) for q in poly]))
                    xs = [f(q) for q in poly]
                    out.append(("label", (sum(q[0] for q in xs) / len(xs) - 0.5, sum(q[1] for q in xs) / len(xs), p["id"], 0.6)))
                for hole in p["holes"]:
                    if hole[0] == "circle":
                        _, cx, cy, r = hole
                        out.append(("circle", (*f((cx, cy)), r)))
                    else:
                        out.append(("cut", [f(q) for q in hole[1]]))
                for a, c in p["folds"]:
                    out.append(("fold", [f(a), f(c)]))
            ox += sw + SHEET_SPACING
    return out


def write_svg(path, prims, title):
    xs, ys = [], []
    for kind, d in prims:
        if kind in ("sheet", "cut", "fold"):
            xs += [q[0] for q in d]; ys += [q[1] for q in d]
    W, H = max(xs) + 1, max(ys) + 2.5
    Y = lambda y: H - 0.5 - y            # SVG y runs down; keep the parts the right way up
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.3f}in" height="{H:.3f}in" viewBox="0 0 {W:.3f} {H:.3f}">',
             f"<title>{title}</title>",
             "<!-- 1:1, 1 user unit = 1 inch. Black = cut, red dashed = score/fold, grey = stock sheet. -->",
             '<g fill="none" stroke-linejoin="round">']
    for kind, d in prims:
        if kind == "sheet":
            pts = " ".join(f"{q[0]:.4f},{Y(q[1]):.4f}" for q in d)
            lines.append(f'<polygon points="{pts}" stroke="#bbbbbb" stroke-width="0.03"/>')
        elif kind == "cut":
            pts = " ".join(f"{q[0]:.4f},{Y(q[1]):.4f}" for q in d)
            lines.append(f'<polygon points="{pts}" stroke="#000000" stroke-width="0.01"/>')
        elif kind == "circle":
            cx, cy, r = d
            lines.append(f'<circle cx="{cx:.4f}" cy="{Y(cy):.4f}" r="{r:.4f}" stroke="#000000" stroke-width="0.01"/>')
        elif kind == "fold":
            (x1, y1), (x2, y2) = d
            lines.append(f'<line x1="{x1:.4f}" y1="{Y(y1):.4f}" x2="{x2:.4f}" y2="{Y(y2):.4f}" stroke="#e03030" stroke-width="0.01" stroke-dasharray="0.25 0.12"/>')
    lines.append("</g>")
    for kind, d in prims:
        if kind == "label":
            x, y, t, size = d
            lines.append(f'<text x="{x:.3f}" y="{Y(y):.3f}" font-family="Helvetica, Arial, sans-serif" font-size="{size}" fill="#2346c8">{t}</text>')
    lines.append("</svg>")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def write_dxf(path, prims):
    """AutoCAD R12 ASCII DXF, inches. Layers: CUT, FOLD, LABEL, SHEET."""
    o = []
    add = lambda *pairs: o.extend(f"{c}\n{v}" for c, v in pairs)
    add((0, "SECTION"), (2, "HEADER"), (9, "$ACADVER"), (1, "AC1009"), (9, "$INSUNITS"), (70, 1),
        (9, "$MEASUREMENT"), (70, 0), (0, "ENDSEC"))
    add((0, "SECTION"), (2, "TABLES"), (0, "TABLE"), (2, "LAYER"), (70, 4))
    for name, colour in (("CUT", 7), ("FOLD", 1), ("LABEL", 5), ("SHEET", 8)):
        add((0, "LAYER"), (2, name), (70, 0), (62, colour), (6, "CONTINUOUS"))
    add((0, "ENDTAB"), (0, "ENDSEC"), (0, "SECTION"), (2, "ENTITIES"))

    def poly(layer, pts, closed=True):
        add((0, "POLYLINE"), (8, layer), (66, 1), (70, 1 if closed else 0))
        for x, y in pts:
            add((0, "VERTEX"), (8, layer), (10, f"{x:.4f}"), (20, f"{y:.4f}"))
        add((0, "SEQEND"), (8, layer))

    for kind, d in prims:
        if kind == "sheet":
            poly("SHEET", d)
        elif kind == "cut":
            poly("CUT", d)
        elif kind == "circle":
            cx, cy, r = d
            add((0, "CIRCLE"), (8, "CUT"), (10, f"{cx:.4f}"), (20, f"{cy:.4f}"), (40, f"{r:.4f}"))
        elif kind == "fold":
            (x1, y1), (x2, y2) = d
            add((0, "LINE"), (8, "FOLD"), (10, f"{x1:.4f}"), (20, f"{y1:.4f}"), (11, f"{x2:.4f}"), (21, f"{y2:.4f}"))
        elif kind == "label":
            x, y, t, size = d
            add((0, "TEXT"), (8, "LABEL"), (10, f"{x:.4f}"), (20, f"{y:.4f}"), (40, f"{size}"), (1, t))
    add((0, "ENDSEC"), (0, "EOF"))
    with open(path, "w") as f:
        f.write("\n".join(o) + "\n")


# ---------------------------------------------------------------- parts lists

def cut_rows(parts, frac):
    rows = []
    for p in parts:
        x0, y0, x1, y1 = bbox(p["outline"])
        rows.append({"id": p["id"], "name": p["name"], "qty": p["qty"],
                     "size": f"{frac(y1 - y0)} x {frac(x1 - x0)}", "note": p["note"]})
    return rows


def joint_length(b):
    """Every inside joint where a cross panel meets a side, both sides, in feet."""
    pts = b.side_points()
    edges = list(zip(b.order, b.order[1:] + b.order[0]))
    total = sum(math.hypot(pts[c][0] - pts[a][0], pts[c][1] - pts[a][1]) for a, c in edges)
    return math.ceil(2 * total / 12)


def buy_list(b, material, sheets, electronics):
    """What to buy for this build in this material. `electronics` is the build's
    controls + electronics group from generate.py."""
    big = size_class(b) == "large"
    name, t, (sw, sh) = STOCK[(material, size_class(b))]
    n = len(sheets)
    ft = joint_length(b)
    if material == "cardboard":
        return None                              # generate.py's cardboard list already covers it
    if material == "wood":
        stuff = [
            (name, f"{n} sheet{'s' if n > 1 else ''}. The cut files are already nested on {sw} x {sh}\" sheets."),
            ('3/4" (18 mm) square pine batten', f"About {ft} ft. Cut into glue blocks for every inside joint."),
            ("Wood glue + " + ('1 1/4" (32 mm) wood screws' if big else '5/8" (16 mm) screws or brads'),
             "Glue and screw each panel to its battens."),
            ("M4/M5 bolts, nuts + washers", "For the joysticks" + ("" if big else " and the deck plate") + "."),
            ("Sandpaper (120), primer + paint", "Or clear finish to keep the ply look."),
        ]
        if big:
            stuff.append(('3/4" T-molding (optional)', f"About {ft} ft, round the side panels' edges."))
        tools = [
            ("Jigsaw or circular saw + straightedge", "Or send the DXF to a CNC shop."),
            ("Drill + hole saws", f"{'30 mm and 25 mm' if big else '24 mm and 25 mm'} for the controls, {b.speaker_d:g}\" for the speakers."),
            ("Clamps + sanding block", ""),
        ]
    else:
        stuff = [
            (name, f"{n} sheet{'s' if n > 1 else ''}. The cut files are already nested on {sw} x {sh}\" sheets."),
            ("15-20 mm aluminium or PVC angle", f"About {ft} ft, for every inside joint."),
            ("PVC cement or CA glue + M4 bolts with nylon nuts", "Glue the angle on, bolt the corners that take load."),
            ("Edge tape or T-molding (optional)", "Hides the foam edge."),
        ]
        tools = [
            ("Long metal straightedge + sharp knife", "Score and snap, several passes; or a jigsaw with a fine blade."),
            ("Drill + hole saws", f"{'30 mm and 25 mm' if big else '24 mm and 25 mm'} for the controls, {b.speaker_d:g}\" for the speakers."),
            ("Deburring tool or fine sandpaper", ""),
        ]
    groups = [(("WOOD" if material == "wood" else "PLASTIC") + " + FIXINGS", stuff)]
    if b.table:
        groups[0][1].insert(1, ("5 mm PVC foam board (Foamex), 12 x 18\"", "The control deck plate P12, shared with the control box."))
    groups.append(electronics)
    groups.append(("TOOLS", tools))
    return groups

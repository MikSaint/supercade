# Supercade: cardboard edition

Printable plans for building the [Supercade](https://github.com/MikSaint/supercade)
arcade cabinet at home out of cardboard, held together with a kids'
cardboard construction kit (plastic screws + nuts, safe saw, crease roller).

**The main build is the bartop:** a 16¾" tall cabinet that stands on a table,
with a 13.3" portable monitor and a 2-player deck. It's the one you can build
in cardboard. The full-size plans are still here; that cabinet is really a
plastic or wood build (wood and plastic plan sets are coming).

> This is a snapshot. Development continues in the Super Labs site; the live
> builder is at [supercade.sprlbs.com](https://supercade.sprlbs.com).

The builder (`viewer/index.html`) shows a parts list, shopping list and
downloads for each size and material. `cad/` has DXF (CNC, laser) and SVG
(printing, Cricut) cut files, nested on stock sheets by `fabrication.py`.

## What to print

### `bartop/` (start here)

| File | Pages | What it is |
|---|---|---|
| `SuperCade-Control-Box.pdf` | 4 | **Try this first.** A tabletop control box (a sloped shoebox) with a USB slot in the back, for a laptop or TV. Its Foamex deck plate is the bartop's, so it moves over later with the wiring intact |
| `SuperCade-Bartop-Plans.pdf` | 8 | Overview, side-panel measurements, cut list, fold layout, back panel (door, cable hole, vents), control layout, shopping list, assembly steps |
| `templates/control-panel-1to1.pdf` | 1 + 2 | Full-size control deck to tape onto the Foamex plate |
| `templates/side-panel-1to1.pdf` | 1 + 4 | Full-size side panel. Optional: page 2 of the plans lets you measure it instead |
| `templates/speaker-cutouts-1to1.pdf` | 1 | Two 2" (50 mm) round speaker holes for the screen board. Skip them if your monitor has speakers |

### `full-size/` (the original 6-foot cabinet)

Same set at 100%, for a 27" monitor, plus a kid-height variant that's 8" lower.
The back panel has a lower door, a hatch behind the monitor, a cable hole and
vents.

Print the templates at **100% / "Actual size"**, not "Fit to page". Every
page has a 2" check bar, so measure it before you tape anything.

## The bartop at a glance

| | |
|---|---|
| Height × depth × inside width | 16¾" × 14⅜" × 14½" |
| Control deck | ~5¾" above the table (7° tilt), about 34" off the floor on a 28" table |
| Screen | 13.3" portable USB-C monitor. The window is 11⅝" × 6½", so measure yours |
| Front | One flat screen board (like [OpenCade](http://opencade.org/)): the window, with both speaker holes under it, leaning back 15°. No recess to build |
| Back | A 10½" × 11½" door, a 1½" cable hole and four vent holes |
| Controls | 2 players × (joystick + 6 buttons) + start/coin each + a menu button, using **24 mm** buttons |
| Body | Cardboard, 2–3 big boxes. The longest parts are under 18" |
| Control deck | 1 layer of cardboard + a **5 mm Foamex (PVC foam board)** top plate |
| Fasteners | Plastic screws + nuts from the kit, plus glue |

### Why the controls use 24 mm buttons

Arcade buttons and joysticks don't shrink. The original 2 × 8-button panel is
27" wide and the bartop deck is 14½". To fit two players with 6 buttons each,
the layout keeps the original arrangement (stick on the left, 3 × 2 buttons,
start/coin above) but uses **24 mm buttons at 30 mm spacing** instead of 30 mm
ones. That also suits small hands. Buy a "zero delay" kit with screw-in 24 mm
buttons, or add a 24 mm button pack.

## Materials: cardboard, plastic or wood?

| Material | How you cut it | Where it fits |
|---|---|---|
| **Cardboard + screw kit** | Safe saw / craft knife | The bartop body. The loads are light, and kids can build most of it |
| **5 mm Foamex / PVC foam board** | Craft knife, several passes | The control deck top plate. It gets hammered, and it gives crisp button holes |
| **Correx / corrugated plastic (4–5 mm)** | Craft knife | A tougher, waterproof rebuild of the same plans. The same kit screws work |
| Acrylic | Needs a laser; cracks when you cut holes by hand | Avoid |
| 6 mm plywood + M4 bolts | Jigsaw + drill | The "properly permanent" version |

## Before you cut anything

1. **Test the screws.** Kids' kit screws are short. Screw a flange scrap to a
   side-panel scrap, nut on. If a double-layer side is too thick, keep the
   sides single-layer and stiffen them with glued ribs.
2. **Buy screw-in buttons, not snap-in.** Snap-in buttons only grip thin
   panels.
3. **Check your joystick's bolt pattern.** The template uses the original
   drawing's 44 × 81 mm pattern. Mark from your actual stick if it differs.
4. **Measure your monitor** and adjust the screen window (and, on the full
   size, the screen shelf height).

## Safety

The bartop is light, but it tips forward if someone leans on the deck. Put
about 1 kg (a bag of rice) on its base and a non-slip mat under it, and keep it
back from the table edge. Adults do the craft-knife and Foamex cutting, and kids
use the kit's safe saw. For the full-size cabinet, weight it and strap it to the
wall.

## Regenerating

The PDFs are generated by `generate.py` (Python 3 + PyMuPDF). The original
CAD geometry is hard-coded at the top, and each entry in `BUILDS` is one plan
set (scale, controls, materials, shopping list). The bartop brings its own
side profile (`bartop_side()`) and panel list.

```sh
pip install pymupdf
python3 generate.py
```

To make another size, add a `Build(...)` with a different `scale`. If the deck
changes size, give it a control layout that fits (see `compact_controls`).

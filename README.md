# Perforated Plant Pot

A 3D-printable plant pot: a thin-walled shell (wall = 2 perimeters wide —
`WALL_T = 2 × LINE_WIDTH`, so 1.6 mm at the 0.8 mm nozzle used for transparency;
set by printability, the loads are tiny) with a 2 mm flat bottom, **perforated to
save material** but braced so it can be filled with wet soil and carried, and
sized to drop inside a watertight outer cachepot for bottom-watering. Size is
parametric (`POT_OD` × `POT_H` are the outer extents, `LINE_WIDTH` the nozzle —
change and re-run); **currently Ø115 mm × 140 mm, 0.8 mm nozzle**.

**Cross-section is selectable** via `NUM_FACES`: `0` = round (the default), or
any integer ≥ 3 for a regular polygon — `4` square, `6` hexagon, `8` octagon, …
A circle is just the N→∞ limit, so every feature (perforation, handles, ribs,
floor waffle, drain pipe) adapts and the round path is unchanged. For a polygon
`POT_OD` is the across-**corners** diameter (vertices sit on that circle, so it
still fits the same round cachepot), the faces are flat with **rounded corners**
(`CORNER_FILLET`), a flat face is centred toward each handle, and the folded
corners act as built-in stiffeners (so a polygon needs only the ribs behind its
handles).

**The wall can taper** to match a real pot's profile: give the base and top
outer sizes separately (`POT_OD_BASE` / `POT_OD_TOP`) and the wall grows from one
to the other at a single even draft angle (a frustum when round, a tapered prism
when faceted). The top is the widest part (the opening) and is what must clear
the cachepot. Set them equal (the default) for a straight wall. The floor sits
at the narrow base; the drain pipe slants to follow the sloping wall; the ribs
become tapered blades that track it. Build a variant without editing via env
overrides: `POT_NUM_FACES=8 POT_OD_BASE=120 POT_OD_TOP=140 py -3.12 -m src.build`
(`POT_OD` still sets a single straight-wall size for both ends).

Designed around **transparent PETG**'s weak bridging — every perforation hole is
a *gabled* hexagon (vertical sides + a 45° peaked roof: prints support-free even
at coarse layers, unlike a regular hex's 30° roof or a round hole's
flat-horizontal crown). The perforation is *fine* (≈ 2.4 mm-wide holes,
2-perimeter webs → ~37 % open) so soil mostly stays put; the floor is
hex-perforated too, between its stiffening ribs, which doubles as drainage.
Two grab handles near the top (each a row of finger holes), opposite each
other. And one angular spot has a vertical perforated pipe down the wall — its
bore holds the drain hose for the outer cachepot.

Uses the same cadquery build setup as the `retractable-cable-spool` project.

## Building

```bash
py -3.12 -m pip install cadquery
py -3.12 -m src.build                  # build both pots + assembly.step, open in the FreeCAD viewer
py -3.12 -m src.build --list           # list available part names
```

(or run the convenience wrapper: `./build.sh`)

This produces `plant_inner_pot.step`, `plant_outer_pot.step`, and a combined
`assembly.step` in the repo root. Geometry-regression check:

```bash
py -3.12 tools/check_geometry.py             # diff against committed baseline
py -3.12 tools/check_geometry.py --update-baseline   # bless current as new baseline
```

### Viewing

Every `src.build` finishes by opening (or refreshing) `assembly.step` in the
shared FreeCAD viewer hub (`../freecad/`) — best-effort, and it never fails the
build. See `../freecad/README.md`.

> Note: the fine perforation makes the inner-pot STEP heavy — scales with the
> hole count, so ~tens of MB for the Ø115 pot, well over 100 MB at Ø250. A big
> STEP is a slog in any viewer/slicer — another reason to keep an eye on
> `HEX_HEIGHT` / `HEX_LIGAMENT` (and `POT_OD`).

## Source layout

| File                   | Contents                                                              |
|------------------------|-----------------------------------------------------------------------|
| `src/dimensions.py`    | All dimensional / material / print constants, with the design rationale + load-fast asserts |
| `src/helpers.py`       | Geometric helpers (`cyl`, `tube`, `compound`, `hex_prism`, `hex_prism_z`, `slot_prism`, `heal`) |
| `src/pot.py`           | The pot body: shell → wall hex perforation → grab handles → floor hex perforation → vertical ribs → floor ribs → optional drainage. Cuts the thousands of tiny hex holes in chunked batches (`_cut_many`) |
| `src/build.py`         | Orchestrator: builds the pots, heals them, exports the STEPs + `assembly.step`, opens the FreeCAD viewer. CLI: `--part NAME` / `--list` |
| `tools/check_geometry.py` | bbox / volume / CoM regression check vs `tools/baseline.tsv`        |

## Outputs

- `plant_pot.step` — the whole pot in one piece: a 2-perimeter wall (1.6 mm at
  the 0.8 mm nozzle) + 2 mm floor; a fine staggered hexagonal perforation over
  the wall (from ~1.6 mm above the floor up to just below the rim cap, with
  solid frames left around the handles, ribs and drain pipe); a solid top rim
  cap with two opposed grab handles cut into it — each a tangential row of
  pointy-top hexagonal finger holes (count auto-set by the diameter, kept *even*
  so the rib behind each handle clears the holes — 4 at Ø250, 2 at Ø115); a thin
  solid base ring; full-height internal ribs (count scales with diameter — 2 at Ø115, one behind
  each handle; 4+ on bigger pots, the extras bracing the open zones); a rib
  waffle on the inside of the floor whose spoke/ring counts also scale; the
  floor membrane between those ribs hex-perforated too (also drainage); and a
  vertical perforated pipe down the wall at one spot (`DRAIN_CHANNEL_ANGLE`,
  midway between ribs) — its bore takes the drain hose for the outer cachepot.

> **Build time:** the perforation is hundreds-to-thousands of individual
> hex-hole cuts (it scales with hole count, so ~minutes at Ø115, ~half an hour
> at Ø250). A one-off per geometry change. A **tapered round** pot would be far
> slower if cut straight into the cone (each hole leaves messy conic edges and
> the solid's complexity snowballs), so it's built by perforating a *cylinder*
> and carving it to the cone with a single intersection — back to ~2 min. (See
> `_build_cone_pot` in `pot.py`.)

## Design notes

**Why hexagonal holes (and why a gabled top).** Transparent PETG bridges and
overhangs poorly — long horizontal spans sag and frost over. So a hole in a
vertical wall lives or dies by its **roof** (the sides are vertical and the
bottom is just a ledge built off solid below — neither is an overhang). The
perforation hole is a **gabled hexagon**: vertical side walls capped top and
bottom by **45° peaks**. At 0.4 mm layers a 45° roof steps inward 0.4 mm per
layer — about 50 % bead-to-bead overlap, so it prints clean and support-free.
(A regular pointy-top hexagon's roof is only 30° off horizontal — ~14 % overlap
at the same layer height, so it droops; a round hole is worse still, its crown
goes flat-horizontal — a true sagging bridge.) The gable keeps the honeycomb's
tight tiling and high open-area ratio and its load-triangulating ligament web,
with none of the weak horizontal plane a grid of round/square holes has.
Counter-intuitively, **smaller holes print *better*** here — the roof angle is
fixed by geometry, so a smaller hole just means a shorter unsupported span.

**Hole size vs web width — the real knobs.** A hole is sized by its
across-flats *width* `HEX_AF` (default **2.4 mm**) — the horizontal, narrowest
dimension, so it's what the nozzle has to keep open and thus the floor on hole
size (reliable minimum ≈ `2 × LINE_WIDTH`, ~1.6 mm with the 0.8 mm nozzle). The
hole is `HEX_SIDE_H` + `HEX_AF` tall (vertical side wall + two 45° caps;
`HEX_SIDE_H` defaults to `HEX_AF/2`). The web between holes, `HEX_LIGAMENT` =
`2 × LINE_WIDTH` (1.6 mm), is set by *printability*, not strength: each web is a
strut 2 perimeters wide × the wall's `WALL_T` thick — the minimum that prints as
a clean solid bead. At 2.4 mm width / 1.6 mm web the band is **~37 % open**; bump
`HEX_LIGAMENT` for a denser wall, or `HEX_AF` for bigger holes (more open, but
more soil gets through, and the file/build balloon — hole count scales like
1/pitch²). A hole isn't a true sieve — fine peat trickles through — so use a
liner / landscape fabric if you plant straight into the pot. Strength is *not* a
constraint on any of this; the structural loads ride the skeleton (rim cap,
base band, ribs, solid frames), not the perforated panels.

**Why it's still strong enough for soil + lifting.** Filled with damp soil
the pot holds ≈ 20 kg, and it gets picked up by the handles/rim. The
reinforcement gives that load a clean path and keeps a thin shell from
creeping:

- **Solid top rim cap** (`RIM_CAP_H` = `max(8, 0.06·OD)` ≈ 8 mm at Ø115,
  ≈ 15 mm at Ø250) — a continuous hoop; the ring you actually grip when
  lifting, so it stays unbroken. A closed ring is stiff in-plane, so it's kept
  lean — just enough lip to hook your fingers under, growing only for bigger,
  heavier pots. The top of the pot carries no soil load — it just has to
  support the handles — so it's the *only* solid band up top: everywhere else
  the perforation runs all the way up to it. Every mm of cap is a mm less soil
  depth (the handle cluster, and so the fill line, sits just below it).
- **Two grab handles** at `0°` / `180°`, just below the cap — each a
  tangential row of `HANDLE_FINGERS` (= 4) pointy-top hexagonal finger holes,
  one per finger (`HANDLE_FINGER_H` ≈ 20 mm tall, ≈ 17 mm wide). Reach your
  fingers through, grip the cap above. Hex finger holes instead of one stadium
  opening for two reasons: a stadium's rounded crown goes flat-horizontal at
  the top (a true bridge that sags in PETG), whereas a hex roof tops out at
  60° off vertical — a real overhang, so the roof underside prints a touch
  rough, but no support needed and no failure (reshape them as a gable —
  vertical sides + a 45° peak — if you want a clean roof); and the solid
  pillars between the fingers add cross-layer material right in the handle
  band — the part that hangs in tension when you lift. Two handles is all you
  need to carry the pot; a `HANDLE_FRAME`-wide solid frame is kept around
  each cluster. The cluster sits as high as it can — only `HANDLE_LINTEL`
  (2 mm) of solid is left between the top of the finger holes and the bottom
  of the rim cap (`HANDLE_Z_HI = POT_H - RIM_CAP_H - HANDLE_LINTEL`). Soil
  can't be filled above the holes anyway, so a low handle just wastes cavity.
- **Full-height internal ribs** running floor → rim, count scaling with
  diameter (one behind each handle minimum — the lift load drops straight down
  it from the grip; bigger pots add more in the open zones to brace a tall
  floppy shell against ovalising). Their inward projection (`RIB_PROJ`) scales
  too — shallower on a small pot so it doesn't eat the cavity.
- **Solid base ring** (`BASE_BAND_H` = floor + one ligament ≈ 3.6 mm) — just a
  few solid layers at the bed for adhesion/warp; the perforation otherwise runs
  almost down to the floor so water drains at the very bottom of the column.
  (This was an 18 mm stress-spreading band, dropped once the load proved
  trivial — doubly so with the light pumice fill.)
- **Floor rib waffle** — radial spokes + concentric ring blades (counts scale
  with size), `WALL_T`-thick (same printable bead as the wall) ×
  `FLOOR_RIB_H` tall, and that height also scales (≈5 mm on a small pot,
  ≈10 mm at Ø250), so a little pot doesn't give up depth to reinforcement it
  doesn't need. The spokes run from the **innermost ring rib out to the wall**
  (not into the centre — central stubs that don't converge brace little, so the
  centre is perforated for drainage instead, with the ring as its hoop). If a
  spoke falls on the drain-channel angle it's truncated just short of the pipe's
  floor bore (so it still braces that corner without blocking the hose), and the
  pipe's hex holes in that little patch are dropped so the spoke butts flush
  against solid wall. The waffle is on the **inside** of the floor on purpose:
  the floor prints as one clean solid disc on the bed and the ribs grow up off
  it as thin walls — no bridging. (Underside ribs would force the floor to
  bridge the gaps between them.) The ribs carry the load; the membrane between
  them barely sees stress, which is why it can be hex-perforated too
  (`FLOOR_PERF`) — extra saving, plus drainage. A `FLOOR_PERF_FRAME`-wide solid
  margin (wider than the wall's ligament, since the floor takes the load) is kept
  around every rib and the perimeter.

**Drainage.** With `FLOOR_PERF = True` (the default) the hex floor already
drains. For a soil-retaining alternative, set `FLOOR_PERF = False` and
`DRAINAGE = True` — a mostly-solid floor with a centre hole plus a ring of
`DRAIN_HOLE_D` holes between the floor ribs.

**Drain-hose channel / pipe** (`DRAIN_CHANNEL`, default **on**). The pot is
sized to sit inside a watertight outer cachepot for *bottom watering* (soak in
water, then drain), with the drain hose threaded down past the inner pot to the
reservoir. To make room for the hose without enlarging the inter-pot gap
everywhere, one angular position (auto-placed midway between two ribs —
`DRAIN_CHANNEL_ANGLE`, never on a rib or handle) is a vertical **pipe** running
floor → rim: a full 360° tube (bore radius `DRAIN_CHANNEL_R_CH = HOSE_D/2 +
CLEARANCE`, wall `WALL_T`) *merged into the wall* — a band of its outer surface
overlaps the existing wall, so it stays one connected solid and the joint is a
clean solid arc; its outer face sits `DRAIN_CHANNEL_OD_RECESS` inside the
nominal OD (so it isn't tangent to the OD — a tangent line confused a STEP
translator and inverted the wall render earlier). The hose threads down the
pipe's bore; the inter-pot gap stays uniformly tiny (no wasted reservoir
water), and the pipe eats only ~1–2 % of the soil cavity. The pipe wall is
hex-perforated on its **inward (soil-facing) arc** — `DRAIN_CHANNEL_PERF_SOLID_HALF_DEG`
of arc around the outward direction stays solid (a hole there would just open
the bore to the inter-pot gap, not the soil) — with the same cell size as the
rest of the wall, all the way down to the floor, so water flows in/out of the
soil right at the bottom of the column. A small `DRAIN_CHANNEL_FLOOR_BORE_R`
hole is cut through the floor too (so the hose reaches the reservoir) — a bit of
fabric / sponge in the pipe blocks soil from sifting through if you're not using
a liner. The pipe also doubles as an extra vertical stiffener (a closed tube is
rigid) — it does *not* replace a rib (it sits between them).

## Print orientation

Material: **transparent PETG**. **No supports needed.**

Print upright, open end up, on the flat 2 mm floor. The perforation holes (wall,
floor, drain-pipe) are *gabled* hexagons with a 45° peaked roof — well within
PETG's support-free range at 0.4 mm layers. The handle finger holes are regular
pointy-top hexagons (a 60°-off-vertical roof), but they're short spans and print
support-free too. So no support anywhere. Notes:

- **Use a 0.8 mm nozzle** (set `LINE_WIDTH = 0.8`) — it's the easy transparency
  win: 2-perimeter walls with full-width beads, fewer bead-to-bead boundaries,
  less internal scatter. (Set `LINE_WIDTH` to whatever your slicer's extrusion
  width is so `WALL_T`/`HEX_LIGAMENT`/ribs stay clean perimeter counts.) Print
  PETG hot (top of its range) and perimeters slow for the clearest result.
- The Ø115 × 140 pot is a comfortable squat print; scaled up toward Ø250 it
  gets tall and thin-walled and a bit wobbly (the ribs help, but slow the upper
  layers and watch for ringing). A brim is cheap insurance against the base
  lifting (the perforated floor has slightly less bed contact than solid).
- PETG likes a slightly slower first layer and minimal part cooling on the
  early layers; the solid 2 mm floor (plus the thin base ring) gives it
  forgiving real estate to grab the bed with. Decent cooling on the hole-roof
  undersides keeps the 45°
  gables crisp.
- The fine hex holes (≈ 2.4 mm wide) bridge trivially, but there are a lot of
  them — the STEP gets heavy and the slicer chugs (worse the bigger the pot).
- If you do see a sagging hole roof, it's cooling/temperature, not geometry.

## Tuning

Everything lives in `src/dimensions.py`. The knobs you'll most likely touch:

- **Cross-section:** `NUM_FACES` — `0` round, or `≥ 3` for a regular polygon
  (square `4`, hexagon `6`, octagon `8`, …). For a polygon `POT_OD` is the
  across-corners diameter and `CORNER_FILLET` rounds the vertical edges; a flat
  face is auto-centred on each handle, the floor waffle and perforation re-tile
  per-face, and only the behind-handle ribs are kept (corners do the rest). On a
  many-sided/small pot the handle finger count drops to fit one flat face (it
  asserts if even two won't fit — use more `POT_OD`, fewer faces, or a smaller
  `HANDLE_FINGER_H`). Overridable per build with `POT_NUM_FACES` / `POT_OD` /
  `POT_H` env vars.
- **Taper:** `POT_OD_BASE` / `POT_OD_TOP` (base & top outer size; equal = straight
  wall). The wall grows at one even draft angle between them; the top is the
  widest part (the opening, what clears the cachepot). Floor/waffle size to the
  base, the drain pipe slants to stay merged into the sloping wall, and the
  vertical ribs become tapered blades. Asserts if the base gets too small for the
  wall or the hose. Overridable per build with `POT_OD_BASE` / `POT_OD_TOP`.
- **Size & nozzle:** `POT_OD` / `POT_H` (outer extents) and `LINE_WIDTH` (your
  slicer's extrusion width — `WALL_T`, `HEX_LIGAMENT`, ribs are `2 × LINE_WIDTH`
  so they print as clean perimeter counts). Most of the model re-derives —
  perforation re-tiles, bands/handles/cut windows recompute, and the structural
  support auto-scales: the handle finger count drops on a small circumference
  (and stays even), the vertical-rib count grows with diameter (`RIB_SCALE_OD`
  thresholds), the floor spoke/ring counts grow too. A `config:` line prints
  the chosen counts. A too-small size trips an assert.
- **Soil retention vs lighter walls:** the perforation is sized by
  `HEX_AF` (hole across-flats width, default 2.4 mm — smaller = retains finer
  media, floor ≈ `2 × LINE_WIDTH`); `HEX_SIDE_H` sets how tall each hole is
  (default `HEX_AF/2`); open area follows from `HEX_LIGAMENT` (= `2 × LINE_WIDTH`;
  raise it for a denser/heavier wall). Grow the perforated band with `PERF_Z_HI`
  / `PERF_Z_LO`. Hole count scales like 1/pitch² — denser perforation (smaller
  `HEX_AF` or bigger `HEX_LIGAMENT` relative to it) = a heavier file and slower
  build.
- **Floor:** `FLOOR_PERF` on/off; the floor holes are the *same size as the
  wall holes* (driven by `HEX_AF` / `HEX_LIGAMENT`); the rib grid scales
  (`FLOOR_SPOKE_COUNT` ∝ diameter, `FLOOR_RING_COUNT` ∝ floor radius — rings
  evenly spread, the wall is the outermost); `FLOOR_PERF_FRAME` the solid
  margins around ribs/rim/centre. `FLOOR_RIB_H` (rib stand-up height) scales
  with the floor radius; rib *thickness* is `WALL_T` (vertical and floor ribs
  both — `RIB_W = FLOOR_RIB_T = WALL_T`).
- **Stiffer:** smaller `HEX_HEIGHT`, bigger `HEX_LIGAMENT`; override the rib
  count (`RIB_COUNT` is computed from `RIB_SCALE_OD` — must stay a multiple of
  `HANDLE_COUNT`) or `RIB_PROJ` / `FLOOR_RIB_H`; grow `BASE_BAND_H` /
  `RIM_CAP_H`.
- **Handles:** `HANDLE_COUNT`, `HANDLE_ANGLES`, `HANDLE_FINGERS_MAX` (the
  desired finger count — auto-reduced *by two at a time* to fit a small
  diameter, capped by `HANDLE_MAX_ARC_DEG`; stays even so the centreline rib
  clears the holes), `HANDLE_FINGER_H` (hole height — width follows, it's a
  regular hex), `HANDLE_FINGER_GAP` (pillar between fingers), `HANDLE_LINTEL`
  (solid left between the holes and the rim cap — `HANDLE_Z_HI` is derived
  from it), `HANDLE_FRAME` (solid border). (`RIB_ANGLES` is
  independent — by default ribs land on `0/90/180/270`, two behind the two
  handles.)
- **Drain-hose channel:** `DRAIN_CHANNEL` on/off; `DRAIN_CHANNEL_HOSE_D` (your
  hose diameter), `DRAIN_CHANNEL_CLEARANCE` (radial slop); `DRAIN_CHANNEL_ANGLE`
  (auto-placed midway between ribs — clear of handles and ribs — asserts trip
  if you point it at one). A floor spoke landing on that angle is auto-truncated
  short of the pipe bore.
- **Drainage round-holes:** `DRAINAGE` (mainly useful with `FLOOR_PERF`
  off), `DRAIN_HOLE_D`, `DRAIN_RING_R`, `DRAIN_RING_N`.

After any change, rerun `py -3.12 -m src.build` and
`py -3.12 tools/check_geometry.py` (and `--update-baseline` once the new
geometry is what you want).

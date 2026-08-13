# Pad Foundation Design Calculator — User Instructions

## 1. Purpose

The program analyses and designs an isolated rectangular reinforced-concrete pad
foundation. It reports bearing, flexural reinforcement, one-way shear, punching
shear, and sliding checks, together with analytical calculations and reinforcement
drawings.

The program is a design aid. Input actions and soil parameters must be supplied or
verified by suitably qualified structural and geotechnical engineers.

### Software basis and GUI

The principal foundation-analysis and design modules used by this program originate
from the open-source
[FoundationDesign project by kunle009](https://github.com/kunle009/FoundationDesign).

This program adds a graphical user interface (GUI) in `pad_foundation_gui.py` to
facilitate data entry, presentation of design results and analytical calculations,
and generation of foundation-layout, section, and reinforcement graphics.

## 2. Starting the program

For the packaged Windows version, open the `dist` directory and double-click
`FoundationDesign.exe`.

Full location:

```text
D:\KostasMy\MySite\programming\civils.ai\FoundationDesign-main\dist\FoundationDesign.exe
```

To run from Python, open PowerShell in the project directory and enter:

```powershell
.\.venv\Scripts\python.exe pad_foundation_gui.py
```

## 3. Recommended workflow

1. Open the **Input Data** tab.
2. Enter the foundation geometry, material properties, and characteristic column
   actions.
3. Confirm the live plan and section show the intended geometry and column position.
4. Select **Run Design**.
5. Review every check in **Design Results**. A satisfactory design should not contain
   `FAIL` or `UNKNOWN` results.
6. Review the detailed derivations in **Analytical Calculations**.
7. Review the designed reinforcement in **Output Graph**.
8. Use **Print / Save Calculation Report** to print the calculation sheet or save it
   as PDF through the browser print dialogue.

Changing an input invalidates the previous reinforcement drawing. Select **Run
Design** again after every change.

## 4. Input Data

### 4.1 Geometry and layout

All geometry values are entered in millimetres.

- **Foundation length:** overall dimension in the global X direction.
- **Foundation width:** overall dimension in the global Y direction.
- **Column length:** column dimension parallel to foundation X.
- **Column width:** column dimension parallel to foundation Y.
- **Column centre, X:** distance from the foundation's left edge to the column centre.
- **Column centre, Y:** distance from the foundation's lower edge to the column centre.
- **Foundation thickness:** overall pad depth.
- **Soil depth above foundation:** soil thickness carried on top of the pad. Enter
  zero where none is present.

For a centrally positioned column:

```text
Column centre X = foundation length / 2
Column centre Y = foundation width / 2
```

### 4.2 Soil and material properties

- **Soil bearing capacity (kN/m²):** allowable service bearing pressure supplied by
  the geotechnical engineer. Confirm whether the project value is gross or net and
  that its basis agrees with the calculation method.
- **Soil unit weight (kN/m³):** unit weight of soil above the foundation.
- **Concrete unit weight (kN/m³):** normally approximately 24–25 kN/m³ for reinforced
  concrete.
- **Concrete strength, fck (N/mm²):** characteristic cylinder compressive strength.
- **Steel yield strength, fyk (N/mm²):** characteristic reinforcement strength.
- **Concrete cover (mm):** nominal cover to the outside of the lowest reinforcement.
- **Initial bar diameter X/Y (mm):** diameters used to determine the effective depths.
  The provision routine may select a different diameter to satisfy the required area.

Supported concrete strengths are 16, 20, 25, 30, 32, 35, 37, 40, 45, and 55 N/mm².
Supported bar diameters are 8, 10, 12, 16, 20, 25, 32, and 40 mm.

### 4.3 Applied column loads and moments

Enter characteristic actions at foundation level. Do not add foundation self-weight
or soil-above-foundation weight to the column axial-load fields; the program adds
these separately.

- **Permanent axial load, Gk (kN):** dead-load column reaction, including permanent
  structural and fixed non-structural loads.
- **Imposed axial load, Qk (kN):** variable/live-load column reaction.
- **Permanent/imposed horizontal load X/Y (kN):** characteristic horizontal column
  reactions in each global direction.
- **Permanent/imposed moment X/Y (kNm):** characteristic column moments about the
  corresponding axes.

The main ULS combination used by the program is generally:

```text
Ed = 1.35 × permanent action + 1.50 × imposed action
```

Use a consistent sign convention for moments and horizontal actions. Verify that the
X/Y axes used by the source structural analysis correspond to the program layout.

## 5. Program tabs

### Input Data

Contains the input fields and live geometry-only plan and section previews. Red or
warning messages identify invalid dimensions or material selections.

### Design Results

Contains derived values and a summary of all verification checks:

- `PASS`: calculated demand does not exceed resistance.
- `FAIL`: calculated demand exceeds resistance; revise the design.
- `UNKNOWN`: insufficient values were exposed to classify the result; investigate
  before using the design.

### Analytical Calculations

Shows formulas, numerical substitutions, resistances, utilization ratios, and
intermediate results. The search box can locate terms such as `VEd`, `As,req`,
`punching`, or `sliding`.

### Output Graph

Shows the designed reinforcement after calculation:

- red lines: X-direction bottom reinforcement;
- green lines/circles: Y-direction bottom reinforcement;
- **X LOWER:** X bars form the lower bottom layer;
- **Y UPPER:** Y bars form the upper bottom layer.

Bar callouts use notation such as `H16mm @ 200 mm c/c`.

## 6. Design checks

- **Bearing pressure (SLS):** compares maximum service pressure with allowable soil
  pressure.
- **Flexural reinforcement X/Y:** compares required and provided steel per metre.
- **Transverse shear X/Y:** checks one-way shear at one effective depth from the
  corresponding column faces.
- **Punching shear at column face:** checks maximum punching resistance adjacent to
  the column.
- **Punching shear at 1d and 2d:** checks punching stress on the calculated control
  perimeters.
- **Sliding resistance:** compares the resultant factored horizontal action with the
  calculated interface-friction resistance.

Utilization is normally reported as:

```text
η = demand / resistance
```

`η ≤ 1.000` passes; `η > 1.000` fails.

## 7. Revising a failed design

Depending on the governing check, typical engineering responses include:

- bearing failure: increase plan dimensions or reassess the allowable pressure;
- flexural failure: increase reinforcement or foundation depth;
- one-way or punching-shear failure: increase foundation depth and rerun the design;
- sliding failure: investigate increased dead load, a shear key, revised interface
  parameters, or another engineered resistance mechanism.

Do not change values merely to obtain `PASS`. Revisions must be compatible with the
geotechnical report, detailing rules, constructability, durability, and applicable
codes.

## 8. Printing and saving

After running the design:

1. Open **Design Results**.
2. Select **Print / Save Calculation Report**.
3. In the browser print dialogue, select a printer or **Save as PDF**.

The report includes inputs, derived values, the check summary, and detailed
analytical calculations. Review the PDF before issue.

## 9. Important limitations

- Confirm all loads, axes, signs, units, material properties, cover, and soil values.
- The program does not replace project-specific geotechnical assessment.
- Check reinforcement anchorage, laps, development length, edge detailing, local
  column transfer, durability, crack control, construction tolerances, and any
  seismic requirements separately where applicable.
- Numerical values can differ slightly from hand calculations because the program
  rounds some intermediate results.
- Final calculations and drawings should be reviewed and approved by a qualified
  engineer before construction.

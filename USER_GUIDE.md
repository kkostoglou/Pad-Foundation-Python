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

Use the **Input Data** tab to define the foundation and all actions applied by the
column. Work through the three input groups from top to bottom:

1. Enter the foundation and column dimensions under **Geometry & Layout**.
2. Enter the allowable soil pressure and the concrete, soil, and reinforcement
   properties under **Soil & Material Properties**.
3. Enter the characteristic axial loads, horizontal loads, and moments under
   **Applied Column Loads & Moments**.
4. Check the live plan and section previews. Confirm the pad dimensions, thickness,
   soil cover, and column location before calculating.
5. Select **Run Design** at the bottom of the input form. The program validates the
   entries, performs the analysis and design checks, creates the reinforcement and
   force diagrams, and then opens the **Output Graph** tab.

If an entry is invalid, the program highlights the affected field and displays an
explanation. Correct the value and select **Run Design** again. **Restore Defaults**
returns all fields to the supplied example values.

Always select **Run Design** after changing an input. Previously calculated results
must not be used for the revised input data.

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

This is the working input form. It contains the geometry, soil and material
properties, and applied column actions described in Section 4. The plan and section
previews update while values are entered, allowing the geometry and column position
to be checked before analysis.

Select **Run Design** when the input is complete. A successful calculation updates
all other tabs and automatically opens **Output Graph**. Highlighted fields or
warning messages indicate dimensions or material selections that must be corrected.

### Design Results

This tab summarizes the calculated structural values and the governing verification
checks. Use it as the first review of the design after selecting **Run Design**. It
reports quantities such as self-weight, required foundation area, design moments,
and required reinforcement, followed by bearing, flexure, one-way shear, punching
shear, and sliding checks.

The demand and capacity columns show the values used in each comparison. Review the
status of every row:

- `PASS`: calculated demand does not exceed resistance.
- `FAIL`: calculated demand exceeds resistance; revise the design.
- `UNKNOWN`: insufficient values were exposed to classify the result; investigate
  before using the design.

The **Print / Save Calculation Report** button opens a printable calculation report,
which can also be saved as PDF through the browser print dialogue.

### Analytical Calculations

This tab provides the traceable calculation sheet behind the summary results. It
shows the formulas, numerical substitutions, design actions, resistances,
utilization ratios, and relevant intermediate results. Use it to verify how a value
was obtained, investigate a failed check, or independently review the calculation.

Press **Ctrl+F** to display the search controls. The search box can locate terms such
as `VEd`, `As,req`, `punching`, or `sliding`; use **Next** and **Previous** to move
between matches. Press **Esc** to close the search bar.

### Output Graph

This tab is populated after a successful design and opens automatically when the
calculation finishes. Use its sub-tabs to review the graphical output:

- **Reinforcement:** foundation plan and X-X section showing the designed bottom
  reinforcement and its layer arrangement.
- **Moment X / Moment Y:** bending-moment diagrams along the foundation length and
  width respectively.
- **Shear X / Shear Y:** shear-force diagrams along the foundation length and width
  respectively.

The action diagrams use the analysed curves generated by the FoundationDesign
calculation engine. Each diagram includes an aligned pad and column elevation so the
curve can be related to the physical foundation and column position. Values are
marked at the left and right pad ends and at both column faces. Moments are displayed
in kNm, shear forces in kN, and positions in m; the underlying SI results are
converted from N.m and N for display.

Changing an input clears the action diagrams and removes the designed reinforcement
from the output preview. Select **Run Design** again to regenerate current results.

Shows the designed reinforcement after calculation:

- red lines: X-direction bottom reinforcement;
- green lines/circles: Y-direction bottom reinforcement;
- **X LOWER:** X bars form the lower bottom layer;
- **Y UPPER:** Y bars form the upper bottom layer.

Bar callouts use notation such as `H16mm @ 200 mm c/c`.

## 6. Worked example

This example uses the values loaded by **Restore Defaults**. It is intended to
demonstrate the program workflow, not to define suitable values for a real project.
Project inputs must be confirmed by the responsible structural and geotechnical
engineers.

### 6.1 Example Input Data

Enter the following values, or select **Restore Defaults** to load them.

The following three tables mirror the groups and field order displayed in the
**Input Data** tab. Enter only the number shown; the units are already identified by
each field label in the program.

#### Geometry & Layout — Input Data example

| Input field shown in the tab | Value to enter |
|---|---:|
| Foundation length (mm) | 2500 |
| Foundation width (mm) | 2500 |
| Column length (mm) | 400 |
| Column width (mm) | 400 |
| Column centre, X (mm) | 1250 |
| Column centre, Y (mm) | 1250 |
| Foundation thickness (mm) | 650 |
| Soil depth above foundation (mm) | 0 |

#### Soil & Material Properties — Input Data example

| Input field shown in the tab | Value to enter |
|---|---:|
| Soil bearing capacity (kN/m²) | 200 |
| Soil unit weight (kN/m³) | 18 |
| Concrete unit weight (kN/m³) | 24 |
| Concrete strength, fck (N/mm²) | 30 |
| Steel yield strength, fyk (N/mm²) | 500 |
| Concrete cover (mm) | 40 |
| Initial bar diameter X (mm) | 16 |
| Initial bar diameter Y (mm) | 16 |

#### Applied Column Loads & Moments — Input Data example

| Input field shown in the tab | Value to enter |
|---|---:|
| Permanent axial load (kN) | 800 |
| Imposed axial load (kN) | 300 |
| Permanent horizontal load X (kN) | 0 |
| Imposed horizontal load X (kN) | 0 |
| Permanent horizontal load Y (kN) | 0 |
| Imposed horizontal load Y (kN) | 0 |
| Permanent moment X (kNm) | 0 |
| Imposed moment X (kNm) | 0 |
| Permanent moment Y (kNm) | 0 |
| Imposed moment Y (kNm) | 0 |

The plan preview should show a square 2500 mm pad with the 400 mm square column at
its centre. The section should show a 650 mm thick pad with no soil above it. After
checking the preview, select **Run Design**.

### 6.2 Example Design Results

The two example tables below use the same titles and columns as the **Design
Results** tab. Entries marked *calculated by program* must be read from the result of
**Run Design**; they are not fixed example assumptions.

#### Calculated Structural Values & Forces

| Item Description | Calculated Value | Unit |
|---|---:|---|
| Concrete self-weight | 15.60 | kN/m² |
| Soil self-weight | 0.00 | kN/m² |
| Minimum required area | approximately 5.97 | m² |
| Design moment X (Med,x) | *calculated by program* | kNm |
| Design moment Y (Med,y) | *calculated by program* | kNm |
| Required steel X (As,req,x) | *calculated by program* | mm²/m |
| Required steel Y (As,req,y) | *calculated by program* | mm²/m |

#### Eurocode Design Checks Summary

| Design Check | Status | Calculated Action / Demand | Allowable Limit / Resistance |
|---|:---:|---|---|
| Bearing pressure (SLS) | PASS/FAIL | Maximum service pressure, qEd | Allowable pressure, qallow |
| Flexural reinforcement X | PASS/FAIL | Required steel, As,req,x | Provided steel, As,prov,x |
| Flexural reinforcement Y | PASS/FAIL | Required steel, As,req,y | Provided steel, As,prov,y |
| Transverse shear X | PASS/FAIL | Design shear action, VEd,x | Concrete shear resistance, VRd,c,x |
| Transverse shear Y | PASS/FAIL | Design shear action, VEd,y | Concrete shear resistance, VRd,c,y |
| Punching shear at column face | PASS/FAIL | Punching demand, vEd | Maximum resistance, vRd,max |
| Punching shear at 1d | PASS/FAIL | Punching demand, vEd | Punching resistance, vRd,c |
| Punching shear at 2d | PASS/FAIL | Punching demand, vEd | Punching resistance, vRd,c |
| Sliding resistance | PASS/FAIL | Applied action, HEd | Sliding resistance, HRd |

The program supplies the numerical values. Confirm every row individually; do not
assume the design is satisfactory merely because most rows show `PASS`.

### 6.3 Example Analytical Calculations

Open **Analytical Calculations** to see the derivation behind the summary. For the
example input, useful review searches include:

- `bearing` to find the service pressure calculation and allowable pressure;
- `Med,x` and `Med,y` to find the design bending moments;
- `As,req` to find required reinforcement and the reinforcement comparison;
- `VEd` to find one-way and punching-shear actions;
- `sliding` to find the horizontal-action and friction-resistance comparison.

A calculation entry is presented in the general form:

```text
symbol = formula
       = numerical substitution
       = calculated result and unit
utilization = demand / resistance
status = PASS or FAIL
```

Use this tab to confirm that the dimensions, loads, load factors, effective depths,
and units used by the calculation agree with the intended design basis.

### 6.4 Example Output Graph

The **Output Graph** tab opens after the example calculation. Review each sub-tab:

- **Reinforcement:** the plan shows X-direction bottom bars in red and Y-direction
  bars in green. The X-X section identifies the lower and upper bottom layers and
  displays bar diameter and spacing callouts.
- **Moment X:** shows the bending-moment curve along the 2.5 m foundation length,
  aligned with the centered 0.4 m column. Read the values in kNm at both pad ends
  and both column faces.
- **Moment Y:** shows the equivalent curve along the 2.5 m foundation width. For
  this square, concentrically loaded example, the X and Y response should be
  geometrically comparable.
- **Shear X:** shows shear force in kN along the foundation length, including values
  at the two ends and column faces.
- **Shear Y:** shows shear force in kN along the foundation width, with the same
  reference locations.

For an eccentric column or non-zero applied moments, the diagrams need not be
symmetrical. Check that the column shown above each graph matches the column position
entered in **Input Data**.

## 7. Design checks

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

## 8. Revising a failed design

Depending on the governing check, typical engineering responses include:

- bearing failure: increase plan dimensions or reassess the allowable pressure;
- flexural failure: increase reinforcement or foundation depth;
- one-way or punching-shear failure: increase foundation depth and rerun the design;
- sliding failure: investigate increased dead load, a shear key, revised interface
  parameters, or another engineered resistance mechanism.

Do not change values merely to obtain `PASS`. Revisions must be compatible with the
geotechnical report, detailing rules, constructability, durability, and applicable
codes.

## 9. Printing and saving

After running the design:

1. Open **Design Results**.
2. Select **Print / Save Calculation Report**.
3. In the browser print dialogue, select a printer or **Save as PDF**.

The report includes inputs, derived values, the check summary, and detailed
analytical calculations. Review the PDF before issue.

## 10. Important limitations

- Confirm all loads, axes, signs, units, material properties, cover, and soil values.
- The program does not replace project-specific geotechnical assessment.
- Check reinforcement anchorage, laps, development length, edge detailing, local
  column transfer, durability, crack control, construction tolerances, and any
  seismic requirements separately where applicable.
- Numerical values can differ slightly from hand calculations because the program
  rounds some intermediate results.
- Final calculations and drawings should be reviewed and approved by a qualified
  engineer before construction.

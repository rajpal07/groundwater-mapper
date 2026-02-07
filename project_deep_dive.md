# Groundwater Mapper & Smart Excel Export: Technical Deep Dive

## 1. Project Overview
This project is a sophisticated **Hydro-Geological Intelligence Platform** designed to automate the processing, analysis, and visualization of complex groundwater data. It bridges the gap between raw Excel datasets and actionable geospatial insights.

The system is built on two core pillars:
1.  **Groundwater Elevation Mapper**: An AI-assisted mapping engine that turns sparse well data into accurate, interactive contour maps, capable of handling complex aquifer stratification ("nested wells").
2.  **Smart Excel Export**: An automated compliance tool that intelligently parses human-readable "threshold rules" (e.g., "pH 6.5-8.5") and applies conditional formatting to raw data sets for reporting.

---

## 2. Core Feature: The Groundwater Map Engine

### A. The "Impossible Physics" Engine (Aquifer Stratification)
**The Problem**: In hydrogeology, multiple wells often exist at the precise same geographic location (same x,y) but tap into different aquifers (different depths). Standard interpolation algorithms crash or produce garbage when fed two different values for the same coordinate.

**Our Solution (`src/aquifer.py`)**:
We developed a specialized **"Jaggedness Intelligence"** algorithm to detect and resolve this:
1.  **Location Clustering**: The system scans the dataset for "Impossible Physics"—locations where $\Delta(x,y) \approx 0$ but $\Delta(Value) \neq 0$.
2.  **Pattern Analysis**: It analyzes the `Well ID` strings at these collision points using regex to detect naming patterns (e.g., endings like "A/B/C", "Deep/Shallow", "U/L").
3.  **Dynamic Layering**: The system automatically splits the single dataset into multiple "Aquifer Layers" (e.g., Layer A, Layer B).
4.  **Context Preservation**: Crucially, "Singleton Bores" (wells that exist only in one layer or have no specific mapping) are intelligentlly preserved and propagated to relevant layers to provide regional context, ensuring no data is hidden.

### B. Coordinate Intelligence (Auto-UTM)
**The Logic (`src/geo.py`)**:
The system acts as a smart GIS analyst. It does not blindly accept coordinates.
1.  **Heuristic Scanning**: Checks columns for keywords like "MGA", "Zone", "Easting".
2.  **Auto-Detection**: If distinct UTM zones are not specified, it calculates the mathematical centroid of the data.
3.  **Land-Mask Validation**: It projects the data using various candidate zones (54S, 55S, 56S) and checks if the resulting Lat/Lon points fall on **Land** or **Ocean**. The zone that places points on solid ground is selected automatically.

### C. The Hybrid Interpolation Engine
**The Backend Process (`src/data.py`)**:
To create the "Heatmap" and "Contour Lines", we use a two-stage hybrid approach for maximum accuracy and aesthetics:
*   **Linear Interpolation (`scipy.interpolate.griddata`)**: Used for the **Color Fill** and **Flow Arrows**. This is strict and scientifically accurate—it never invents data outside the bounds of the wells (Convex Hull).
*   **Cubic/RBF Interpolation**: Used optionally for **Contour Lines** to produce smooth, non-jagged curves that look professional, filling gaps intelligently where data is sparse.

### D. Label Physics Engine (Force-Directed Layout)
**The Problem**: In dense clusters of wells, text labels overlap each other and, critically, obscure the data points (dots) themselves, making the map unreadable.

**So Solution (`src/templates.py`)**:
We implemented a custom **Physics Simulation** running directly in the browser via JavaScript.
1.  **Gravity (Anchor Force)**: Each label is attached to its well by a "weak spring". It *wants* to sit on top of the dot, but is allowed to drift if pushed.
2.  **Marker Repulsion**: Every data point emits a "Repulsive Force Field". If a label tries to sit on top of *any* dot (not just its own), it is violently pushed away. This guarantees **Zero Marker Coverage**.
3.  **Collision Repulsion**: Labels push against each other. If Label A touches Label B, they shove apart.
4.  **Visual Association**: When a label is pushed far from its home, a **"Halo" Leader Line** (White stroke + Black core) automatically draws itself to connect the label to the dot, ensuring zero ambiguity even in chaos.

---

## 3. Core Feature: Smart Excel Export

### The Concept
A "Context-Aware" formatting engine (`smart_excel_utils.py`). Unlike standard conditional formatting which requires manual setup, this tool **Reads** the Excel header rows like a human would.

### The Deep Logic
1.  **Threshold Detection**: The backend scans the top 20 rows of any sheet. It looks for "Color Clusters"—rows that are heavily highlighted, indicating they contain guideline rules (e.g., EPA limits).
    *   *Note*: This is heuristic. If the auto-detection misses a row (e.g., due to subtle formatting), the **User Interface allows Manual Override**, giving the user full control to force specific rows as thresholds.
2.  **Regex Parsing**: It extracts logic from text strings:
    *   `"6.5 - 8.5"` $\rightarrow$ **Range Rule** (Min 6.5, Max 8.5)
    *   `"> 500"` $\rightarrow$ **Exceedance Rule** (Min 500)
    *   `"< 1"` $\rightarrow$ **Lower Limit Rule** (Max 1)
3.  **Ambiguity Resolution**:
    *   *The "Less Than" Paradox*: Does "5.0" mean "Exceedance > 5" or "Limit < 5"?
    *   The system looks at the **Column Context**. If it sees a Range (6-8) elsewhere, and sees "5", it knows 5 is below the range, so it treats it as a Lower Bound. If it sees "500", it treats it as an Upper Bound.
4.  **Strictest Rule Wins**: If multiple rules apply (e.g., a "Warning" threshold at 5 and a "Danger" threshold at 10), the system scores them by strictness and applies the most critical color.

---

## 4. System Architecture & Backend

### Technology Stack
*   **Frontend**: Streamlit (Python) - Serves the UI.
*   **Data Processing**: Pandas (Dataframes), NumPy (Matrix math for grids).
*   **Geospatial**: PyProj (CRS transformations), Shapely (Geometry).
*   **AI/Parser**: LlamaIndex (LlamaParse) - Used for intelligence extraction from non-standard Excel files.

### Critical Functions
| Function | Module | Description | Backend Action |
| :--- | :--- | :--- | :--- |
| `process_excel_data` | `data.py` | Orchestrator | Loads data, triggers aquifer check, interpolates grids, generates images. |
| `analyze_aquifer_layers` | `aquifer.py` | Intelligence | Clusters (x,y) points, regexes IDs, determines stratification strategy. |
| `apply_thresholds` | `smart_excel_utils.py` | Excel Logic | Opens Excel binary, iterates cell-by-cell, applies Hex color fills based on rules. |
| `inject_controls_to_html` | `templates.py` | UI Injection | Reads the static Map HTML and injects 500+ lines of custom JavaScript for the Compass, Legend, and footer. |

---

## 5. Tools, APIs & Optimization

### External APIs
1.  **Llama Cloud (LlamaParse)**
    *   **The "Why"**: Standard Python libraries (`pandas.read_excel`) fail on messy, human-centric spreadsheets (e.g., merged headers, multiple tables on one sheet, non-standard layouts).
    *   **The Solution**: We treat the Excel file not as a grid, but as a **Document**.
    *   **Workflow**:
        1.  **Upload**: Raw binary Excel is sent to LlamaCloud.
        2.  **Vision/OCR**: LlamaParse analyzes the visual structure of the sheet.
        3.  **Reconstruction**: It returns a clean **Markdown** representation of the tables.
        4.  **Extraction**: `sheet_agent.py` parses this Markdown back into a structured DataFrame.
    *   **Rate Limiting**: **Critical**. The document parsing is expensive. Caching is implemented based on MD5 file hash (`cache_llama_{hash}.md`) to prevent redundant API calls for the same file.
2.  **Google Earth Engine (GEE)**
    *   **Usage**: Provides the Satellite Basemap.
    *   **Authentication**: Supports both Service Account (Secret-based) for Cloud and Local Auth for Dev.
    *   **Optimization**: We use `folium` for the overlay and only fetch standard tiles from GEE. Heavy computation is done locally in Python (SciPy), saving GEE quotas.

### Optimization Status
1.  **Vectorization**: Most geometric operations (`numpy.meshgrid`, `scipy.griddata`) are vectorized 2D array operations. This is $O(1)$ relative to Python loops, making map generation sub-second for typical datasets.
2.  **Fragment Caching**: The Smart Excel Export uses `st.fragment` and `st.cache_data`. When you change a color in the preview, it does **not** reload the file or the entire page. It only re-renders the small table fragment.
3.  **Visual Asset Injection**: Logos and assets are Base64 encoded and embedded directly into the HTML. This makes the Output Map **Offline-Portable**—it has no external dependencies on images or servers.

---

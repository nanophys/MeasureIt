# MeasureIt Plotting Roadmap

## 0. Objectives
- Ship a structured `measureit.plot` package that turns MeasureIt datasets into publication-quality figures with minimal boilerplate.
- Support every sweep style we generate today: `Sweep0D`, `Sweep1D`, `Sweep2D`, `SimulSweep`, and queue-driven runs (sequential sweeps + database hop actions).
- Replace the ad-hoc `examples/content/data processing.ipynb` workflow by turning its logic into reusable, well-tested modules driven by sweep metadata.
- Keep the API ergonomic enough for notebooks (`measureit.plot.x.y(...)`), but cleanly separated so future CLI/GUI visualizers can reuse the same primitives.

## 1. Current Assets & Gaps
- Notebook demonstrates how to:
  - Load datasets via QCoDeS, inspect `dataset.metadata["measureit"]`, and manually build Matplotlib figures.
  - Handle 0D (time series), 1D (single set-parameter), SimulSweep (multiple independent parameters vs time), and 2D (heatmap) plots with one-off scripts.
  - Access metadata helpers (`measureit.visualization.helper.print_metadata`), but there is no higher-level plotting API.
- Metadata is already injected in `RunnerThread` via each sweep’s `export_json` implementation; queue wraps the metadata provider and adds `attributes["launched_by"] = "SweepQueue"`.
- No code currently transforms metadata into plot-ready descriptors, meaning every notebook/result is bespoke.

## 2. Metadata Reference (what we will parse)
- **Common base (`BaseSweep.export_json`)**
  - `class` / `module`
  - `attributes`: `inter_delay`, `save_data`, `plot_data`, `plot_bin`, plus subclass extras.
  - `follow_params`: map `instrument.parameter` → `(instrument_name, instrument_module, instrument_class)`
- **Sweep0D**
  - `set_param`: `None`
  - `attributes.max_time`
- **Sweep1D**
  - `set_param`: instrument metadata + `start`, `stop`, `step`
  - `attributes`: `bidirectional`, `continual`, `x_axis_time`
  - Follow params exclude the driving parameter.
- **Sweep2D**
  - `inner_sweep` + `outer_sweep`: each carries instrument info + `start/stop/step` + `param_key`
  - `attributes.outer_delay`
  - Follow params exclude both sweep axes.
- **SimulSweep**
  - `set_params`: dict keyed by `instrument.parameter`, each with instrument info + `start/stop/step`
  - `attributes`: `bidirectional`, `continual`
  - Follow params exclude all simultaneously driven parameters.
- **Queue metadata augmentation**
  - Additional `attributes["launched_by"] = "SweepQueue"` injected around the inner sweep metadata.
  - Database entries have their own JSON (`DatabaseEntry.export_json`) but no datasets; sweeps produce normal MeasureIt metadata with the added flag.

## 3. Proposed Package Layout (`src/measureit/plot`)
```
measureit/plot/
  __init__.py          # expose high-level API: load, dispatch, shortcuts
  core.py              # Dataset adapters, metadata parsing, PlotContext dataclass
  utils.py             # shared helpers (unit formatting, axis labeling, color maps)
  sweep0d.py           # time-series plotting primitives
  sweep1d.py           # 1D sweep plotting (single + bidirectional)
  sweep2d.py           # 2D heatmaps / contour helpers
  simul.py             # multi-parameter simultaneous sweeps
  queue.py             # orchestrate sequences, combine multiple runs
  styles.py            # centralize Matplotlib style defaults, theme hooks
  exporters.py         # optional saving to PNG/SVG/HTML (future)
```
- Add `measureit/plot/__init__.py` re-exporting endpoints so users can call `from measureit.plot import sweep, queue` or `measureit.plot.auto_plot(dataset)`.
- Update top-level `src/measureit/__init__.py` to import and attach `plot` for `measure.plot.xxx` usage without breaking existing imports.

## 4. Core Architecture
1. **Dataset Intake**
   - `PlotDataset` wrapper that accepts a `qcodes.dataset.data_set.DataSet` or run ID and resolves to a dataset with metadata + parameter data (lazy loaded).
   - Provide factory `from_run_id`, `from_path`, or pass dataset directly.
2. **Metadata Parser**
   - Parse `dataset.metadata["measureit"]` (JSON string) into a typed `SweepMetadata` dataclass with fields `sweep_type`, `attributes`, `axes`, `follow_params`, `queue_info`.
   - Validate required keys per sweep type; raise informative error if metadata missing/corrupt.
   - Detect queue origin via `attributes.get("launched_by")` and encapsulate in `QueueContext` with optional queue position info (requires future work to log order).
3. **Data Alignment Utilities**
   - Utilities to extract setpoint arrays, measured signals, and reshape them based on metadata.
   - Handle bidirectional sweeps by splitting dataset into forward/back segments (1D & Simul).
   - 2D helper to reshape flattened arrays into meshgrid based on unique (outer, inner) combos; fallback to `griddata` when irregular.
4. **Plot Builders**
   - For each sweep type deliver both low-level primitives and high-level convenience:
     - `plot_time_series(context, params, *, ax=None, style=...)`
     - `plot_1d_traces(context, measured_params=None, sharex=True, bidirectional_style=...)`
     - `plot_heatmap(context, param, interpolation='auto')`
     - `plot_simul_matrix(context, layout='auto')`
   - Each function should accept optional Matplotlib `Axes`/`Figure` to integrate into user layouts and return the axes for further customization.
   - Provide `auto_plot(dataset, *, style='default')` that dispatches to the right builder(s) using metadata.
5. **Queue Visualization**
   - Introduce collector that, given a list of run IDs (possibly from queue export JSON), builds composite dashboards (e.g., timeline of sweeps, compare results).
   - For initial scope: provide `plot_queue_runs(run_ids, layout='tabbed')` generating Matplotlib figure grid or return contexts for user iteration.
   - Later phase: integrate with interactive viewer (Panel/Holoviz) once static basics ship.
6. **Styling & Metadata Display**
   - Centralize default styles (line colors, marker shapes for forward/back sweeps, color maps for 2D) in `styles.py`.
   - Add helper to annotate plots with sweep metadata: axis labels from param names/units, titles with run IDs and attributes, text boxes summarizing follow params.
   - Provide optional `show_metadata(ax, context)` to embed metadata in the plot.

## 5. Implementation Milestones
1. **Foundations**
   - Create package skeleton (`plot/__init__.py`, `core.py`, `utils.py`).
   - Implement `SweepMetadata` + parser functions with unit tests covering all sweep types using fixture JSON from existing export code.
   - Build `PlotDataset` wrapper fetching parameter data lazily (reuse QCoDeS `.get_parameter_data()`).
2. **0D Support**
   - Implement `sweep0d.plot_time_series` with metadata-driven axis labeling (time on x, follow params on y).
   - Unit tests: synthetic dataset objects verifying splitting & labeling.
3. **1D Support**
   - Implement forward/back trace splitting + optional overlay/dual-subplot outputs.
   - Provide `auto_plot` dispatch for 0D + 1D; update tests.
4. **SimulSweep Support**
   - Build matrix plotting (rows = follow params, cols = driving params) with metadata-provided step info.
   - Handle bidirectional fallback similar to 1D (per column).
5. **2D Support**
   - Implement heatmap/contour plot builder; choose heuristics for interpolation (use `griddata` only if SciPy present, fallback to `pcolormesh` with NaN mask).
   - Support selecting specific follow param and customizing colormap.
6. **Queue Integrations (Phase 1)**
   - Expose helper that takes queue JSON export or list of run IDs and returns list of `PlotDataset` instances with metadata including `launched_by` flag.
   - Provide convenience `plot_queue_sequence(queue_export)` generating subplot grid for each dataset in order.
7. **API Surface Stabilization**
   - Add top-level exports: `measureit.plot.load`, `measureit.plot.auto_plot`, `measureit.plot.sweep0d`, etc.
   - Update `src/measureit/__init__.py` to `from . import plot as plot` to enable `measure.plot` alias.
   - Write usage documentation referencing new API, refactor notebook to call new functions (converted to `.py` example or simplified notebook).
8. **Testing & CI**
   - Build fixtures using tiny mock datasets (leveraging qcodes `LoopDataSet` or stand-in objects) to avoid heavy DB dependencies.
   - Snapshot-test Matplotlib figures using `matplotlib.testing.compare` or hash-based check to ensure layout consistency (optional; at minimum ensure data arrays returned correctly).
   - Add metadata parser regression tests to guard against future export changes.
9. **Documentation**
   - Create Sphinx/Markdown guides under `docs/plotting/` with sections per sweep type.
   - Provide quick-start snippet showing `auto_plot(load_by_id(5))` usage.
  - Update README highlights (new “Data Visualization” bullet).
  - Add `measureit.plot.db.overview()` (or similar) that visualizes database contents: summaries of experiments, dataset metadata heatmaps, run timelines. Initially build a static Matplotlib/Plotly figure showing counts per experiment and run metadata; later integrate into Dash dashboard.

## 6. Dependencies & Compatibility Considerations
- Matplotlib already used; confirm version compatibility (≥3.6?). Document optional SciPy dependency for smooth 2D interpolation; degrade gracefully otherwise.
- Ensure no hard dependency on Qt event loop (plots run in headless mode). All functions should respect existing `MPLBACKEND` environment settings.
- Keep QCoDeS imports lazy inside functions to avoid heavy import cost for users doing offline analysis without hardware drivers.
- Offer dataset-like protocol so advanced users can supply custom data structures if metadata structure matches (e.g., saved JSON + CSV).
- Treat Dash/Plotly as an **optional** extra (`pip install measureit[plot]`). Guard imports so the core package remains lightweight and doesn’t conflict with PyQtGraph/QCoDeS environments. Provide clear error messages or fallbacks when the optional deps are missing.

## 7. Decisions & Follow-Ups
- **Plotting backend**: adopt Plotly Dash for the interactive UX. Primary implementation should target Dash components and ensure the metadata parsing feeds Dash layouts.
- **Queue visualizations**: include aggregated metadata such as database transitions; design the queue dashboard to highlight each sweep segment plus the DB context.
- **Caching**: no extra metadata caching required—parsing on demand is acceptable.
- **Naming**: stick with `measureit.plot`; no additional aliases needed.

## 8. Deliverables Timeline (draft)
1. Week 1: Foundations + metadata parser + 0D/1D support.
2. Week 2: Simul + 2D, integrate auto dispatch, initial docs.
3. Week 3: Queue helpers, finalize API, convert notebook example, expand tests.
4. Week 4: Polish (styling, metadata annotations, docs review), prep minor release (e.g., `0.x.y`).

Progress should be tracked by converting this TODO into GitHub issues / milestones once vetted.

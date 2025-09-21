.. _gettingstarted:

Getting Started
===============

Installation
------------

- Python 3.8–3.11 supported.
- Install the core package:

  - ``pip install MeasureIt``

- Optional extras:

  - Drivers (NI/Zurich Instruments): ``pip install "MeasureIt[drivers]"``
  - Jupyter/Dev/Docs: see extras in ``pyproject.toml`` or README.

Launch the GUI
--------------

- After install, run: ``measureit-gui``
- The first launch creates a per-user data directory (MeasureItHome) automatically.

Data Directory (MeasureItHome)
------------------------------

- If the environment variable ``MeasureItHome`` is set, that path is used.
- Otherwise, a sensible per-user location is created using platform conventions
  (e.g., ``~/.local/share/MeasureIt`` on Linux, ``%APPDATA%\MeasureIt`` on Windows).
- Subfolders are prepared automatically: ``Databases/``, ``Origin Files/``, ``cfg/``, ``logs/``.

Jupyter Usage
-------------

- Use Qt integration: start your notebook cell with ``%gui qt`` before starting sweeps.
- Programmatic example (headless plotting):

  .. code-block:: python

     from MeasureIt import Sweep1D
     from qcodes.instrument_drivers.mock_instruments import MockParabola

     inst = MockParabola(name="demo")
     s = Sweep1D(inst.x, start=0.0, stop=1.0, step=0.1, plot_data=False)
     s.follow_param(inst.parabola)
     s.start()

Example notebooks
-----------------

- See the repository's ``examples/`` folder (e.g., ``examples/content/quick start.ipynb``).


.. _gettingstarted:

Getting Started
===============

Installation
------------

- Python 3.8â€“3.11 supported.
- Install the core package:

  - ``pip install measureit``

- Optional extras:

  - Drivers (NI/Zurich Instruments): ``pip install "measureit[drivers]"``
  - Jupyter/Dev/Docs: see extras in ``pyproject.toml`` or README.

Data Directory
-----------------

- MeasureIt chooses a per-user location automatically using ``platformdirs`` (for example, ``~/.local/share/measureit`` on Linux, ``~/Library/Application Support/measureit`` on macOS, or ``%APPDATA%\measureit`` on Windows).
- Override the location at runtime via ``measureit.set_data_dir("/path/to/data")`` or set the ``MEASUREIT_HOME`` environment variable before importing MeasureIt.
- Legacy ``MeasureItHome`` environment variables continue to work, but new deployments should prefer ``MEASUREIT_HOME``.
- Subfolders such as ``Databases/``, ``Origin Files/``, ``cfg/``, and ``logs/`` are created on demand when accessed.

Jupyter Usage
-------------

- Use Qt integration: call ``measureit.tools.ensure_qt()`` before starting sweeps from a notebook.

  .. code-block:: python

     from measureit.tools import ensure_qt
     ensure_qt()  # set MEASUREIT_FORCE_QT=1 to bypass the probe once configured
- On WSL, if the probe warns about the XCB plugin, install the required Qt packages:

  .. code-block:: bash

     sudo apt install libxcb-xinerama0 libxkbcommon-x11-0 libqt5gui5 libegl1 libopengl0
- Programmatic example (headless plotting):

  .. code-block:: python

     from measureit import Sweep1D
     from qcodes.instrument_drivers.mock_instruments import MockParabola

     inst = MockParabola(name="demo")
     s = Sweep1D(inst.x, start=0.0, stop=1.0, step=0.1, plot_data=False)
     s.follow_param(inst.parabola)
     s.start()

Example notebooks
-----------------

- See the repository's ``examples/`` folder (e.g., ``examples/content/quick start.ipynb``).

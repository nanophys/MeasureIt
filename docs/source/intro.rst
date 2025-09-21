Introduction
============

MeasureIt is a QCoDeS-based measurement toolkit for condensed matter experiments,
providing threaded data acquisition, live plotting, and a PyQt5 GUI.

Highlights
----------

- Sweep abstractions: 0D/1D/2D sweeps with live data and saving through QCoDeS.
- Qt-friendly plotting: high-performance real-time plotting via pyqtgraph.
- GUI: configure stations, follow parameters, and run sweeps interactively.
- Extensible drivers: integrate lab hardware via QCoDeS and community drivers.

Quick Start
-----------

- Install: ``pip install MeasureIt`` (see :ref:`gettingstarted` for extras).
- Launch GUI: ``measureit-gui``.
- Use in notebooks: enable Qt with ``%gui qt`` then start sweeps.

Contributing
------------

We welcome issues and pull requests. See the README for development setup.

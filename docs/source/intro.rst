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

- Install: ``pip install measureit`` (see :ref:`gettingstarted` for extras).
- Launch GUI: ``measureit-gui``.
- Use in notebooks: call ``measureit.tools.ensure_qt()`` to enable Qt before starting sweeps. Under WSL, install Qt's XCB dependencies if the probe warns about them (e.g. ``sudo apt install libxcb-xinerama0 libxkbcommon-x11-0 libqt5gui5 libegl1 libopengl0``) or set ``MEASUREIT_FORCE_QT=1`` once your Qt setup is confirmed.

Contributing
------------

We welcome issues and pull requests. See the README for development setup.

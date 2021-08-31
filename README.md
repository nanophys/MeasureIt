# MeasureIt [![Documentation Status](https://readthedocs.org/projects/measureituw/badge/?version=latest)](https://measureituw.readthedocs.io/en/latest/?badge=latest)

Measurement software based on [QCoDeS](https://qcodes.github.io/), developed in University of Washington physics.

## Build the documentation

To build the documentation, first install Sphinx and Sphinx-rtd-theme:

```bash
pip install sphinx
pip install sphinx-rtd-theme
```

The documentation is located directory `docs/source`. A `makefile` or `make.bat` is set up for quick building:

For HTML version, go to the directory `docs/source` and

```bash
make html
```

which generates the mainpage, `index.html` in `docs/source/_build/html`.

For pdf version, go to the directory `docs/source` and

```bash
make latex
```

then go to `docs/source/_build/latex`, and with a proper latex version, a makefile is automatically generated. 

```bash
make
```

This will build the pdf version of the documentation.

## External links

[David Cobden's lab](https://sites.google.com/uw.edu/nanodevice-physics)

[Xiaodong Xu's lab](https://sites.google.com/uw.edu/xulab)

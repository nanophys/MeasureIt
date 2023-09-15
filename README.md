# MeasureIt [![Documentation Status](https://readthedocs.org/projects/measureituw/badge/?version=latest)](https://measureituw.readthedocs.io/en/latest/?badge=latest)

Measurement software based on [QCoDeS](https://qcodes.github.io/), developed in University of Washington physics.

## Build the documentation

To build the documentation, first install requirements(if GUI has already successfully run, only `sphinx` and `sphinx-rtd-theme` are needed):

```bash
pip install -r requirements_doc.txt
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

## Installation

- Download Anaconda3 https://www.anaconda.com/download/
- Download Git https://git-scm.com/download/win
- Download and install the NI DAQmx drivers at 'http://www.ni.com/en-us/support/downloads/drivers/download/unpackaged.ni-daqmx.291872.html'
- Download and install the NI VISA package at 'http://www.ni.com/download/ni-visa-18.5/7973/en/'

- To install QCoDeS, either:
    1) (RECOMMENDED) run the following to install a non-editable version
      - conda update -n base -c defaults conda
      - conda create --name qcodes python=3.9 (Python 3.10 breaks nidaqmx-python as of now)
      - conda activate qcodes
      - conda install -c conda-forge qcodes
    2) Run the following to install an editable version of QCoDeS
      - Download QCoDeS repository 'git clone https://github.com/QCoDeS/Qcodes.git' (will download QCoDeS repository at current location)
      - From Anaconda Prompt, move into QCoDeS repository, and run:
      - conda update -n base -c defaults conda
      - conda env create -f environment.yml
      - conda activate qcodes
      - pip install qcodes
After installing QCoDeS, install the rest of the packages
- conda config --add channels conda-forge 
- conda install nidaqmx-python jupyterlab conda-build pyqt
- Download this repository 'git clone https://github.com/nanophys/MeasureIt.git'
- Set 'MeasureItHome' to base folder in the MeasureIt repository as an environment variable in your Windows system.
- From Anaconda Prompt, move into MeasureIt repository, and run:
    - conda activate qcodes
    - python setup.py

To install the contributor drivers (such as the Oxford IPS120):
- Download repository, 'git clone https://github.com/QCoDeS/Qcodes_contrib_drivers.git'
- Move into the repository directory, and run 'conda develop .'
- You can now directly access the module by calling 'import qcodes_contrib_drivers' in python scripts

To create a desktop icon:
- Add the following to PATH (under system's environment variables):
    - "%USERPROFILE%\anaconda3"
    - "%USERPROFILE%\anaconda3\Scripts"
    - "%USERPROFILE%\anaconda3\condabin"
- Right-click 'MeasureIt.bat' in the repository, and change the second line to match the user's path to the repository
- Right-click 'MeasureIt.bat' and click 'Create shortcut' and drag the new shortcut to the desktop

TO UPDATE:
- To update MeasureIt, open the terminal, move into the MeasureIt base directory and run:
    - git pull
- To update QCodes_contrib_drivers, open the terminal, move into the Qcodes_contrib_drivers base directory and run:
    - git pull
- To update a non-editable installation of QCoDeS from Anaconda Prompt:
    - conda update -n base -c defaults conda  (not strictly required but is best practice)
    - conda activate qcodes
    - conda update qcodes
- To update an editable installation of QCoDeS: from Anaconda Prompt, move into QCoDeS repository, and run:
    - conda update -n base -c defaults conda  (not strictly required but is best practice)
    - git pull
    - conda activate qcodes
    - conda env update --file environment.yml
    - conda develop .

## External links

[David Cobden's lab](https://sites.google.com/uw.edu/nanodevice-physics)

[Xiaodong Xu's lab](https://sites.google.com/uw.edu/xulab)

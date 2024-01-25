# MeasureIt [![Documentation Status](https://readthedocs.org/projects/measureituw/badge/?version=latest)](https://measureituw.readthedocs.io/en/latest/?badge=latest)

Measurement software based on [QCoDeS](https://qcodes.github.io/), developed in University of Washington physics.

## Installation & Updating

The following downloads are required/strongly recommended:
- A version of Conda (see below)
- Git 
- NI DAQmx drivers: http://www.ni.com/en-us/support/downloads/drivers/download/unpackaged.ni-daqmx.291872.html
- NI VISA package: http://www.ni.com/download/ni-visa-18.5/7973/en/

It is useful to first create a conda environment to manage all the required 
packages for this package to work. First, download some form of conda 
(Miniforge3 is strongly recommended since it comes with mamba):

* Download Miniforge: https://github.com/conda-forge/miniforge
* Download Anaconda: https://www.anaconda.com/download/
* Download Miniconda: https://docs.conda.io/projects/miniconda/en/latest/miniconda-install.html

### Environments and Mamba

Since this is a package that will be shared across many computers at the UW, it 
is important that each one use the same versions of python packages so that 
errors can be isolated and taken care of more easily. A great way of doing this 
is by using conda environments to manage the packages we have available and 
standardizing the packages we use by storing references to them in a shared 
file. In this package, this is simply titled "environment.yml". Updating 
packages from .yml files can take a while though, but installing mamba can make 
it much faster. This is just a re-working of some of the conda functions using 
C/C++ to make them much faster. Using mamba is simple: you simply replace 
"conda" with "mamba" in any commands and it will execute much faster. As 
previously mentioned, Miniforge3 comes with mamba already, so no work needs to 
be done if you install this from the get go. Alternatively, you can follow the 
deprecated method of adding mamba to an existing install of conda by running

```
(base) $ conda install -n base --override-channels -c conda-forge mamba 'python_abi=*=*cp*'
```

### Create qcodes environment using environment.yml file

You can create a new environment with all the necessary packages for MeasureIt 
by stepping into the MeasureIt directory and simply running

```
(base) $ conda env create -f environment.yml
```

This will create an environment called "qcodes" for you containing all the 
dependency packages for MeasureIt. NOTE: you will still need to manually
install the "MeasureIt" package (and, for the time being, MultiPyVu) even when
following this method until MeasureIt is officially packaged on pypi.

### Create qcodes environment from scratch

To create a new environment from scratch, you can do the following. After 
downloading your preferred conda version, create a new environment. In this 
example, we've named the environment "qcodes" and given it Python v3.9:

```
(base) $ conda update conda
(base) $ conda create --name qcodes python=3.9
```

Activate the qcodes environment with

```
(base) $ conda activate qcodes
```

To install the MeasureIt package, begin by installing pip (>=23.1) to your 
environment:

```
(base) $ conda activate qcodes
(qcodes) $ conda install pip
```

### Installing the MeasureIt package

Since MeasureIt is still under construction and remains for UW Physics use, it
has not been published to PyPI and cannot be installed by simply running a pip 
install command yet. As such, we first need to download the package contents
using git:

Download Git: https://git-scm.com/download/win

1) Navigate to https://github.com/nanophys/MeasureIt and clone the repository from the browser, or
2) run `$ git clone https://github.com/nanophys/MeasureIt` while in the base directory of your machine.

To begin, we want to use pip to install the developmental build of MeasureIt to
the qcodes environment. Do this by navigating to the folder "MeasureIt" in your
command line. This folder should contain a folder named "src" and a file named 
"pyproject.toml". Next, run the following commands:

```
(base) $ conda activate qcodes
(qcodes) $ python -m pip install --no-deps --editable . --config-settings editable_mode=strict
```

This will use pip to install the package as an importable package when using 
your qcodes conda environment. The --no-deps flag prevents installation of the 
dependencies, or packages which are required for running the MeasureIt package. 
We want to be able to install these separately in the next step. The --editable 
flag allows for your version to respond to changes to your version of MeasureIt, 
which is helpful while it remains under development. The last flag is just a 
random thing fom stackexchange to hopefully make it run better for VSCode. 
Next, we want to install the necessary packages to our envirnment, which we do
with an environment.yaml file to make sure that each computer using MeasureIt 
runs with the same versions of packages. To do this, navigate again to the 
"MeasureIt" folder which contains "environment.yaml" and run:

```
(qcodes) $ conda env update --file environment.yaml
(qcodes) $ python -m pip install --no-deps MultiPyVu==1.2.0
(qcodes) $ python -m pip install --no-deps nidaqmx==0.6.2
```

Most of tha packages are reasonable, but there is an issue with installing 
MultiPyVu for OS other than Windows via pip, so until that issue can be fixed 
this is the workaround.

If packages need to updated at any point, navigate to the MeasureIt directory
and run:

```
(qcodes) $ conda env update --file environment.yaml --prune
(qcodes) $ python -m pip install --no-deps --editable . --config-settings editable_mode=strict
(qcodes) $ python -m pip install --no-deps MultiPyVu==1.2.0
(qcodes) $ python -m pip install --no-deps nidaqmx==0.6.2
```

This udpates all the packages listed in the environment.yaml file and then 
installs the other required dependencies.

### Updating MeasureIt with git

To update MeasureIt to the newest version on git, navigate to "MeasureIt" in 
your command line and run:

```
$ git pull
```

To update required packages, navigate to "MeasureIt" in your command line and 
run:

```
(qcodes) $ conda env update --file environment.yaml --prune
(qcodes) $ python -m pip install --no-deps --editable . --config-settings editable_mode=strict
(qcodes) $ python -m pip install --no-deps MultiPyVu==1.2.0
```

The --prune flag cuts installations not explicitly listed in environment.yaml, 
which includes MeasureIt and MultiPyVu.

### Creating a desktop icon:

- Add the following to PATH (under system's environment variables):
    - "%USERPROFILE%\anaconda3"
    - "%USERPROFILE%\anaconda3\Scripts"
    - "%USERPROFILE%\anaconda3\condabin"
- Right-click 'MeasureIt.bat' in the repository, and change the second line 
to match the user's path to the repository
- Right-click 'MeasureIt.bat' and click 'Create shortcut' and drag the new 
shortcut to the desktop

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

## External links

[David Cobden's lab](https://sites.google.com/uw.edu/nanodevice-physics)

[Xiaodong Xu's lab](https://sites.google.com/uw.edu/xulab)

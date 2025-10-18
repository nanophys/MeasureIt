# MeasureIt [![Documentation Status](https://readthedocs.org/projects/measureituw/badge/?version=latest)](https://measureituw.readthedocs.io/en/latest/?badge=latest)

Measurement software based on [QCoDeS](https://qcodes.github.io/), developed in University of Washington physics.

## Community information
[Join our slack channel!](https://join.slack.com/t/measureit-workspace/shared_invite/zt-2ws3h3k2q-78XfSUNtqCjSUkydRW2MXA)

## High-Level Design

MeasureIt is a measurement software package built on top of QCoDeS (Quantum Computing Data Structures) for physics experiments. The architecture follows these key patterns:

### Core Architecture
- **Sweep-based Measurement System**: The core abstraction is the `BaseSweep` class with specialized implementations (`Sweep0D`, `Sweep1D`, `Sweep2D`) for different dimensional measurements
- **Qt-based Threading**: Uses PyQt5 with separate threads for data acquisition (`RunnerThread`) and plotting (`PlotterThread`) 
- **Driver Layer**: Custom instrument drivers in the `Drivers/` module that interface with various lab equipment
- **Notebook Workflow**: Designed for Jupyter/CLI usage; PyQt5 powers background threading and signaling
- **Data Management**: Integration with QCoDeS for data storage and experiment management

### Key Components
- **Base Classes**: `BaseSweep` provides the foundation with parameter following, measurement creation, and thread management
- **Measurement Types**: 
  - 0D (time-based measurements)
  - 1D (single parameter sweep) 
  - 2D (dual parameter sweep)
- **Queue System**: `SweepQueue` for batch experiment execution
- **Real-time Plotting**: Live data visualization during measurements
- **Station Management**: QCoDeS Station integration for instrument management

### Package Structure
```
src/measureit/
    sweep/             # Measurement implementations
    base_sweep.py      # Core sweep functionality
    tools/             # Data utilities and sweep helpers
    Drivers/           # Instrument drivers
    visualization/     # Plotting helpers
```

## Quick Start

### Prerequisites

- Python 3.8+
- Git 
- NI DAQmx drivers: http://www.ni.com/en-us/support/downloads/drivers/download/unpackaged.ni-daqmx.291872.html
- NI VISA package: http://www.ni.com/download/ni-visa-18.5/7973/en/

## Installation

  ### Using pip (recommended)
  ```bash
  pip install measureit
  ```

  ### From source
  ```bash
  git clone https://github.com/nanophys/MeasureIt.git
  cd MeasureIt
  pip install -e .
  ```

## Data Directory Configuration

  measureit stores databases, logs, and configuration files. You have three options:

  ### Option 1: Use defaults (recommended)
  Data is automatically stored in OS-appropriate locations:
  - **Linux**: `~/.local/share/measureit/`
  - **macOS**: `~/Library/Application Support/measureit/`
  - **Windows**: `C:\Users\<username>\AppData\Local\measureit\`

  ### Option 2: Set environment variable
  ```bash
  export MEASUREIT_HOME="/path/to/your/data"  # Linux/macOS
  set MEASUREIT_HOME="C:\path\to\data"        # Windows
  ```

  ### Option 3: Programmatic configuration
  ```python
  import measureit
  measureit.set_data_dir('/custom/path')
  ```

  ### Migration from old setup
  If you have existing `MeasureItHome` setup:
  - The `MeasureItHome` environment variable still works (backward compatible)
  - Or copy your `databases/` folder to the new location

### Updating MeasureIt

```bash
cd /path/to/MeasureIt
git pull
pip install -e . --upgrade
```

### Known Issues

- `ipykernel` 7.0.x has a dormant event-loop bug that prevents the Qt/pyqtgraph
  plotter from updating. Stick to `ipykernel>=6.29` (or the newer 7.1+ series).

## Installation & Updating

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
file. In this package, this is simply titled "environment.yaml". Updating 
packages from .yaml files can take a while though, but installing mamba can make 
it much faster. This is just a re-working of some of the conda functions using 
C/C++ to make them much faster. Using mamba is simple: you simply replace 
"conda" with "mamba" in any commands and it will execute much faster. As 
previously mentioned, Miniforge3 comes with mamba already, so no work needs to 
be done if you install this from the get go. Alternatively, you can follow the 
deprecated method of adding mamba to an existing install of conda by running

```
(base) $ conda install -n base --override-channels -c conda-forge mamba 'python_abi=*=*cp*'
```

### Create qcodes environment using environment.yaml file

You can create a new environment with all the necessary packages for MeasureIt 
by stepping into the MeasureIt directory and simply running

```
(base) $ conda env create -f environment.yaml
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
```

Most of the packages are reasonable, but there is an issue with installing 
MultiPyVu for OSs other than Windows via pip, so until that issue can be fixed 
this is the workaround.

If packages need to updated at any point, navigate to the MeasureIt directory
and run:

```
(qcodes) $ conda env update --file environment.yaml --prune
(qcodes) $ python -m pip install --no-deps --editable . --config-settings editable_mode=strict
(qcodes) $ python -m pip install --no-deps MultiPyVu==1.2.0
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

## Basic Usage

### Programmatic Usage

```python
import measureit
from qcodes import Station

# Create a station and add instruments
station = Station()
# ... add your instruments ...

# Choose where databases should be stored (optional)
measureit.set_data_dir("/path/to/measureit-data")

# Create a 1D sweep
sweep = measureit.Sweep1D(
    set_param=dac.voltage,
    start=0,
    stop=1,
    step=0.01,
    inter_delay=0.1
)

# Follow parameters to measure
sweep.follow_param(dmm.voltage, lockin.x)

# Start the measurement
sweep.start()
```

## Documentation

### Building Documentation

```bash
# Install documentation dependencies
uv pip install -e ".[docs]"  # or pip install -e ".[docs]"

# Build HTML documentation
cd docs/source
make html
```

The documentation is located in the `docs/source` directory. The built documentation will be in `docs/source/_build/html/`.

### Online Documentation

Visit our [online documentation](https://measureituw.readthedocs.io/en/latest/?badge=latest) for detailed guides and API reference.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed information about:

- Setting up a development environment
- Code quality standards and tools
- Testing guidelines
- Documentation standards
- Submitting pull requests

For quick development setup:
```bash
# Clone and set up development environment
git clone https://github.com/nanophys/MeasureIt
cd MeasureIt
uv pip install -e ".[dev,docs,jupyter]"  # or pip install -e ".[dev,docs,jupyter]"
```

## External links and active users

# Seattle
[David Cobden's lab](https://sites.google.com/uw.edu/nanodevice-physics)

[Xiaodong Xu's lab](https://sites.google.com/uw.edu/xulab)

# Cambridge
[Pablo Jarillo-Herrero's lab](https://jarillo-herrero.mit.edu)

[Long Ju's lab](https://physics.mit.edu/faculty/long-ju)

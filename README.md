        # R290 Heat Pump–Chiller Performance and Optimisation Model

## Overview

This repository contains the Python model developed for the master's thesis:

**Performance Analysis and Optimization of a Reversible R290 Heat Pump–Chiller System**

The model was developed to analyse the field performance of a three-unit reversible air-to-water heat pump–chiller plant using propane (R-290), validate a manufacturer-based compressor representation against measured operating data, and investigate operational and system-level improvement measures.

The model is structured as a reproducible calculation pipeline. It processes input data, generates the required model databases, performs validation and optimisation analyses, and creates the corresponding result tables and figures.

Company-confidential measurement data and thesis result files are not distributed with the public repository.

## Main purposes of the model

The model is used to:

- process detailed and long-term heat pump–chiller measurement data
- identify quasi-steady operating periods
- determine active refrigerant circuits from measured operating conditions
- evaluate Frascold V30-84AXHT R-290 compressor performance
- compare predicted electrical power with measured heat pump–chiller power
- calibrate effective air-side and water-side heat-exchanger conductances
- model one refrigerant circuit, one two-circuit HERA unit, and the three-unit plant
- analyse circuit staging and plant dispatch
- reconstruct missing long-term building heating and cooling loads
- estimate annual plant performance
- calculate COP, EER, SCOP and SEER-related performance indicators
- compare modelled performance with Carnot and second-law reference values
- analyse glycol-property effects
- investigate heat-exchanger, fan, flow and pump sensitivities
- investigate buffer-tank cycling
- screen a hypothetical water/water heat-recovery concept
- investigate mixed unit sizing
- generate thesis figures and result tables

The model is quasi-steady. It is not a dynamic refrigerant-cycle simulation and does not reproduce the complete internal controller of the installed units.

## Software requirements

### Python

**Minimum:** Python 3.10  

Python 3.10 or newer is required because the project uses modern Python type syntax.

### Required Python packages

The project requires:

| Package | Minimum version | Purpose |
|---|---:|---|
| `numpy` | 1.24 | numerical calculations and arrays |
| `pandas` | 2.0 | data processing, filtering, aggregation and table handling |
| `matplotlib` | 3.7 | plotting and thesis figures |
| `openpyxl` | 3.1 | reading and writing Excel `.xlsx` files |
| `scipy` | 1.10 | interpolation for performance-map plotting |


Install the required packages with:

```bash
python -m pip install "numpy>=1.24" "pandas>=2.0" "matplotlib>=3.7" "openpyxl>=3.1" "scipy>=1.10"
```

A virtual environment is recommended.

### Windows example

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install "numpy>=1.24" "pandas>=2.0" "matplotlib>=3.7" "openpyxl>=3.1" "scipy>=1.10"
```

### macOS / Linux example

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "numpy>=1.24" "pandas>=2.0" "matplotlib>=3.7" "openpyxl>=3.1" "scipy>=1.10"
```

---

## Project structure

The repository is organised around the following main folders:

```text
r290-heat-pump-chiller-model/
│
├── 00_CONFIG/
│   └── common configuration and table input/output helpers
│
├── 01_RAW_DATA/
│   └── external input data required by the model
│
├── 02_PROCESSED_DATA/
│   └── generated cleaned and filtered datasets
│
├── 04_GENERATE_DATABASES/
│   └── scripts that generate compressor, glycol and HERA databases
│
├── 05_ANALYSIS/
│   └── validation, annual analysis and optimisation scripts
│
├── 06_RESULTS/
│   └── generated result tables
│
├── 07_PLOTS/
│   └── plotting scripts
│
├── 08_THESIS_EXPORT/
│   └── generated thesis figures
│
└── run_thesis_model.py
    └── master script for running the complete workflow or selected tasks
```

`02_PROCESSED_DATA`, `06_RESULTS`, and generated thesis figures are build outputs and can be regenerated when all required inputs are available.

---

## Input data

The public repository does not contain the original confidential field measurements or proprietary manufacturer datasets.

To reproduce the complete thesis workflow, equivalent input files must be supplied in the expected locations.

### 1. Frascold compressor performance data

The model uses performance data for the:

**Frascold V30-84AXHT R-290 compressor**

The source workbook used in the thesis contains compressor performance over:

- evaporating temperature
- condensing temperature
- compressor frequency
- evaporator capacity
- condenser capacity
- electrical input
- refrigerant mass flow
- discharge temperature

The thesis model does not extrapolate beyond valid manufacturer-map data.

The original manufacturer workbook is not redistributed unless redistribution permission has been obtained.

Typical project location:

```text
01_RAW_DATA/
└── Frascold/
    └── Frascold_R290_V30-84AXHT.xlsx
```

### 2. DOWCAL 200E property data

Temperature-dependent water/glycol properties are required for the glycol model.

The model uses properties including:

- density
- specific heat capacity
- dynamic viscosity
- thermal conductivity

The thesis analysis uses 40 vol.% glycol as the installed reference condition and includes additional concentrations for sensitivity analysis.

The original manufacturer property source should be obtained separately from Dow.

### 3. Detailed field measurement data

The detailed field dataset is used for:

- stable-period filtering
- refrigerant-circuit identification
- electrical-power validation
- heat-exchanger calibration
- measured staging assessment

Relevant signals include, where available:

- timestamp
- outdoor-air temperature
- unit electrical power
- unit capacity request
- operating setpoint
- evaporating pressure
- condensing pressure
- suction temperature
- superheat
- water/glycol temperatures
- thermal-energy meter values
- pump and valve states
- compressor runtime information
- fan-related controller signals

The original SINTEF/Kiona field data are not distributed in this repository.

### 4. Long-term building data

The annual workflow requires long-term building-side data containing the signals used to construct heating and cooling loads, including the heating branch, reversible ventilation branch and outdoor temperature.

The original building data are confidential and are therefore excluded from the public repository.

---

## Running the model

The project is controlled by:

```text
run_thesis_model.py
```

### Complete run

For a complete calculation and plotting run, open `run_thesis_model.py` and set:

```python
RUN_COMPLETE_PIPELINE_ONCE = True
```

Then run:

```bash
python run_thesis_model.py
```

The master runner executes the required scripts in dependency order.

A complete run generates cleaned datasets, model databases, validation results, optimisation results, annual results and thesis figures.

### Plot-only run

If all calculations have already completed and only the figures should be regenerated, use:

```python
RUN_ALL_PLOTS_ONLY_ONCE = True
```

with:

```python
RUN_COMPLETE_PIPELINE_ONCE = False
```

Then run:

```bash
python run_thesis_model.py
```

### Running individual analyses

Individual task flags are also available in `run_thesis_model.py`.

For example:

```python
RUN_COMPLETE_PIPELINE_ONCE = False
RUN_PARAMETRIC_ANALYSIS = True
RUN_PARAMETRIC_PLOTS = True
```

Only activate the analyses required for the current run.

Some later analyses depend on files generated by earlier stages. A complete pipeline run is therefore recommended when setting up the project for the first time.

---

## Generated outputs

The principal generated output locations are:

```text
02_PROCESSED_DATA/
```

Cleaned and filtered input datasets.

```text
06_RESULTS/
```

Numerical model results, validation tables, optimisation tables, annual results and supporting model databases.

```text
08_THESIS_EXPORT/figures/
```

Figures generated for the thesis and supplementary analysis.

The model uses a clean-build procedure during a complete run so that obsolete result files from earlier model versions are not silently mixed with current outputs.

---

## Model hierarchy

The numerical model follows a hierarchical structure:

```text
Frascold compressor map
        ↓
single R-290 refrigerant circuit
        ↓
two-circuit HERA heat pump–chiller unit
        ↓
three-unit plant
        ↓
annual building-load and optimisation analyses
```

For the single-circuit model, evaporating and condensing saturation temperatures are coupled iteratively to effective air-side and water-side heat-exchanger conductances.

The model then extends the circuit calculation to:

- one- and two-circuit operation
- one-, two-, and three-unit operation
- plant-level load dispatch
- annual heating and cooling operation

---

## Important modelling boundaries

The main electrical model boundary includes:

- compressor electrical input
- outdoor-coil fan electrical input

External hydronic pump power is excluded from the primary heat pump–chiller validation boundary.

Pump electricity is added only in analyses explicitly identified as pump-inclusive.

The field-validation comparison therefore represents:

```text
modelled compressor power + modelled fan power
```

compared with measured heat pump–chiller unit electrical power.

Internal auxiliary loads that are not separately measured may contribute to the remaining validation residual.

---

## Important limitations

The model should be interpreted within the following limitations:

- The core thermodynamic model is quasi-steady.
- Start-up and shutdown transients are not resolved.
- Refrigerant redistribution during cycling is not modelled dynamically.
- Defrost is not represented as a detailed transient process.
- Compressor operation is limited to the valid manufacturer-map domain.
- Complete heat-exchanger geometry is not available.
- Effective heat-exchanger UA values are therefore field-calibrated model parameters.
- Some controller relationships are represented through explicit assumptions.
- External hydronic pump power is estimated rather than measured where pump-inclusive results are shown.
- Long-term loads contain both measured and reconstructed periods.
- Heat-recovery and mixed-unit-sizing studies are conceptual screening analyses rather than validated retrofit designs.
- Results obtained with different electrical boundaries should not be compared as if they were identical COP or EER definitions.

---

## Confidential and non-distributed material

The public repository intentionally excludes:

- original SINTEF/Kiona measurement exports
- confidential company data
- processed datasets that would reproduce confidential measurements
- generated thesis result files derived directly from confidential data
- proprietary manufacturer source files where redistribution rights are not available

The source code can therefore be inspected and reused independently, but exact reproduction of the thesis results requires access to the original input datasets.

Users applying the code to another installation must adapt the input data mapping, configuration values and equipment-specific manufacturer data.

---

## Reproducibility

For reproducible use of the public model:

1. Install Python and the required packages listed above.
2. Obtain or prepare equivalent input data.
3. Preserve the expected folder structure.
4. Check the configuration files before running the model.
5. Run `run_thesis_model.py`.
6. Review model warnings and invalid operating points.
7. Do not interpret out-of-map or infeasible operating points as valid predictions.

For archival publication, a tagged GitHub release can be deposited in Zenodo and cited using the DOI assigned to that release.

---

## Scientific basis and external data

The implementation uses established thermodynamic, heat-transfer, hydraulic and statistical methods described and referenced in the accompanying master's thesis.

External sources include, among others:

- Frascold compressor manufacturer performance data
- Euroklimat HERA manufacturer information
- DOWCAL 200E thermophysical property data
- IAPWS water-property formulation
- European performance standards used for seasonal assessment
- published thermodynamic, heat-transfer and statistical methods

These sources provide scientific methods and input data. The project-specific Python implementation is part of this repository.

---

## Author

**Jonas Schwitalla**

Developed as part of a master's thesis carried out at NTNU in Trondheim in cooperation with SINTEF Energi.

---


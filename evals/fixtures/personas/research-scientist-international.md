# Mateus Ferreira -- Career Knowledge Base

## Personal Information

| Field         | Value                                       |
|---------------|---------------------------------------------|
| Name          | Dr. Mateus Ferreira                         |
| Email         | mateus.ferreira@example.com                 |
| Phone         | +49 30 555-0174                             |
| Location      | Halvenstadt, Germany                        |
| Website       | https://mateusferreira.example.org          |
| Work status   | Brazilian citizen with German permanent residence; requires visa sponsorship for roles in the US |

## Languages

- Portuguese (native)
- English (fluent, C2; all publications and teaching in English)
- German (B2)

## Professional Summary

Atmospheric scientist and machine learning researcher with nine years of
research since his master's degree, applying deep learning to weather and
renewable energy forecasting. Builds PyTorch models for precipitation
nowcasting and probabilistic forecasting, trains them at scale on HPC
clusters, and evaluates them with the verification statistics forecasters
trust.

Led a six-month industry project with a German grid operator that cut the
error of day-ahead solar generation forecasts by 11%, and maintains an
open-source Python package for radar nowcasting. Seven peer-reviewed
publications, six as first author.

His fixed-term postdoctoral contract ends in 2027-06, and he wants to move
into an applied scientist role in industry where models reach production and
are judged by how well they forecast.

## Technical Skills -- Master List

### Machine Learning
- Deep learning with PyTorch (8 years): convolutional networks, U-Nets, convolutional recurrent networks, and graph neural networks
- Probabilistic forecasting: ensembles, quantile regression, and the continuous ranked probability score (CRPS)
- Time series forecasting for weather and energy data
- Distributed training with PyTorch DistributedDataParallel on multi-GPU nodes
- Model evaluation and forecast verification: critical success index (CSI), reliability diagrams, and skill scores
- Neural network emulators of physical parameterizations
- JAX (1 year, exploratory projects)

### Scientific Computing and Data
- Python: NumPy, xarray, Dask, pandas, scikit-learn, matplotlib
- Zarr and NetCDF for large gridded datasets
- Fortran (reading and modifying numerical weather prediction code)
- C++ (small extensions and bindings)
- R (statistics during the master's degree)
- Slurm on HPC clusters, Linux, Git, and Docker

### Atmospheric Science
- Numerical weather prediction and data assimilation (ensemble Kalman filter, 4D-Var concepts)
- Radar meteorology and precipitation nowcasting
- Statistical downscaling of rainfall and temperature
- Solar irradiance and photovoltaic generation forecasting

### Research Practice
- Writing papers and grant proposals
- Supervising master's and bachelor's theses
- Teaching tutorials and lab sessions
- Presenting to scientific and industry audiences

## Career History -- Complete and Detailed

### Halvenstadt Institute for Atmospheric Research -- Postdoctoral Researcher (Wissenschaftlicher Mitarbeiter, Postdoc)
**2021-07 to present** | Halvenstadt, Germany

Machine learning group of seven researchers in a public research institute.
Fixed-term contract ending 2027-06.

- Built a PyTorch nowcasting model for 0 to 2 hour precipitation from radar composites; the critical success index at a one-hour lead rose from 0.41 to 0.48 over the optical-flow baseline used by the national weather service
- Added probabilistic outputs with a 20-member ensemble and evaluated calibration with CRPS and reliability diagrams
- Trained graph neural networks that downscale 25 km reanalysis data to a 2 km grid for regional precipitation studies
- Scaled training to 32 GPUs on the national HPC center with DistributedDataParallel and Slurm, cutting one training epoch from 9 hours on 1 GPU to 40 minutes on 32 GPUs
- Built the data pipeline for 8 years of radar composites (1.2 TB) in Zarr with xarray and Dask
- Led a six-month industry project in 2022 with Nordwerk Netz, a regional grid operator, on day-ahead solar generation forecasting for 1,400 photovoltaic sites
  - The time series model reduced day-ahead mean absolute error by 11% compared with the operator's statistical baseline
  - Delivered the model, documentation, and a handover workshop; the operator's analysts ran it in shadow mode for three months
- Maintains rainflowcast, an open-source Python package for radar nowcasting, with about 300 GitHub stars and contributors from four institutes
- Co-wrote a successful national research grant proposal for EUR 480,000 over three years
- Co-supervised 3 master's theses and 1 bachelor's thesis
- Tools: PyTorch, xarray, Dask, Zarr, Slurm, Git, Docker

### Technische Universität Halvenstadt -- Doctoral Researcher (Wissenschaftlicher Mitarbeiter)
**2017-04 to 2021-06** | Halvenstadt, Germany

Doctoral position in the Institute of Meteorology, funded as a research
associate with teaching duties.

- Dissertation: neural network emulators of a convection parameterization in a global climate model
- Trained a PyTorch emulator that reproduced the convection scheme's heating and moistening tendencies while running 20 times faster inside the Fortran model
- Coupled the trained network into the Fortran model through a C++ interface and ran 10-year stable climate simulations
- Published 3 first-author papers from the dissertation
- Taught the tutorial for Numerical Methods in Atmospheric Science for 6 semesters, about 35 students each
- Tools: PyTorch, Fortran, C++, Python

### Universidade Federal de Serra Alta -- Graduate Researcher (Mestrado)
**2015-03 to 2017-02** | Serra Alta, Brazil

Master's research in the meteorology graduate program, funded by a national
graduate scholarship.

- Built statistical downscaling models for daily rainfall in the Serra Alta region with R and Fortran
- Showed that the downscaled rainfall improved drought index estimates for 42 rain gauge stations
- Published 1 first-author paper from the thesis

### Universidade Federal de Serra Alta -- Undergraduate Research Fellow (Iniciação Científica)
**2013-03 to 2014-12** | Serra Alta, Brazil

- Analyzed lightning and radar data for severe thunderstorm cases in the physics department's atmospheric lab
- Presented a poster at the national undergraduate research congress

## Publications

- Ferreira, M. et al. (2025). Probabilistic precipitation nowcasting with convolutional recurrent ensembles. Journal of Applied Weather Modeling.
- Ferreira, M., Brandt, K. (2024). Graph neural networks for kilometer-scale downscaling of reanalysis precipitation. Atmospheric Data Science Letters.
- Brandt, K., Ferreira, M. et al. (2023). Day-ahead photovoltaic generation forecasting with weather-informed deep learning. Renewable Energy Forecasting Review.
- Ferreira, M. et al. (2021). Stable neural network emulation of deep convection in a climate model. Journal of Climate Modeling Systems.
- Ferreira, M., Vogel, L. (2020). Training data selection for neural network parameterizations. Geoscientific Machine Learning Letters.
- Ferreira, M. et al. (2019). An emulator of tropical convection for faster climate simulations. Proceedings of the Halvenstadt Workshop on Climate Informatics.
- Ferreira, M., Souza, R. (2017). Statistical downscaling of daily rainfall for drought monitoring in Serra Alta. Revista Brasileira de Meteorologia Aplicada.
- Six journal articles and one peer-reviewed workshop paper (2019); about 410 citations in total

## Key Achievements

- Precipitation nowcasting: critical success index from 0.41 to 0.48 over the operational optical-flow baseline
- Industry project: day-ahead solar forecast error reduced by 11% for a grid operator's 1,400 sites
- Training time per epoch cut from 9 hours to 40 minutes by scaling to 32 GPUs
- Neural network emulator running 20 times faster than the physical convection scheme
- Successful EUR 480,000 research grant as co-author

## Education

### Technische Universität Halvenstadt -- Dr. rer. nat. (doctorate in natural sciences, equivalent to a PhD), Meteorology
**2017-04 to 2021-06** | Halvenstadt, Germany

- Awarded magna cum laude; defense in 2021-06
- Doctoral program in atmospheric physics; dissertation in English

### Universidade Federal de Serra Alta -- Mestrado (MSc), Meteorology
**2015-03 to 2017-02** | Serra Alta, Brazil

- Two-year research master's degree with a thesis
- Graduate scholarship from the national research council

### Universidade Federal de Serra Alta -- Bacharelado (BSc, four-year degree), Physics
**2011-03 to 2014-12** | Serra Alta, Brazil

- Final year research project on thunderstorm electrification
- Brazilian academic years run from March to December

## Awards

- Best student paper, Halvenstadt Workshop on Climate Informatics (2019)
- Institute travel fellowship for an international conference on weather and climate machine learning (2023)

## Strengths

- Moves comfortably between physics, statistics, and engineering
- Evaluates models honestly, including where they fail
- Explains forecast uncertainty to non-specialists, including grid operators
- Writes clean, tested research code that other people reuse

## Passions & Interests

- Plays samba percussion in a local community band
- Storm chasing and weather photography
- Cycling between Halvenstadt and the nearby lakes

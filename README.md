# PRISMA-Guided Bibliometric Review: Probabilistic Modeling in Agrometeorology

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.XXXXXXX.svg)](https://doi.org/10.5281/zenodo.XXXXXXX)

## Overview
This repository contains the data, automated Python extraction scripts, and analysis pipeline for the systematic bibliometric review of probabilistic reference evapotranspiration (ET₀) modeling and irrigation decision support systems. 

The analysis employs a two-tier approach to formally quantify two critical methodological gaps in the current literature:
1. **The Software and Data Fusion Gap (Chapter 3):** The absence of operational, scalable, and open-source software capable of fusing multi-source meteorological data in data-scarce regions. This gap justifies the development of the **EVAonline** platform.
2. **The Stochastic Decision Gap (Chapter 4):** The lack of field-scale irrigation scheduling tools that formally propagate uncertainty by integrating long-term climatological priors and oceanic teleconnections within a fully Bayesian framework.

## Repository Structure
* `/data/raw/`: Raw CSV files extracted directly from the Scopus API via `pybliometrics`.
* `/data/processed/`: Cleaned datasets post-PRISMA screening, ready for network analysis.
* `/scripts/`: Python routines for data collection (`01_data_collection.py`) and processing (`02_prisma_screening.py`).
* `/results/`: Exported network graphs, PRISMA flow diagrams, and summary tables.

## Reproducibility
To reproduce the data collection and PRISMA screening initialization:
1. Clone this repository.
2. Install the required dependencies: `pip install -r requirements.txt`
3. Configure your Scopus API key via `pybliometrics`.
4. Run `python scripts/01_data_collection.py` to extract the vanguard literature.
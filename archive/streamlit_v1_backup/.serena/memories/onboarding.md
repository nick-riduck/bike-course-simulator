# Project Onboarding: Bike Course Simulator

## Purpose
High-fidelity cycling course simulation based on GPX data to predict finish times (PR) and optimal pacing strategies. It accounts for physics (gravity, drag, rolling resistance), weather (wind, temperature), and rider physiology (Critical Power, W' balance, fatigue).

## Tech Stack
- **Language:** Python 3 (standard libraries primarily).
- **Key Libraries:** `argparse`, `urllib.request`, `xml.etree.ElementTree`, `json`, `math`.
- **Testing:** `pytest` (suggested) or direct script execution (as seen in `tests/test_weather.py`).

## Core Architecture
- **`GpxLoader` (`src/gpx_loader.py`):** Parses GPX files, applies data cleaning (min distance filtering, elevation smoothing), and uses adaptive segmentation (based on grade and heading changes).
- **`PhysicsEngine` (`src/physics_engine.py`):** Uses Work-Energy theorem for distance-based integration. Features sub-stepping (20m intervals), optimal pacing search (binary search), and fatigue/torque decay models.
- **`Rider` (`src/rider.py`):** Models the rider's physiological state using Critical Power (CP) and W' Balance (anaerobic capacity).
- **`WeatherClient` (`src/weather_client.py`):** Connects to Open-Meteo API for real-time/historical weather or uses a scenario mode for static values.

## Key Files & Entry Points
- `simulate.py`: Primary CLI tool for running simulations.
- `src/`: Core logic modules.
- `docs/`: Technical whitepapers and roadmap documents.
- `tools/`: Visualization scripts (e.g., `visualize_result.py`).

## Development Guidelines
- **Documentation First:** Finalize docs/specs before coding.
- **Jira Driven:** Refer to `docs/PROJECT_GUIDELINES.md` for task tracking (e.g., Epic PRO-742).
- **Physics Stability:** Prioritize data cleaning and safeguards to prevent speed/grade spikes.
- **Style:** Use type hints, `dataclasses`, and follow PEP 8 (snake_case for functions, CamelCase for classes).

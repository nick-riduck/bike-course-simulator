# Suggested Commands for Bike Course Simulator

## Running Simulation
Run the simulator on a GPX file with rider parameters:
```bash
python simulate.py <path_to_gpx> --cp 250 --w-prime 20000 --weight 70
```

## Running Tests
Run weather client tests:
```bash
python tests/test_weather.py
```

## Visualization (Tools)
Visualize simulation results (requires `simulation_result.json` to be generated):
```bash
python tools/visualize_result.py
```

## Linting & Formatting
(Note: Specific tools not configured in repo, but recommended):
```bash
ruff check .
black .
```

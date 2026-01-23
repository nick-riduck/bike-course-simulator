# Style and Conventions

## Python Coding Style
- **Version:** Python 3.10+ (uses `from __future__ import annotations`).
- **Data Structures:** Prefer `dataclasses` for simple data containers.
- **Naming:**
    - Classes: `PascalCase`
    - Functions/Variables: `snake_case`
    - Constants: `UPPER_SNAKE_CASE`
- **Typing:** Use type hints for function arguments and return types.
- **Documentation:** Use Google-style or similar descriptive docstrings for classes and public methods.

## Physics Modeling
- **Integration:** Use distance-based integration (Work-Energy) rather than time-based.
- **Sub-stepping:** Use small intervals (e.g., 20m) for accurate physics calculation within segments.
- **Safeguards:** Clamp values like grade and speed to realistic physical limits.

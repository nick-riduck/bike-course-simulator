# Task Completion Workflow

## 1. Documentation & Planning
- Review Jira sub-tasks in `docs/PROJECT_GUIDELINES.md`.
- Update technical docs in `docs/` if logic changes.
- Approve plan with the user.

## 2. Implementation
- Follow existing patterns in `src/`.
- Maintain type safety and clear naming.

## 3. Verification
- Run existing tests (e.g., `tests/test_weather.py`).
- Create new test cases for new features.
- Run `simulate.py` with sample GPX (`20seorak.gpx`) to ensure no regressions.
- Check `simulation_result.json` for data integrity.

## 4. Final Review
- Execute linting (if available).
- Ensure no "speed spikes" or "grade spikes" in the physics output.

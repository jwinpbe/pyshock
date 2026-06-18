# https://just.systems

install:
    uv sync --all-extras

lint:
    uv run ruff format src/pyshock
    uv run ruff check --fix src/pyshock tests/
    pyrefly check src/pyshock

test:
    uv run pytest --cov=pyshock --cov-report=term-missing

security:
    uv run bandit -c pyproject.toml -r src/pyshock/ -ll

publish:
    uv build && uv publish

version bump:
    cz bump {{bump}}

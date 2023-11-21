flake8:
    flake8 --exclude .tox .

mypy:
    mypy --strict .

isort:
    isort --skip .mypy_cache --skip .hypothesis --skip .tox .

black: isort
    black --extend-exclude="\.env/|\.tox/" .

coverage:
    COVERAGE_FILE=.coverage/.coverage python -m pytest --cov=aiofreqlimit \
    --cov-report term --cov-report html:.coverage tests

build:
    if [ -d dist ]; then rm -rf dist; fi
    python -m build
    rm -rf *.egg-info

upload:
    twine upload dist/*
    rm -rf dist

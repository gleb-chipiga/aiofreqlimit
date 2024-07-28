isort:
    isort --skip .mypy_cache --skip .hypothesis --skip .tox .

sort-all:
    -sort-all aiofreqlimit/*.py
    -sort-all tests/*.py

black:
    black --extend-exclude="\.env/|\.tox/" .

flake8:
    flake8 --exclude .tox .

mypy:
    mypy --strict .

pyright:
    pyright

test:
    python -m pytest tests

coverage:
    COVERAGE_FILE=.coverage/.coverage python -m pytest --cov=aiofreqlimit \
    --cov-report term --cov-report html:.coverage tests

all: isort sort-all black flake8 mypy pyright coverage

build:
    if [ -d dist ]; then rm -rf dist; fi
    python -m build
    rm -rf *.egg-info

upload:
    twine upload dist/*
    rm -rf dist

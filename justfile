# Birdsong acoustic modem justfile

default:
    @just --list

send *args:
    uv run python3 birdsong.py send {{args}}

recv *args:
    uv run python3 birdsong.py recv {{args}}

run *args:
    uv run python3 birdsong.py send {{args}}

test:
    uv run python3 -m unittest discover -s tests -p 'test_*.py'

e2e:
    uv run python3 birdsong.py send -o /tmp/birdsong-e2e.wav < docs/project_notes/restructure_plan.md
    uv run python3 birdsong.py recv -i /tmp/birdsong-e2e.wav > /tmp/birdsong-e2e.out
    cmp docs/project_notes/restructure_plan.md /tmp/birdsong-e2e.out

e2e-pipes:
    uv run python3 birdsong.py send -o - < docs/project_notes/restructure_plan.md 2>/dev/null | uv run python3 birdsong.py recv -i - 2>/dev/null > /tmp/birdsong-e2e-pipes.out
    cmp docs/project_notes/restructure_plan.md /tmp/birdsong-e2e-pipes.out

install:
    uv sync --group dev

format:
    uv run ruff format .

lint:
    uv run ruff check . --fix

check:
    uv run ruff check .

clean:
    rm -f *.wav *.png
    find . -name '*.pyc' -delete

help:
    @just --list

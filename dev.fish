#!/usr/bin/env fish

if not command -s uv
    curl -LsSf https://astral.sh/uv/install.sh | sh
end

if test -d "venv"
    rm -rf venv
end

uv venv --python 3.12.12 venv

if not string length -q "$VIRTUAL_ENV"
    . venv/bin/activate.fish
end

uv pip install -r dev.txt

if test -d "out"
    rm -rf out
end

sphinx-build -b html . out

deactivate

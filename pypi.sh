python3 -m venv venv
. venv/bin/activate
python3 -m pip install -r pypi.txt
python3 -m pip freeze > pypi.lock
deactivate
rm -rf venv

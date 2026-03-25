import os
import shutil
import venv
import subprocess

def remove_directory(dir_path):
    """Deletes the directory if it exists."""
    if os.path.exists(dir_path):
        print(f"Removing '{dir_path}' directory...")
        shutil.rmtree(dir_path)

def main():
    venv_dir = "venv"
    out_dir = "out"
    
    # 1. Delete venv and out directories if they exist
    remove_directory(venv_dir)
    remove_directory(out_dir)
    
    # 2. Create the virtual environment
    print(f"Creating virtual environment in '{venv_dir}'...")
    # venv.create is the Python API for creating a venv (equivalent to `python -m venv venv`)
    venv.create(venv_dir, with_pip=True)
    
    # Define paths to the venv's executables
    if os.name == 'nt':
        venv_python = os.path.join(venv_dir, 'Scripts', 'python.exe')
        venv_pip = os.path.join(venv_dir, 'Scripts', 'pip.exe')
    else:
        venv_python = os.path.join(venv_dir, 'bin', 'python')
        venv_pip = os.path.join(venv_dir, 'bin', 'pip')

    # 3. Install dependencies
    print("Installing dependencies...")
    # pip does not have a supported public Python API, so subprocess is the officially recommended way to invoke it
    subprocess.run([venv_pip, "install", "-r", "pypi.txt"], check=True)

    # 4. Invoke Sphinx build using its Python API
    print("Building Sphinx docs...")
    # To answer your question: Yes, Sphinx has a Python API (sphinx.cmd.build.main).
    # However, because we just installed Sphinx into the newly created venv, the current Python process 
    # running this script won't have it in its module path. The cleanest way to use the Python API 
    # within the context of the new venv is to execute a small script using the venv's Python executable.
    sphinx_script = """
import sys
from sphinx.cmd.build import main
sys.exit(main(['--exception-on-warning', '-b', 'html', 'src', 'out']))
"""
    subprocess.run([venv_python, "-c", sphinx_script], check=True)

if __name__ == "__main__":
    main()

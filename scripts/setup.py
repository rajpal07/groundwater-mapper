#!/usr/bin/env python3
"""
Setup script for Groundwater Mapper Python environment
Run this to set up the virtual environment and install dependencies
"""

import os
import sys
import subprocess
import venv
from pathlib import Path


def create_venv(venv_path: str):
    """Create a virtual environment"""
    print(f"Creating virtual environment at {venv_path}...")
    venv.create(venv_path, with_pip=True)
    print("Virtual environment created.")


def install_requirements(venv_path: str, requirements_file: str):
    """Install requirements in the virtual environment"""
    if sys.platform == 'win32':
        pip_path = os.path.join(venv_path, 'Scripts', 'pip')
    else:
        pip_path = os.path.join(venv_path, 'bin', 'pip')
    
    print("Installing requirements...")
    subprocess.check_call([pip_path, 'install', '-r', requirements_file])
    print("Requirements installed.")


def main():
    # Get script directory
    script_dir = Path(__file__).parent.absolute()
    venv_path = script_dir.parent / 'venv'
    requirements_file = script_dir / 'requirements.txt'
    
    print("Groundwater Mapper Setup")
    print("=" * 50)
    
    # Check if venv already exists
    if venv_path.exists():
        print(f"Virtual environment already exists at {venv_path}")
        response = input("Recreate? (y/N): ").strip().lower()
        if response == 'y':
            import shutil
            print("Removing existing venv...")
            shutil.rmtree(venv_path)
        else:
            print("Using existing virtual environment.")
            install_requirements(str(venv_path), str(requirements_file))
            return
    
    # Create venv
    create_venv(str(venv_path))
    install_requirements(str(venv_path), str(requirements_file))
    
    print("\n" + "=" * 50)
    print("Setup complete!")
    print(f"\nTo activate the virtual environment:")
    if sys.platform == 'win32':
        print(f"  {venv_path}\\Scripts\\activate")
    else:
        print(f"  source {venv_path}/bin/activate")
    
    print(f"\nTo process a file:")
    print(f"  python scripts/process_map.py --input data.xlsx --parameter 'GW Level'")


if __name__ == '__main__':
    main()

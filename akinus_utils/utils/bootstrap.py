# akinus_utils/utils/bootstrap.py
import sys
import subprocess
from pathlib import Path
import ast
from stdlib_list import stdlib_list

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent

def bootstrap_dependencies():
    """
    Automatically detect and install missing dependencies.
    Scans all .py files, filters stdlib and project modules,
    and installs any missing external packages via uv + pip.
    """
    print("[BOOTSTRAP] Scanning project for imports...")

    # 1️⃣ Collect all .py files
    python_files = [f for f in PROJECT_ROOT.rglob("*.py")]

    # 2️⃣ Collect all top-level imports
    imports = set()
    for file in python_files:
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue  # skip empty or commented lines

                # import x
                if line.startswith("import "):
                    name = line.split()[1].split(".")[0]
                    if name and name != ".":
                        imports.add(name)

                # from x import y
                elif line.startswith("from "):
                    name = line.split()[1].split(".")[0]
                    if name and name != ".":
                        imports.add(name)

    # 3️⃣ Filter standard library modules
    stdlib_modules = set(stdlib_list(f"{sys.version_info.major}.{sys.version_info.minor}"))

    # 4️⃣ Filter project packages (top-level folders in PROJECT_ROOT)
    project_packages = {p.name for p in PROJECT_ROOT.iterdir() if p.is_dir()}

    # 5️⃣ Keep only external modules
    external_modules = imports - stdlib_modules - project_packages

    print(f"[BOOTSTRAP] Found external modules: {sorted(external_modules)}")

    # 6️⃣ Install missing modules
    for module in sorted(external_modules):
        try:
            __import__(module)
        except ModuleNotFoundError:
            print(f"[BOOTSTRAP] Installing missing module: {module}")
            # Add to uv
            subprocess.run(["uv", "add", module], check=True)
            # Install via pip
            subprocess.run([sys.executable, "-m", "pip", "install", module], check=True)

    print("[BOOTSTRAP] All missing dependencies installed.")

# Optional: allow running this script directly
if __name__ == "__main__":
    bootstrap_dependencies()

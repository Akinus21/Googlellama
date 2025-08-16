import os
import subprocess
import sys
from stdlib_list import stdlib_list
from akinus_utils.utils.logger import log
from akinus_utils.utils.app_details import PROJECT_ROOT

def install_project_dependencies():
    import os
    import subprocess
    import sys
    from stdlib_list import stdlib_list

    from akinus_utils.utils.logger import log
    from akinus_utils.utils.app_details import PROJECT_ROOT

    project_dir = PROJECT_ROOT

    # Scan .py files and collect imports
    python_files = []
    for root, dirs, files in os.walk(project_dir):
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))

    imports = set()
    for file in python_files:
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("import "):
                    imports.add(line.split()[1].split(".")[0])
                elif line.startswith("from "):
                    imports.add(line.split()[1].split(".")[0])

    stdlib_modules = set(stdlib_list(f"{sys.version_info.major}.{sys.version_info.minor}"))
    project_packages = {name for name in os.listdir(project_dir) if os.path.isdir(os.path.join(project_dir, name))}
    external_modules = imports - stdlib_modules - project_packages

    for module in sorted(external_modules):
        print(f"uv add {module}")
        log("INFO", "uv", f"Adding module {module} to uv")
        subprocess.run(["uv", "add", module])

if __name__ == "__main__":
    install_project_dependencies()

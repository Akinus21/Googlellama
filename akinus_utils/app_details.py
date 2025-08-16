
from pathlib import Path
import pathlib
import tomllib
import toml

# ---------------------- Define the main app entrypoint -------------------
APP_ENTRYPOINT = "supreme_research_mcp"
# -------------------------------------------------------------------------

def find_project_root(start_path: Path) -> Path:
    """Search upward from start_path to find the project root containing pyproject.toml."""
    for parent in [start_path] + list(start_path.parents):
        if (parent / "pyproject.toml").is_file():
            return parent
    raise FileNotFoundError("Could not find pyproject.toml in any parent directory.  Start path: {start_path}")

# ------------------- Define the project root directory -------------------
PROJECT_ROOT = find_project_root(Path.cwd())
# -------------------------------------------------------------------------

def find_pyproject():
    cwd = pathlib.Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        candidate = parent / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None

# ------------------- Define the path to pyproject.toml -------------------
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
#--------------------------------------------------------------------------

def app_name() -> str:
    """Read the app name from pyproject.toml."""
    with open(PYPROJECT_PATH, "rb") as f:
        data = tomllib.load(f)

    # Check top-level 'project' key (PEP 621)
    if "project" in data and "name" in data["project"]:
        return data["project"]["name"]

    # Check legacy or tool-specific locations (Poetry, Hatch)
    if "tool" in data:
        if "poetry" in data["tool"] and "name" in data["tool"]["poetry"]:
            return data["tool"]["poetry"]["name"]
        elif "hatch" in data["tool"] and "name" in data["tool"]["hatch"]:
            return data["tool"]["hatch"]["name"]

    raise KeyError("App name not found in pyproject.toml")

# ------------------- Define the app name ---------------------------------
APP_NAME = app_name()
# -------------------------------------------------------------------------

def find_repo_owner():
    try:
        with open(PYPROJECT_PATH) as f:
            pyproject = toml.load(f)
        project = pyproject.get("project", {})
        authors = project.get("authors")
        if not authors or not isinstance(authors, list):
            raise ValueError("The 'authors' field must be a non-empty list of tables with 'name' keys.")
        
        first_author = authors[0]
        if not isinstance(first_author, dict) or "name" not in first_author:
            raise ValueError("Each author entry must be a table with a 'name' key.")

        repo_owner = first_author["name"].strip()

        if not repo_owner:
            raise ValueError("Author 'name' is empty.")

        return repo_owner

    except Exception as e:
        print(f"Warning: Could not parse repository info from pyproject.toml. Using fallback values. Error: {e}")
        return "unknown_owner", "unknown_repo"

# ------------------- Define repo information ------------------------------
REPO_OWNER = find_repo_owner()
# --------------------------------------------------------------------------

# find app version from pyproject.toml
def get_app_version():
    try:
        with open(PYPROJECT_PATH) as f:
            pyproject = toml.load(f)
        return pyproject["project"]["version"]
    except Exception as e:
        print(f"ERROR app_details.py!! Failed to read app version: {e}")
        return "0.0.0"  # Fallback version if reading fails
    
# ------------------- Define the app version --------------------------------
APP_VERSION = get_app_version()
# ---------------------------------------------------------------------------
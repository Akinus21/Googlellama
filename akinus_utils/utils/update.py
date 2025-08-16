import sys
import subprocess
import requests
import os
import asyncio
import shutil
import tempfile
import zipfile
from pathlib import Path
from packaging import version
import platform
from akinus_utils.utils.notify import notify
from akinus_utils.utils.logger  import log
from akinus_utils.utils.app_details import PYPROJECT_PATH, APP_ENTRYPOINT, REPO_OWNER, PROJECT_ROOT, APP_NAME, APP_VERSION

if PYPROJECT_PATH is None:
    raise FileNotFoundError("Could not find pyproject.toml in current or parent dirs")


async def get_latest_release(repo_owner, repo_name):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        latest_ver = data["tag_name"].lstrip("v")
        return latest_ver, data
    except Exception as e:
        await log("ERROR", "update.py", f"Failed to get latest release info: {e}")
        return None, None


def prompt_user(message):
    resp = input(f"{message} [y/N]: ").strip().lower()
    return resp == 'y'


def run_command(cmd_list, description):
    asyncio.run(log("INFO", "update.py", f"Running command: {' '.join(cmd_list)} - {description}"))
    subprocess.run(cmd_list, check=True)
    asyncio.run(log("INFO", "update.py", f"Command succeeded: {' '.join(cmd_list)}"))


def run_update_git(repo_root):
    asyncio.run(log("INFO", "update.py", "Git repo detected, pulling latest changes..."))
    run_command(["git", "-C", str(repo_root), "pull"], "git pull")
    asyncio.run(log("INFO", "update.py", "Reinstalling in editable mode..."))
    run_command(["uv", "pip", "install", "-e", str(repo_root)], "uv pip install -e")


def run_update_pip(repo_name):
    asyncio.run(log("INFO", "update.py", "No git repo detected, upgrading installed package..."))
    run_command(["uv", "pip", "install", "--upgrade", repo_name], "uv pip install --upgrade")


def download_asset(url, dest_path):
    asyncio.run(log("INFO", "update.py", f"Downloading asset from {url} to {dest_path}"))
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    asyncio.run(log("INFO", "update.py", "Download complete"))


def extract_zip(zip_path, extract_to):
    asyncio.run(log("INFO", "update.py", f"Extracting {zip_path} to {extract_to}"))
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    asyncio.run(log("INFO", "update.py", "Extraction complete"))


def restart_app():
    asyncio.run(log("INFO", "update.py", f"Restarting app with: uv run {APP_ENTRYPOINT}"))
    print(f"\n🎉 Update complete! Restarting app now...\n")
    notify("Update Complete", "The application has been updated and will restart now.")

    # Cross-platform restart: spawn detached process to avoid blocking current
    if platform.system() == "Windows":
        DETACHED_PROCESS = 0x00000008
        subprocess.Popen(["uv", "run", APP_ENTRYPOINT], creationflags=DETACHED_PROCESS)
    else:
        subprocess.Popen(["uv", "run", APP_ENTRYPOINT], start_new_session=True)

    asyncio.run(log("INFO", "update.py", "Restart command issued, exiting update script."))
    sys.exit(0)


async def perform_update():
    repo_root = PROJECT_ROOT
    repo_owner = REPO_OWNER
    repo_name = APP_NAME
    await log("INFO", "update.py", f"Starting update check for {repo_owner}/{repo_name}...")

    local_ver = APP_VERSION
    latest_ver, release_data = await get_latest_release(repo_owner, repo_name)

    if not local_ver or not latest_ver:
        await log("WARNING", "update.py", "Could not determine versions, skipping update.")
        print("Could not determine version info, skipping update.")
        notify("Update Skipped", "Could not determine version info.")
        return

    await log("INFO", "update.py", f"Current version: {local_ver}, Latest version: {latest_ver}")
    print(f"Current version: {local_ver}")
    print(f"Latest version: {latest_ver}")

    if version.parse(local_ver) >= version.parse(latest_ver):
        await log("INFO", "update.py", "Already running the latest version.")
        print("You are already running the latest version.")
        notify("No Update Needed", "You are already running the latest version.")
        return

    if not prompt_user("New version available. Update now?"):
        await log("INFO", "update.py", "Update skipped by user.")
        print("Update skipped.")
        notify("Update Skipped", "User chose not to update.")
        return

    try:
        if (repo_root / ".git").exists():
            run_update_git(repo_root)
            await log("INFO", "update.py", "Update successful via git pull.")
            print("Update successful via git pull!")
            notify("Update Successful", "Updated via git pull.")
        else:
            assets = release_data.get("assets", [])
            if not assets:
                run_update_pip(repo_name)
                await log("INFO", "update.py", "Update successful via pip upgrade (no assets found).")
                print("Update successful via pip upgrade!")
                notify("Update Successful", "Updated via pip upgrade (no assets found).")
            else:
                asset = None
                for a in assets:
                    name = a.get("name", "").lower()
                    if name.endswith(".whl") or name.endswith(".zip"):
                        asset = a
                        break

                if not asset:
                    run_update_pip(repo_name)
                    await log("WARNING", "update.py", "No wheel or zip asset found, falling back to pip upgrade.")
                    print("No suitable release asset found, falling back to pip upgrade...")
                    print("Update successful via pip upgrade!")
                    notify("Update Successful", "No suitable asset, fallback to pip upgrade.")
                else:
                    temp_dir = tempfile.mkdtemp(prefix="uv_update_")
                    asset_path = Path(temp_dir) / asset["name"]
                    download_asset(asset["browser_download_url"], asset_path)

                    if asset_path.suffix == ".whl":
                        asyncio.run(log("INFO", "update.py", f"Installing wheel {asset_path}"))
                        run_command(["uv", "pip", "install", "--force-reinstall", str(asset_path)], "install wheel asset")
                        print("Update successful via wheel install!")
                        notify("Update Successful", "Updated via wheel install.")
                    elif asset_path.suffix == ".zip":
                        extract_dir = Path(temp_dir) / "extracted"
                        extract_zip(asset_path, extract_dir)
                        for root, dirs, files in os.walk(extract_dir):
                            rel_root = Path(root).relative_to(extract_dir)
                            for file in files:
                                src_file = Path(root) / file
                                dest_file = repo_root / rel_root / file
                                dest_file.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(src_file, dest_file)
                        print("Update successful via zip extraction!")
                        notify("Update Successful", "Updated via zip extraction.")
                        await log("INFO", "update.py", "Update successful via zip extraction.")
                    else:
                        run_update_pip(repo_name)
                        print("Unknown asset type, fallback to pip upgrade.")
                        notify("Update Warning", "Unknown asset type, fallback to pip upgrade.")
                        await log("WARNING", "update.py", "Unknown asset type, falling back to pip upgrade.")

                    shutil.rmtree(temp_dir, ignore_errors=True)
                    await log("INFO", "update.py", f"Cleaned up temporary directory {temp_dir}")

        restart_app()

    except subprocess.CalledProcessError as e:
        await log("ERROR", "update.py", f"Update failed: {e}")
        err_msg = f"❌ Update failed: {e}"
        print(f"\n{err_msg}\n")
        notify("Update Failed", err_msg)


async def main():
    await perform_update()


if __name__ == "__main__":
    asyncio.run(main())

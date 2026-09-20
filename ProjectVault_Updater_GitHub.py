import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

# ============================================================
# Project Vault Updater
#
# Update server: GitHub Releases
#
# Change these two values to your GitHub repository:
#   GITHUB_OWNER = your GitHub username
#   GITHUB_REPO  = your repository name
#
# The GitHub release must contain:
#   ProjectVault.exe
#   ProjectVaultPico.exe
#   manifest.json
#
# Example manifest.json:
# {
#   "version": "1.1.0",
#   "files": {
#     "ProjectVault.exe": "SHA256_HASH_HERE",
#     "ProjectVaultPico.exe": "SHA256_HASH_HERE"
#   }
# }
# ============================================================

GITHUB_OWNER = "lahaanshuman-tech"
GITHUB_REPO = "ProjectVault-Source_Updater"

MANIFEST_NAME = "manifest.json"
APP_FILES = ["ProjectVault.exe", "ProjectVaultPico.exe"]
VERSION_FILE = "ProjectVault.version.txt"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().lower()


def version_tuple(version):
    try:
        return tuple(int(x) for x in version.strip().lstrip("v").split("."))
    except ValueError:
        return (0,)


def get_current_version(base_dir):
    version_file = base_dir / VERSION_FILE

    if version_file.is_file():
        value = version_file.read_text(encoding="utf-8").strip()
        if value:
            return value

    # Fallback if the version file doesn't exist yet.
    return "1.0.0"


def download(url, destination):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ProjectVault-Updater"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        with open(destination, "wb") as f:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                f.write(block)


def get_release():
    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    )

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "ProjectVault-Updater"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def find_asset(release, filename):
    for asset in release.get("assets", []):
        if asset.get("name") == filename:
            return asset.get("browser_download_url")
    return None


def replace_file(downloaded, destination):
    temporary = destination.with_suffix(destination.suffix + ".new")
    backup = destination.with_suffix(destination.suffix + ".backup")

    # Keep a backup until both files have been replaced successfully.
    if destination.exists():
        if backup.exists():
            backup.unlink()
        os.replace(destination, backup)

    try:
        os.replace(downloaded, temporary)
        os.replace(temporary, destination)
    except Exception:
        # Restore the old version if replacement failed.
        if destination.exists():
            destination.unlink()
        if backup.exists():
            os.replace(backup, destination)
        raise

    return backup


def main():
    if GITHUB_OWNER == "YOUR_GITHUB_USERNAME":
        messagebox.showerror(
            "Project Vault Updater",
            "Open ProjectVault_Updater.py and set GITHUB_OWNER and "
            "GITHUB_REPO first."
        )
        return

    base_dir = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent
    )

    app = base_dir / "ProjectVault.exe"
    pico = base_dir / "ProjectVaultPico.exe"

    missing = [p.name for p in (app, pico) if not p.is_file()]
    if missing:
        messagebox.showerror(
            "Project Vault Updater",
            "Required files are missing:\n\n" + "\n".join(missing)
        )
        return

    current_version = get_current_version(base_dir)

    try:
        release = get_release()
    except Exception as e:
        messagebox.showerror(
            "Project Vault Updater",
            f"Could not check for updates.\n\n{e}"
        )
        return

    latest_version = release.get("tag_name", "").lstrip("v")

    if not latest_version:
        messagebox.showerror(
            "Project Vault Updater",
            "The GitHub release does not contain a valid version."
        )
        return

    if version_tuple(latest_version) <= version_tuple(current_version):
        messagebox.showinfo(
            "Project Vault Updater",
            f"You already have the latest version.\n\n"
            f"Installed: {current_version}\n"
            f"Latest:    {latest_version}"
        )
        return

    manifest_url = find_asset(release, MANIFEST_NAME)
    app_url = find_asset(release, "ProjectVault.exe")
    pico_url = find_asset(release, "ProjectVaultPico.exe")

    if not manifest_url or not app_url or not pico_url:
        messagebox.showerror(
            "Project Vault Updater",
            "The release is incomplete.\n\n"
            "It must contain:\n"
            "manifest.json\n"
            "ProjectVault.exe\n"
            "ProjectVaultPico.exe"
        )
        return

    answer = messagebox.askyesno(
        "Project Vault Update",
        f"Update available!\n\n"
        f"Installed: {current_version}\n"
        f"Latest:    {latest_version}\n\n"
        "Download and install this update?\n\n"
        "Your .pcv vault files will not be modified."
    )

    if not answer:
        return

    # ProjectVault.exe cannot be replaced while it is running.
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq ProjectVault.exe"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if "ProjectVault.exe" in result.stdout:
            messagebox.showerror(
                "Project Vault Updater",
                "ProjectVault.exe is still running.\n\n"
                "Close Project Vault and run the updater again."
            )
            return
    except Exception:
        pass

    temp_dir = Path(tempfile.mkdtemp(prefix="ProjectVaultUpdate_"))
    backups = []

    try:
        manifest_path = temp_dir / MANIFEST_NAME
        new_app = temp_dir / "ProjectVault.exe"
        new_pico = temp_dir / "ProjectVaultPico.exe"

        download(manifest_url, manifest_path)
        download(app_url, new_app)
        download(pico_url, new_pico)

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        if manifest.get("version", "").lstrip("v") != latest_version:
            raise RuntimeError("Manifest version does not match the release.")

        expected = manifest.get("files", {})

        for filename, path in [
            ("ProjectVault.exe", new_app),
            ("ProjectVaultPico.exe", new_pico),
        ]:
            expected_hash = expected.get(filename, "").lower()

            if len(expected_hash) != 64:
                raise RuntimeError(
                    f"Invalid SHA-256 value for {filename}."
                )

            actual_hash = sha256(path)

            if actual_hash != expected_hash:
                raise RuntimeError(
                    f"SHA-256 verification failed for {filename}."
                )

        backups.append(replace_file(new_app, app))
        backups.append(replace_file(new_pico, pico))

        (base_dir / VERSION_FILE).write_text(
            latest_version + "\n",
            encoding="utf-8"
        )

        for backup in backups:
            try:
                if backup.exists():
                    backup.unlink()
            except Exception:
                pass

        messagebox.showinfo(
            "Project Vault Updater",
            f"Project Vault was updated successfully!\n\n"
            f"Version: {latest_version}\n\n"
            "Your .pcv vault files were not modified."
        )

    except Exception as e:
        # Try to restore old binaries if the update failed midway.
        for backup, destination in zip(
            backups,
            [app, pico]
        ):
            try:
                if backup.exists():
                    if destination.exists():
                        destination.unlink()
                    os.replace(backup, destination)
            except Exception:
                pass

        messagebox.showerror(
            "Project Vault Updater",
            f"Update failed:\n\n{e}\n\n"
            "Your .pcv vault files were not modified."
        )

    finally:
        try:
            for item in temp_dir.iterdir():
                item.unlink()
            temp_dir.rmdir()
        except Exception:
            pass


if __name__ == "__main__":
    main()

import sys
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

PROJECT_VERSION = "1.0.0"
FILES = ["ProjectVault.exe", "ProjectVaultPico.exe"]

def resource_path(filename: str) -> Path:
    """Find a bundled file when frozen, or a source file when running normally."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / filename
    return Path(__file__).resolve().parent / filename

def main():
    root = tk.Tk()
    root.withdraw()

    messagebox.showinfo(
        "Project Vault Setup",
        "Select the portable drive/folder where Project Vault should be installed."
    )

    # Use a folder picker without requiring extra packages.
    from tkinter import filedialog
    destination = filedialog.askdirectory(
        title="Choose your Project Vault portable drive/folder"
    )

    if not destination:
        return

    destination = Path(destination)

    try:
        for filename in FILES:
            source = resource_path(filename)
            if not source.is_file():
                raise FileNotFoundError(
                    f"Bundled file is missing: {filename}\n"
                    f"Expected at: {source}"
                )

        # Copy only the Project Vault application binaries.
        # Existing .pcv vault files are never touched.
        for filename in FILES:
            shutil.copy2(resource_path(filename), destination / filename)

        # Store the installed application version for the updater.
        (destination / "ProjectVault.version.txt").write_text(
            PROJECT_VERSION + "\n",
            encoding="utf-8"
        )

        messagebox.showinfo(
            "Project Vault Setup",
            "Project Vault was installed successfully.\n\n"
            f"Location: {destination}\n"
            f"Version: {PROJECT_VERSION}\n\n"
            "Existing .pcv vault files were not modified."
        )

    except Exception as exc:
        messagebox.showerror(
            "Project Vault Setup - Error",
            str(exc)
        )

if __name__ == "__main__":
    main()

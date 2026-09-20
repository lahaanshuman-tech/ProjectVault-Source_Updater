import os
import sys
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

APP_FILES = ["ProjectVault.exe", "ProjectVaultPico.exe"]

def resource_path(filename):
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / filename
    return Path(__file__).resolve().parent / filename

def main():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.askdirectory(
        title="Select the Project Vault portable drive"
    )
    root.destroy()

    if not selected:
        return

    drive = Path(selected).resolve()

    missing = [f for f in APP_FILES if not resource_path(f).is_file()]
    if missing:
        messagebox.showerror(
            "Project Vault Setup",
            "This Setup executable is missing bundled files:\n\n"
            + "\n".join(missing)
            + "\n\nRebuild it using the --add-binary options provided."
        )
        return

    try:
        for filename in APP_FILES:
            source = resource_path(filename)
            destination = drive / filename
            temp = drive / (filename + ".new")
            shutil.copy2(source, temp)
            os.replace(temp, destination)

    except Exception as e:
        for filename in APP_FILES:
            temp = drive / (filename + ".new")
            try:
                if temp.exists():
                    temp.unlink()
            except Exception:
                pass
        messagebox.showerror("Project Vault Setup", f"Setup failed:\n\n{e}")
        return

    messagebox.showinfo(
        "Project Vault Setup",
        "Project Vault has been prepared successfully.\n\n"
        f"Drive: {drive}\n\n"
        "Installed:\n"
        "• ProjectVault.exe\n"
        "• ProjectVaultPico.exe\n\n"
        "Existing .pcv vaults were left untouched."
    )

if __name__ == "__main__":
    main()

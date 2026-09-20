import sys
import os
import shutil
import zipfile
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QMessageBox,
    QDialog,
    QFormLayout,
    QProgressBar,
    QComboBox,
    QFileDialog,
    QInputDialog,
)


# ============================================================
# CONFIGURATION
# ============================================================

APP_NAME = "ProjectVault"

import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent
PICOCRYPT = BASE_DIR / "ProjectVaultPico.exe"

WORKSPACE = BASE_DIR / ".ProjectVault_Work"

ACTIVE_MARKER = ".projectvault_active"

TEMP_DECRYPTED = BASE_DIR / ".ProjectVault_Decrypted.tmp"
TEMP_NEW_VAULT = BASE_DIR / ".ProjectVault_New.tmp"


# ============================================================
# UI STYLE
# ============================================================

STYLE = """
QWidget {
    background: #101114;
    color: #F2F2F2;
    font-family: "Segoe UI";
}

QLabel#Title {
    font-size: 28px;
    font-weight: 700;
}

QLabel#Subtitle {
    color: #9A9DA5;
    font-size: 13px;
}

QLabel#Status {
    font-size: 15px;
    font-weight: 600;
}

QWidget#Card {
    background: #181A1F;
    border: 1px solid #292C33;
    border-radius: 14px;
}

QPushButton {
    background: #24272E;
    border: 1px solid #343842;
    border-radius: 9px;
    padding: 11px 18px;
    font-size: 14px;
}

QPushButton:hover {
    background: #2D3038;
}

QPushButton#Primary {
    background: #315EFB;
    border: none;
    font-weight: 600;
}

QPushButton#Danger {
    background: #B83A3A;
    border: none;
    font-weight: 600;
}

QLineEdit, QComboBox {
    background: #181A1F;
    border: 1px solid #343842;
    border-radius: 8px;
    padding: 10px;
    color: white;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #315EFB;
}

QProgressBar {
    background: #181A1F;
    border: none;
    border-radius: 5px;
    height: 8px;
}

QProgressBar::chunk {
    background: #315EFB;
    border-radius: 5px;
}
"""


# ============================================================
# GENERAL FUNCTIONS
# ============================================================

def get_vaults():
    """
    Return all .pcv files beside ProjectVault.py.
    """

    return sorted(
        [
            p
            for p in BASE_DIR.glob("*.pcv")
            if p.is_file()
        ],
        key=lambda p: p.name.lower()
    )


def remove_path(path):
    """
    Delete a file or directory.
    """

    path = Path(path)

    if not path.exists():
        return

    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def file_is_valid(path):
    path = Path(path)

    return (
        path.is_file()
        and path.stat().st_size > 0
    )


# ============================================================
# ZIP EXTRACTION
# ============================================================

def safe_extract(zip_file, destination):
    """
    Extract a ZIP without allowing paths outside the workspace.
    """

    destination = Path(destination).resolve()

    destination.mkdir(
        parents=True,
        exist_ok=True
    )

    with zipfile.ZipFile(zip_file, "r") as archive:

        for member in archive.infolist():

            target = (
                destination / member.filename
            ).resolve()

            if (
                target != destination
                and destination not in target.parents
            ):
                raise RuntimeError(
                    "The vault contains an unsafe archive path."
                )

        archive.extractall(destination)


# ============================================================
# PICOCrypt
# ============================================================

def run_picocrypt(
    target,
    password,
    output=None,
    encryption=False
):
    """
    Run ProjectVaultPico.exe.

    Encryption:

        ProjectVaultPico.exe
        -stdin-password
        -o OUTPUT
        SOURCE

    stdin:

        password
        password

    Decryption:

        ProjectVaultPico.exe
        -stdin-password
        VAULT

    stdin:

        password
    """

    if not PICOCRYPT.is_file():

        raise RuntimeError(
            "ProjectVaultPico.exe was not found.\n\n"
            f"Expected:\n{PICOCRYPT}"
        )

    command = [
        str(PICOCRYPT),
        "-stdin-password",
    ]

    if output is not None:

        command.extend(
            [
                "-o",
                str(output),
            ]
        )

    command.append(
        str(target)
    )

    # --------------------------------------------------------
    # Password input
    # --------------------------------------------------------

    stdin_data = password + "\n"

    if encryption:

        stdin_data += password + "\n"

    # --------------------------------------------------------
    # Run PicoCrypt
    # --------------------------------------------------------

    try:

        result = subprocess.run(
        command,
        input=stdin_data,
        text=True,
        capture_output=True,
        cwd=str(BASE_DIR),
        timeout=300,
    )

    except subprocess.TimeoutExpired:

        raise RuntimeError(
            "ProjectVaultPico.exe timed out."
        )

    except Exception as exc:

        raise RuntimeError(
            "Could not start ProjectVaultPico.exe:\n\n"
            f"{exc}"
        )

    # --------------------------------------------------------
    # Error
    # --------------------------------------------------------

    if result.returncode != 0:

        message = (
            result.stderr
            or result.stdout
            or "Unknown PicoCrypt error."
        ).strip()

        raise RuntimeError(
            "ProjectVaultPico.exe failed:\n\n"
            + message
        )

    return result


# ============================================================
# ACTIVE VAULT
# ============================================================

def get_active_vault():
    """
    Read the active vault marker from the workspace.
    """

    if not WORKSPACE.is_dir():
        return None

    marker = (
        WORKSPACE / ACTIVE_MARKER
    )

    if not marker.is_file():
        return None

    try:

        name = marker.read_text(
            encoding="utf-8"
        ).strip()

    except Exception:

        return None

    if not name:
        return None

    # Only permit a simple filename.
    if Path(name).name != name:
        return None

    candidate = BASE_DIR / name

    if (
        candidate.is_file()
        and candidate.suffix.lower() == ".pcv"
    ):
        return candidate

    return None


def save_active_vault(vault):
    """
    Store the vault filename in the workspace.

    No password is stored.
    """

    WORKSPACE.mkdir(
        parents=True,
        exist_ok=True
    )

    marker = (
        WORKSPACE / ACTIVE_MARKER
    )

    marker.write_text(
        Path(vault).name,
        encoding="utf-8"
    )


# ============================================================
# PROJECT DETECTION
# ============================================================

def find_project():

    if not WORKSPACE.exists():
        return None

    bluej = list(
        WORKSPACE.rglob("package.bluej")
    )

    if bluej:
        return bluej[0].parent

    java_files = list(
        WORKSPACE.rglob("*.java")
    )

    if java_files:
        return java_files[0].parent

    return WORKSPACE


# ============================================================
# UNLOCK
# ============================================================

def unlock_vault(vault, password):

    vault = Path(vault).resolve()

    if not vault.is_file():

        raise RuntimeError(
            "The selected vault does not exist."
        )

    if WORKSPACE.exists():

        raise RuntimeError(
            "A workspace already exists.\n\n"
            "Lock the current vault first."
        )

    remove_path(TEMP_DECRYPTED)

    # --------------------------------------------------------
    # Decrypt
    # --------------------------------------------------------

    run_picocrypt(
        vault,
        password,
        encryption=False
    )

    # --------------------------------------------------------
    # PicoCrypt normally creates:
    #
    # Something.pcv
    #
    # ->
    #
    # Something
    # --------------------------------------------------------

    decrypted = (
        BASE_DIR / vault.stem
    )

    if not file_is_valid(decrypted):

        raise RuntimeError(
            "PicoCrypt reported successful decryption, "
            "but the decrypted archive could not be found.\n\n"
            f"Expected:\n{decrypted}"
        )

    try:

        decrypted.rename(
            TEMP_DECRYPTED
        )

    except Exception as exc:

        raise RuntimeError(
            "Could not prepare the decrypted archive:\n\n"
            f"{exc}"
        )

    # --------------------------------------------------------
    # Extract
    # --------------------------------------------------------

    try:

        safe_extract(
            TEMP_DECRYPTED,
            WORKSPACE
        )

        save_active_vault(
            vault
        )

    except Exception:

        remove_path(
            WORKSPACE
        )

        raise

    finally:

        remove_path(
            TEMP_DECRYPTED
        )

    return find_project()


# ============================================================
# CREATE NEW VAULT
# ============================================================

def create_vault(
    source_folder,
    vault,
    password
):

    source_folder = Path(
        source_folder
    ).resolve()

    vault = Path(
        vault
    ).resolve()

    if not source_folder.is_dir():

        raise RuntimeError(
            "The selected item is not a folder."
        )

    if source_folder == BASE_DIR.resolve():

        raise RuntimeError(
            "Do not encrypt the ProjectVault program folder."
        )

    if vault.parent != BASE_DIR.resolve():

        raise RuntimeError(
            "The vault must be created beside ProjectVault.py."
        )

    if vault.suffix.lower() != ".pcv":

        vault = vault.with_suffix(".pcv")

    if vault.exists():

        raise RuntimeError(
            f"{vault.name} already exists."
        )

    remove_path(
        TEMP_NEW_VAULT
    )

    # --------------------------------------------------------
    # Encrypt
    # --------------------------------------------------------

    run_picocrypt(
        source_folder,
        password,
        output=TEMP_NEW_VAULT,
        encryption=True
    )

    if not file_is_valid(
        TEMP_NEW_VAULT
    ):

        raise RuntimeError(
            "PicoCrypt did not produce a vault."
        )

    try:

        TEMP_NEW_VAULT.rename(
            vault
        )

    except Exception as exc:

        remove_path(
            TEMP_NEW_VAULT
        )

        raise RuntimeError(
            "Could not create the vault:\n\n"
            f"{exc}"
        )

    # IMPORTANT:
    #
    # The original folder is NOT deleted.
    #
    return vault


# ============================================================
# LOCK
# ============================================================

def lock_vault(
    vault,
    password
):

    vault = Path(
        vault
    ).resolve()

    if not WORKSPACE.is_dir():

        raise RuntimeError(
            "The workspace is not unlocked."
        )

    if not vault.is_file():

        raise RuntimeError(
            "The active vault no longer exists."
        )

    remove_path(
        TEMP_NEW_VAULT
    )

    # --------------------------------------------------------
    # Re-encrypt workspace
    # --------------------------------------------------------

    run_picocrypt(
        WORKSPACE,
        password,
        output=TEMP_NEW_VAULT,
        encryption=True
    )

    if not file_is_valid(
        TEMP_NEW_VAULT
    ):

        raise RuntimeError(
            "PicoCrypt did not create the replacement vault."
        )

    backup = (
        BASE_DIR /
        f".{vault.name}.backup"
    )

    try:

        remove_path(
            backup
        )

        # Keep old vault until new one is ready.
        vault.rename(
            backup
        )

        TEMP_NEW_VAULT.rename(
            vault
        )

    except Exception:

        remove_path(
            TEMP_NEW_VAULT
        )

        if (
            backup.exists()
            and not vault.exists()
        ):

            backup.rename(
                vault
            )

        raise

    # --------------------------------------------------------
    # Delete plaintext workspace
    # --------------------------------------------------------

    try:

        remove_path(
            WORKSPACE
        )

    except Exception as exc:

        raise RuntimeError(
            "The vault was re-encrypted, but "
            "the temporary workspace could not be deleted.\n\n"
            f"{exc}"
        )

    remove_path(
        backup
    )


# ============================================================
# EJECT
# ============================================================

def eject_drive():

    drive = BASE_DIR.drive

    if not drive:
        return False

    drive = drive.replace(
        "'",
        "''"
    )

    command = (
        "$shell=New-Object -ComObject Shell.Application;"
        "$folder=$shell.Namespace(17);"
        f"$item=$folder.ParseName('{drive}');"
        "if($item){$item.InvokeVerb('Eject')}"
    )

    try:

        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0
            ),
        )

        return True

    except Exception:

        return False


# ============================================================
# PASSWORD DIALOG
# ============================================================

class PasswordDialog(QDialog):

    def __init__(
        self,
        title,
        confirm=False,
        parent=None
    ):

        super().__init__(
            parent
        )

        self.setWindowTitle(
            title
        )

        self.setFixedWidth(
            420
        )

        layout = QVBoxLayout(
            self
        )

        heading = QLabel(
            title
        )

        heading.setObjectName(
            "Title"
        )

        layout.addWidget(
            heading
        )

        description = QLabel(
            "Enter the vault password."
        )

        if confirm:

            description.setText(
                "Enter the password twice."
            )

        description.setObjectName(
            "Subtitle"
        )

        layout.addWidget(
            description
        )

        form = QFormLayout()

        self.password_box = QLineEdit()

        self.password_box.setEchoMode(
            QLineEdit.Password
        )

        form.addRow(
            "Password:",
            self.password_box
        )

        self.confirm_box = None

        if confirm:

            self.confirm_box = QLineEdit()

            self.confirm_box.setEchoMode(
                QLineEdit.Password
            )

            form.addRow(
                "Confirm:",
                self.confirm_box
            )

        layout.addLayout(
            form
        )

        buttons = QHBoxLayout()

        cancel = QPushButton(
            "Cancel"
        )

        cancel.clicked.connect(
            self.reject
        )

        continue_button = QPushButton(
            "Continue"
        )

        continue_button.setObjectName(
            "Primary"
        )

        continue_button.clicked.connect(
            self.validate
        )

        buttons.addWidget(
            cancel
        )

        buttons.addWidget(
            continue_button
        )

        layout.addLayout(
            buttons
        )

    def validate(self):

        password = (
            self.password_box.text()
        )

        if not password:

            QMessageBox.warning(
                self,
                APP_NAME,
                "Password cannot be empty."
            )

            return

        if self.confirm_box is not None:

            if (
                password
                != self.confirm_box.text()
            ):

                QMessageBox.warning(
                    self,
                    APP_NAME,
                    "Passwords don't match."
                )

                return

        self.accept()

    def password(self):

        return self.password_box.text()


# ============================================================
# BACKGROUND WORKER
# ============================================================

class Worker(QThread):

    success = Signal(object)

    error = Signal(str)

    def __init__(
        self,
        operation
    ):

        super().__init__()

        self.operation = operation

    def run(self):

        try:

            operation = (
                self.operation[0]
            )

            if operation == "unlock":

                result = unlock_vault(
                    self.operation[1],
                    self.operation[2]
                )

            elif operation == "create":

                result = create_vault(
                    self.operation[1],
                    self.operation[2],
                    self.operation[3]
                )

            elif operation == "lock":

                result = lock_vault(
                    self.operation[1],
                    self.operation[2]
                )

            else:

                raise RuntimeError(
                    f"Unknown operation: {operation}"
                )

            self.success.emit(
                result
            )

        except Exception as exc:

            self.error.emit(
                str(exc)
            )


# ============================================================
# MAIN WINDOW
# ============================================================

class ProjectVaultWindow(QWidget):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            APP_NAME
        )

        self.setMinimumSize(
            650,
            560
        )

        self.worker = None

        self.active_vault = (
            get_active_vault()
        )

        self.build_ui()

        self.refresh()


    # ========================================================
    # BUILD UI
    # ========================================================

    def build_ui(self):

        root = QVBoxLayout(
            self
        )

        root.setContentsMargins(
            40,
            35,
            40,
            30
        )

        root.setSpacing(
            16
        )

        title = QLabel(
            "PROJECT VAULT"
        )

        title.setObjectName(
            "Title"
        )

        root.addWidget(
            title
        )

        subtitle = QLabel(
            "Encrypted USB workspace"
        )

        subtitle.setObjectName(
            "Subtitle"
        )

        root.addWidget(
            subtitle
        )

        # ----------------------------------------------------
        # Vault card
        # ----------------------------------------------------

        card = QWidget()

        card.setObjectName(
            "Card"
        )

        card_layout = QVBoxLayout(
            card
        )

        card_layout.setContentsMargins(
            25,
            25,
            25,
            25
        )

        card_layout.setSpacing(
            12
        )

        heading = QLabel(
            "Vault Selection"
        )

        heading.setStyleSheet(
            "font-size:18px;font-weight:600;"
        )

        card_layout.addWidget(
            heading
        )

        self.vault_combo = QComboBox()

        self.vault_combo.currentIndexChanged.connect(
            self.selection_changed
        )

        card_layout.addWidget(
            self.vault_combo
        )

        self.status_label = QLabel()

        self.status_label.setObjectName(
            "Status"
        )

        card_layout.addWidget(
            self.status_label
        )

        self.location_label = QLabel()

        self.location_label.setStyleSheet(
            "color:#9A9DA5;"
        )

        card_layout.addWidget(
            self.location_label
        )

        root.addWidget(
            card
        )

        # ----------------------------------------------------
        # Unlock
        # ----------------------------------------------------

        self.unlock_button = QPushButton(
            "Unlock Selected Vault"
        )

        self.unlock_button.setObjectName(
            "Primary"
        )

        self.unlock_button.setMinimumHeight(
            48
        )

        self.unlock_button.clicked.connect(
            self.unlock_clicked
        )

        root.addWidget(
            self.unlock_button
        )

        # ----------------------------------------------------
        # Create
        # ----------------------------------------------------

        self.create_button = QPushButton(
            "Encrypt Folder as New Vault"
        )

        self.create_button.setMinimumHeight(
            45
        )

        self.create_button.clicked.connect(
            self.create_clicked
        )

        root.addWidget(
            self.create_button
        )

        # ----------------------------------------------------
        # Bottom buttons
        # ----------------------------------------------------

        row = QHBoxLayout()

        self.open_button = QPushButton(
            "Open Project Folder"
        )

        self.open_button.clicked.connect(
            self.open_project
        )

        self.lock_button = QPushButton(
            "Lock & Eject"
        )

        self.lock_button.setObjectName(
            "Danger"
        )

        self.lock_button.clicked.connect(
            self.lock_clicked
        )

        row.addWidget(
            self.open_button
        )

        row.addWidget(
            self.lock_button
        )

        root.addLayout(
            row
        )

        # ----------------------------------------------------
        # Stale workspace cleanup
        # ----------------------------------------------------

        self.cleanup_button = QPushButton(
            "Remove Stale Workspace"
        )

        self.cleanup_button.clicked.connect(
            self.cleanup_clicked
        )

        self.cleanup_button.hide()

        root.addWidget(
            self.cleanup_button
        )

        # ----------------------------------------------------
        # Progress
        # ----------------------------------------------------

        self.progress = QProgressBar()

        self.progress.setRange(
            0,
            0
        )

        self.progress.hide()

        root.addWidget(
            self.progress
        )

        # ----------------------------------------------------
        # Info
        # ----------------------------------------------------

        self.info_label = QLabel()

        self.info_label.setWordWrap(
            True
        )

        self.info_label.setStyleSheet(
            "color:#777B85;font-size:12px;"
        )

        root.addWidget(
            self.info_label
        )

        root.addStretch()

        footer = QLabel(
            "ProjectVault • ProjectVaultPico"
        )

        footer.setAlignment(
            Qt.AlignCenter
        )

        footer.setStyleSheet(
            "color:#555861;"
        )

        root.addWidget(
            footer
        )


    # ========================================================
    # REFRESH
    # ========================================================

    def refresh(self):

        found = get_vaults()

        self.vault_combo.blockSignals(
            True
        )

        previous = (
            self.vault_combo.currentData()
        )

        self.vault_combo.clear()

        for vault in found:

            self.vault_combo.addItem(
                vault.name,
                str(vault)
            )

        if previous:

            index = (
                self.vault_combo.findData(
                    previous
                )
            )

            if index >= 0:

                self.vault_combo.setCurrentIndex(
                    index
                )

        self.vault_combo.blockSignals(
            False
        )

        # ----------------------------------------------------
        # Workspace exists
        # ----------------------------------------------------

        if WORKSPACE.exists():

            self.active_vault = (
                get_active_vault()
            )

            if self.active_vault is None:

                self.status_label.setText(
                    "Workspace detected — active vault unknown"
                )

                self.status_label.setStyleSheet(
                    "color:#E0A458;"
                )

                self.location_label.setText(
                    "The workspace cannot safely be associated "
                    "with a vault."
                )

                self.unlock_button.setEnabled(
                    False
                )

                self.create_button.setEnabled(
                    False
                )

                self.open_button.setEnabled(
                    False
                )

                self.lock_button.setEnabled(
                    False
                )

                self.cleanup_button.show()

                self.info_label.setText(
                    "If this is leftover test data you no longer need, "
                    "remove it with the button below."
                )

                return

            self.status_label.setText(
                "Workspace UNLOCKED"
            )

            self.status_label.setStyleSheet(
                "color:#57C785;"
            )

            self.location_label.setText(
                f"Active vault: {self.active_vault.name}"
            )

            self.unlock_button.setEnabled(
                False
            )

            self.create_button.setEnabled(
                False
            )

            self.open_button.setEnabled(
                True
            )

            self.lock_button.setEnabled(
                True
            )

            self.cleanup_button.hide()

            self.info_label.setText(
                f"Working directory:\n{WORKSPACE}"
            )

            return

        # ----------------------------------------------------
        # No workspace
        # ----------------------------------------------------

        self.cleanup_button.hide()

        self.open_button.setEnabled(
            False
        )

        self.lock_button.setEnabled(
            False
        )

        self.active_vault = None

        # ----------------------------------------------------
        # Vaults exist
        # ----------------------------------------------------

        if found:

            self.status_label.setText(
                f"{len(found)} vault"
                + (
                    "s"
                    if len(found) != 1
                    else ""
                )
                + " found"
            )

            self.status_label.setStyleSheet(
                "color:#9A9DA5;"
            )

            self.location_label.setText(
                "Select a vault and unlock it."
            )

            self.unlock_button.setEnabled(
                self.selected_vault()
                is not None
            )

            self.create_button.setEnabled(
                True
            )

            self.info_label.setText(
                "You can create additional vaults without "
                "changing the existing ones."
            )

            return

        # ----------------------------------------------------
        # No vaults
        # ----------------------------------------------------

        self.status_label.setText(
            "No vaults found"
        )

        self.status_label.setStyleSheet(
            "color:#E0A458;"
        )

        self.location_label.setText(
            "Create your first encrypted vault."
        )

        self.unlock_button.setEnabled(
            False
        )

        self.create_button.setEnabled(
            True
        )

        self.info_label.setText(
            "Use Encrypt Folder as New Vault to create "
            "your first .pcv file."
        )


    # ========================================================
    # SELECTED VAULT
    # ========================================================

    def selected_vault(self):

        value = (
            self.vault_combo.currentData()
        )

        if not value:
            return None

        path = Path(
            value
        )

        if not path.is_file():
            return None

        return path


    def selection_changed(self):

        if (
            self.worker is not None
            or WORKSPACE.exists()
        ):
            return

        vault = (
            self.selected_vault()
        )

        if vault:

            self.location_label.setText(
                f"Selected: {vault.name}"
            )

        self.unlock_button.setEnabled(
            vault is not None
        )


    # ========================================================
    # BUSY STATE
    # ========================================================

    def set_busy(self, busy):

        self.progress.setVisible(
            busy
        )

        self.vault_combo.setEnabled(
            not busy
        )

        self.unlock_button.setEnabled(
            (
                not busy
                and not WORKSPACE.exists()
                and self.selected_vault() is not None
            )
        )

        self.create_button.setEnabled(
            (
                not busy
                and not WORKSPACE.exists()
            )
        )

        self.open_button.setEnabled(
            (
                not busy
                and WORKSPACE.exists()
            )
        )

        self.lock_button.setEnabled(
            (
                not busy
                and WORKSPACE.exists()
                and self.active_vault is not None
            )
        )


    # ========================================================
    # START WORKER
    # ========================================================

    def start_worker(
        self,
        operation
    ):

        self.set_busy(
            True
        )

        self.worker = Worker(
            operation
        )

        self.worker.success.connect(
            self.operation_success
        )

        self.worker.error.connect(
            self.operation_error
        )

        self.worker.finished.connect(
            self.worker_finished
        )

        self.worker.start()


    # ========================================================
    # UNLOCK BUTTON
    # ========================================================

    def unlock_clicked(self):

        vault = (
            self.selected_vault()
        )

        if vault is None:

            QMessageBox.warning(
                self,
                APP_NAME,
                "Select a vault first."
            )

            return

        dialog = PasswordDialog(
            f"Unlock {vault.name}",
            confirm=False,
            parent=self
        )

        if (
            dialog.exec()
            != QDialog.Accepted
        ):
            return

        self.start_worker(
            (
                "unlock",
                vault,
                dialog.password()
            )
        )


    # ========================================================
    # CREATE BUTTON
    # ========================================================

    def create_clicked(self):

        if WORKSPACE.exists():

            QMessageBox.warning(
                self,
                APP_NAME,
                "Lock the current workspace first."
            )

            return

        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Encrypt",
            str(BASE_DIR.parent)
        )

        if not folder:
            return

        source = Path(
            folder
        ).resolve()

        if source == BASE_DIR.resolve():

            QMessageBox.warning(
                self,
                APP_NAME,
                "Do not select the ProjectVault program folder."
            )

            return

        default_name = (
            source.name
            + ".pcv"
        )

        name, ok = QInputDialog.getText(
            self,
            "New Vault",
            "Vault filename:",
            QLineEdit.Normal,
            default_name
        )

        if not ok:
            return

        name = name.strip()

        if not name:

            QMessageBox.warning(
                self,
                APP_NAME,
                "Vault filename cannot be empty."
            )

            return

        if not name.lower().endswith(
            ".pcv"
        ):

            name += ".pcv"

        if Path(name).name != name:

            QMessageBox.warning(
                self,
                APP_NAME,
                "Enter only a filename."
            )

            return

        vault = (
            BASE_DIR / name
        )

        if vault.exists():

            QMessageBox.warning(
                self,
                APP_NAME,
                f"{name} already exists."
            )

            return

        dialog = PasswordDialog(
            f"Create {name}",
            confirm=True,
            parent=self
        )

        if (
            dialog.exec()
            != QDialog.Accepted
        ):
            return

        self.start_worker(
            (
                "create",
                source,
                vault,
                dialog.password()
            )
        )


    # ========================================================
    # LOCK BUTTON
    # ========================================================

    def lock_clicked(self):

        if not WORKSPACE.exists():

            QMessageBox.warning(
                self,
                APP_NAME,
                "No workspace is unlocked."
            )

            return

        if self.active_vault is None:

            self.active_vault = (
                get_active_vault()
            )

        if self.active_vault is None:

            QMessageBox.critical(
                self,
                APP_NAME,
                "Active vault is unknown."
            )

            return

        answer = QMessageBox.question(
            self,
            "Lock Project",
            (
                f"Lock '{self.active_vault.name}' "
                "and eject the USB?\n\n"
                "Save your work first."
            ),
            QMessageBox.Yes
            | QMessageBox.No,
            QMessageBox.No
        )

        if answer != QMessageBox.Yes:
            return

        dialog = PasswordDialog(
            f"Lock {self.active_vault.name}",
            confirm=False,
            parent=self
        )

        if (
            dialog.exec()
            != QDialog.Accepted
        ):
            return

        self.start_worker(
            (
                "lock",
                self.active_vault,
                dialog.password()
            )
        )


    # ========================================================
    # OPERATION SUCCESS
    # ========================================================

    def operation_success(
        self,
        result
    ):

        operation = (
            self.worker.operation[0]
        )

        # ----------------------------------------------------
        # Unlock
        # ----------------------------------------------------

        if operation == "unlock":

            self.active_vault = (
                get_active_vault()
            )

            self.refresh()

            QMessageBox.information(
                self,
                APP_NAME,
                (
                    f"'{self.active_vault.name}' "
                    "unlocked successfully."
                )
            )

            self.open_project()

        # ----------------------------------------------------
        # Create
        # ----------------------------------------------------

        elif operation == "create":

            created = Path(
                result
            )

            self.refresh()

            index = (
                self.vault_combo.findData(
                    str(created)
                )
            )

            if index >= 0:

                self.vault_combo.setCurrentIndex(
                    index
                )

            QMessageBox.information(
                self,
                APP_NAME,
                (
                    f"Created:\n\n"
                    f"{created.name}\n\n"
                    "The original folder was left unchanged."
                )
            )

        # ----------------------------------------------------
        # Lock
        # ----------------------------------------------------

        elif operation == "lock":

            locked_name = (
                self.active_vault.name
            )

            self.active_vault = None

            self.refresh()

            ejected = eject_drive()

            message = (
                f"'{locked_name}' was locked successfully.\n\n"
                "The temporary workspace was deleted."
            )

            if ejected:

                message += (
                    "\n\nWindows was asked to eject the drive."
                )

            else:

                message += (
                    "\n\nWindows did not report a successful "
                    "eject request."
                )

            QMessageBox.information(
                self,
                APP_NAME,
                message
            )

            self.close()


    # ========================================================
    # ERROR
    # ========================================================

    def operation_error(
        self,
        message
    ):

        self.set_busy(
            False
        )

        QMessageBox.critical(
            self,
            "ProjectVault Error",
            message
        )

        self.refresh()


    # ========================================================
    # WORKER FINISHED
    # ========================================================

    def worker_finished(self):

        self.worker = None

        self.set_busy(
            False
        )

        self.refresh()


    # ========================================================
    # CLEANUP
    # ========================================================

    def cleanup_clicked(self):

        if not WORKSPACE.exists():

            self.refresh()

            return

        answer = QMessageBox.warning(
            self,
            APP_NAME,
            (
                "This workspace cannot be associated "
                "with a vault.\n\n"
                "Only use this for leftover test data "
                "that you no longer need.\n\n"
                "Delete .ProjectVault_Work?"
            ),
            QMessageBox.Yes
            | QMessageBox.No,
            QMessageBox.No
        )

        if answer != QMessageBox.Yes:
            return

        try:

            remove_path(
                WORKSPACE
            )

            self.active_vault = None

            self.refresh()

        except Exception as exc:

            QMessageBox.critical(
                self,
                APP_NAME,
                (
                    "Could not remove the workspace:\n\n"
                    f"{exc}"
                )
            )


    # ========================================================
    # OPEN PROJECT
    # ========================================================

    def open_project(self):

        project = (
            find_project()
        )

        if project is None:

            QMessageBox.information(
                self,
                APP_NAME,
                "No project was detected."
            )

            return

        try:

            os.startfile(
                str(project)
            )

        except Exception as exc:

            QMessageBox.warning(
                self,
                APP_NAME,
                (
                    "Could not open the project folder:\n\n"
                    f"{exc}"
                )
            )


    # ========================================================
    # CLOSE
    # ========================================================

    def closeEvent(
        self,
        event
    ):

        if (
            self.worker is not None
            and self.worker.isRunning()
        ):

            QMessageBox.warning(
                self,
                APP_NAME,
                "Please wait for the current operation to finish."
            )

            event.ignore()

            return

        if WORKSPACE.exists():

            QMessageBox.warning(
                self,
                APP_NAME,
                (
                    "The vault is still unlocked.\n\n"
                    "Lock it before closing ProjectVault."
                )
            )

            event.ignore()

            return

        event.accept()


# ============================================================
# MAIN
# ============================================================

def main():

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        APP_NAME
    )

    app.setStyleSheet(
        STYLE
    )

    window = ProjectVaultWindow()

    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":

    main()
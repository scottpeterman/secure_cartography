import sys
from pathlib import Path
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QUrl, QObject, pyqtSlot, Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QApplication, QMessageBox
from PyQt6.QtWebEngineWidgets import QWebEngineView
from importlib.resources import files
import base64
import logging

from secure_cartography.credslib import SecureCredentials

logger = logging.getLogger(__name__)


class WebPasswordDialog(QDialog):
    def __init__(self, creds_manager):
        super().__init__()
        self.creds_manager = creds_manager
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.resize(800, 600)

        layout = QVBoxLayout(self)
        self.web = QWebEngineView()
        layout.addWidget(self.web)

        self.channel = QWebChannel()
        self.web.page().setWebChannel(self.channel)

        class Bridge(QObject):
            def __init__(self, dialog):
                super().__init__()
                self.dialog = dialog
                self.attempts = 0
                self.max_attempts = 3

            @pyqtSlot(str)
            def submitPassword(self, password):
                if not password:
                    self.dialog.web.page().runJavaScript('alert("Password cannot be empty")')
                    return

                self.attempts += 1
                is_unlocked = self.dialog.creds_manager.unlock(password)

                if not is_unlocked:
                    remaining = self.max_attempts - self.attempts
                    if remaining > 0:
                        self.dialog.web.page().runJavaScript(
                            f'alert("Invalid password. {remaining} attempts remaining.")'
                        )
                    else:
                        self.dialog.web.page().runJavaScript(
                            'alert("Maximum attempts reached. Application will now close.")'
                        )
                        self.dialog.reject()
                    return

                try:
                    config_dir = self.dialog.creds_manager._get_config_dir()
                    creds_path = Path(config_dir) / "NetworkMapper.yaml"
                    if not creds_path.exists():
                        self.dialog.accept()  # New installation
                        return

                    creds = self.dialog.creds_manager.load_credentials(creds_path)
                    if not creds:
                        self.dialog.accept()  # Empty credentials file
                        return

                    # Try decrypting first credential to verify the key
                    self.dialog.creds_manager.decrypt_value(creds[0]['primary_password'])
                    self.dialog.accept()

                except Exception as e:
                    QMessageBox.critical(self.dialog, 'Invalid Password',
                                         "Failed to decrypt credentials with provided password.")
                    self.dialog.reject()

            @pyqtSlot()
            def resetCredentials(self):
                reply = QMessageBox.warning(
                    self.dialog,
                    "Reset Credentials",
                    "Warning: This will remove all stored credentials and reset the master password.\n\n"
                    "You will need to re-enter your credentials after this operation.\n\n"
                    "Are you sure you want to continue?",
                    QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Cancel
                )

                if reply == QMessageBox.StandardButton.Ok:
                    try:
                        # Remove the salt file
                        salt_path = Path(self.dialog.creds_manager._get_config_dir()) / ".salt"
                        if salt_path.exists():
                            salt_path.unlink()

                        # Remove credential files
                        config_dir = Path(self.dialog.creds_manager._get_config_dir())
                        cred_files = ["NetworkMapper.yaml", "network_mapper_passwords.yaml", "credentials.yaml"]
                        for file in cred_files:
                            creds_path = config_dir / file
                            if creds_path.exists():
                                creds_path.unlink()

                        # Clear keyring
                        try:
                            import keyring
                            keyring.delete_password(self.dialog.creds_manager.app_name,
                                                    self.dialog.creds_manager.key_identifier)
                        except Exception as e:
                            logger.warning(f"Could not clear keyring entry: {e}")

                        self.dialog.web.page().runJavaScript(
                            'alert("Credentials have been reset. The application will now shutdown.\n\n'
                            'Next login, you will be prompted to create a new master password.")'
                        )

                        self.dialog.creds_manager.is_initialized = False
                        sys.exit()

                    except Exception as e:
                        self.dialog.web.page().runJavaScript(
                            f'alert("Failed to reset credentials: {str(e)}\\n\\nPlease try again.")'
                        )

        self.bridge = Bridge(self)
        self.channel.registerObject('qt', self.bridge)

        background_path = files('secure_cartography.resources') / 'splash.jpeg'
        with open(background_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()

        html_content = '''
        <!DOCTYPE html>
        <html>
        <head>
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.js"></script>
            <style>
            body {
                    margin: 0;
                    height: 100vh;
                    background: linear-gradient(rgba(0, 0, 0, 0.6), rgba(0, 0, 0, 0.6)), 
                          url('data:image/jpeg;base64,''' + img_data + '''') center/cover no-repeat;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-family: Arial, sans-serif;
                }
                @keyframes glow {
                    0% { box-shadow: 0 0 5px #0ff, 0 0 10px #0ff, 0 0 15px #0ff; }
                    50% { box-shadow: 0 0 10px #0ff, 0 0 20px #0ff, 0 0 30px #0ff; }
                    100% { box-shadow: 0 0 5px #0ff, 0 0 10px #0ff, 0 0 15px #0ff; }
                }
                @keyframes scanline {
                    0% { transform: translateY(-100%); }
                    100% { transform: translateY(100%); }
                }
                .cyberpunk-input {
                    background: rgba(0, 255, 255, 0.1);
                    border: 1px solid #0ff;
                    color: #0ff;
                    text-shadow: 0 0 5px #0ff;
                }
                .cyberpunk-input:focus {
                    animation: glow 1.5s ease-in-out infinite;
                    outline: none;
                    color: #000000;
                }
                .cyberpunk-button {
                    background: linear-gradient(45deg, #0ff, #00b3ff);
                    border: 1px solid #0ff;
                    text-transform: uppercase;
                    letter-spacing: 2px;
                    position: relative;
                    overflow: hidden;
                }
                .cyberpunk-button:before {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: linear-gradient(transparent 50%, rgba(0, 255, 255, 0.2) 50%);
                    background-size: 100% 4px;
                    animation: scanline 4s linear infinite;
                }
                .reset-button {
                    background: linear-gradient(45deg, #ff0055, #ff0088);
                    border: 1px solid #ff0055;
                }
                .hud-box {
                    border: 1px solid #0ff;
                    background: rgba(0, 0, 0, 0.8);
                    backdrop-filter: blur(10px);
                    position: relative;
                }
                .hud-box:before {
                    content: '';
                    position: absolute;
                    top: -1px;
                    left: -1px;
                    right: -1px;
                    bottom: -1px;
                    background: linear-gradient(45deg, #0ff, transparent);
                    z-index: -1;
                }
            </style>
        </head>
        <body>
            <div class="hud-box p-8 w-96">
                <h2 class="text-3xl font-bold mb-8 text-cyan-400 text-center tracking-wider">SECURE CARTOGRAPHY</h2>
                <form id="passwordForm" class="space-y-6">
                    <div class="relative">
                        &nbsp;&nbsp;<input type="password" 
                               id="masterPassword" 
                               placeholder="ENTER MASTER KEY" 
                               autocomplete="off"
                               class="cyberpunk-input w-full p-3 text-lg placeholder-cyan-300 bg-opacity-20">
                    </div>
                    <button type="submit" 
                            class="cyberpunk-button w-full p-3 text-white font-bold hover:brightness-125 transition-all duration-300">
                        UNLOCK SYSTEM
                    </button>
                    <button type="button" 
                            id="resetBtn"
                            class="cyberpunk-button reset-button w-full p-3 text-white font-bold hover:brightness-125 transition-all duration-300">
                        RESET CREDENTIALS
                    </button>
                    <div id="error-message" class="text-red-400 text-center hidden"></div>
                </form>
            </div>
            <script>
                new QWebChannel(qt.webChannelTransport, function(channel) {
                    window.qt = channel.objects.qt;

                    const form = document.getElementById('passwordForm');
                    const input = document.getElementById('masterPassword');
                    const resetBtn = document.getElementById('resetBtn');

                    form.onsubmit = function(e) {
                        e.preventDefault();
                        if (!input.value.trim()) {
                            document.getElementById('error-message').style.display = 'block';
                            document.getElementById('error-message').textContent = 'Password cannot be empty';
                            return;
                        }
                        window.qt.submitPassword(input.value);
                        input.value = '';
                    };

                    resetBtn.onclick = function() {
                        window.qt.resetCredentials();
                    };
                });
            </script>
        </body>
        </html>
        '''

        self.web.setHtml(html_content)


def main():
    app = QApplication(sys.argv)
    creds_manager = SecureCredentials()
    password_dialog = WebPasswordDialog(creds_manager)
    result = password_dialog.exec()

    if result == QDialog.DialogCode.Accepted:
        print("Password accepted!")
    else:
        print("Login cancelled")

    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
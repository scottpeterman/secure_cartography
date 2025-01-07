from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QApplication
from PyQt6.QtCore import Qt, QTimer
import json
import sys
from secure_cartography.mviewer import TopologyViewer


class TopologyPreviewWidget(QWidget):
    def __init__(self, parent=None, dark_mode=True):
        super().__init__(parent)
        self.dark_mode = dark_mode
        self.current_json_path = None
        self.setup_ui()
        self.clear_view()  # Initialize with empty view

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

    def clear_view(self):
        """Load an empty view with appropriate theme background"""
        background_color = "#000000" if self.dark_mode else "#FFFFFF"
        text_color = "#FFFFFF" if self.dark_mode else "#000000"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    background-color: {background_color};
                    color: {text_color};
                    height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    font-family: system-ui, -apple-system, sans-serif;
                }}
            </style>
        </head>
        <body>
        </body>
        </html>
        """
        self.web_view.setHtml(html_content)
        self.inject_scrollbar_style()

    def set_dark_mode(self, is_dark: bool):
        """Update the dark mode state and refresh the view"""
        if self.dark_mode != is_dark:
            self.dark_mode = is_dark
            if self.current_json_path:
                self.load_topology(self.current_json_path)
            else:
                self.clear_view()

    def inject_scrollbar_style(self):
        """Inject scrollbar styling based on current theme"""
        scrollbar_script = """
            (function() {
                const darkMode = %s;
                const style = document.createElement('style');
                style.type = 'text/css';
                if (darkMode) {
                    style.innerHTML = `
                        ::-webkit-scrollbar {
                            width: 12px;
                        }
                        ::-webkit-scrollbar-thumb {
                            background-color: #444;
                            border-radius: 6px;
                        }
                        ::-webkit-scrollbar-thumb:hover {
                            background-color: #555;
                        }
                        ::-webkit-scrollbar-track {
                            background-color: #1a1a1a;
                        }
                    `;
                } else {
                    style.innerHTML = `
                        ::-webkit-scrollbar {
                            width: 12px;
                        }
                        ::-webkit-scrollbar-thumb {
                            background-color: #ccc;
                            border-radius: 6px;
                        }
                        ::-webkit-scrollbar-thumb:hover {
                            background-color: #aaa;
                        }
                        ::-webkit-scrollbar-track {
                            background-color: #f5f5f5;
                        }
                    `;
                }
                document.head.appendChild(style);
            })();
        """ % ("true" if self.dark_mode else "false")

        self.web_view.page().runJavaScript(scrollbar_script)

    def load_topology(self, json_path):
        """Load and display a topology from a JSON file"""
        try:
            self.current_json_path = json_path
            with open(json_path) as f:
                topology_data = json.load(f)
                viewer = TopologyViewer(topology_data=topology_data, dark_mode=self.dark_mode)
                viewer.layout_combo.setCurrentText('LR')
                html_content = viewer.generate_html(viewer.generate_mermaid(), show_device_list=False)
                self.web_view.setHtml(html_content)

            # Delay scrollbar style injection to ensure content is loaded
            QTimer.singleShot(1000, self.inject_scrollbar_style)

        except Exception as e:
            print(f"Error loading topology: {e}")
            error_message = f"""
            <h1 style="color: {'white' if self.dark_mode else 'black'}">
                Error loading topology: {str(e)}
            </h1>
            """
            self.web_view.setHtml(error_message)
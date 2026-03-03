import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from app import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Orbit Sample Manager")

    # Base font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

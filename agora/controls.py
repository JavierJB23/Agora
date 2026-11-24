"""Safe form widgets: scrolling the page must never change exam settings."""
from PySide6.QtWidgets import QComboBox, QSpinBox, QDoubleSpinBox

class SafeComboBox(QComboBox):
    def wheelEvent(self, event):
        # The popup list handles its own scrolling; the closed field never changes.
        event.ignore()

class SafeSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()

class SafeDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event):
        event.ignore()

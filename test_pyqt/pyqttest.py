import typing

from PyQt5.QtCore import QObject, pyqtProperty, pyqtSignal


@typing.final
class FeatureModel(QObject):

    stateChanged = pyqtSignal()

    def __init__(self, enabled: bool, /) -> None:
        super().__init__()
        self._enabled = enabled

    @pyqtProperty(bool, notify=stateChanged)
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, enabled):
        self._enabled = enabled
        self.stateChanged.emit()

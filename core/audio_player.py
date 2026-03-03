import os
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import QUrl, QObject, pyqtSignal


class AudioPlayer(QObject):
    """Singleton-style audio player. Only one sample plays at a time."""

    playback_started = pyqtSignal(str)   # emits slot key of playing slot
    playback_stopped = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(1.0)
        self._current_key = None

        self._player.playbackStateChanged.connect(self._on_state_changed)

    def play(self, path: str, slot_key: str):
        """Play a file. If the same slot is already playing, stop it."""
        if self._current_key == slot_key and self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.stop()
            return

        self._player.stop()
        self._player.setSource(QUrl.fromLocalFile(os.path.abspath(path)))
        self._current_key = slot_key
        self._player.play()
        self.playback_started.emit(slot_key)

    def stop(self):
        self._player.stop()
        self._current_key = None
        self.playback_stopped.emit()

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.StoppedState:
            self._current_key = None
            self.playback_stopped.emit()

    @property
    def current_key(self):
        return self._current_key

    def is_playing(self, slot_key: str) -> bool:
        return (self._current_key == slot_key and
                self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)


# Global singleton
_player_instance = None

def get_player() -> AudioPlayer:
    global _player_instance
    if _player_instance is None:
        _player_instance = AudioPlayer()
    return _player_instance

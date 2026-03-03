import wave
import os

TARGET_SR = 44100
TARGET_BIT_DEPTH = 16


def validate_wav(path: str) -> dict:
    """
    Validate a WAV file against Orbit requirements.

    Returns a dict:
      {
        "valid": bool,
        "error": str | None,       # fatal error (unreadable file, wrong extension)
        "needs_conversion": bool,
        "info": dict               # sample_rate, bit_depth, channels, duration_sec
      }
    """
    ext = os.path.splitext(path)[1].lower()
    if ext != '.wav':
        return {
            "valid": False,
            "error": f"Only .wav files are supported.\n\nFile: {os.path.basename(path)}",
            "needs_conversion": False,
            "info": {},
        }

    try:
        with wave.open(path, 'rb') as wf:
            sr = wf.getframerate()
            bit_depth = wf.getsampwidth() * 8
            channels = wf.getnchannels()
            frames = wf.getnframes()
            duration = frames / sr if sr > 0 else 0

        info = {
            "sample_rate": sr,
            "bit_depth": bit_depth,
            "channels": channels,
            "duration_sec": duration,
        }

        needs_conversion = (sr != TARGET_SR or bit_depth != TARGET_BIT_DEPTH or channels != 1)

        return {
            "valid": not needs_conversion,
            "error": None,
            "needs_conversion": needs_conversion,
            "info": info,
        }

    except wave.Error as e:
        return {
            "valid": False,
            "error": f"Could not read WAV file: {e}\n\nFile: {os.path.basename(path)}",
            "needs_conversion": False,
            "info": {},
        }
    except Exception as e:
        return {
            "valid": False,
            "error": f"Unexpected error: {e}\n\nFile: {os.path.basename(path)}",
            "needs_conversion": False,
            "info": {},
        }

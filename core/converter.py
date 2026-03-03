import os
import tempfile
import wave

TARGET_SR = 44100
TARGET_BIT_DEPTH = 16
TARGET_SUBTYPE = "PCM_16"


def get_wav_info(path: str) -> dict:
    """Return dict with sample_rate, bit_depth, channels, duration_sec."""
    try:
        with wave.open(path, 'rb') as wf:
            sr = wf.getframerate()
            bit_depth = wf.getsampwidth() * 8
            channels = wf.getnchannels()
            frames = wf.getnframes()
            duration = frames / sr if sr > 0 else 0
            return {
                "sample_rate": sr,
                "bit_depth": bit_depth,
                "channels": channels,
                "duration_sec": duration,
                "needs_resample": sr != TARGET_SR,
                "needs_redepth": bit_depth != TARGET_BIT_DEPTH,
            }
    except Exception as e:
        return {"error": str(e)}


def convert_to_orbit_wav(src_path: str, dst_path: str) -> tuple[bool, str]:
    """
    Convert src_path to mono 16-bit 44100 Hz WAV and save to dst_path.
    Returns (success, error_message).
    """
    try:
        import soundfile as sf
        import resampy
        import numpy as np
    except ImportError as e:
        missing = str(e).split("'")[1] if "'" in str(e) else str(e)
        return False, (
            f"Missing library: '{missing}'\n\n"
            f"Please install it by running:\n\n"
            f"    pip install soundfile resampy\n\n"
            f"Then try again."
        )

    try:
        data, sr = sf.read(src_path, always_2d=False)
        import numpy as np

        # Downmix to mono — keep left channel (index 0) of stereo/multi
        if data.ndim > 1:
            data = data[:, 0]

        # Resample if needed
        if sr != TARGET_SR:
            data = resampy.resample(data, sr, TARGET_SR)

        # Clip to [-1, 1] to avoid clipping artefacts on conversion
        data = np.clip(data, -1.0, 1.0)

        os.makedirs(os.path.dirname(dst_path) or ".", exist_ok=True)
        sf.write(dst_path, data, TARGET_SR, subtype=TARGET_SUBTYPE)
        return True, ""

    except Exception as e:
        return False, f"Conversion failed: {e}"


def check_libraries_available() -> tuple[bool, str]:
    """Check if soundfile and resampy are installed."""
    missing = []
    try:
        import soundfile
    except ImportError:
        missing.append("soundfile")
    try:
        import resampy
    except ImportError:
        missing.append("resampy")

    if missing:
        libs = " ".join(missing)
        return False, (
            f"The following libraries are required for conversion but are not installed:\n\n"
            f"    pip install {libs}\n\n"
            f"Install them and restart the app."
        )
    return True, ""
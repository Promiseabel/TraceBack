"""Audio and frame extraction via ffmpeg subprocess calls.

All ffmpeg interaction is isolated in this module. No other module may call ffmpeg directly.
Raises subprocess.CalledProcessError on ffmpeg failure — callers handle recovery.

ffmpeg flag reference (confirmed standards):
  Full audio:    ffmpeg -i <video> -vn -acodec pcm_s16le -ac 2 -ar 44100 <output.wav>
  Segment audio: ffmpeg -i <video> -ss <start> -to <end>
                 -acodec pcm_s16le -ac 2 -ar 44100 <output.wav>
  Keyframe:      ffmpeg -ss <timestamp> -i <video> -frames:v 1 <output.png>
  Note: -ss before -i for fast seeking on keyframe extraction.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def extract_full_audio(video_path: Path, output_path: Path) -> Path:
    """Extract full audio track from video as PCM WAV.

    Args:
        video_path: Path to the input video file.
        output_path: Destination path for the output WAV file.

    Returns:
        output_path (unchanged).

    Raises:
        subprocess.CalledProcessError: If ffmpeg exits non-zero.
        FileNotFoundError: If ffmpeg is not on PATH.
    """
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ac", "2",
            "-ar", "44100",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )
    return output_path


def extract_segment_audio(
    video_path: Path,
    start: float,
    end: float,
    output_path: Path,
) -> Path:
    """Extract a time-bounded audio segment from video as PCM WAV.

    Args:
        video_path: Path to the input video file.
        start: Start time in seconds.
        end: End time in seconds.
        output_path: Destination path for the output WAV file.

    Returns:
        output_path (unchanged).

    Raises:
        subprocess.CalledProcessError: If ffmpeg exits non-zero.
        FileNotFoundError: If ffmpeg is not on PATH.
    """
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-ss", str(start),
            "-to", str(end),
            "-acodec", "pcm_s16le",
            "-ac", "2",
            "-ar", "44100",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )
    return output_path


def extract_frame(video_path: Path, timestamp: float, output_path: Path) -> Path:
    """Extract a single keyframe at the given timestamp as PNG.

    The -ss flag is placed before -i for fast input seeking.

    Args:
        video_path: Path to the input video file.
        timestamp: Timestamp in seconds at which to extract the frame.
        output_path: Destination path for the output PNG file.

    Returns:
        output_path (unchanged).

    Raises:
        subprocess.CalledProcessError: If ffmpeg exits non-zero.
        FileNotFoundError: If ffmpeg is not on PATH.
    """
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", str(timestamp),
            "-i", str(video_path),
            "-frames:v", "1",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )
    return output_path

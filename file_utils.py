from pathlib import Path
from config import IMAGE_EXT, VIDEO_EXT

def is_image(f: Path):
    return f.suffix.lower() in IMAGE_EXT

def is_video(f: Path):
    return f.suffix.lower() in VIDEO_EXT

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

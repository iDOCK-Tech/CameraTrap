from pathlib import Path
import sys
import os

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Model paths
BEST_MODEL_PATH = resource_path("best1.pt")  # For specific animals: leopard, tiger, hyena
WEIGHT1_MODEL_PATH = resource_path("weight1.pt")  # For human/animal classification

# Confidence thresholds
BEST_CLASS_CONF = {
    "leopard": 0.55,
    "tiger": 0.75,  # Increased from 0.55 to reduce false positives
    "hyena": 0.97,
    "elephant": 0.60,
}

# Classes to exclude from best.pt
BEST_MODEL_EXCLUDE_CLASSES = {"person"}

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}

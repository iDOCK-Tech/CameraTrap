import os, sys

# ---- HARD DISABLE YOLOv5 AUTO INSTALL / TORCH HUB ----
os.environ["YOLOv5_REQUIREMENTS"] = "0"
os.environ["TORCH_HOME"] = os.path.abspath(".")
os.environ["ULTRALYTICS_SETTINGS"] = "false"

if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")

import torch
torch.hub.load = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("torch.hub disabled"))
torch.hub._get_cache_or_reload = lambda *a, **k: None

import cv2
import warnings
from PIL import Image
from tqdm import tqdm
from pathlib import Path
import pandas as pd
from datetime import datetime

from speciesnet.classifier import SpeciesNetClassifier

# ============================================================
# SUPPRESS YOLOv5 AMP FUTURE WARNING
# ============================================================
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    message=".*torch.cuda.amp.autocast.*"
)

# ============================================================
# PATHS (EXE + SCRIPT SAFE)
# ============================================================
if hasattr(sys, "_MEIPASS"):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(__file__)

MEGADETECTOR_PATH = os.path.join(base_path, "best.pt")
SPECIESNET_PT = os.path.join(base_path, "species.pt")
SPECIESNET_LABELS = os.path.join(
    base_path,
    "species_labels.txt",
)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ============================================================
# LEOPARD SPECIES MAPPING
# ============================================================
LEOPARD_SPECIES = {
    "ocelot",
    "jaguarundi",
    "jaguar",
    "leopard tortoise",
    "leopard ctenotus",
    "margay",
    "panthera species",
    "snow leopard",
    "clouded leopard",
    "pampas cat",
}

# ============================================================
# CLEAN LABEL FUNCTION
# ============================================================
def clean_species_name(raw_label: str) -> str:
    label = raw_label.lower()
    if ";" in label:
        label = label.split(";")[-1]
    if "_" in label:
        label = label.split("_")[-1]
    label = label.replace("-", " ").replace(".", " ")
    cleaned = label.strip().title()
    
    # Check if this is a leopard species
    if cleaned.lower() in LEOPARD_SPECIES:
        return "Leopard"
    
    return cleaned


# ============================================================
# TARGET CLASS NORMALIZATION / CHECK
# - treat variants like "Animal (All)", "animals all", "AnimalAll" as the same
# ============================================================
def _normalize_target_string(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


def target_is_animals_all(target_classes) -> bool:
    if not target_classes:
        return False
    for tc in target_classes:
        if not isinstance(tc, str):
            continue
        norm = _normalize_target_string(tc)
        if "animal" in norm and "all" in norm:
            return True
    return False

# ============================================================
# LOAD MEGADETECTOR (YOLOv5) — CORRECT WAY
# ============================================================
import torch.serialization
from yolov5.models.yolo import Model
from yolov5.models.common import AutoShape

torch.serialization.add_safe_globals({Model: Model})

ckpt = torch.load(
    MEGADETECTOR_PATH,
    map_location=DEVICE,
    weights_only=False,
)

md_model = ckpt["model"].float().to(DEVICE)

# 🔑 THIS IS THE CRITICAL FIX
md_model = AutoShape(md_model)
md_model.eval()

md_model.conf = 0.30
md_model.iou = 0.45
md_model.classes = [0]  # animal by default

# ============================================================
# LOAD SPECIESNET
# ============================================================
print("[INFO] Loading SpeciesNet (explicit .pt + labels)...")

classifier = SpeciesNetClassifier.__new__(SpeciesNetClassifier)
classifier.device = DEVICE

classifier.model = torch.load(
    SPECIESNET_PT,
    map_location=DEVICE,
    weights_only=False,
)
classifier.model.eval()

for p in classifier.model.parameters():
    p.requires_grad = False

with open(SPECIESNET_LABELS, "r", encoding="utf-8") as f:
    classifier.labels = {i: line.strip() for i, line in enumerate(f.readlines())}

classifier.model_info = type(
    "ModelInfoStub",
    (),
    {"type_": "full_image"},
)()

print(f"[INFO] Loaded {len(classifier.labels)} species classes")

# ============================================================
# IMAGE PROCESSING
# ============================================================
def process_image(img_path: Path, out_dir: Path, stop_flag=None, target_classes=None, detection_mode=None):

    if stop_flag and stop_flag.is_set():
        return None

    image = cv2.imread(str(img_path))
    detected_classes = set()
    all_boxes = []

    # Check if we should show species (skip for Animal All mode)
    show_species = not target_is_animals_all(target_classes)

    # ---- SpeciesNet classification (only if showing species) ----
    if show_species:
        frame_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(frame_rgb)

        pre_img = classifier.preprocess(pil_img)
        result = classifier.predict(str(img_path), pre_img)

        if "classifications" in result:
            raw_label = result["classifications"]["classes"][0]
            species_conf = result["classifications"]["scores"][0]
            species_name = clean_species_name(raw_label)
        else:
            species_name = "Unknown"
            species_conf = 0.0
    else:
        species_name = "Animal"
        species_conf = 1.0

    species_label = f"{species_name} {species_conf:.2f}"

    # ---- MegaDetector ----
    md_model.classes = [1] if detection_mode == "human" else [0]

    results = md_model(image)

    if results.xyxy and results.xyxy[0] is not None:
        for *xyxy, conf, cls in results.xyxy[0].cpu().numpy():
            x1, y1, x2, y2 = map(int, xyxy)
            if (x2 - x1) < 40 or (y2 - y1) < 40:
                continue

            # Skip blank detections - don't draw or save
            if species_name.lower() == "blank":
                continue

            # Use MegaDetector confidence for Animal (All) mode, species confidence otherwise
            display_conf = conf if show_species == False else species_conf
            display_label = f"{species_name} {display_conf:.2f}"

            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                image,
                display_label,
                (x1, max(y1 - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
            detected_classes.add(species_name)
            all_boxes.append((x1, y1, x2 - x1, y2 - y1, species_name))

    if detection_mode == "human":
        should_save = len(all_boxes) > 0
    elif target_classes:
        if target_is_animals_all(target_classes):
            should_save = len(all_boxes) > 0
        else:
            should_save = any(
                s.lower() in [tc.lower() for tc in target_classes]
                for s in detected_classes
            )
    else:
        should_save = len(all_boxes) > 0

    if not should_save:
        return None

    save_path = out_dir / img_path.name
    cv2.imwrite(str(save_path), image)

    return {
        "filename": img_path.name,
        "filepath": str(img_path),
        "type": "image",
        "num_detections": len(all_boxes),
        "classes": ", ".join(sorted(detected_classes)),
    }

# ============================================================
# VIDEO PROCESSING
# ============================================================

# ============================================================
# SIMPLE IOU-BASED TRACKER (lightweight alternative to ByteTrack/DeepSORT)
# - assigns persistent `track_id` by IoU matching
# - caches species per `track_id` so SpeciesNet runs only when a new track appears
# ============================================================

def _iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interW = max(0, xB - xA)
    interH = max(0, yB - yA)
    interArea = interW * interH
    if interArea == 0:
        return 0.0
    boxAArea = max(0, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
    boxBArea = max(0, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))
    return interArea / float(boxAArea + boxBArea - interArea)


class Track:
    def __init__(self, tid, bbox, species=None, last_seen=0):
        self.id = tid
        self.bbox = bbox  # [x1,y1,x2,y2]
        self.species = species
        self.species_conf = 0.0
        self.last_seen = last_seen
        self.missed = 0


class SimpleTracker:
    def __init__(self, iou_threshold=0.3, max_age=30):
        self.tracks = {}
        self.next_id = 1
        self.iou_threshold = iou_threshold
        self.max_age = max_age

    def update(self, detections, frame_idx):
        """
        detections: list of [x1,y1,x2,y2]
        returns list of tuples (track_id, bbox, is_new)
        """
        assigned = []
        unmatched = set(range(len(detections)))

        # try to match existing tracks by IoU
        for tid, track in list(self.tracks.items()):
            best_iou = 0.0
            best_det = -1
            for di in list(unmatched):
                i = _iou(track.bbox, detections[di])
                if i > best_iou:
                    best_iou = i
                    best_det = di

            if best_iou >= self.iou_threshold and best_det != -1:
                det_bbox = detections[best_det]
                track.bbox = det_bbox
                track.last_seen = frame_idx
                track.missed = 0
                assigned.append((tid, det_bbox, False))
                unmatched.remove(best_det)
            else:
                track.missed += 1

        # create new tracks for remaining detections
        for di in list(unmatched):
            bbox = detections[di]
            tid = self.next_id
            self.next_id += 1
            self.tracks[tid] = Track(tid, bbox, species=None, last_seen=frame_idx)
            assigned.append((tid, bbox, True))

        # remove old tracks
        stale = [tid for tid, tr in self.tracks.items() if tr.missed > self.max_age]
        for tid in stale:
            del self.tracks[tid]

        return assigned

    def predict(self, frame_idx):
        """Return current tracks as assigned when detector is skipped.
        Increments missed for each track (no detection this frame).
        """
        assigned = []
        for tid, tr in list(self.tracks.items()):
            tr.missed += 1
            if tr.missed <= self.max_age:
                assigned.append((tid, tr.bbox, False))

        # remove stale tracks
        stale = [tid for tid, tr in self.tracks.items() if tr.missed > self.max_age]
        for tid in stale:
            del self.tracks[tid]

        return assigned


# single global tracker instance used for video processing
video_tracker = SimpleTracker(iou_threshold=0.3, max_age=30)

def process_video(video_path: Path, out_dir: Path, stop_flag=None, target_classes=None, detection_mode=None, detector_interval=5, detector_width=512):

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None

    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    temp_out = out_dir / ("temp_" + video_path.name)
    writer = cv2.VideoWriter(
        str(temp_out),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (w, h),
    )

    # start timing for this video
    start_time = datetime.now()

    detected_classes = set()
    any_detect = False
    has_matching_detection = False

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Check if we should show species (skip for Animal All mode)
    show_species = not target_is_animals_all(target_classes)

    for frame_idx in tqdm(range(total_frames), desc="Processing video", unit="frame"):

        if stop_flag and stop_flag.is_set():
            break

        ret, frame = cap.read()
        if not ret:
            break

        all_boxes = []

        # prepare scaled frame for faster detection/tracking/classification
        orig_h, orig_w = frame.shape[:2]
        target_w = int(detector_width)
        if orig_w > target_w:
            scale = target_w / orig_w
        else:
            scale = 1.0

        scaled_w = max(1, int(orig_w * scale))
        scaled_h = max(1, int(orig_h * scale))
        if scale != 1.0:
            scaled_frame = cv2.resize(frame, (scaled_w, scaled_h))
        else:
            scaled_frame = frame

        # Run MegaDetector only every `detector_interval` frames (and on frame 0)
        bbox_conf_map = {}
        if frame_idx % detector_interval == 0:
            md_model.classes = [1] if detection_mode == "human" else [0]
            results = md_model(scaled_frame)

            # collect raw detections in scaled frame coordinates for association
            det_boxes = []
            bbox_conf_map = {}  # Store MegaDetector confidence keyed by bbox tuple
            if results.xyxy and results.xyxy[0] is not None:
                for (*xyxy, conf, cls) in results.xyxy[0].cpu().numpy():
                    x1s, y1s, x2s, y2s = map(int, xyxy)
                    if (x2s - x1s) < 40 or (y2s - y1s) < 40:
                        continue
                    bbox = [x1s, y1s, x2s, y2s]
                    det_boxes.append(bbox)
                    bbox_conf_map[tuple(bbox)] = float(conf)

            # update tracker with fresh detections (scaled coords)
            assigned = video_tracker.update(det_boxes, frame_idx)
        else:
            # skip running detector — predict/return existing tracks (scaled coords)
            assigned = video_tracker.predict(frame_idx)

        # annotate frame and run SpeciesNet only for newly created tracks
        for (tid, bbox, is_new) in assigned:
            x1s, y1s, x2s, y2s = bbox
            species_name = "Unknown"
            species_conf = 0.0
            bbox_conf = bbox_conf_map.get(tuple(bbox), 0.0)  # Get MegaDetector confidence

            if is_new:
                # crop and classify only for the new track using the scaled frame (if showing species)
                if show_species:
                    x1c = max(0, x1s)
                    y1c = max(0, y1s)
                    x2c = min(scaled_w, x2s)
                    y2c = min(scaled_h, y2s)
                    crop = scaled_frame[y1c:y2c, x1c:x2c]
                    if crop.size > 0:
                        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                        pil_crop = Image.fromarray(crop_rgb)
                        pre_img = classifier.preprocess(pil_crop)
                        result = classifier.predict(f"track_{tid}_frame_{frame_idx}", pre_img)
                        if "classifications" in result:
                            raw_label = result["classifications"]["classes"][0]
                            species_conf = result["classifications"]["scores"][0]
                            species_name = clean_species_name(raw_label)
                else:
                    # For Animal All mode use MegaDetector label/conf
                    if detection_mode == "human":
                        species_name = "Human"
                        species_conf = bbox_conf
                    else:
                        species_name = "Animal"
                        species_conf = bbox_conf
                # cache into track (scaled coords)
                video_tracker.tracks[tid].species = species_name
                video_tracker.tracks[tid].species_conf = species_conf
            else:
                # reuse cached species
                tr = video_tracker.tracks.get(tid)
                if tr is not None:
                    species_name = tr.species or "Unknown"
                    species_conf = getattr(tr, "species_conf", 0.0)

            # Skip blank detections when species classifier returned blank
            if show_species and species_name.lower() == "blank":
                continue

            # Determine display label
            if detection_mode == "human":
                display_label = f"Human {bbox_conf:.2f}"
            elif show_species:
                display_label = f"{species_name} {species_conf:.2f}"
            else:
                display_label = f"Animal {bbox_conf:.2f}"

            # map bbox from scaled coords back to original frame coords for drawing/saving
            if scale != 0:
                inv_scale = 1.0 / scale
            else:
                inv_scale = 1.0
            x1 = int(x1s * inv_scale)
            y1 = int(y1s * inv_scale)
            x2 = int(x2s * inv_scale)
            y2 = int(y2s * inv_scale)

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                frame,
                display_label,
                (x1, max(y1 - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
            # record detected class for summaries
            detected_classes.add("Human" if detection_mode == "human" else ("Animal" if not show_species else species_name))
            all_boxes.append(species_name if show_species else ("Human" if detection_mode == "human" else "Animal"))

        if all_boxes:
            any_detect = True
            if detection_mode == "human":
                has_matching_detection = True
            elif target_classes:
                if target_is_animals_all(target_classes):
                    has_matching_detection = True
                else:
                    has_matching_detection |= any(
                        s.lower() in [tc.lower() for tc in target_classes]
                        for s in detected_classes
                    )
            else:
                has_matching_detection = True

        writer.write(frame)

    cap.release()
    writer.release()

    # print elapsed time for this video processing
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"[INFO] Video {video_path.name} processed in {elapsed:.2f}s")

    if not any_detect or not has_matching_detection:
        temp_out.unlink(missing_ok=True)
        return None

    final_out = out_dir / video_path.name
    if final_out.exists():
        final_out.unlink()
    os.replace(temp_out, final_out)

    return {
        "filename": video_path.name,
        "filepath": str(video_path),
        "type": "video",
        "num_detections": "multiple",
        "classes": ", ".join(sorted(detected_classes)),
    }

# ============================================================
# MAIN ENTRY
# ============================================================
def run_detection(input_dir, output_dir, progress_cb, device_cb=None, stop_flag=None, target_classes=None, detection_mode=None):

    if device_cb:
        device_cb("GPU" if torch.cuda.is_available() else "CPU")

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    from file_utils import is_image, is_video

    files = [f for f in input_dir.iterdir() if f.is_file() and (is_image(f) or is_video(f))]
    logs = []

    # start total run timer
    run_start = datetime.now()

    should_continue = progress_cb(0, len(files))
    if should_continue is False:
        return None, []

    for idx, file in enumerate(files, 1):

        if stop_flag and stop_flag.is_set():
            break

        if is_image(file):
            info = process_image(file, output_dir, stop_flag, target_classes, detection_mode)
        else:
            info = process_video(file, output_dir, stop_flag, target_classes, detection_mode)

        if info:
            logs.append(info)

        if progress_cb(idx, len(files)) is False:
            break

    if logs:
        excel_path = output_dir / f"detections_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        pd.DataFrame(logs).to_excel(excel_path, index=False)
        total_elapsed = (datetime.now() - run_start).total_seconds()
        print(f"[INFO] Total processing time: {total_elapsed:.2f}s")
        return excel_path, logs

    total_elapsed = (datetime.now() - run_start).total_seconds()
    print(f"[INFO] Total processing time: {total_elapsed:.2f}s")
    return None, []

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

COLORS = ["BLUE", "CYAN", "GREEN", "ORANGE", "PINK", "RED", "YELLOW"]
SLOTS = list(range(8))
SIDES = ["L", "R"]
INDICES = list(range(4))


def empty_slot_data():
    data = {}
    for side in SIDES:
        for idx in INDICES:
            data[f"{side}{idx}"] = None
    return data


def empty_project():
    colors = {}
    for color in COLORS:
        colors[color] = {"slots": {str(s): empty_slot_data() for s in SLOTS}}
    return colors


class Project:
    def __init__(self):
        self.project_path = None
        self.project_name = "Untitled Project"
        self.created = datetime.now().isoformat()
        self.colors = empty_project()

    @property
    def json_path(self):
        if self.project_path:
            return os.path.join(self.project_path, "project.json")
        return None

    def to_dict(self):
        return {
            "project_name": self.project_name,
            "created": self.created,
            "colors": self.colors,
        }

    def save(self):
        if not self.project_path:
            return False
        os.makedirs(self.project_path, exist_ok=True)
        for color in COLORS:
            os.makedirs(os.path.join(self.project_path, color), exist_ok=True)
        with open(self.json_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return True

    @classmethod
    def load(cls, project_path):
        json_path = os.path.join(project_path, "project.json")
        if not os.path.exists(json_path):
            return None
        with open(json_path, "r") as f:
            data = json.load(f)
        proj = cls()
        proj.project_path = project_path
        proj.project_name = data.get("project_name", "Untitled Project")
        proj.created = data.get("created", "")
        proj.colors = data.get("colors", empty_project())
        return proj

    def get_sample(self, color, slot, key):
        """Returns sample dict or None. key like 'L0', 'R3'"""
        return self.colors[color]["slots"][str(slot)].get(key)

    def set_sample(self, color, slot, key, original_name, original_path, source_path, duration_sec=None):
        """Copy file into project and record metadata."""
        slot_str = str(slot)
        ext = Path(original_path).suffix
        dest_filename = f"{color}_SLOT{slot}_{key}{ext}"
        dest_dir = os.path.join(self.project_path, color)
        dest_path = os.path.join(dest_dir, dest_filename)
        os.makedirs(dest_dir, exist_ok=True)

        # Remove existing file if present
        existing = self.colors[color]["slots"][slot_str].get(key)
        if existing:
            old_file = os.path.join(self.project_path, color,
                                    f"{color}_SLOT{slot}_{key}{Path(existing.get('original_name','.wav')).suffix}")
            if os.path.exists(old_file):
                os.remove(old_file)

        shutil.copy2(source_path, dest_path)
        self.colors[color]["slots"][slot_str][key] = {
            "original_name": original_name,
            "original_path": original_path,
            "project_filename": dest_filename,
            "duration_sec": duration_sec,
        }
        self.save()

    def remove_sample(self, color, slot, key):
        slot_str = str(slot)
        existing = self.colors[color]["slots"][slot_str].get(key)
        if existing:
            # Try to find and delete the file
            for ext in ['.wav', '.aif', '.aiff', '.mp3']:
                candidate = os.path.join(self.project_path, color,
                                         f"{color}_SLOT{slot}_{key}{ext}")
                if os.path.exists(candidate):
                    os.remove(candidate)
                    break
            # Also try using stored filename
            pf = existing.get("project_filename")
            if pf:
                fp = os.path.join(self.project_path, color, pf)
                if os.path.exists(fp):
                    os.remove(fp)
        self.colors[color]["slots"][slot_str][key] = None
        self.save()

    def move_sample(self, src_color, src_slot, src_key, dst_color, dst_slot, dst_key):
        """Move a sample from one slot to another within the project."""
        src_data = self.get_sample(src_color, src_slot, src_key)
        if not src_data:
            return

        src_filename = src_data.get("project_filename", "")
        src_path = os.path.join(self.project_path, src_color, src_filename)

        if not os.path.exists(src_path):
            return

        # Remove destination if occupied
        self.remove_sample(dst_color, dst_slot, dst_key)

        ext = Path(src_filename).suffix
        dst_filename = f"{dst_color}_SLOT{dst_slot}_{dst_key}{ext}"
        dst_dir = os.path.join(self.project_path, dst_color)
        os.makedirs(dst_dir, exist_ok=True)
        dst_path = os.path.join(dst_dir, dst_filename)

        shutil.move(src_path, dst_path)

        self.colors[dst_color]["slots"][str(dst_slot)][dst_key] = {
            "original_name": src_data["original_name"],
            "original_path": src_data["original_path"],
            "project_filename": dst_filename,
            "duration_sec": src_data.get("duration_sec"),
        }
        self.colors[src_color]["slots"][str(src_slot)][src_key] = None
        self.save()

    def copy_sample(self, src_color, src_slot, src_key, dst_color, dst_slot, dst_key):
        """Copy a sample to another slot, leaving the source intact."""
        src_data = self.get_sample(src_color, src_slot, src_key)
        if not src_data:
            return

        src_filename = src_data.get("project_filename", "")
        src_path = os.path.join(self.project_path, src_color, src_filename)

        if not os.path.exists(src_path):
            return

        # Remove destination if occupied
        self.remove_sample(dst_color, dst_slot, dst_key)

        ext = Path(src_filename).suffix
        dst_filename = f"{dst_color}_SLOT{dst_slot}_{dst_key}{ext}"
        dst_dir = os.path.join(self.project_path, dst_color)
        os.makedirs(dst_dir, exist_ok=True)
        dst_path = os.path.join(dst_dir, dst_filename)

        shutil.copy2(src_path, dst_path)

        self.colors[dst_color]["slots"][str(dst_slot)][dst_key] = {
            "original_name": src_data["original_name"],
            "original_path": src_data["original_path"],
            "project_filename": dst_filename,
            "duration_sec": src_data.get("duration_sec"),
        }
        self.save()

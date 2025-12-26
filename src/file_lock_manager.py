import threading
import os
import json
import datetime
from src.utils import logger


class FileLockManager:
    def __init__(self):
        self.locks = {}  # file_path -> threading.Lock
        self.lock = threading.Lock()  # Protectlocksdictionary

    def acquire_lock(self, file_path, timeout=5):
        """Get file lock"""
        with self.lock:
            if file_path not in self.locks:
                self.locks[file_path] = threading.Lock()

        lock = self.locks[file_path]
        acquired = lock.acquire(timeout=timeout)

        if acquired:
            logger.debug(f"🔒 File locked: {file_path}")
            return True
        else:
            logger.debug(f"⏰ Lock file timeout: {file_path}")
            return False

    def get_lock(self, file_path, timeout=5):
        """Get file lock（Compatibility method）"""
        return self.acquire_lock(file_path, timeout)

    def release_lock(self, file_path):
        """Release file lock"""
        with self.lock:
            if file_path in self.locks:
                lock = self.locks[file_path]
                try:
                    lock.release()
                    logger.debug(f"🔓 File lock released: {file_path}")
                except RuntimeError:
                    # The lock may have been released
                    logger.debug(f"⚠️ The file lock is released: {file_path}")
                # Optional：Remove no longer used locks from the dictionary
                # if not lock.locked():
                #     del self.locks[file_path]

    def save_text_changes_to_json_with_lock(
        self, project_dir, slide_index, shape_id, new_text
    ):
        """Save text modifications using file lock"""
        lock_acquired = False
        slide_path = ""

        try:
            # buildslidefile path
            slide_id = f"slide_{slide_index:03d}"
            slide_dir = os.path.join(project_dir, "slides")
            os.makedirs(slide_dir, exist_ok=True)
            slide_path = os.path.join(slide_dir, f"{slide_id}.json")

            logger.debug(f"🔒 Get file lock: {slide_path}")

            # use acquire_lock or get_lock
            lock_acquired = self.acquire_lock(slide_path)
            # or：lock_acquired = self.get_lock(slide_path)

            if not lock_acquired:
                return False, "Failed to acquire file lock"

            # read or createslidedata
            slide_data = self._load_or_create_slide_data(
                slide_path, slide_id, slide_index
            )

            # Update modification time
            if "meta" not in slide_data:
                slide_data["meta"] = {}
            slide_data["meta"]["modified"] = datetime.datetime.now().isoformat()

            # saveshapedata
            success = self._save_shape_data(slide_data, shape_id, new_text)

            if success:
                # save to file
                with open(slide_path, "w", encoding="utf-8") as f:
                    json.dump(slide_data, f, indent=2, ensure_ascii=False)

                logger.debug(f"✅ Saved successfully: {shape_id}")
                return True, "Saved successfully"
            else:
                return False, "saveshapeData failed"

        except Exception as e:
            logger.debug(f"❌ Failed to save text changes to file: {e}")
            import traceback

            traceback.print_exc()
            return False, str(e)
        finally:
            if lock_acquired and slide_path:
                logger.debug(f"🔓 File lock released: {slide_path}")
                self.release_lock(slide_path)

    def _load_or_create_slide_data(self, slide_path, slide_id, slide_index):
        """Safely load or createslidedata"""
        if os.path.exists(slide_path):
            try:
                with open(slide_path, "r", encoding="utf-8") as f:
                    slide_data = json.load(f)

                # Make sure the necessary keys exist
                if "id" not in slide_data:
                    slide_data["id"] = slide_id
                if "slide_number" not in slide_data:
                    slide_data["slide_number"] = slide_index + 1
                if "meta" not in slide_data:
                    slide_data["meta"] = {}
                if "shapes" not in slide_data:
                    slide_data["shapes"] = {}

                return slide_data
            except (json.JSONDecodeError, FileNotFoundError):
                logger.debug(
                    f"⚠️ JSONParse error or file does not exist，Create new structure: {slide_path}"
                )

        # Create new structure
        return {
            "id": slide_id,
            "slide_number": slide_index + 1,
            "shapes": {},
            "meta": {},
        }

    def _save_shape_data(self, slide_data, shape_id, new_text):
        """Save safelyshapedata"""
        try:
            # parseshape_id
            parts = shape_id.split("_")
            if len(parts) < 4 or parts[0] != "slide" or parts[2] != "shape":
                logger.debug(f"⚠️ Invalid shapeIDFormat: {shape_id}")
                return False

            # make sureshapesdictionary exists
            if "shapes" not in slide_data:
                slide_data["shapes"] = {}

            # Get or createshapetype
            shape_type = "txt"  # Default text box type
            if shape_id in slide_data["shapes"]:
                shape_type = slide_data["shapes"][shape_id].get("t", "txt")

            # renewshapedata
            slide_data["shapes"][shape_id] = {
                "t": shape_type,
                "txt": new_text,
                "mod": datetime.datetime.now().isoformat(),
            }

            return True

        except Exception as e:
            logger.debug(f"❌ saveshapeData failed: {e}")
            return False

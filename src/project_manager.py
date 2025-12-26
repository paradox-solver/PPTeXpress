# project_data_manager.py
import tempfile
import os
import yaml
import time
import json
import uuid
import shutil
import datetime
from typing import Optional, Dict, Any
from pptx import Presentation

# Assuming these modules exist in your project
from src.pptx_form_editor import PPTXFormEditor
from src.utils import calculate_template_hash
from src.git_manager import GitManager
from src.utils import logger
from src.utils import cleanup_temp_files


class ProjectManager:
    """Manage project data, sessions, and project lifecycle（Create, load, etc.）."""

    def __init__(self):
        self.projects = (
            {}
        )  # project_id -> {project_dir, project_data, content, file_changes, memory_changes}
        self.sessions = {}  # session_id -> project_id
        self.git_managers = {}

    # --- Data management methods ---

    # existproject_manager.pymiddle，make surecreate_project_sessionreturn correctsession_id
    def create_project_session(
        self, project_dir: str, project_data: dict, content_structure: dict
    ) -> str:
        """
        Create a new session for existing project data.
        simplify：session_idIt's the directory name.

        Args:
            project_dir: Project directory path
            project_data: Project data dictionary
            content_structure: Content structure

        Returns:
            str: sessionID（directory name）
        """
        project_id = project_data.get("project", {}).get("id")
        if not project_id:
            project_id = str(uuid.uuid4())[:8]
            project_data["project"]["id"] = project_id

        # 🔧 Revise：session_idIt’s the directory name
        session_id = os.path.basename(project_dir)

        logger.debug(f"🆕 Create project session:")
        logger.debug(f"  projectID: {project_id}")
        logger.debug(f"  sessionID（directory name）: {session_id}")
        logger.debug(f"  Project directory: {project_dir}")

        # 🔧 Make sure the content structure is in array format
        if isinstance(content_structure, dict) and "slides" in content_structure:
            logger.debug("  🔄 Convert dictionary to array format")
            content_structure = content_structure["slides"]

        # Store project data
        self.projects[project_id] = {
            "project_dir": project_dir,
            "project_data": project_data,
            "content": content_structure,
            "file_changes": {},
            "memory_changes": {},
        }

        # 🔧 Create mapping：session_id（directory name） -> project_id
        self.sessions[session_id] = project_id

        logger.debug(f"✅ Storage completed:")
        logger.debug(f"  sessionID: {session_id}")
        logger.debug(f"  mapping: {session_id} -> {project_id}")
        logger.debug(f"  Current number of sessions: {len(self.sessions)}")
        logger.debug(f"  Current number of projects: {len(self.projects)}")

        return session_id  # 🔧 Return directory name

    def get_project_by_session(self, session_id: str):
        """
        via sessionIDGet associated project data.
        Supports two types ofsession_id：
        1. Regular items：The name of the project directory in the application data directory
        2. Snapshot viewer：Snapshot session in temporary cache directory
        """
        logger.debug(f"🔍 get_project_by_session called: {session_id}")

        # 🔧 Original regular item search logic（remain unchanged）
        app_data_dir = self.get_app_data_dir()
        project_dir = os.path.join(app_data_dir, session_id)

        if not os.path.exists(project_dir):
            logger.debug(f"❌ Project directory does not exist: {project_dir}")
            return None

        # 🔧 Revise：examineassetsDoes the directory exist?
        assets_dir = os.path.join(project_dir, "assets", "images")
        if not os.path.exists(assets_dir):
            logger.debug(f"⚠️ assetsDirectory does not exist，create: {assets_dir}")
            os.makedirs(assets_dir, exist_ok=True)

        # 🔧 Revise2：Check if it is already in memory，If not, load from file system
        # First find the project by directory nameID
        yaml_path = os.path.join(project_dir, "project.yaml")
        if not os.path.exists(yaml_path):
            logger.debug(f"❌ project.yamldoes not exist: {yaml_path}")
            return None

        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                project_data = yaml.safe_load(f)

            if not project_data or "project" not in project_data:
                logger.debug(f"❌ Invalid project data format: {session_id}")
                return None

            project_id = project_data["project"].get("id")
            if not project_id:
                logger.debug(f"⚠️ Item missingID，Before using directory name8Bit")
                project_id = session_id[:8]
                project_data["project"]["id"] = project_id

            # 🔧 Revise3：If the item is not in memory，load into memory
            if project_id not in self.projects:
                logger.debug(
                    f"🔄 Item is not in memory，Load from file system: {project_id}"
                )

                # Parse template content（if needed）
                content_structure = []
                template_file = project_data.get("template", {}).get("file")
                if template_file:
                    template_path = os.path.join(project_dir, template_file)
                    if os.path.exists(template_path):
                        try:
                            editor = PPTXFormEditor(template_path)
                            pptx_content = editor.extract_editable_content()
                            content_structure = pptx_content.get("slides", [])
                            logger.debug(
                                f"📊 Load template content，slidesquantity: {len(content_structure)}"
                            )
                        except Exception as e:
                            logger.debug(
                                f"⚠️ Parsing template failed，Use empty content: {e}"
                            )
                            content_structure = []

                # store to memory
                self.projects[project_id] = {
                    "project_dir": project_dir,
                    "project_data": project_data,
                    "content": content_structure,
                    "file_changes": {},
                    "memory_changes": {},
                }

            # 🔧 Revise4：Create session mapping（session_id -> project_id）
            if session_id not in self.sessions:
                self.sessions[session_id] = project_id
                # logger.debug(f"🔄 Create session mapping: {session_id} -> {project_id}")

            project = self.projects[project_id]
            # logger.debug(f"✅ Obtain project data successfully")
            # logger.debug(f"   Project directory: {project.get('project_dir')}")
            # logger.debug(f"   projectID: {project_id}")
            # logger.debug(f"   slidesquantity: {len(project.get('content', []))}")

            if session_id not in self.git_managers:
                # createGitManagerbut not initialized（The user may manually initialize）
                git_manager = GitManager(project_dir)
                self.git_managers[session_id] = git_manager
                logger.debug(f"🔧 GitManagerCreated（not initialized）")

            project["assets_dir"] = assets_dir
            project["images_dir"] = assets_dir
            project["git_manager"] = self.git_managers[
                session_id
            ]  # 🔥 Optional：WillGitManagerAdd to project data
            return project

        except Exception as e:
            logger.debug(f"❌ Failed to obtain project information {session_id}: {e}")
            import traceback

            traceback.print_exc()
            return None

    def update_memory_changes(self, session_id: str, changes: dict) -> bool:
        """
        Updates temporary modifications in memory for the specified session.

        Args:
            session_id (str): sessionID.
            changes (dict): The modifications to be updated.

        Returns:
            bool: Returns if updated successfullyTrue，Otherwise returnFalse.
        """
        project = self.get_project_by_session(session_id)
        if project:
            project["memory_changes"].update(changes)
            return True
        return False

    def clear_memory_changes(self, session_id: str) -> bool:
        """
        Clears temporary modifications in memory for the specified session.

        Args:
            session_id (str): sessionID.

        Returns:
            bool: Returns if cleared successfullyTrue，Otherwise returnFalse.
        """
        project = self.get_project_by_session(session_id)
        if project:
            project["memory_changes"] = {}
            return True
        return False

    def remove_session(self, session_id: str) -> bool:
        """
        （Optional）Remove a session map，But the project data is not deleted.
        This helps manage active sessions.

        Args:
            session_id (str): sessionID.

        Returns:
            bool: Returns if removed successfullyTrue，Otherwise returnFalse.
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True  # Indicates that the session exists and has been removed
        return False  # Indicates that the session does not exist

    def load_project_yaml(self, session_id: str) -> bool:
        """Load from fileYAMLdata to memory"""
        project = self.get_project_by_session(session_id)
        if not project:
            return False

        yaml_path = os.path.join(project["project_dir"], "project.yaml")
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                project["project_data"] = yaml.safe_load(f) or {}
            return True
        except Exception as e:
            logger.debug(f"❌ loadYAMLfail: {e}")
            return False

    def create_project_with_data(
        self, pptx_path: str, project_dir: str, project_name: str = None
    ) -> dict:
        """
        More advanced ways to create projects，Contains more options.

        Args:
            pptx_path: PPTXfile path
            project_dir: Project directory
            project_name: Project name（Optional）

        Returns:
            dict: A dictionary containing all creation information
        """
        # Create project
        project_id, project_data, editor_format = self._initialize_new_project(
            pptx_path, project_dir
        )

        # if needed，Update project name
        if project_name:
            project_data["project"]["name"] = project_name
            # Save the updatedYAML
            yaml_path = os.path.join(project_dir, "project.yaml")
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(project_data, f, default_flow_style=False, allow_unicode=True)

        # Create session
        session_id = self.create_project_session(
            project_dir=project_dir,
            project_data=project_data,
            content_structure=editor_format.get("slides", []),
        )

        logger.debug(f"🔧 automatic initializationGitstorehouse...")
        git_init_result = self.init_project_git(session_id)

        if git_init_result.get("success"):
            logger.debug(f"✅ GitWarehouse initialization successful")
        else:
            logger.debug(
                f"⚠️ GitWarehouse initialization failed: {git_init_result.get('message')}"
            )

        return {
            "project_id": project_id,
            "session_id": session_id,
            "project_data": project_data,
            "editor_format": editor_format,
            "project_dir": project_dir,
            "message": f"project '{project_data['project']['name']}' Created successfully",
        }

    def _initialize_new_project(
        self, pptx_path: str, project_dir: str
    ) -> tuple[str, dict, dict]:
        """
        Refactored project initialization method - usePPTXFormEditornew method

        Args:
            pptx_path (str): originalPPTXfile path
            project_dir (str): Target directory for new projects

        Returns:
            tuple[str, dict, dict]: projectID, project data, Front-end editor format
        """
        try:
            logger.debug(f"🔄 Initialize new project: {pptx_path} -> {project_dir}")

            # 1. Create directory structure
            self._create_project_structure(project_dir)

            # 2. Copy template file
            template_name = f"template_{int(time.time())}.pptx"
            template_path = os.path.join(project_dir, template_name)
            shutil.copy2(pptx_path, template_path)
            logger.debug(f"📋 Copy template file: {template_name}")

            # 3. Compute template hash
            template_hash = calculate_template_hash(template_path)

            # 4. Create projectIDand basic project data
            project_id = str(uuid.uuid4())[:8]
            project_name = (
                os.path.basename(project_dir.rstrip("/\\")).strip()
                or f"Project_{project_id}"
            )

            initial_project_data = {
                "project": {
                    "id": project_id,
                    "name": project_name,
                    "created_at": datetime.datetime.now().isoformat(),
                    "modified_at": datetime.datetime.now().isoformat(),
                    "author": "user@example.com",
                },
                "template": {
                    "file": template_name,
                    "hash": template_hash,
                    "original_name": os.path.basename(pptx_path),
                },
                "slides": [],  # Initially empty
            }

            # 5. parsePPTXcontent（incomingproject_dirto save the picture）
            logger.debug(f"📊 parsePPTXcontent...")
            editor = PPTXFormEditor(template_path)
            # 🔧 Revise：incomingproject_dirparameter
            project_data = editor.extract_for_project_init(project_dir=project_dir)

            if not project_data:
                logger.debug("⚠️ No project data was extracted")
                # Create project anyway，but probably notslidedocument

            # 6. saveslidedocument
            if project_data.get("slide_files_data"):
                success = editor.save_slide_files(
                    project_data["slide_files_data"], project_dir
                )
                if not success:
                    logger.debug(
                        "⚠️ saveslideFile failed，But continue project creation"
                    )

            # 7. renewproject.yaml（Add toimagesinformation）
            if project_data.get("slides_info"):
                initial_project_data["slides"] = project_data["slides_info"]

            # Add image information toproject.yaml
            if project_data.get("images_info"):
                initial_project_data["images"] = {
                    "count": len(project_data["images_info"]),
                    "directory": "assets/images/",
                }

            yaml_path = os.path.join(project_dir, "project.yaml")
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    initial_project_data,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                )

            logger.debug(f"💾 Save project configuration: {yaml_path}")

            # 8. Reload for consistency
            with open(yaml_path, "r", encoding="utf-8") as f:
                loaded_project_data = yaml.safe_load(f)

            # 9. Get front-end editor format
            editor_format = project_data.get("editor_format", {"slides": []})

            # 10. Statistical picture information
            image_count = len(project_data.get("images_info", {}))

            logger.debug(f"✅ Project initialization completed:")
            logger.debug(f"   projectID: {project_id}")
            logger.debug(f"   Project name: {project_name}")
            logger.debug(
                f"   slidesquantity: {len(loaded_project_data.get('slides', []))}"
            )
            logger.debug(f"   Number of pictures: {image_count}")
            logger.debug(
                f"   front-end formatslides: {len(editor_format.get('slides', []))}"
            )

            return project_id, loaded_project_data, editor_format

        except Exception as e:
            logger.debug(f"❌ Project initialization failed: {e}")
            import traceback

            traceback.print_exc()
            raise

    def _create_project_structure(self, project_dir: str):
        """Create project directory structure"""
        os.makedirs(project_dir, exist_ok=True)
        os.makedirs(os.path.join(project_dir, "slides"), exist_ok=True)
        os.makedirs(os.path.join(project_dir, "assets"), exist_ok=True)
        os.makedirs(os.path.join(project_dir, "assets", "images"), exist_ok=True)  # New
        logger.debug(f"📁 Create project directory structure: {project_dir}")

    def open_project(self, project_dir: str) -> dict:
        """
        Open an existing project，Verify its validity.
        simplify：session_idIt's the directory name.

        Args:
            project_dir (str): Project directory path

        Returns:
            dict: Contains operation results and necessary data
        """
        # normalized path
        project_dir = os.path.abspath(project_dir)

        logger.debug(f"🔄 Open project directory: {project_dir}")

        # Basic verification：Does the project directory exist?
        if not os.path.exists(project_dir):
            error_msg = f"Project directory does not exist: {project_dir}"
            logger.debug(f"❌ {error_msg}")
            return {
                "status": "error",
                "message": error_msg,
                "error_type": "directory_not_found",
            }

        # Verify required documents
        yaml_path = os.path.join(project_dir, "project.yaml")
        if not os.path.exists(yaml_path):
            error_msg = f"Project directory is missing project.yaml document"
            logger.debug(f"❌ {error_msg}")
            return {
                "status": "error",
                "message": error_msg,
                "error_type": "missing_yaml",
            }

        # load project.yaml
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                project_data = yaml.safe_load(f)

            if not project_data or "project" not in project_data:
                error_msg = "project.yaml Invalid file format"
                logger.debug(f"❌ {error_msg}")
                return {
                    "status": "error",
                    "message": error_msg,
                    "error_type": "invalid_yaml_format",
                }

        except yaml.YAMLError as e:
            error_msg = f"YAML File parsing error: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            return {
                "status": "error",
                "message": error_msg,
                "error_type": "yaml_parse_error",
            }
        except Exception as e:
            error_msg = f"read project.yaml fail: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            return {
                "status": "error",
                "message": error_msg,
                "error_type": "file_read_error",
            }

        # 🔧 Revise1：session_idIt’s the directory name
        session_id = os.path.basename(project_dir)
        project_id = project_data.get("project", {}).get("id", session_id[:8])

        logger.debug(
            f"✅ Load project configuration: {project_data.get('project', {}).get('name', 'Unnamed')}"
        )
        logger.debug(f"   projectID: {project_id}")
        logger.debug(f"   sessionID（directory name）: {session_id}")

        # 🔧 Revise2：No need to check for existing sessions，Direct loading
        # callget_project_by_sessionwill be automatically loaded into memory
        project_obj = self.get_project_by_session(session_id)
        if not project_obj:
            error_msg = f"Unable to load project: {session_id}"
            logger.debug(f"❌ {error_msg}")
            return {
                "status": "error",
                "message": error_msg,
                "error_type": "project_load_failed",
            }

        # Get content structure
        content_structure = project_obj.get("content", [])

        # Build return data
        project_info = {
            "name": project_data.get("project", {}).get("name", "Unnamed project"),
            "id": project_id,
            "directory_name": session_id,  # session_idIt’s the directory name
            "template": project_data.get("template", {}).get("file", ""),
            "created_at": project_data.get("project", {}).get("created_at", ""),
        }

        logger.debug(f"✅ Project opened successfully:")
        logger.debug(f"   sessionID: {session_id}")
        logger.debug(f"   Project name: {project_info['name']}")
        logger.debug(f"   slidesquantity: {len(content_structure)}")

        return {
            "status": "success",
            "message": f"project '{project_info['name']}' Opened",
            "session_id": session_id,  # 🔧 Return directory name assession_id
            "project_data": project_data,
            "content_structure": content_structure,
            "project_info": project_info,
        }

    def validate_project_structure(self, project_dir: str) -> tuple[bool, str]:
        """
        Verify the validity of the project directory structure.
        Simplified version of inspection，For external calls.

        Args:
            project_dir (str): Project directory path

        Returns:
            tuple[bool, str]: (Is it valid?, information)
        """
        project_dir = os.path.abspath(project_dir)

        if not os.path.exists(project_dir):
            return False, f"Project directory does not exist: {project_dir}"

        # Check required documents
        yaml_path = os.path.join(project_dir, "project.yaml")
        if not os.path.exists(yaml_path):
            return False, f"Lack project.yaml document"

        # Check required directories
        slides_dir = os.path.join(project_dir, "slides")
        if not os.path.exists(slides_dir):
            return False, f"Lack slides Table of contents"

        # try to loadYAMLVerify format
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                project_data = yaml.safe_load(f)

            if not project_data or "project" not in project_data:
                return False, "project.yaml Invalid format"

            # Check template file
            template_file = project_data.get("template", {}).get("file")
            if template_file:
                template_path = os.path.join(project_dir, template_file)
                if not os.path.exists(template_path):
                    # Try fuzzy matching
                    template_files = [
                        f
                        for f in os.listdir(project_dir)
                        if f.startswith("template_") and f.endswith(".pptx")
                    ]
                    if not template_files:
                        return False, f"Template file does not exist: {template_file}"

        except Exception as e:
            return False, f"Authentication failed: {str(e)}"

        return True, "Effective project structure"

    # existProjectManagerAdd debugging method to class
    def debug_session_mapping(self):
        """Debug session mapping"""
        logger.debug("🔍 ProjectManager Session map debugging:")
        logger.debug(f"  - Total number of sessions: {len(self.sessions)}")
        logger.debug(f"  - Total number of projects: {len(self.projects)}")

        for session_id, project_id in self.sessions.items():
            logger.debug(f"  - session {session_id[:8]}... → project {project_id}")
            project = self.projects.get(project_id)
            if project:
                logger.debug(
                    f"    - Project directory: {project.get('project_dir', 'N/A')}"
                )
                logger.debug(f"    - slidesquantity: {len(project.get('content', []))}")

    def check_project(self, session_id: str) -> dict:
        """
        Check whether the project corresponding to the specified session is valid，Verify necessary file structure.
        """
        # Get project data
        project = self.get_project_by_session(session_id)
        if not project:
            raise ValueError(f"Invalid sessionID: {session_id}")

        project_dir = project["project_dir"]
        project_data = project["project_data"]

        # Calculate critical path based on project directory
        slides_dir = os.path.join(project_dir, "slides")
        assets_dir = os.path.join(project_dir, "assets")
        images_dir = os.path.join(project_dir, "assets", "images")

        # Get template file name from project data
        template_name = project_data.get("template", {}).get("file")
        if not template_name:
            raise ValueError("Template file information is missing in project data")

        template_file = os.path.join(project_dir, template_name)

        # Check directories and files
        dirs_to_check = [project_dir, slides_dir, assets_dir]

        result = {
            "session_id": session_id,
            "project_id": project_data.get("project", {}).get("id"),
            "project_dir": project_dir,
            "directories": {},
            "files": {},
            "template": {
                "exists": os.path.exists(template_file),
                "path": (
                    os.path.abspath(template_file)
                    if os.path.exists(template_file)
                    else None
                ),
                "name": template_name,
            },
        }

        images_info = self.list_project_images(session_id)
        result["images"] = images_info

        # Check directory
        for dir_path in dirs_to_check:
            dir_name = os.path.basename(dir_path)
            result["directories"][dir_name] = {
                "exists": os.path.exists(dir_path),
                "path": dir_path,
                "files": [],
            }

            if os.path.exists(dir_path):
                try:
                    for filename in os.listdir(dir_path):
                        filepath = os.path.join(dir_path, filename)
                        if os.path.isfile(filepath):
                            file_info = {
                                "name": filename,
                                "size": os.path.getsize(filepath),
                                "modified": datetime.datetime.fromtimestamp(
                                    os.path.getmtime(filepath)
                                ).isoformat(),
                            }
                            result["directories"][dir_name]["files"].append(file_info)
                except PermissionError:
                    result["directories"][dir_name]["permission_error"] = True

        # Check specific important files
        important_files = {
            "project.yaml": os.path.join(project_dir, "project.yaml"),
            "latest_slide": None,
        }

        # find the latestslidedocument
        if os.path.exists(slides_dir):
            try:
                slide_files = [f for f in os.listdir(slides_dir) if f.endswith(".json")]
                if slide_files:
                    latest = max(
                        slide_files,
                        key=lambda f: os.path.getmtime(os.path.join(slides_dir, f)),
                    )
                    important_files["latest_slide"] = os.path.join(slides_dir, latest)
            except PermissionError:
                result["files"]["slides_permission_error"] = True

        for name, path in important_files.items():
            if path and os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()[:500]  # Read only before500character

                    result["files"][name] = {
                        "exists": True,
                        "path": path,
                        "preview": content,
                        "size": os.path.getsize(path),
                        "modified": datetime.datetime.fromtimestamp(
                            os.path.getmtime(path)
                        ).isoformat(),
                    }
                except Exception as e:
                    result["files"][name] = {
                        "exists": True,
                        "path": path,
                        "error": str(e),
                    }
            elif path:
                result["files"][name] = {"exists": False, "path": path}

        # Add effectiveness assessment
        result["valid"] = result["template"]["exists"] and result["files"].get(
            "project.yaml", {}
        ).get("exists", False)

        # Statistics
        slide_count = len(result["directories"].get("slides", {}).get("files", []))
        result["stats"] = {
            "slide_files": slide_count,
            "asset_files": len(
                result["directories"].get("assets", {}).get("files", [])
            ),
            "total_directories": sum(
                1 for d in result["directories"].values() if d.get("exists", False)
            ),
            "valid_structure": result["valid"],
        }

        result["stats"]["image_files"] = images_info.get("count", 0)
        return result

    def validate_project(self, session_id: str) -> tuple[bool, str]:
        """
        Simple verification of project validity（quick check）.
        Transplant the originalvalidate_projectcore logic.

        Returns:
            tuple[bool, str]: (Is it valid?, information)
        """
        project = self.get_project_by_session(session_id)
        if not project:
            return False, "Invalid sessionID"

        project_dir = project["project_dir"]
        project_data = project["project_data"]

        # Check required directories
        required_dirs = ["slides"]
        for dir_name in required_dirs:
            if not os.path.exists(os.path.join(project_dir, dir_name)):
                return False, f"Missing required directory: {dir_name}"

        # verifyproject.yamlFormat
        yaml_path = os.path.join(project_dir, "project.yaml")
        if not os.path.exists(yaml_path):
            return False, "Lackproject.yamldocument"

        # Validation template file
        template_file = project_data.get("template", {}).get("file")
        if not template_file:
            return False, "Template file information is missing in project data"

        template_path = os.path.join(project_dir, template_file)
        if not os.path.exists(template_path):
            # Try fuzzy matching
            template_files = [
                f
                for f in os.listdir(project_dir)
                if f.startswith("template_") and f.endswith(".pptx")
            ]
            if not template_files:
                return False, "Template file missing"
            # Use the first template file found
            template_path = os.path.join(project_dir, template_files[0])

        # Verify template hash（critical safety features）
        expected_hash = project_data.get("template", {}).get("hash")
        if expected_hash:
            try:
                actual_hash = calculate_template_hash(template_path)
                if actual_hash != expected_hash:
                    return False, "The template file has been modified，Hash mismatch"
            except Exception as e:
                return False, f"Hash verification failed: {str(e)}"

        return True, "Project is valid"

    def update_project_yaml(self, session_id: str, update_data: dict = None) -> bool:
        """
        Update the items corresponding to the specified session YAML document，And synchronously update the project data in the memory.

        Args:
            session_id (str): sessionID
            update_data (dict, optional): data to update，Supports dotted paths such as "template.hash"

        Returns:
            bool: Update successfully returnedTrue，Otherwise returnFalse
        """
        # Get project data
        project = self.get_project_by_session(session_id)
        if not project:
            logger.debug(f"❌ Update failed：Invalid sessionID: {session_id}")
            return False

        project_dir = project["project_dir"]
        yaml_path = os.path.join(project_dir, "project.yaml")

        try:
            # Read current file data（as a baseline）
            with open(yaml_path, "r", encoding="utf-8") as f:
                file_data = yaml.safe_load(f) or {}

            # Get project data in memory
            memory_data = project["project_data"]

            # Ensure the data structure is complete
            if "project" not in memory_data:
                memory_data["project"] = {}
            if "project" not in file_data:
                file_data["project"] = {}

            # Update modification time（Update memory and file data simultaneously）
            current_time = datetime.datetime.now().isoformat()
            memory_data["project"]["modified_at"] = current_time
            file_data["project"]["modified_at"] = current_time

            # Apply additional updates（if providedupdate_data）
            if update_data:
                self._apply_yaml_updates(memory_data, update_data)
                self._apply_yaml_updates(file_data, update_data)

            # save to file
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(file_data, f, default_flow_style=False, allow_unicode=True)

            # Synchronously update project data in memory
            project["project_data"] = memory_data

            logger.debug(f"✅ renewproject.yamlsuccess: {yaml_path}")
            logger.debug(f"  sessionID: {session_id}")
            logger.debug(f"  Update data: {update_data}")

            return True

        except Exception as e:
            logger.debug(f"❌ renewproject.yamlfail: {e}")
            return False

    def _apply_yaml_updates(self, data: dict, update_data: dict):
        """
        internal method：Apply updated data toYAMLin data structure，Supports dotted paths.

        Args:
            data (dict): target data
            update_data (dict): Update data
        """
        for key, value in update_data.items():
            if "." in key:
                # Support dotted paths，like "template.hash"
                parts = key.split(".")
                current = data
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    elif not isinstance(current[part], dict):
                        # If there is not a dictionary in the middle of the path，Create new dictionary（May overwrite original data）
                        logger.debug(
                            f"⚠️  warn：path {key} middle part {part} not a dictionary，will be overwritten"
                        )
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = value
            else:
                # Top level key update
                data[key] = value

    def get_project_yaml_path(self, session_id: str) -> str:
        """
        Get the item corresponding to the specified sessionYAMLFile path.

        Args:
            session_id (str): sessionID

        Returns:
            str: YAMLfile path，Returns an empty string if the session is invalid
        """
        project = self.get_project_by_session(session_id)
        if not project:
            return ""

        project_dir = project["project_dir"]
        return os.path.join(project_dir, "project.yaml")

    def fetch_changes(self, session_id: str, merge_with_existing: bool = True) -> dict:
        """
        fromslide JSONExtract all modifications (text and tables) from the file.

        Args:
            session_id (str): sessionID
            merge_with_existing (bool): Whether to merge with existing modifications in memory，Default isTrue

        Returns:
            dict: The format is {shape_id: content_data, ...}
                For text: {shape_id: {"txt": text_content}}
                For table: {shape_id: {"type": "table", "changes": {}, "original_data": table_data}}
        """
        project = self.get_project_by_session(session_id)
        if not project:
            logger.debug(f"❌ fetch_changesfail：Invalid sessionID: {session_id}")
            return {}

        project_dir = project["project_dir"]
        slides_dir = os.path.join(project_dir, "slides")

        changes = {}

        if not os.path.exists(slides_dir):
            logger.debug(f"⚠️  slidesDirectory does not exist: {slides_dir}")
            return changes

        try:
            json_files = [f for f in os.listdir(slides_dir) if f.endswith(".json")]
            logger.debug(f"🔍 Discover {len(json_files)} indivualslide JSONdocument")

            for filename in json_files:
                json_file = os.path.join(slides_dir, filename)
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        slide_data = json.load(f)

                    # extractslide IDfor contextual information
                    slide_id = slide_data.get("id", filename.replace(".json", ""))

                    # Extract all modifications (text and tables)
                    if "shapes" in slide_data:
                        for shape_id, shape_data in slide_data["shapes"].items():
                            # 🎯 Case 1: Text data
                            if "txt" in shape_data:
                                text_content = shape_data["txt"]
                                changes[shape_id] = {"txt": text_content}

                                # debugging information
                                if (
                                    len(json_files) <= 5
                                ):  # Print in detail when the file is small
                                    shape_type = shape_data.get("t", "unknown")
                                    logger.debug(
                                        f"  extract: slide={slide_id}, shape={shape_id}, type={shape_type}, textlength={len(text_content)}"
                                    )

                            # 🎯 Case 2: Table data (NEW)
                            if "table_data" in shape_data and shape_data["table_data"]:
                                try:
                                    # Parse table data
                                    table_json = shape_data["table_data"]
                                    table_data = (
                                        json.loads(table_json)
                                        if isinstance(table_json, str)
                                        else table_json
                                    )

                                    # Extract cell changes
                                    cell_changes = {}
                                    if isinstance(table_data, list):
                                        for row_idx, row in enumerate(table_data):
                                            if isinstance(row, list):
                                                for col_idx, cell in enumerate(row):
                                                    if (
                                                        isinstance(cell, dict)
                                                        and "text" in cell
                                                    ):
                                                        # Create cell key
                                                        cell_key = (
                                                            f"row{row_idx}_col{col_idx}"
                                                        )
                                                        cell_changes[cell_key] = {
                                                            "row": row_idx,
                                                            "col": col_idx,
                                                            "text": cell.get(
                                                                "text", ""
                                                            ),
                                                            "original_text": cell.get(
                                                                "original_text", ""
                                                            ),
                                                        }

                                    # Build table structure
                                    table_structure = {
                                        "type": "table",
                                        "changes": cell_changes,
                                        "original_data": (
                                            table_json
                                            if isinstance(table_json, str)
                                            else json.dumps(
                                                table_json, ensure_ascii=False
                                            )
                                        ),
                                        "mod": shape_data.get("mod", ""),
                                        "rows": (
                                            len(table_data)
                                            if isinstance(table_data, list)
                                            else 0
                                        ),
                                        "cols": (
                                            len(table_data[0])
                                            if (
                                                isinstance(table_data, list)
                                                and len(table_data) > 0
                                                and isinstance(table_data[0], list)
                                            )
                                            else 0
                                        ),
                                    }

                                    # Handle shape with both text and table data
                                    if shape_id in changes:
                                        # Already has text data, add table data
                                        changes[shape_id]["table"] = table_structure
                                    else:
                                        # Only table data
                                        changes[shape_id] = table_structure

                                    if len(json_files) <= 5:
                                        logger.debug(
                                            f"  extract: slide={slide_id}, shape={shape_id}, table={table_structure['rows']}x{table_structure['cols']}, cells={len(cell_changes)}"
                                        )

                                except (json.JSONDecodeError, TypeError) as e:
                                    logger.debug(
                                        f"❌ Failed to parse table data for {shape_id}: {e}"
                                    )

                except json.JSONDecodeError as e:
                    logger.debug(f"❌ JSONParse error {filename}: {e}")
                except Exception as e:
                    logger.debug(f"❌ Reading file error {filename}: {e}")

            # Merge with changes in memory (if needed)
            if merge_with_existing and project.get("memory_changes"):
                existing_changes = project["memory_changes"]
                logger.debug(
                    f"🔄 Merge in memory {len(existing_changes)} modifications"
                )

                # File modifications take precedence over memory modifications
                for shape_id, content in existing_changes.items():
                    if shape_id not in changes:
                        changes[shape_id] = content

            # Merge with changes in file (if needed)
            if merge_with_existing and project.get("file_changes"):
                file_changes = project["file_changes"]
                logger.debug(f"🔄 in the merge file {len(file_changes)} modifications")

                # File modifications take precedence over memory modifications，butslideFile modification takes priority
                for shape_id, content in file_changes.items():
                    if shape_id not in changes:
                        changes[shape_id] = content

            # 🎯 Ensure consistent format
            for shape_id, content in changes.items():
                if isinstance(content, list) or isinstance(content, str):
                    # Legacy text format, convert to new format
                    changes[shape_id] = {"txt": content}
                elif (
                    isinstance(content, dict)
                    and "txt" not in content
                    and "type" not in content
                ):
                    # Unknown dict format, assume text
                    changes[shape_id] = {"txt": content}

            logger.debug(
                f"✅ fetch_changesFinish: Total extraction {len(changes)} modifications"
            )

            # Statistics
            text_count = sum(
                1
                for content in changes.values()
                if isinstance(content, dict) and "txt" in content
            )
            table_count = sum(
                1
                for content in changes.values()
                if isinstance(content, dict) and content.get("type") == "table"
            )
            logger.debug(
                f"📊 Statistics: {text_count} text shapes, {table_count} table shapes"
            )

            return changes

        except Exception as e:
            logger.debug(f"❌ fetch_changesfail: {e}")
            return {}

    def fetch_changes_by_slide(self, session_id: str) -> dict:
        """
        according toslideExtract modifications in groups.

        Args:
            session_id (str): sessionID

        Returns:
            dict: The format is {slide_id: {shape_id: content_data, ...}, ...}
        """
        project = self.get_project_by_session(session_id)
        if not project:
            return {}

        project_dir = project["project_dir"]
        slides_dir = os.path.join(project_dir, "slides")

        slide_changes = {}

        if not os.path.exists(slides_dir):
            return slide_changes

        try:
            for filename in os.listdir(slides_dir):
                if not filename.endswith(".json"):
                    continue

                json_file = os.path.join(slides_dir, filename)
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        slide_data = json.load(f)

                    slide_id = slide_data.get("id", filename.replace(".json", ""))
                    slide_changes[slide_id] = {}

                    if "shapes" in slide_data:
                        for shape_id, shape_data in slide_data["shapes"].items():
                            # 🎯 Text data
                            if "txt" in shape_data:
                                slide_changes[slide_id][shape_id] = {
                                    "txt": shape_data["txt"]
                                }

                            # 🎯 Table data (NEW)
                            if "table_data" in shape_data and shape_data["table_data"]:
                                try:
                                    table_json = shape_data["table_data"]
                                    table_data = (
                                        json.loads(table_json)
                                        if isinstance(table_json, str)
                                        else table_json
                                    )

                                    # Extract cell changes
                                    cell_changes = {}
                                    if isinstance(table_data, list):
                                        for row_idx, row in enumerate(table_data):
                                            if isinstance(row, list):
                                                for col_idx, cell in enumerate(row):
                                                    if (
                                                        isinstance(cell, dict)
                                                        and "text" in cell
                                                    ):
                                                        cell_key = (
                                                            f"row{row_idx}_col{col_idx}"
                                                        )
                                                        cell_changes[cell_key] = {
                                                            "row": row_idx,
                                                            "col": col_idx,
                                                            "text": cell.get(
                                                                "text", ""
                                                            ),
                                                            "original_text": cell.get(
                                                                "original_text", ""
                                                            ),
                                                        }

                                    table_structure = {
                                        "type": "table",
                                        "changes": cell_changes,
                                        "original_data": (
                                            table_json
                                            if isinstance(table_json, str)
                                            else json.dumps(
                                                table_json, ensure_ascii=False
                                            )
                                        ),
                                        "rows": (
                                            len(table_data)
                                            if isinstance(table_data, list)
                                            else 0
                                        ),
                                        "cols": (
                                            len(table_data[0])
                                            if (
                                                isinstance(table_data, list)
                                                and len(table_data) > 0
                                                and isinstance(table_data[0], list)
                                            )
                                            else 0
                                        ),
                                    }

                                    if shape_id in slide_changes[slide_id]:
                                        # Already has text data
                                        slide_changes[slide_id][shape_id][
                                            "table"
                                        ] = table_structure
                                    else:
                                        slide_changes[slide_id][
                                            shape_id
                                        ] = table_structure

                                except (json.JSONDecodeError, TypeError) as e:
                                    logger.debug(
                                        f"❌ Failed to parse table data for {shape_id}: {e}"
                                    )

                except Exception as e:
                    logger.debug(f"❌ deal with {filename} fail: {e}")

            return slide_changes

        except Exception as e:
            logger.debug(f"❌ fetch_changes_by_slidefail: {e}")
            return {}

    def get_changes_summary(self, session_id: str) -> dict:
        """
        Get a statistical summary of modifications.

        Args:
            session_id (str): sessionID

        Returns:
            dict: Modify statistics
        """
        all_changes = self.fetch_changes(session_id, merge_with_existing=True)
        slide_changes = self.fetch_changes_by_slide(session_id)

        # Statistics
        text_shapes = 0
        table_shapes = 0
        mixed_shapes = 0  # Shapes with both text and table
        total_cells_modified = 0
        total_text_length = 0

        for shape_id, content in all_changes.items():
            if isinstance(content, dict):
                if "txt" in content and content.get("type") == "table":
                    mixed_shapes += 1
                elif "txt" in content:
                    text_shapes += 1
                    # Calculate text length
                    if isinstance(content["txt"], str):
                        total_text_length += len(content["txt"])
                    elif isinstance(content["txt"], list):
                        for item in content["txt"]:
                            if isinstance(item, dict) and "text" in item:
                                total_text_length += len(item["text"])
                elif content.get("type") == "table":
                    table_shapes += 1
                    # Count modified cells
                    if "changes" in content:
                        total_cells_modified += len(content["changes"])

        avg_text_length = total_text_length / text_shapes if text_shapes > 0 else 0

        return {
            "total_shapes": len(all_changes),
            "text_shapes": text_shapes,
            "table_shapes": table_shapes,
            "mixed_shapes": mixed_shapes,
            "slides_affected": len(slide_changes),
            "total_text_length": total_text_length,
            "average_text_length": round(avg_text_length, 2),
            "total_cells_modified": total_cells_modified,
            "changes_by_slide": {
                slide_id: len(changes) for slide_id, changes in slide_changes.items()
            },
        }

    def fetch_table_changes(self, session_id: str) -> dict:
        """
        Extract only table modifications.

        Args:
            session_id (str): sessionID

        Returns:
            dict: Table modifications {shape_id: table_data, ...}
        """
        all_changes = self.fetch_changes(session_id, merge_with_existing=False)

        table_changes = {}
        for shape_id, content in all_changes.items():
            if isinstance(content, dict):
                if content.get("type") == "table":
                    table_changes[shape_id] = content
                elif "table" in content:
                    table_changes[shape_id] = content["table"]

        logger.debug(f"📊 Extracted {len(table_changes)} table modifications")
        return table_changes

    def get_table_cell_data(
        self, session_id: str, shape_id: str, row: int, col: int
    ) -> dict:
        """
        Get specific cell data from table.

        Args:
            session_id (str): sessionID
            shape_id (str): shape ID
            row (int): row index
            col (int): column index

        Returns:
            dict: Cell data or empty dict if not found
        """
        table_changes = self.fetch_table_changes(session_id)

        if shape_id in table_changes:
            table_data = table_changes[shape_id]
            cell_key = f"row{row}_col{col}"

            if "changes" in table_data and cell_key in table_data["changes"]:
                return table_data["changes"][cell_key]

            # Try to get from original data
            if "original_data" in table_data:
                try:
                    original = json.loads(table_data["original_data"])
                    if (
                        isinstance(original, list)
                        and row < len(original)
                        and col < len(original[row])
                        and isinstance(original[row][col], dict)
                    ):
                        return original[row][col]
                except (json.JSONDecodeError, TypeError, IndexError):
                    pass

        return {}

    def merge_table_changes(
        self, session_id: str, shape_id: str, new_changes: dict
    ) -> bool:
        """
        Merge new table changes with existing ones.

        Args:
            session_id (str): sessionID
            shape_id (str): shape ID
            new_changes (dict): new cell changes

        Returns:
            bool: Success or not
        """
        project = self.get_project_by_session(session_id)
        if not project:
            return False

        project_dir = project["project_dir"]
        slides_dir = os.path.join(project_dir, "slides")

        # Find the slide file containing this shape
        slide_idx = None
        for filename in os.listdir(slides_dir):
            if filename.endswith(".json"):
                json_file = os.path.join(slides_dir, filename)
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        slide_data = json.load(f)

                    if "shapes" in slide_data and shape_id in slide_data["shapes"]:
                        # Extract slide index from filename
                        slide_idx = int(
                            filename.replace("slide_", "").replace(".json", "")
                        )

                        # Merge changes
                        shape_info = slide_data["shapes"][shape_id]
                        if "table_data" in shape_info:
                            try:
                                table_data = json.loads(shape_info["table_data"])

                                # Apply new changes
                                for cell_key, cell_change in new_changes.items():
                                    if (
                                        isinstance(cell_change, dict)
                                        and "row" in cell_change
                                        and "col" in cell_change
                                    ):
                                        row = cell_change["row"]
                                        col = cell_change["col"]

                                        if (
                                            isinstance(table_data, list)
                                            and row < len(table_data)
                                            and col < len(table_data[row])
                                            and isinstance(table_data[row][col], dict)
                                        ):

                                            table_data[row][col]["text"] = (
                                                cell_change.get("text", "")
                                            )

                                # Save back
                                shape_info["table_data"] = json.dumps(
                                    table_data, ensure_ascii=False
                                )
                                shape_info["mod"] = datetime.datetime.now().isoformat()

                                with open(json_file, "w", encoding="utf-8") as f:
                                    json.dump(
                                        slide_data, f, ensure_ascii=False, indent=2
                                    )

                                logger.debug(f"✅ Merged table changes for {shape_id}")
                                return True

                            except (json.JSONDecodeError, TypeError, ValueError) as e:
                                logger.debug(f"❌ Failed to merge table changes: {e}")
                                return False

                except Exception as e:
                    logger.debug(f"❌ Error processing {filename}: {e}")

        return False

    def get_app_data_dir(self) -> str:
        """
        Get the application data directory.

        Returns:
            str: Cross-platform application data directory path
        """
        try:
            # Try using platformdirs
            import platformdirs

            return platformdirs.user_data_dir("PPTeXpress", "Paradoxsolver")
        except ImportError:
            # Fallback plan
            if os.name == "nt":  # Windows
                base_dir = os.getenv(
                    "LOCALAPPDATA",
                    os.path.join(os.path.expanduser("~"), "AppData", "Local"),
                )
                return os.path.join(base_dir, "PPTeXpress", "projects")
            elif os.name == "posix":  # Linux/Mac
                if sys.platform == "darwin":  # macOS
                    return os.path.join(
                        os.path.expanduser("~"),
                        "Library",
                        "Application Support",
                        "PPTeXpress",
                        "projects",
                    )
                else:  # Linux
                    return os.path.join(
                        os.path.expanduser("~"),
                        ".local",
                        "share",
                        "pptexpress",
                        "projects",
                    )
            else:
                return os.path.join(os.path.expanduser("~"), "PPTeXpress", "projects")

    def get_recent_projects(self, limit: int = 10) -> list:
        """
        Scan the application data directory directly，Get the latest information on all projects.
        simplify：session_idIt's the directory name.
        """
        try:
            app_data_dir = self.get_app_data_dir()
            logger.debug(f"📁 Scan project directory: {app_data_dir}")

            if not os.path.exists(app_data_dir):
                logger.debug(
                    f"⚠️ Application data directory does not exist: {app_data_dir}"
                )
                return []

            # Get all subdirectories（session_idTable of contents）
            projects = []
            for directory_name in os.listdir(app_data_dir):
                project_dir = os.path.join(app_data_dir, directory_name)

                # Check if it is a directory
                if os.path.isdir(project_dir):
                    yaml_path = os.path.join(project_dir, "project.yaml")
                    if os.path.exists(yaml_path):
                        try:
                            # read project.yaml
                            with open(yaml_path, "r", encoding="utf-8") as f:
                                project_data = yaml.safe_load(f)

                            if not project_data or "project" not in project_data:
                                continue

                            # 🔧 Revise：session_idIt’s the directory name
                            project_id = project_data["project"].get(
                                "id", directory_name[:8]
                            )
                            last_modified = os.path.getmtime(project_dir)

                            # Get project information
                            project_info = {
                                "session_id": directory_name,  # 🔧 session_idIt’s the directory name
                                "project_dir": project_dir,
                                "name": project_data["project"].get(
                                    "name", "Unnamed project"
                                ),
                                "id": project_id,
                                "created_at": project_data["project"].get(
                                    "created_at", ""
                                ),
                                "modified_at": project_data["project"].get(
                                    "modified_at", ""
                                ),
                                "last_opened": datetime.datetime.fromtimestamp(
                                    last_modified
                                ).isoformat(),
                                "valid": True,
                            }

                            # statisticsslidequantity
                            slides_dir = os.path.join(project_dir, "slides")
                            if os.path.exists(slides_dir):
                                slide_files = [
                                    f
                                    for f in os.listdir(slides_dir)
                                    if f.endswith(".json")
                                ]
                                project_info["slide_count"] = len(slide_files)
                            else:
                                project_info["slide_count"] = 0

                            projects.append(project_info)

                        except Exception as e:
                            logger.debug(
                                f"⚠️ Processing project failed {directory_name}: {e}"
                            )
                            continue

            # Sort by last modified time in descending order
            projects.sort(key=lambda x: x.get("last_opened", ""), reverse=True)

            # Limit the number of returns
            recent_projects = projects[:limit]

            logger.debug(
                f"✅ Get recent project completions: {len(recent_projects)} items"
            )

            return recent_projects

        except Exception as e:
            logger.debug(f"❌ Failed to get recent items: {e}")
            import traceback

            traceback.print_exc()
            return []

    def get_image_path(self, session_id: str, image_filename: str) -> str:
        """
        Get the full path of the image file.

        Args:
            session_id: sessionID
            image_filename: Image file name

        Returns:
            str: Full path to image，Returns an empty string if it does not exist
        """
        project = self.get_project_by_session(session_id)
        if not project:
            return ""

        assets_dir = project.get("assets_dir")
        if not assets_dir or not os.path.exists(assets_dir):
            return ""

        image_path = os.path.join(assets_dir, image_filename)
        return image_path if os.path.exists(image_path) else ""

    def list_project_images(self, session_id: str) -> dict:
        """
        Lists information about all images in the project.

        Args:
            session_id: sessionID

        Returns:
            dict: Picture information dictionary
                {
                    'images_dir': str,
                    'count': int,
                    'files': [
                        {
                            'filename': str,
                            'size_bytes': int,
                            'last_modified': str,
                            'url_path': str
                        },
                        ...
                    ]
                }
        """
        project = self.get_project_by_session(session_id)
        if not project:
            return {"error": "Project does not exist"}

        assets_dir = project.get("assets_dir")
        if not assets_dir or not os.path.exists(assets_dir):
            return {"images_dir": assets_dir, "count": 0, "files": []}

        images = []
        try:
            for filename in os.listdir(assets_dir):
                filepath = os.path.join(assets_dir, filename)
                if os.path.isfile(filepath) and filename.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".gif", ".bmp")
                ):
                    stat_info = os.stat(filepath)
                    images.append(
                        {
                            "filename": filename,
                            "size_bytes": stat_info.st_size,
                            "last_modified": datetime.datetime.fromtimestamp(
                                stat_info.st_mtime
                            ).isoformat(),
                            "url_path": f"/api/project/{session_id}/image/{filename}",
                        }
                    )
        except Exception as e:
            logger.debug(f"❌ Failed to list images: {e}")

        return {"images_dir": assets_dir, "count": len(images), "files": images}

    def upload_image(self, session_id: str, filename: str, image_data: bytes) -> dict:
        """
        Upload images to the project.

        Args:
            session_id: sessionID
            filename: file name
            image_data: Image binary data

        Returns:
            dict: Upload results
        """
        project = self.get_project_by_session(session_id)
        if not project:
            return {"success": False, "error": "Project does not exist"}

        assets_dir = project.get("assets_dir")
        if not assets_dir:
            assets_dir = os.path.join(project["project_dir"], "assets", "images")
            os.makedirs(assets_dir, exist_ok=True)

        try:
            # Clean up filenames，Prevent path traversal attacks
            safe_filename = os.path.basename(filename)
            # Add timestamp to prevent duplicate names
            import time

            name, ext = os.path.splitext(safe_filename)
            timestamp = int(time.time())
            final_filename = f"uploaded_{timestamp}_{name}{ext}"

            filepath = os.path.join(assets_dir, final_filename)

            with open(filepath, "wb") as f:
                f.write(image_data)

            # Get file information
            stat_info = os.stat(filepath)

            return {
                "success": True,
                "filename": final_filename,
                "original_filename": filename,
                "size_bytes": len(image_data),
                "filepath": filepath,
                "url_path": f"/api/project/{session_id}/image/{final_filename}",
                "last_modified": datetime.datetime.fromtimestamp(
                    stat_info.st_mtime
                ).isoformat(),
            }

        except Exception as e:
            logger.debug(f"❌ Failed to upload image: {e}")
            return {"success": False, "error": str(e)}

    def get_git_manager(self, session_id: str) -> Optional[GitManager]:
        """
        Get the projectGitManager

        Args:
            session_id: sessionID

        Returns:
            GitManagerExample，Return if it does not existNone
        """
        try:
            # if already exists，Return directly
            if session_id in self.git_managers:
                return self.git_managers[session_id]

            # Get project data
            project = self.get_project_by_session(session_id)
            if not project:
                logger.debug(
                    f"❌ Unable to obtainGitManager: Project does not exist (session_id: {session_id})"
                )
                return None

            project_dir = project.get("project_dir")
            if not project_dir:
                logger.debug(
                    f"❌ Unable to obtainGitManager: Project directory does not exist"
                )
                return None

            # createGitManagerExample
            git_manager = GitManager(project_dir)
            self.git_managers[session_id] = git_manager

            logger.debug(f"✅ createGitManager: {session_id}")
            return git_manager

        except Exception as e:
            logger.debug(f"❌ GetGitManagerfail: {e}")
            return None

    def init_project_git(self, session_id: str, force: bool = False) -> Dict[str, Any]:
        """
        Initialize the projectGitstorehouse

        Args:
            session_id: sessionID
            force: Whether to force reinitialization

        Returns:
            Initialization result
        """
        try:
            git_manager = self.get_git_manager(session_id)
            if not git_manager:
                return {
                    "success": False,
                    "message": "Unable to obtainGitManager",
                    "session_id": session_id,
                }

            # initializationGitstorehouse
            result = git_manager.init_repository(force=force)

            logger.debug(
                f"🔧 initializationGitWarehouse results: {result.get('success')}"
            )
            return result

        except Exception as e:
            error_msg = f"initializationGitWarehouse failed: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            return {"success": False, "message": error_msg, "session_id": session_id}

    def create_project_snapshot(
        self, session_id: str, message: str = ""
    ) -> Dict[str, Any]:
        """
        Create a snapshot of the project

        Args:
            session_id: sessionID
            message: Snapshot description

        Returns:
            Create snapshot results
        """
        try:
            git_manager = self.get_git_manager(session_id)
            if not git_manager:
                return {
                    "success": False,
                    "message": "Unable to obtainGitManager",
                    "session_id": session_id,
                }

            # Create snapshot
            result = git_manager.create_snapshot(message)

            logger.debug(f"📸 Create snapshot results: {result.get('success')}")

            # If created successfully，Update project modification time
            if result.get("success"):
                self.update_project_yaml(
                    session_id,
                    {
                        "project.modified_at": datetime.datetime.now().isoformat(),
                        "project.last_snapshot": result.get("short_hash"),
                    },
                )

            return result

        except Exception as e:
            error_msg = f"Failed to create snapshot: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            return {"success": False, "message": error_msg, "session_id": session_id}

    def list_project_snapshots(
        self, session_id: str, limit: int = 10
    ) -> Dict[str, Any]:
        """
        List snapshots of projects

        Args:
            session_id: sessionID
            limit: Limit on the number of snapshots returned

        Returns:
            Snapshot list results
        """
        try:
            git_manager = self.get_git_manager(session_id)
            if not git_manager:
                return {
                    "success": False,
                    "message": "Unable to obtainGitManager",
                    "session_id": session_id,
                    "snapshots": [],
                }

            # Get snapshot list
            result = git_manager.list_snapshots(limit=limit)

            logger.debug(f"📋 Get {result.get('count', 0)} snapshots")
            return result

        except Exception as e:
            error_msg = f"Failed to get snapshot list: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            return {
                "success": False,
                "message": error_msg,
                "session_id": session_id,
                "snapshots": [],
            }

    def restore_project_snapshot(
        self, session_id: str, commit_hash: str
    ) -> Dict[str, Any]:
        """
        Restore project to specified snapshot

        Args:
            session_id: sessionID
            commit_hash: commit hash

        Returns:
            Recovery results
        """
        try:
            git_manager = self.get_git_manager(session_id)
            if not git_manager:
                return {
                    "success": False,
                    "message": "Unable to obtainGitManager",
                    "session_id": session_id,
                }

            # Restore snapshot
            result = git_manager.restore_snapshot(commit_hash)

            if result.get("success"):
                logger.debug(f"✅ Snapshot recovery successful: {commit_hash[:8]}")

                # 🔥 important：Project data needs to be reloaded after rollback
                self._reload_project_after_restore(session_id)

            return result

        except Exception as e:
            error_msg = f"Failed to restore snapshot: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            return {"success": False, "message": error_msg, "session_id": session_id}

    def _reload_project_after_restore(self, session_id: str) -> bool:
        """
        Reload project data after restoring snapshot

        Args:
            session_id: sessionID

        Returns:
            Is reloading successful?
        """
        try:
            project = self.get_project_by_session(session_id)
            if not project:
                return False

            project_dir = project.get("project_dir")
            if not project_dir:
                return False

            # reloadproject.yaml
            yaml_path = os.path.join(project_dir, "project.yaml")
            if os.path.exists(yaml_path):
                with open(yaml_path, "r", encoding="utf-8") as f:
                    project_data = yaml.safe_load(f)

                # Update project data in memory
                if project.get("project_data"):
                    project["project_data"] = project_data

                logger.debug(f"🔄 Project data has been reloaded")
                return True

            return False

        except Exception as e:
            logger.debug(f"⚠️ Reloading project data failed: {e}")
            return False

    def get_git_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get the projectGitstate

        Args:
            session_id: sessionID

        Returns:
            Gitstatus information
        """
        try:
            git_manager = self.get_git_manager(session_id)
            if not git_manager:
                return {
                    "success": False,
                    "message": "Unable to obtainGitManager",
                    "session_id": session_id,
                }

            return git_manager.get_status()

        except Exception as e:
            error_msg = f"GetGitstatus failed: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            return {"success": False, "message": error_msg, "session_id": session_id}

    def cleanup_git_manager(self, session_id: str) -> bool:
        """
        cleanup projectGitManager

        Args:
            session_id: sessionID

        Returns:
            Is the cleanup successful?
        """
        try:
            if session_id in self.git_managers:
                del self.git_managers[session_id]
                logger.debug(f"🗑️ clean upGitManager: {session_id}")
                return True
            return False
        except Exception as e:
            logger.debug(f"⚠️ clean upGitManagerfail: {e}")
            return False

    def cleanup_project_for_deletion(self, session_id: str) -> Dict[str, Any]:
        """
        Preparing for project deletion，clean upGitWarehouse etc.

        Args:
            session_id: sessionID

        Returns:
            Clean results
        """
        try:
            logger.debug(f"🧹 Prepare for project deletion: {session_id}")

            # 1. Get project data
            project = self.get_project_by_session(session_id)
            if not project:
                return {
                    "success": False,
                    "message": f"Project does not exist: {session_id}",
                    "project_exists": False,
                }

            project_dir = project.get("project_dir")
            if not project_dir or not os.path.exists(project_dir):
                return {
                    "success": False,
                    "message": f"Project directory does not exist: {project_dir}",
                    "project_dir_exists": False,
                }

            # 2. clean upGitstorehouse
            git_manager = self.get_git_manager(session_id)
            git_cleaned = False

            if git_manager:
                try:
                    git_result = git_manager.cleanup_repository()
                    git_cleaned = git_result.get("success", False)
                    logger.debug(f"🧹 GitClean results: {git_cleaned}")
                except Exception as e:
                    logger.debug(f"⚠️ GitCleanup failed: {e}")

            # 3. Clean up the in-memory manager
            self.cleanup_git_manager(session_id)

            # 4. If you are in snapshot viewing mode，ensure recovery
            try:
                if git_manager and git_manager.check_snapshot_view_status():
                    logger.debug("⚠️ Snapshot viewing mode detected，force restore...")
                    git_manager.force_recover()
            except:
                pass

            logger.debug(f"✅ Project cleanup completed")
            return {
                "success": True,
                "message": "Project has been cleared，Can be deleted",
                "project_dir": project_dir,
                "git_cleaned": git_cleaned,
                "ready_for_deletion": True,
            }

        except Exception as e:
            error_msg = f"Cleanup project failed: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            return {"success": False, "message": error_msg, "ready_for_deletion": False}

    def save_structured_data_to_json(
        self, project_dir, slide_idx, shape_id, structured_data
    ):
        """Save structured data toJSONdocument"""
        try:
            # buildslidefile path
            slides_dir = os.path.join(project_dir, "slides")
            slide_filename = f"slide_{slide_idx:03d}.json"
            slide_path = os.path.join(slides_dir, slide_filename)

            if not os.path.exists(slide_path):
                logger.debug(f"❌ SlideFile does not exist: {slide_path}")
                return False

            # Read existing data
            with open(slide_path, "r", encoding="utf-8") as f:
                slide_data = json.load(f)

            # Update designationshapestructured data
            if "shapes" in slide_data and shape_id in slide_data["shapes"]:
                # Only update text data，Keep other properties
                slide_data["shapes"][shape_id]["txt"] = structured_data

                # Set modification timestamp
                slide_data["shapes"][shape_id][
                    "mod"
                ] = datetime.datetime.now().isoformat()

                # write back file
                with open(slide_path, "w", encoding="utf-8") as f:
                    json.dump(slide_data, f, ensure_ascii=False, indent=2)

                logger.debug(f"✅ Structured data saved to: {slide_path}")
                return True
            else:
                logger.debug(f"❌ not foundshape: {shape_id} exist {slide_path}")
                return False

        except Exception as e:
            logger.debug(f"❌ Failed to save structured data: {e}")
            return False

    def save_table_changes(
        self, project_dir, slide_idx, shape_id, changes, original_data
    ):
        """Save table changes to JSON file"""
        try:
            # Buildslidefile path
            slides_dir = os.path.join(project_dir, "slides")
            slide_filename = f"slide_{slide_idx:03d}.json"
            slide_path = os.path.join(slides_dir, slide_filename)

            if not os.path.exists(slide_path):
                logger.debug(f"❌ Slide file not found: {slide_path}")
                return False

            # Read existing data
            with open(slide_path, "r", encoding="utf-8") as f:
                slide_data = json.load(f)

            # Check if the shape exists
            if "shapes" not in slide_data or shape_id not in slide_data["shapes"]:
                logger.debug(f"❌ Shape not found: {shape_id}")
                return False

            shape_info = slide_data["shapes"][shape_id]

            # Parse tabular data
            try:
                if "table_data" in shape_info:
                    table_data = json.loads(shape_info["table_data"])
                else:
                    table_data = json.loads(original_data)
            except json.JSONDecodeError:
                logger.debug(f"❌ Failed to parse table data for {shape_id}")
                return False

            # Apply changes
            modified_cells = 0
            for cell_id, cell_change in changes.items():
                # parse cellIDFormat: cell_changeshould containrowandcol
                if "row" in cell_change and "col" in cell_change:
                    row_idx = cell_change["row"]
                    col_idx = cell_change["col"]

                    # Make sure the index is valid
                    if (
                        isinstance(table_data, list)
                        and row_idx < len(table_data)
                        and col_idx < len(table_data[row_idx])
                    ):

                        table_data[row_idx][col_idx]["text"] = cell_change.get(
                            "text", ""
                        )
                        modified_cells += 1

            # update and save
            shape_info["table_data"] = json.dumps(table_data, ensure_ascii=False)
            shape_info["mod"] = datetime.datetime.now().isoformat()

            with open(slide_path, "w", encoding="utf-8") as f:
                json.dump(slide_data, f, ensure_ascii=False, indent=2)

            logger.debug(f"✅ Table changes saved: {shape_id} ({modified_cells} cells)")
            return True

        except Exception as e:
            logger.debug(f"❌ Failed to save table changes: {e}")
            return False

    def generate_modified_pptx(self, session_id: str) -> str:
        """
        Generate modifiedPPTXfile and returns the file path

        Args:
            session_id: sessionID

        Returns:
            str: generatedPPTXfile path
        """
        project_data_obj = self.get_project_by_session(session_id)
        if not project_data_obj:
            raise RuntimeError("Session does not exist")

        project_dir = project_data_obj.get("project_dir")
        if not project_dir:
            raise RuntimeError("This session has no associated project directory")

        # Load project configuration
        yaml_path = os.path.join(project_dir, "project.yaml")
        with open(yaml_path, "r", encoding="utf-8") as f:
            project_data = yaml.safe_load(f)

        template_file = project_data["template"]["file"]
        template_path = os.path.join(project_dir, template_file)

        if not os.path.exists(template_path):
            raise RuntimeError("Template file does not exist")

        # Load modifications
        structured_changes = {}
        table_changes = {}
        slides_dir = os.path.join(project_dir, "slides")

        if os.path.exists(slides_dir):
            for filename in sorted(os.listdir(slides_dir)):
                if filename.endswith(".json"):
                    slide_path = os.path.join(slides_dir, filename)
                    try:
                        with open(slide_path, "r", encoding="utf-8") as f:
                            slide_data = json.load(f)

                        if "shapes" in slide_data:
                            for shape_id, shape_info in slide_data["shapes"].items():
                                # text data
                                if "txt" in shape_info and isinstance(
                                    shape_info["txt"], list
                                ):
                                    structured_changes[shape_id] = shape_info["txt"]

                                # tabular data
                                if (
                                    "table_data" in shape_info
                                    and shape_info["table_data"]
                                ):
                                    try:
                                        table_json = shape_info["table_data"]
                                        table_data = (
                                            json.loads(table_json)
                                            if isinstance(table_json, str)
                                            else table_json
                                        )

                                        has_changes = False
                                        if isinstance(table_data, list):
                                            for row in table_data:
                                                if isinstance(row, list):
                                                    for cell in row:
                                                        if (
                                                            isinstance(cell, dict)
                                                            and "text" in cell
                                                        ):
                                                            if (
                                                                "original_text" in cell
                                                                and cell.get("text")
                                                                != cell.get(
                                                                    "original_text"
                                                                )
                                                            ):
                                                                has_changes = True
                                                            elif (
                                                                "text" in cell
                                                                and cell["text"]
                                                            ):
                                                                has_changes = True

                                        if has_changes:
                                            table_changes[shape_id] = table_data

                                    except (json.JSONDecodeError, TypeError):
                                        pass
                    except Exception:
                        continue

        # Load image modification
        assets_dir = os.path.join(project_dir, "assets", "images")
        image_modifications = {}

        if os.path.exists(assets_dir):
            try:
                images_json_path = os.path.join(project_dir, "images.json")
                if os.path.exists(images_json_path):
                    with open(images_json_path, "r", encoding="utf-8") as f:
                        images_data = json.load(f)

                    for shape_id, image_info in images_data.items():
                        if "image_ref" in image_info:
                            image_path = os.path.join(
                                assets_dir, image_info["image_ref"]
                            )
                            if os.path.exists(image_path):
                                image_modifications[shape_id] = image_path
            except Exception:
                pass

        # Apply changes and buildPPTX
        prs = Presentation(template_path)
        editor = PPTXFormEditor(template_path)

        if structured_changes:
            editor.apply_structured_changes_to_pptx(prs, structured_changes)

        if table_changes:
            editor.apply_table_changes_to_pptx(prs, table_changes)

        if image_modifications:
            for shape_id, image_path in image_modifications.items():
                editor.apply_image_to_pptx(prs, shape_id, image_path)

        # Create temporary files
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
        pptx_path = temp_file.name
        prs.save(pptx_path)
        temp_file.close()

        return pptx_path

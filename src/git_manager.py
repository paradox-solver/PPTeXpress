# src/git_manager.py
import os
import subprocess
import json
import shutil
import tempfile
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import traceback
from pathlib import Path
import os
import subprocess
from src.utils import logger

GITIGNORE_TEMPLATE = """# ========================================
# PPTX Express project Git Ignore configuration
# ========================================

# ========== binary file（No version control）==========
*.pptx
*.pdf
*.zip
*.tar
*.gz
*.7z

# ========== Image files ==========
*.png
*.jpg
*.jpeg
*.gif
*.bmp
*.tiff
*.ico
*.svg

# ========== Project resource directory ==========
assets/images/
!assets/images/README.md  # Keep documentation（if needed）
!assets/images/.gitkeep  # Leave empty files to maintain directory structure

# ========== System files ==========
.DS_Store
Thumbs.db
*.swp
*.swo
*~
~*

# ========== temporary files ==========
*.tmp
*.temp
*.log
*.cache
*.pid
*.lock

# ========== Environment configuration ==========
.env
.env.local
.env.*.local
.env.production
.env.development

# ========== IDE/Editor file ==========
.vscode/
.idea/
*.swp
*.swo
*.sublime-*

# ========== Python temporary files ==========
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
env.bak/
venv.bak/

# ========== Front-end build files ==========
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
dist/
build/
static/js/*.min.js
static/css/*.min.css

# ========== other ==========
*.db
*.sqlite
*.sqlite3
"""


class GitManager:
    """
    Gitversion management manager
    Responsible for the projectGitWarehouse initialization, snapshot creation, history viewing and rollback operations
    """

    def __init__(self, project_dir: str):
        """
        initializationGitManager

        Args:
            project_dir: Project directory path
        """
        self.project_dir = Path(project_dir).absolute()
        self.git_dir = self.project_dir / ".git"

        # Gitoperating status
        self.is_operating = False
        self.last_error = None

    def _run_git_command(
        self, args: List[str], cwd: str = None, capture_output: bool = True
    ) -> Tuple[bool, str]:
        """
        runGitHelper methods for commands
        """
        if self.is_operating:
            return False, "anotherGitOperation in progress"

        try:
            if cwd is None:
                cwd = self.project_dir

            os.makedirs(cwd, exist_ok=True)

            cmd = ["git"] + args
            logger.debug(f"🔧 implementGitOrder: {' '.join(cmd)}")
            logger.debug(f"   working directory: {cwd}")

            self.is_operating = True

            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                shell=False,
                errors="replace",
            )

            self.is_operating = False

            logger.debug(f"🔧 GitCommand return code: {result.returncode}")

            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                # 🔥 improve：Better extraction of error messages
                error_parts = []

                # 1. priority usestderr
                if result.stderr and result.stderr.strip():
                    error_parts.append(result.stderr.strip())

                # 2. then checkstdout（GitSometimes the error message is placed instdout）
                if result.stdout and result.stdout.strip():
                    stdout = result.stdout.strip()
                    # examinestdoutDoes it contain error information?（like"nothing to commit"）
                    if any(
                        keyword in stdout.lower()
                        for keyword in ["error", "fatal", "nothing to commit", "failed"]
                    ):
                        error_parts.append(stdout)

                # 3. If there is no information，Use universal messages
                if not error_parts:
                    error_parts.append(
                        f"Gitcommand failed，return code: {result.returncode}"
                    )

                # Merge error messages
                error_msg = " | ".join(error_parts)
                self.last_error = error_msg

                # 🔥 improve：Distinguish between different types of errors
                error_lower = error_msg.lower()
                if (
                    "nothing to commit" in error_lower
                    or "working tree clean" in error_lower
                ):
                    logger.debug(f"ℹ️ Githint: No changes need to be submitted")
                else:
                    logger.debug(f"❌ Gitcommand failed:")
                    logger.debug(f"   return code: {result.returncode}")
                    logger.debug(f"   error message: {error_msg}")
                    if result.stdout and len(result.stdout.strip()) > 0:
                        logger.debug(f"   standard output: {result.stdout[:100]}...")

                return False, error_msg

        except subprocess.TimeoutExpired:
            self.is_operating = False
            error_msg = "GitCommand execution timeout（30Second）"
            self.last_error = error_msg
            return False, error_msg
        except Exception as e:
            self.is_operating = False
            error_msg = (
                f"implementGitAn unknown error occurred while commanding: {str(e)}"
            )
            self.last_error = error_msg
            logger.debug(f"❌ {error_msg}")
            traceback.print_exc()
            return False, error_msg

    def init_repository(self, force: bool = False) -> Dict[str, Any]:
        """
        initializationGitstorehouse，set up.gitignore
        """
        try:
            logger.debug(f"🔄 initializationGitstorehouse: {self.project_dir}")

            # Check if it is alreadyGitstorehouse
            if os.path.exists(self.git_dir):
                if force:
                    logger.debug(
                        f"⚠️ GitWarehouse already exists，force reinitialization"
                    )
                    # backup old.gitTable of contents
                    backup_dir = self.git_dir + ".backup"
                    if os.path.exists(backup_dir):
                        shutil.rmtree(backup_dir)
                    shutil.move(self.git_dir, backup_dir)
                    logger.debug(f"📦 oldGitWarehouse backup to: {backup_dir}")
                else:
                    logger.debug(f"✅ GitWarehouse already exists: {self.git_dir}")
                    return {
                        "success": True,
                        "message": "GitWarehouse already exists",
                        "repo_exists": True,
                        "git_dir": self.git_dir,
                    }

            # 1. initializationGitstorehouse
            logger.debug(f"🔧 implement git init...")
            success, message = self._run_git_command(["init"])

            if not success:
                return {
                    "success": False,
                    "message": f"GitWarehouse initialization failed: {message}",
                    "repo_exists": False,
                }

            # 2. set upGitUser information
            logger.debug(f"🔧 set upGitUser information...")
            self._run_git_command(
                ["config", "user.name", "Paradoxsolver"], capture_output=False
            )
            self._run_git_command(
                ["config", "user.email", "paradoxsolver@somemail.com"],
                capture_output=False,
            )

            # 3. create.gitignoredocument
            gitignore_path = os.path.join(self.project_dir, ".gitignore")
            try:
                with open(gitignore_path, "w", encoding="utf-8") as f:
                    f.write(GITIGNORE_TEMPLATE)
                logger.debug(f"✅ create.gitignore: {gitignore_path}")
            except Exception as e:
                logger.debug(f"⚠️ create.gitignorefail: {e}")
                # Continue execution，This is not a fatal error

            # 4. 🔥 critical fix：Submit all project documents（and not just.gitignore）
            logger.debug(f"🔧 Submit all project documents...")

            # Get all text files
            text_files = self._find_text_files()

            if text_files:
                logger.debug(
                    f"📋 turn up {len(text_files)} text files need to be submitted"
                )

                # add all files（include.gitignore）
                if ".gitignore" not in text_files:
                    text_files.append(".gitignore")

                # Execute add
                add_success, add_msg = self._run_git_command(["add"] + text_files)

                if add_success:
                    # Execute commit
                    commit_success, commit_msg = self._run_git_command(
                        ["commit", "-m", "Initial commit: Project files"]
                    )

                    if commit_success:
                        logger.debug(
                            f"✅ Initial submission completed，Submitted {len(text_files)} files"
                        )
                    else:
                        logger.debug(f"⚠️ Initial commit failed: {commit_msg}")
                else:
                    logger.debug(f"⚠️ Failed to add file: {add_msg}")
            else:
                logger.debug(f"⚠️ Text file not found")

            # 5. Verify that the warehouse is created successfully
            if os.path.exists(self.git_dir):
                logger.debug(
                    f"✅ GitWarehouse initialization successful: {self.git_dir}"
                )

                # Get initial commit information
                hash_success, hash_result = self._run_git_command(["rev-parse", "HEAD"])
                commit_hash = hash_result.strip() if hash_success else None

                return {
                    "success": True,
                    "message": "GitWarehouse initialization successful",
                    "repo_exists": True,
                    "git_dir": self.git_dir,
                    "commit_hash": commit_hash,
                    "has_initial_commit": commit_hash is not None,
                }
            else:
                return {
                    "success": False,
                    "message": "GitThe warehouse directory was not created successfully",
                    "repo_exists": False,
                }

        except Exception as e:
            error_msg = f"initializationGitAn error occurred in the warehouse: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            traceback.print_exc()
            return {"success": False, "message": error_msg, "repo_exists": False}

    def create_snapshot(self, message: str = "", user: str = None) -> Dict[str, Any]:
        """
        Create snapshot（Submit all current text files）
        """
        try:
            if not message or message.strip() == "":
                return {
                    "success": False,
                    "message": "Snapshot description cannot be empty",
                    "commit_hash": None,
                    "no_message": True,
                    "error_type": "validation_error",
                }

            logger.debug(f"📸 Create snapshot: '{message}'")

            # 1. Check if the warehouse exists
            if not self.git_dir.exists():
                return {
                    "success": False,
                    "message": "GitThe warehouse is not initialized",
                    "commit_hash": None,
                    "repo_exists": False,
                    "error_type": "repo_not_initialized",
                }

            # 2. set upGitUser information（Silent execution）
            self._run_git_command(
                ["config", "user.name", "Paradoxsolver"], capture_output=False
            )
            self._run_git_command(
                ["config", "user.email", "paradoxsolver@somemail.com"],
                capture_output=False,
            )

            # 3. Get the text file to track
            text_files = self._find_text_files()

            if not text_files:
                return {
                    "success": False,
                    "message": "No traceable text file found",
                    "commit_hash": None,
                    "no_files": True,
                    "error_type": "no_text_files",
                }

            logger.debug(f"📋 turn up {len(text_files)} text files")

            # 4. Add files to the staging area
            add_success, add_msg = self._run_git_command(["add"] + text_files)

            if not add_success:
                return {
                    "success": False,
                    "message": f"Failed to add files to staging area: {add_msg}",
                    "commit_hash": None,
                    "error_type": "add_failed",
                }

            # 5. Build commit message
            commit_message = self._build_commit_message(message, user)

            # 6. submit
            commit_success, commit_msg = self._run_git_command(
                ["commit", "-m", commit_message]
            )

            if commit_success:
                # Extract commit hash
                hash_success, hash_result = self._run_git_command(["rev-parse", "HEAD"])

                if hash_success:
                    commit_hash = hash_result.strip()
                    logger.debug(
                        f"✅ Snapshot created successfully: {commit_hash[:8]} - '{message}'"
                    )
                    return {
                        "success": True,
                        "message": "Snapshot created successfully",
                        "commit_hash": commit_hash,
                        "short_hash": commit_hash[:8],
                        "description": message,
                        "files_count": len(text_files),
                    }
                else:
                    return {
                        "success": True,
                        "message": "Snapshot created successfully，But unable to get commit hash",
                        "commit_hash": None,
                        "description": message,
                        "warning": "cannot_get_hash",
                    }
            else:
                # 🔥 improve：Detect more accurately"no change"situation
                commit_msg_lower = commit_msg.lower()

                is_no_changes = any(
                    phrase in commit_msg_lower
                    for phrase in [
                        "nothing to commit",
                        "no changes added to commit",
                        "working tree clean",
                    ]
                )

                if is_no_changes:
                    logger.debug(f"ℹ️ no file changes，Skip creating snapshot")
                    return {
                        "success": False,
                        "message": "No file changes need to be submitted",
                        "no_changes": True,
                        "commit_hash": None,
                        "is_expected": True,  # This is expected behavior，not a mistake
                        "error_type": "no_changes",
                    }
                else:
                    # real error
                    logger.debug(f"❌ Failed to create snapshot: {commit_msg}")
                    return {
                        "success": False,
                        "message": f"Submission failed: {commit_msg}",
                        "commit_hash": None,
                        "error_type": "commit_failed",
                    }

        except Exception as e:
            error_msg = f"An error occurred while creating the snapshot: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            traceback.print_exc()
            return {
                "success": False,
                "message": error_msg,
                "commit_hash": None,
                "error_type": "exception",
            }

    def _build_commit_message(self, user_message: str, user: str = None) -> str:
        """
        Build commit message - The simplest and most secure one-line version
        """
        # Take only the first row，Avoid newline problems
        first_line = user_message.strip().split("\n")[0] if user_message else "Snapshot"

        # Add timestamp but keep single line
        timestamp = datetime.now().isoformat()

        # single line format：main message [Timestamp]
        return f"{first_line} [{timestamp}]"

    def list_snapshots(self, limit: int = 10) -> Dict[str, Any]:
        """
        List recent snapshots
        """
        try:
            # Check if it isGitstorehouse
            if not self.git_dir.exists():
                return {
                    "success": False,
                    "message": "noGitstorehouse",
                    "snapshots": [],
                    "repo_exists": False,
                }

            # 🔥 use %ai instead of %ad（Cross-platform compatible）
            success, log_output = self._run_git_command(
                [
                    "log",
                    f"--max-count={limit}",
                    "--pretty=format:%H|%ai|%s",  # %ai: ISO 8601format date
                    "--no-merges",
                ]
            )

            if not success:
                return {
                    "success": False,
                    "message": f"Failed to get commit history: {log_output}",
                    "snapshots": [],
                    "repo_exists": True,
                }

            # Parse log output
            snapshots = []
            for line in log_output.strip().split("\n"):
                if not line:
                    continue

                parts = line.split("|", 2)
                if len(parts) >= 3:
                    commit_hash = parts[0]
                    date_str = parts[1]
                    message = parts[2]

                    # Parse metadata
                    metadata = self._parse_commit_metadata(message)

                    # Get short description（first line）
                    full_message_lines = message.split("\n")
                    short_description = (
                        full_message_lines[0]
                        if full_message_lines
                        else "No description"
                    )

                    # Get file change statistics
                    file_count = self._get_commit_file_count(commit_hash)

                    snapshots.append(
                        {
                            "hash": commit_hash,
                            "short_hash": commit_hash[:8],
                            "date": date_str,
                            "timestamp": date_str,
                            "description": short_description,
                            "full_message": message,
                            "metadata": metadata,
                            "file_count": file_count,
                            "files": self._get_commit_files(commit_hash),
                        }
                    )

            logger.debug(f"📋 Get {len(snapshots)} snapshots")
            return {
                "success": True,
                "message": f"Get {len(snapshots)} snapshots",
                "snapshots": snapshots,
                "count": len(snapshots),
                "repo_exists": True,
            }

        except Exception as e:
            error_msg = f"Failed to get snapshot list: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            return {"success": False, "message": error_msg, "snapshots": []}

    def _get_commit_files(self, commit_hash: str) -> List[str]:
        """Get the list of files modified in a commit"""
        success, output = self._run_git_command(
            ["show", "--name-only", "--format=", commit_hash]
        )

        if success and output:
            files = [f.strip() for f in output.strip().split("\n") if f.strip()]
            return files

        return []

    def _get_commit_file_count(self, commit_hash: str) -> int:
        """Get the number of files in a commit"""
        success, output = self._run_git_command(
            ["show", "--name-only", "--format=", commit_hash]
        )

        if success and output:
            # Count non-blank lines
            files = [f for f in output.strip().split("\n") if f.strip()]
            return len(files)

        return 0

    def _parse_commit_metadata(self, commit_message: str) -> Dict[str, Any]:
        """
        Parse metadata from commit message

        Args:
            commit_message: Complete submission information

        Returns:
            The parsed metadata dictionary
        """
        metadata = {}

        try:
            lines = commit_message.split("\n")
            in_metadata_section = False

            for line in lines:
                line = line.strip()

                if line == "[metadata]":
                    in_metadata_section = True
                    continue
                elif line.startswith("[") and line.endswith("]"):
                    # Go to other sections，Stop parsing metadata
                    if line != "[metadata]":
                        in_metadata_section = False
                    continue

                if in_metadata_section and ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip()] = value.strip()

        except Exception as e:
            logger.debug(f"⚠️ Failed to parse metadata: {e}")

        return metadata

    def get_snapshot_content(self, commit_hash: str) -> Dict[str, Any]:
        """
        Get the contents of the specified snapshot（Do not write to workspace）
        Now returns the contents of the actual file in the project，instead ofdata.json

        Args:
            commit_hash: commit hash（full or brief）

        Returns:
            A dictionary containing the contents of the snapshot
        """
        try:
            # Verify commit hash
            if not self._commit_exists(commit_hash):
                return {
                    "success": False,
                    "message": f"Submit does not exist: {commit_hash}",
                    "content": None,
                }

            # 🔥 Revise：Get the contents of all files in the project，instead ofdata.json
            snapshot_content = {
                "commit_hash": commit_hash,
                "short_hash": commit_hash[:8] if len(commit_hash) >= 8 else commit_hash,
                "files": {},
                "metadata": {},
                "timestamp": datetime.now().isoformat(),
            }

            # Get a list of all files in a commit
            success, files_output = self._run_git_command(
                ["ls-tree", "-r", "--name-only", commit_hash]
            )

            if not success:
                return {
                    "success": False,
                    "message": f"Unable to get list of files in commit: {files_output}",
                    "content": None,
                }

            files = [f.strip() for f in files_output.split("\n") if f.strip()]

            # 🔥 Get only the contents of key files（Avoid getting binaries）
            key_files = ["project.yaml", "images.json", ".gitignore"]
            text_extensions = {".yaml", ".yml", ".json", ".txt", ".md"}

            for file in files:
                # Check if it is a text file
                if (file in key_files) or any(
                    file.endswith(ext) for ext in text_extensions
                ):
                    # Get file content
                    file_success, file_content = self._run_git_command(
                        ["show", f"{commit_hash}:{file}"]
                    )

                    if file_success:
                        snapshot_content["files"][file] = {
                            "content": file_content,
                            "size": len(file_content),
                        }

                        # in the case ofproject.yaml，Extract metadata
                        if file == "project.yaml":
                            try:
                                import yaml

                                yaml_data = yaml.safe_load(file_content)
                                if isinstance(yaml_data, dict):
                                    snapshot_content["metadata"].update(
                                        {
                                            "project_name": yaml_data.get(
                                                "project", {}
                                            ).get("name", ""),
                                            "project_id": yaml_data.get(
                                                "project", {}
                                            ).get("id", ""),
                                            "created_at": yaml_data.get(
                                                "project", {}
                                            ).get("created_at", ""),
                                            "template": yaml_data.get(
                                                "template", {}
                                            ).get("file", ""),
                                        }
                                    )
                            except:
                                pass

            # Get commit information as additional metadata
            log_success, log_output = self._run_git_command(
                ["log", "--format=%s", "-n", "1", commit_hash]
            )

            if log_success:
                snapshot_content["metadata"]["commit_message"] = log_output.strip()

            logger.debug(
                f"✅ Obtaining snapshot content successfully: {commit_hash[:8]}, Include {len(snapshot_content['files'])} files"
            )

            return {
                "success": True,
                "message": "Snapshot content obtained successfully",
                "content": snapshot_content,
                "commit_hash": commit_hash,
            }

        except Exception as e:
            error_msg = f"Failed to obtain snapshot content: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            traceback.print_exc()
            return {"success": False, "message": error_msg, "content": None}

    def _commit_exists(self, commit_hash: str) -> bool:
        """
        Check if the commit exists

        Args:
            commit_hash: commit hash

        Returns:
            exists
        """
        success, _ = self._run_git_command(["cat-file", "-e", commit_hash])
        return success

    def restore_snapshot(self, commit_hash: str) -> Dict[str, Any]:
        """
        Roll back to the specified snapshot（hard reset）

        Args:
            commit_hash: commit hash（full or brief）

        Returns:
            A dictionary containing rollback results
        """
        try:
            # Verify commit hash
            if not self._commit_exists(commit_hash):
                return {
                    "success": False,
                    "message": f"Submit does not exist: {commit_hash}",
                    "restored": False,
                }

            # warn：This will discard all uncommitted changes
            logger.debug(f"⚠️ About to rollback to commit: {commit_hash}")
            logger.debug(f"   Changes that are currently uncommitted will be lost！")

            # Perform a hard reset
            success, message = self._run_git_command(["reset", "--hard", commit_hash])

            if success:
                logger.debug(f"✅ Rolled back to commit: {commit_hash}")
                return {
                    "success": True,
                    "message": f"Rolled back to snapshot {commit_hash[:8]}",
                    "restored": True,
                    "commit_hash": commit_hash,
                }
            else:
                return {
                    "success": False,
                    "message": f"Rollback failed: {message}",
                    "restored": False,
                }

        except Exception as e:
            error_msg = f"Rollback failed: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            traceback.print_exc()
            return {"success": False, "message": error_msg, "restored": False}

    def get_status(self) -> Dict[str, Any]:
        """
        GetGitWarehouse status

        Returns:
            status information dictionary
        """
        try:
            # Check if it isGitstorehouse
            if not os.path.exists(self.git_dir):
                return {
                    "success": False,
                    "is_repository": False,
                    "message": "noGitstorehouse",
                    "git_available": self._check_git_available(),
                }

            # Get status
            success, status_output = self._run_git_command(["status", "--porcelain"])

            if not success:
                return {
                    "success": False,
                    "is_repository": True,
                    "message": f"Failed to get status: {status_output}",
                }

            # parsing status
            changes = []
            staged_changes = []
            unstaged_changes = []

            for line in status_output.strip().split("\n"):
                if not line:
                    continue

                status = line[:2]
                filename = line[3:]

                change_info = {
                    "status": status,
                    "file": filename,
                    "status_description": self._parse_status_code(status),
                }

                changes.append(change_info)

                # Classification
                if status[0] != " " and status[0] != "?":  # Staging area
                    staged_changes.append(change_info)
                if status[1] != " ":  # workspace
                    unstaged_changes.append(change_info)

            # Get the current branch
            branch_success, branch_output = self._run_git_command(
                ["branch", "--show-current"]
            )
            current_branch = branch_output.strip() if branch_success else "unknown"

            # Get the number of submissions
            count_success, count_output = self._run_git_command(
                ["rev-list", "--count", "HEAD"]
            )
            commit_count = int(count_output.strip()) if count_success else 0

            return {
                "success": True,
                "is_repository": True,
                "has_changes": len(changes) > 0,
                "changes": changes,
                "staged_changes": staged_changes,
                "unstaged_changes": unstaged_changes,
                "change_count": len(changes),
                "staged_count": len(staged_changes),
                "unstaged_count": len(unstaged_changes),
                "current_branch": current_branch,
                "commit_count": commit_count,
                "git_dir": self.git_dir,
                "project_dir": self.project_dir,
            }

        except Exception as e:
            error_msg = f"Failed to get status: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            return {"success": False, "message": error_msg}

    def _check_git_available(self) -> bool:
        """examineGitIs it available"""
        try:
            result = subprocess.run(
                ["git", "--version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def _parse_status_code(self, status: str) -> str:
        """parseGitstatus code"""
        status_map = {
            "  ": "unmodified",
            "M ": "modified (staged)",
            " M": "modified (not staged)",
            "A ": "added (staged)",
            " A": "added (not staged)",
            "D ": "deleted (staged)",
            " D": "deleted (not staged)",
            "R ": "renamed (staged)",
            " R": "renamed (not staged)",
            "C ": "copied (staged)",
            " C": "copied (not staged)",
            "??": "untracked",
            "!!": "ignored",
        }
        return status_map.get(status, f"unknown ({status})")

    def export_repository(self, export_path: str = None) -> Dict[str, Any]:
        """
        ExportGitstorehouse（for user cloning）

        Args:
            export_path: export path（Optional）

        Returns:
            Export results
        """
        try:
            if export_path is None:
                # Create temporary export directory
                temp_dir = tempfile.mkdtemp(prefix="pptexpress_repo_")
                export_path = os.path.join(temp_dir, "repository.git")

            # Make sure the target directory does not exist
            if os.path.exists(export_path):
                shutil.rmtree(export_path)

            # Copy bare repository
            shutil.copytree(self.git_dir, export_path)

            return {
                "success": True,
                "message": "Warehouse exported successfully",
                "export_path": export_path,
                "is_temp": export_path.startswith(tempfile.gettempdir()),
            }

        except Exception as e:
            error_msg = f"Failed to export warehouse: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            return {"success": False, "message": error_msg, "export_path": None}

    def _find_text_files(self) -> List[str]:
        """
        Find all that should beGitTraced text file

        Returns:
            Text file path list（Relative to project directory，usePOSIXpath）
        """
        text_files = []
        project_path = Path(self.project_dir)

        # 1. key documents - Must track
        key_files = ["project.yaml", "images.json", ".gitignore"]

        for filename in key_files:
            file_path = project_path / filename
            if file_path.is_file():
                rel_path = str(file_path.relative_to(project_path))
                text_files.append(rel_path.replace("\\", "/"))

        # 2. slidesall in directoryJSONdocument
        slides_dir = project_path / "slides"
        if slides_dir.is_dir():
            for json_file in slides_dir.rglob("*.json"):
                if json_file.is_file():
                    rel_path = str(json_file.relative_to(project_path))
                    text_files.append(rel_path.replace("\\", "/"))

        # 3. Other possible configuration files
        other_files = ["README.md", "CHANGELOG.md", "LICENSE"]
        for filename in other_files:
            file_path = project_path / filename
            if file_path.is_file():
                rel_path = str(file_path.relative_to(project_path))
                text_files.append(rel_path.replace("\\", "/"))

        # Remove duplicates and sort
        return sorted(set(text_files))

    def get_repository_info(self) -> Dict[str, Any]:
        """
        Get warehouse details

        Returns:
            Warehouse information dictionary
        """
        status = self.get_status()

        if not status.get("success", False):
            return status

        # Get more information
        info = {
            **status,
            "project_dir": self.project_dir,
            "git_dir_exists": os.path.exists(self.git_dir),
            "gitignore_exists": os.path.exists(
                os.path.join(self.project_dir, ".gitignore")
            ),
            "text_files_count": len(self._find_text_files()),
            "git_available": self._check_git_available(),
            "is_operating": self.is_operating,
            "last_error": self.last_error,
        }

        return info

    def _ensure_git_user_config(self):
        """make sureGitUser information has been set"""
        try:
            logger.debug(f"🔧 set upGitusername...")
            self._run_git_command(
                ["config", "user.name", '"Paradoxsolver"'], capture_output=False
            )

            logger.debug(f"🔧 set upGitMail...")
            self._run_git_command(
                ["config", "user.email", '"paradoxsolver@somemail.com"'],
                capture_output=False,
            )

        except Exception as e:
            logger.debug(f"⚠️ set upGitUser information failed: {e}")

    def view_snapshot(self, commit_hash: str) -> Dict[str, Any]:
        """
        Switch to the specified snapshot to view（use git checkout）
        Notice：This will go into separationHEADstate，The workspace changes to the specified submitted content

        Args:
            commit_hash: The commit hash to view

        Returns:
            Switch results
        """
        try:
            logger.debug(
                f"👀 Switch to snapshot viewing mode: {commit_hash[:8] if len(commit_hash) >= 8 else commit_hash}"
            )

            # 1. Verify commit hash
            if not self._commit_exists(commit_hash):
                return {
                    "success": False,
                    "message": f"Submit does not exist: {commit_hash}",
                    "error_type": "commit_not_found",
                }

            # 2. Save current state（for recovery）
            current_status = self._save_current_state()

            # 3. implement git checkout（separationHEADmodel）
            logger.debug(f"🔧 implement git checkout {commit_hash}...")
            success, message = self._run_git_command(["checkout", commit_hash])

            if not success:
                # Try to restore the original state
                self._restore_current_state(current_status)
                return {
                    "success": False,
                    "message": f"Switching to snapshot failed: {message}",
                    "error_type": "checkout_failed",
                }

            # 4. Record snapshot information to a temporary file
            snapshot_info = {
                "is_snapshot_view": True,
                "commit_hash": commit_hash,
                "original_state": current_status,
                "switched_at": datetime.now().isoformat(),
                "project_dir": str(self.project_dir),
            }

            self._save_snapshot_info(snapshot_info)

            # 5. Get snapshot details
            log_success, log_output = self._run_git_command(
                ["log", "--format=%s|%ai", "-n", "1", commit_hash]
            )

            commit_info = {}
            if log_success:
                parts = log_output.strip().split("|", 1)
                if len(parts) == 2:
                    commit_info = {"message": parts[0], "date": parts[1]}

            logger.debug(f"✅ Switched to snapshot: {commit_hash[:8]}")
            logger.debug(f"   describe: {commit_info.get('message', 'unknown')}")
            logger.debug(f"   time: {commit_info.get('date', 'unknown')}")

            return {
                "success": True,
                "message": f"Switched to snapshot {commit_hash[:8]}",
                "commit_hash": commit_hash,
                "short_hash": commit_hash[:8] if len(commit_hash) >= 8 else commit_hash,
                "commit_info": commit_info,
                "snapshot_info": snapshot_info,
                "is_snapshot_view": True,
            }

        except Exception as e:
            error_msg = f"Switching to snapshot failed: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            traceback.print_exc()
            return {"success": False, "message": error_msg, "error_type": "exception"}

    def recover_from_snapshot(self) -> Dict[str, Any]:
        """
        Restoring from Snapshot View Mode（Return to original state）

        Returns:
            Recovery results
        """
        try:
            logger.debug(f"🔄 Restoring from Snapshot View Mode...")

            # 1. Check if you are in snapshot viewing mode
            snapshot_info = self._load_snapshot_info()
            if not snapshot_info or not snapshot_info.get("is_snapshot_view"):
                return {
                    "success": False,
                    "message": "Not currently in snapshot viewing mode",
                    "error_type": "not_in_snapshot_view",
                }

            original_state = snapshot_info.get("original_state")
            if not original_state:
                return {
                    "success": False,
                    "message": "Unable to find original status information",
                    "error_type": "missing_original_state",
                }

            # 2. Perform recovery（Return to original branch/submit）
            logger.debug(
                f"🔧 Restore original state: {original_state.get('type', 'unknown')} - {original_state.get('ref', 'unknown')}"
            )

            if original_state.get("type") == "branch":
                # Restore original branch
                branch_name = original_state["ref"]
                success, message = self._run_git_command(["checkout", branch_name])
            elif original_state.get("type") == "commit":
                # Revert original commit
                commit_hash = original_state["ref"]
                success, message = self._run_git_command(["checkout", commit_hash])
            else:
                # Used by default git checkout -- .
                success, message = self._run_git_command(["checkout", "--", "."])

            if not success:
                return {
                    "success": False,
                    "message": f"Recovery failed: {message}",
                    "error_type": "recover_failed",
                }

            # 3. Clean snapshot information
            self._cleanup_snapshot_info()

            # 4. If there were previously uncommitted changes，try to restore
            if original_state.get("has_uncommitted_changes"):
                logger.debug(
                    f"⚠️ Notice：Uncommitted changes to the original state were detected during recovery"
                )
                # Users may need to handle these changes manually

            logger.debug(f"✅ Restored from snapshot view mode")

            return {
                "success": True,
                "message": "Restored to original state",
                "original_state": original_state,
                "recovered": True,
            }

        except Exception as e:
            error_msg = f"Restore from snapshot failed: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            traceback.print_exc()
            return {"success": False, "message": error_msg, "error_type": "exception"}

    def _save_current_state(self) -> Dict[str, Any]:
        """
        save currentGitstate

        Returns:
            status information
        """
        try:
            # Get the current branch or commit
            branch_success, branch_output = self._run_git_command(
                ["branch", "--show-current"]
            )
            current_branch = branch_output.strip() if branch_success else None

            # Get the current commit hash
            hash_success, hash_output = self._run_git_command(["rev-parse", "HEAD"])
            current_commit = hash_output.strip() if hash_success else None

            # Check for uncommitted changes
            status_success, status_output = self._run_git_command(
                ["status", "--porcelain"]
            )
            has_uncommitted_changes = bool(status_output.strip())

            state = {
                "saved_at": datetime.now().isoformat(),
                "has_uncommitted_changes": has_uncommitted_changes,
                "project_dir": str(self.project_dir),
            }

            if current_branch:
                state.update(
                    {"type": "branch", "ref": current_branch, "commit": current_commit}
                )
            else:
                state.update(
                    {"type": "commit", "ref": current_commit, "commit": current_commit}
                )

            logger.debug(
                f"📝 Save current state: {state.get('type', 'unknown')} - {state.get('ref', 'unknown')}"
            )

            return state

        except Exception as e:
            logger.debug(f"⚠️ Failed to save state: {e}")
            # Return to base state
            return {
                "type": "unknown",
                "saved_at": datetime.now().isoformat(),
                "has_uncommitted_changes": False,
            }

    def _restore_current_state(self, state: Dict[str, Any]) -> bool:
        """
        Restore previously saved state

        Args:
            state: Previously saved status information

        Returns:
            Is it successful?
        """
        try:
            if not state or state.get("type") == "unknown":
                logger.debug(f"⚠️ Unable to restore unknown state")
                return False

            ref = state.get("ref")
            if not ref:
                logger.debug(f"⚠️ missing from statusrefinformation")
                return False

            success, message = self._run_git_command(["checkout", ref])

            if success:
                logger.debug(
                    f"✅ Status restored successfully: {state.get('type')} - {ref}"
                )
            else:
                logger.debug(f"❌ Status recovery failed: {message}")

            return success

        except Exception as e:
            logger.debug(f"❌ Error while restoring state: {e}")
            return False

    def _save_snapshot_info(self, info: Dict[str, Any]):
        """
        Save snapshot information to temporary file
        """
        try:
            info_file = self.project_dir / ".snapshot_view_info.json"
            with open(info_file, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)
            logger.debug(f"💾 Snapshot information is saved to: {info_file}")
        except Exception as e:
            logger.debug(f"⚠️ Failed to save snapshot information: {e}")

    def _load_snapshot_info(self) -> Optional[Dict[str, Any]]:
        """
        Load snapshot information from temporary file
        """
        try:
            info_file = self.project_dir / ".snapshot_view_info.json"
            if not info_file.exists():
                return None

            with open(info_file, "r", encoding="utf-8") as f:
                info = json.load(f)

            # Verify information validity
            if info.get("project_dir") != str(self.project_dir):
                logger.debug(f"⚠️ Snapshot information project directory does not match")
                return None

            return info

        except Exception as e:
            logger.debug(f"⚠️ Failed to load snapshot information: {e}")
            return None

    def _cleanup_snapshot_info(self):
        """
        Clean snapshot information files
        """
        try:
            info_file = self.project_dir / ".snapshot_view_info.json"
            if info_file.exists():
                info_file.unlink()
                logger.debug(f"🗑️ Clean snapshot information files: {info_file}")
        except Exception as e:
            logger.debug(f"⚠️ Failed to clean snapshot information file: {e}")

    def get_snapshot_view_status(self) -> Dict[str, Any]:
        """
        Get the current snapshot view status

        Returns:
            status information
        """
        snapshot_info = self._load_snapshot_info()

        if not snapshot_info or not snapshot_info.get("is_snapshot_view"):
            return {
                "is_snapshot_view": False,
                "message": "Not in snapshot viewing mode",
            }

        # Get currentHEADinformation
        hash_success, hash_output = self._run_git_command(["rev-parse", "HEAD"])
        current_commit = hash_output.strip() if hash_success else None

        # Check if snapshot commit is still happening
        in_snapshot = current_commit == snapshot_info.get("commit_hash")

        return {
            "is_snapshot_view": True,
            "in_snapshot": in_snapshot,
            "commit_hash": snapshot_info.get("commit_hash"),
            "short_hash": snapshot_info.get("commit_hash", "")[:8],
            "original_state": snapshot_info.get("original_state"),
            "switched_at": snapshot_info.get("switched_at"),
            "project_dir": snapshot_info.get("project_dir"),
        }

    def force_recover(self) -> Dict[str, Any]:
        """
        Forced restoration to original state（Used to clean up abnormal conditions）

        Returns:
            Recovery results
        """
        try:
            logger.debug(f"⚠️ Forced restoration to original state...")

            # 1. try to restore tomaster/mainbranch
            for branch in ["main", "master", "HEAD"]:
                success, message = self._run_git_command(["checkout", branch])
                if success:
                    logger.debug(f"✅ Force switch to branch: {branch}")
                    break

            # 2. Clean snapshot information
            self._cleanup_snapshot_info()

            # 3. Clean up possibleworktreeResidue
            if hasattr(self, "_cleanup_all_view_worktrees"):
                cleaned = self._cleanup_all_view_worktrees()
                logger.debug(f"🧹 clean upworktreeResidue: {cleaned}indivual")

            return {
                "success": True,
                "message": "Forced to restore to original state",
                "force_recovered": True,
            }

        except Exception as e:
            error_msg = f"Force recovery failed: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            return {"success": False, "message": error_msg}

    def check_snapshot_view_status(self) -> bool:
        """
        Check if you are in snapshot viewing mode

        Returns:
            Whether to be in snapshot viewing mode
        """
        status = self.get_snapshot_view_status()
        return status.get("is_snapshot_view", False) and status.get(
            "in_snapshot", False
        )

    def ensure_not_in_snapshot_view(self) -> bool:
        """
        Make sure you are not in snapshot viewing mode（If you are viewing，then restore）

        Returns:
            Whether it is successful ensures that it is not in snapshot mode
        """
        if self.check_snapshot_view_status():
            logger.debug("⚠️ Currently in snapshot viewing mode，try to restore...")
            result = self.recover_from_snapshot()
            return result.get("success", False)
        return True

    def cleanup_repository(self) -> Dict[str, Any]:
        """
        clean upGitstorehouse，Release file lock
        Returns:
            Clean results
        """
        try:
            logger.debug(f"🧹 clean upGitstorehouse: {self.project_dir}")

            # Check if it isGitstorehouse
            if not os.path.exists(self.git_dir):
                return {
                    "success": True,
                    "message": "noGitstorehouse，No need to clean up",
                    "cleaned": False,
                    "was_git_repo": False,
                }

            # 1. If you are in snapshot viewing mode，Restore first
            if self.check_snapshot_view_status():
                logger.debug("⚠️ Currently in snapshot viewing mode，try to restore...")
                recover_result = self.recover_from_snapshot()
                if not recover_result.get("success"):
                    logger.debug("⚠️ Recovery failed，Try force recovery...")
                    force_result = self.force_recover()
                    if not force_result.get("success"):
                        logger.debug(
                            "❌ Force recovery failed，But still continue to clean up"
                        )

            # 2. reset all possibleGitoperate
            operations = [
                ["reset", "--hard", "HEAD"],
                ["clean", "-fd"],
                ["gc", "--auto"],
                [
                    "config",
                    "--unset-all",
                    "core.fileMode",
                ],  # Remove possible problematic configuration
            ]

            for cmd in operations:
                try:
                    self._run_git_command(cmd)
                except:
                    pass  # Ignore failures of individual commands

            # 3. make sureGitProcess ends
            try:
                import psutil

                for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                    try:
                        cmdline = proc.info.get("cmdline", [])
                        if cmdline and "git" in cmdline[0].lower():
                            if self.git_dir in " ".join(cmdline):
                                logger.debug(
                                    f"🛑 terminationGitprocess: {proc.info['pid']}"
                                )
                                proc.terminate()
                    except:
                        pass
            except ImportError:
                logger.debug("⚠️ psutilNot installed，Unable to checkGitprocess")

            # 4. Explicitly close any file handle
            try:
                import gc

                gc.collect()
            except:
                pass

            logger.debug(f"✅ GitWarehouse cleaning completed")
            return {
                "success": True,
                "message": "GitWarehouse has been cleaned",
                "cleaned": True,
                "was_git_repo": True,
            }

        except Exception as e:
            error_msg = f"clean upGitWarehouse error: {str(e)}"
            logger.debug(f"❌ {error_msg}")
            return {"success": False, "message": error_msg, "cleaned": False}

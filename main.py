from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel, Field

import tempfile
import os
from typing import Dict
import json
import uuid
import yaml
import platformdirs
from typing import Optional
import datetime

from src.git_manager import GitManager
from src.template_loader import template_loader
from src.file_lock_manager import FileLockManager
from src.project_manager import ProjectManager


from src.utils import convert_pptx_to_pdf
from src.utils import force_delete_directory
from src.utils import logger

app = FastAPI(
    title="PPTXSlideshow editor", description="Online editingPPTXpresentation"
)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global project manager
file_locks = FileLockManager()
# Global manager instance
project_manager = ProjectManager()


class SlideUpdate(BaseModel):
    session_id: str
    current_slide: int
    shape_changes: Dict[str, Dict]  # 🎯 Change to required


@app.post("/api/save")
async def save_changes(update: SlideUpdate):
    """Save slide changes（Supports both text and table data）"""
    logger.debug(
        f"💾 Save request received - Type: {type(update.shape_changes).__name__}"
    )

    try:
        if not hasattr(update, "shape_changes") or not update.shape_changes:
            logger.debug(f"❌ No structured data provided")
            raise HTTPException(400, "Please use structured data format")

        shape_changes = update.shape_changes
        logger.debug(f"  - Total shapes to save: {len(shape_changes)}")

        project_data_obj = project_manager.get_project_by_session(update.session_id)
        if not project_data_obj:
            raise HTTPException(404, "Session does not exist")

        project_dir = project_data_obj.get("project_dir")
        if not project_dir:
            raise HTTPException(400, "No project directory")

        logger.debug(f"✅ Project directory: {project_dir}")

        file_save_success = 0
        file_save_failed = 0
        total_runs_saved = 0
        total_paragraphs_saved = 0
        total_tables_saved = 0

        for shape_id, change_data in shape_changes.items():
            try:
                logger.debug(f"🔄 Processing: {shape_id}")

                # 🎯 Analyze shapesID
                parts = shape_id.split("_")
                if not (
                    len(parts) >= 4 and parts[0] == "slide" and parts[2] == "shape"
                ):
                    logger.debug(f"⚠️ Invalid shape ID format: {shape_id}")
                    file_save_failed += 1
                    continue

                slide_idx = int(parts[1])

                # 🎯 Determine the data type and process accordingly
                success = False

                # Condition1：text data（Include'txt'Field）
                if isinstance(change_data, dict) and "txt" in change_data:
                    structured_data = change_data["txt"]
                    if isinstance(structured_data, list):
                        # statisticsruns
                        runs_count = 0
                        for para in structured_data:
                            runs_count += len(para.get("runs", []))

                        # Save text data
                        success = project_manager.save_structured_data_to_json(
                            project_dir, slide_idx, shape_id, structured_data
                        )

                        if success:
                            total_runs_saved += runs_count
                            total_paragraphs_saved += len(structured_data)
                            logger.debug(f"  - ✅ Text data saved ({runs_count} runs)")

                # 🎯 Condition2：tabular data（Include'type': 'table'）
                elif (
                    isinstance(change_data, dict)
                    and change_data.get("type") == "table"
                    and "changes" in change_data
                ):

                    # Call the table save function
                    success = project_manager.save_table_changes(
                        project_dir,
                        slide_idx,
                        shape_id,
                        change_data["changes"],
                        change_data.get("original_data", "[]"),
                    )

                    if success:
                        total_tables_saved += 1
                        logger.debug(f"  - ✅ Table data saved")

                # Condition3：other formats（jump over）
                else:
                    logger.debug(
                        f"⚠️ Unsupported data format for {shape_id}: {type(change_data)}"
                    )
                    file_save_failed += 1
                    continue

                # Update statistics
                if success:
                    file_save_success += 1
                else:
                    file_save_failed += 1

            except Exception as e:
                logger.debug(f"❌ Failed to process {shape_id}: {e}")
                file_save_failed += 1

        # Update projectYAML
        try:
            project_manager.update_project_yaml(update.session_id)
            logger.debug(f"✅ Project YAML updated")
        except Exception as e:
            logger.debug(f"⚠️ Failed to update project YAML: {e}")

        # Return statistics
        logger.debug(f"📊 Save statistics:")
        logger.debug(f"  - Success: {file_save_success}")
        logger.debug(f"  - Failed: {file_save_failed}")
        logger.debug(f"  - Paragraphs: {total_paragraphs_saved}")
        logger.debug(f"  - Runs: {total_runs_saved}")
        logger.debug(f"  - Tables: {total_tables_saved}")

        response = {
            "status": "success",
            "message": f"Saved {file_save_success} modifications",
            "stats": {
                "shapes_success": file_save_success,
                "shapes_failed": file_save_failed,
                "paragraphs_saved": total_paragraphs_saved,
                "runs_saved": total_runs_saved,
                "tables_saved": total_tables_saved,
                "data_format": "structured",
            },
        }

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"❌ Save failed: {e}")
        raise HTTPException(500, f"Save failed: {str(e)}")


@app.get("/api/get-changes/{session_id}")
async def get_saved_changes(session_id: str):
    """Get saved changes（Load from file, support both text and table data）"""
    logger.debug(f"📤 Get modifications - sessionID: {session_id}")

    changes = {}

    try:
        # Get project data from project manager
        project_data_obj = project_manager.get_project_by_session(session_id)
        if not project_data_obj:
            raise HTTPException(404, "Session does not exist")

        project_dir = project_data_obj.get("project_dir")
        if not project_dir:
            raise HTTPException(400, "No project directory")

        logger.debug(f"✅ Project directory: {project_dir}")

        # Load all changes
        changes = project_manager.fetch_changes(session_id)
        logger.debug(f"📁 Load from file to {len(changes)} Modify everywhere")

        # 🎯 new features：Load table data
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
                                # Check if there is table data
                                if (
                                    "table_data" in shape_info
                                    and shape_info["table_data"]
                                ):
                                    try:
                                        # Parse tabular data
                                        table_data = json.loads(
                                            shape_info["table_data"]
                                        )

                                        # Build tabular data structure
                                        table_structure = {
                                            "type": "table",
                                            "original_data": shape_info.get(
                                                "table_data", "[]"
                                            ),
                                            "changes": {},  # Initially empty，The front end can be populated
                                            "rows": len(table_data),
                                            "cols": (
                                                len(table_data[0])
                                                if table_data and len(table_data) > 0
                                                else 0
                                            ),
                                        }

                                        # Add table data tochangesmiddle
                                        if shape_id not in changes:
                                            changes[shape_id] = {}

                                        # Make sure the table data is formatted correctly
                                        if isinstance(changes[shape_id], dict):
                                            changes[shape_id]["table"] = table_structure
                                        else:
                                            # If it is already text data，merge
                                            changes[shape_id] = {
                                                "txt": changes[shape_id],
                                                "table": table_structure,
                                            }

                                        logger.debug(
                                            f"📊 Load table data: {shape_id} ({table_structure['rows']}x{table_structure['cols']})"
                                        )

                                    except json.JSONDecodeError as e:
                                        logger.debug(
                                            f"⚠️ Failed to parse table data for {shape_id}: {e}"
                                        )

                    except Exception as e:
                        logger.debug(f"⚠️ load {filename} fail: {e}")

        # 🎯 Replenish：Make sure all table shapes have the correct structure
        for shape_id, shape_data in changes.items():
            if isinstance(shape_data, dict) and "table" in shape_data:
                # Ensure table data is in the correct format
                table_info = shape_data["table"]
                if "type" not in table_info:
                    table_info["type"] = "table"
                if "changes" not in table_info:
                    table_info["changes"] = {}
                if "original_data" not in table_info:
                    table_info["original_data"] = "[]"

        # 🎯 new features：Merge text and tabular data
        merged_changes = {}
        for shape_id, shape_data in changes.items():
            if isinstance(shape_data, dict):
                # If there is tabular data，Build the complete structure
                if "table" in shape_data:
                    merged_changes[shape_id] = {
                        "type": "table",
                        "changes": shape_data["table"].get("changes", {}),
                        "original_data": shape_data["table"].get("original_data", "[]"),
                    }
                # If there is text data
                elif "txt" in shape_data:
                    merged_changes[shape_id] = {"txt": shape_data["txt"]}
                # Other formats remain unchanged
                else:
                    merged_changes[shape_id] = shape_data
            else:
                # Old format text data
                merged_changes[shape_id] = {"txt": shape_data}

        changes = merged_changes
        logger.debug(f"📊 After merging: {len(changes)} shapes")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Loading modifications failed: {e}")
        raise HTTPException(500, f"Loading modifications failed: {str(e)}")

    logger.debug(f"📤 return {len(changes)} Modify to session {session_id}")
    return changes


@app.get("/editor/{session_id}", response_class=HTMLResponse)
async def editor_page(session_id: str):
    """Editor page - Support snapshot viewing mode"""
    try:
        logger.debug(f"🎯 Load editor page - sessionID: {session_id}")

        # Notice：Here you need to get the query parameters from the request
        # because FastAPI Parameter acquisition method，we need to adjust

        project_data_obj = project_manager.get_project_by_session(session_id)
        if not project_data_obj:
            raise HTTPException(404, f"Session does not exist: {session_id}")

        # GetGitstate，Determine whether you are in snapshot viewing mode
        git_manager = project_manager.get_git_manager(session_id)
        if git_manager:
            snapshot_status = git_manager.get_snapshot_view_status()
            is_snapshot_view = snapshot_status.get("is_snapshot_view", False)
        else:
            is_snapshot_view = False

        # Get project information
        project_dir = project_data_obj.get("project_dir", "")
        project_data = project_data_obj.get("project_data", {})
        content_structure = project_data_obj.get("content", [])

        # make sureslidesis an array
        slides = content_structure
        if isinstance(slides, dict) and "slides" in slides:
            slides = slides["slides"]
        if not isinstance(slides, list):
            slides = []

        total_slides = len(slides)

        # loadeditor.htmlcontent
        editor_html_path = "templates/editor.html"
        with open(editor_html_path, "r", encoding="utf-8") as f:
            editor_html = f.read()

        # usebase.htmltemplate
        base_html = template_loader.load_template("base.html")
        html_content = base_html.replace("{{content}}", editor_html)

        # 🔥 key：Inject data，Contains snapshot viewing mode information
        snapshot_extra_data = {}
        if is_snapshot_view and git_manager:
            snapshot_status = git_manager.get_snapshot_view_status()
            snapshot_extra_data = {
                "is_snapshot_view": True,
                "commit_hash": snapshot_status.get("commit_hash"),
                "short_hash": snapshot_status.get("short_hash"),
                "switched_at": snapshot_status.get("switched_at"),
                "original_state": snapshot_status.get("original_state"),
                "can_exit_snapshot": True,
            }

            # Get snapshot description
            commit_hash = snapshot_status.get("commit_hash")
            if commit_hash:
                log_success, log_output = git_manager._run_git_command(
                    ["log", "--format=%s", "-n", "1", commit_hash]
                )
                if log_success:
                    snapshot_extra_data["snapshot_description"] = log_output.strip()
        data_injection = f"""
        <script type="module">
        import {{ logger }} from "/static/js/logger.js";
        // Set data
        window.editorData = {{
            slidesData: {json.dumps(slides)},
            sessionId: "{session_id}",
            totalSlides: {total_slides},
            projectInfo: {{
                session_id: "{session_id}",
                project_dir: {json.dumps(project_dir)},
                project_id: "{project_data.get('project', {}).get('id', '')}",
                project_name: "{project_data.get('project', {}).get('name', 'Unnamed')}",
                ...{json.dumps(snapshot_extra_data)}
            }}
        }};
        
        logger.debug("✅ window.editorData Already set");
        logger.debug("📊 slidesDatalength:", window.editorData.slidesData.length);
        logger.debug("📸 Snapshot viewing mode:", window.editorData.projectInfo.is_snapshot_view);
        
        // Initialize immediately（make sureeditor.jsLoaded）
        if (typeof initEditor === 'function') {{
            logger.debug("🚀 Initialize editor now");
            initEditor(
                window.editorData.slidesData,
                window.editorData.sessionId,
                window.editorData.totalSlides,
                window.editorData.projectInfo
            );
        }} else {{
            logger.debug("⏳ editor.jsnot loaded，Wait for loading to complete");
            // monitoreditor.jsload
            const checkInterval = setInterval(function() {{
                if (typeof initEditor === 'function') {{
                    clearInterval(checkInterval);
                    logger.debug("🚀 detectedinitEditor，Start initialization");
                    initEditor(
                        window.editorData.slidesData,
                        window.editorData.sessionId,
                        window.editorData.totalSlides,
                        window.editorData.projectInfo
                    );
                }}
            }}, 100);
        }}
        </script>
        """

        html_content = html_content.replace("</body>", f"{data_injection}\n</body>")

        logger.debug(f"✅ Editor page generation completed")
        return HTMLResponse(html_content)

    except Exception as e:
        logger.debug(f"❌ Failed to load editor page: {e}")
        import traceback

        traceback.print_exc()

        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Editor error</title></head>
        <body style="font-family: Arial; padding: 20px;">
            <h1>Editor failed to load</h1>
            <p>sessionID: {session_id}</p>
            <p>mistake: {str(e)}</p>
            <pre>{traceback.format_exc()}</pre>
            <a href="/">Return to homepage</a>
        </body>
        </html>
        """
        return HTMLResponse(error_html)


@app.get("/api/debug-filesystem/{session_id}")
async def debug_filesystem(session_id):
    """Debug file system status"""

    return project_manager.check_project(session_id)


@app.post("/api/create-project")
async def create_project(
    pptx_file: UploadFile = File(...),
    project_name: str = Form(...),
    # no longer needed project_dir parameter
):
    """Create new project - Use system-specific data directories"""
    try:
        logger.debug(f"🔄 Start creating a project: {project_name}")

        # 1. Determine application data directory
        user_data_dir = platformdirs.user_data_dir("PPTeXpress", "Paradoxsolver")

        # Make sure the application directory exists
        os.makedirs(user_data_dir, exist_ok=True)
        logger.debug(f"📁 application data directory: {user_data_dir}")

        # 2. Create project directory（use session_id as directory name）
        # First generate session_id
        session_id = str(uuid.uuid4())
        project_dir = os.path.join(user_data_dir, session_id)

        logger.debug(f"📁 Project directory: {project_dir}")

        # 3. Save uploadedPPTXto temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tmp:
            content = await pptx_file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # 4. Initialize project
        logger.debug(f"🔄 Initialize project...")
        try:
            results = project_manager.create_project_with_data(
                tmp_path, project_dir, project_name
            )
            logger.debug(f"✅ Project created successfully: {session_id}")

        except Exception as e:
            logger.debug(f"❌ Project creation failed: {e}")
            raise

        # 5. Clean temporary files
        os.unlink(tmp_path)
        return results

    except Exception as e:
        logger.debug(f"❌ Failed to create project: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(500, f"Failed to create project: {str(e)}")


@app.get("/api/recent-projects")
async def recent_projects():
    """List available items"""
    try:
        logger.debug("🔄 Get a list of recent projects")

        # Call the project manager to get the project list
        projects = project_manager.get_recent_projects()

        logger.debug(f"✅ Get {len(projects)} items")

        # Returns the format expected by the front end（IncludestatusField）
        return {
            "status": "success",
            "projects": projects,
            "count": len(projects),
            "message": f"turn up {len(projects)} items",
        }

    except Exception as e:
        logger.debug(f"❌ Failed to get recent items: {e}")
        import traceback

        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Failed to get project list: {str(e)}",
            "projects": [],
        }


@app.get("/", response_class=HTMLResponse)
async def home():
    """Home page"""
    logger.debug("🔄 Visit homepage")

    try:
        home_content = template_loader.load_template("home.html")
        return HTMLResponse(home_content)

    except Exception as e:
        logger.debug(f"❌ Failed to load home page: {e}")
        import traceback

        traceback.print_exc()

        # Return to simple error page
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Home page error</title></head>
        <body style="font-family: Arial; padding: 20px;">
            <h1>Home page loading error</h1>
            <p>mistake: {str(e)}</p>
        </body>
        </html>
        """
        return HTMLResponse(error_html)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Unified error handling"""
    if request.url.path.startswith("/api/"):
        # APIerror returnJSON
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "message": exc.detail},
        )
    else:
        # Page error returnHTML
        error_html = f"""
        <div style="max-width: 600px; margin: 100px auto; text-align: center;">
            <h1>mistake {exc.status_code}</h1>
            <p>{exc.detail}</p>
            <a href="/">Return to homepage</a>
        </div>
        """
        return HTMLResponse(error_html, status_code=exc.status_code)


@app.get("/new-project", response_class=HTMLResponse)
async def new_project_page():
    """New project page"""
    logger.debug("🔄 Visit the new project page")

    # try to loadnew-project.htmltemplate，Create a simple version if it does not exist
    try:
        # First check if the template exists
        template_path = "templates/new-project.html"
        with open(template_path, "r", encoding="utf-8") as f:
            new_project_html = f.read()

        # usebase.htmlTemplate packaging
        base_html = template_loader.load_template("base.html")
        html_content = base_html.replace("{{content}}", new_project_html)

        return HTMLResponse(html_content)

    except Exception as e:
        logger.debug(f"❌ Failed to load new project page: {e}")
        import traceback

        traceback.print_exc()

        # Return error page
        error_html = f"""
        <div style="padding: 20px; color: #721c24; background: #f8d7da; border: 1px solid #f5c6cb;">
            <h2>Failed to load new project page</h2>
            <p>{str(e)}</p>
            <a href="/">Return to home page</a>
        </div>
        """

        base_html = template_loader.load_template("base.html")
        html_content = base_html.replace("{{content}}", error_html)
        return HTMLResponse(html_content)


@app.get("/api/verify-session/{session_id}")
async def verify_session(session_id: str):
    """Verify session state"""
    project_data_obj = project_manager.get_project_by_session(session_id)

    if not project_data_obj:
        return {"valid": False, "error": "Session does not exist"}

    content = project_data_obj.get("content", {})
    project_data = project_data_obj.get("project_data", {})

    return {
        "valid": True,
        "session_id": session_id,
        "project_id": project_data.get("project", {}).get("id"),
        "project_name": project_data.get("project", {}).get("name"),
        "content_type": type(content).__name__,
        "is_list": isinstance(content, list),
        "list_length": len(content) if isinstance(content, list) else 0,
        "has_slides_key": isinstance(content, dict) and "slides" in content,
        "session_in_manager": session_id in project_manager.sessions,
    }


@app.get("/debug-sessions")
async def debug_all_sessions():
    """Debug all sessions"""
    # useProjectManagerdebugging method
    logger.debug("🔍 Debug all sessions...")

    sessions_info = []

    for session_id, project_id in project_manager.sessions.items():
        project = project_manager.projects.get(project_id)
        sessions_info.append(
            {
                "session_id": session_id,
                "project_id": project_id,
                "project_dir": project.get("project_dir", "N/A") if project else "N/A",
                "content_length": len(project.get("content", [])) if project else 0,
                "has_content": bool(project.get("content")) if project else False,
            }
        )

    return {
        "total_sessions": len(project_manager.sessions),
        "total_projects": len(project_manager.projects),
        "sessions": sessions_info,
    }


@app.get("/api/open-recent/{session_id}")
async def api_open_recent_project(session_id: str):
    """passsession_id（directory name）Open recent projects"""
    try:
        logger.debug(f"🔄 Open recent projects: session_id={session_id}")

        # 1. Build project directory path（session_idIt’s the directory name）
        app_data_dir = project_manager.get_app_data_dir()
        project_dir = os.path.join(app_data_dir, session_id)

        # 2. Verify directory exists
        if not os.path.exists(project_dir):
            raise HTTPException(404, f"Project directory does not exist: {session_id}")

        # 3. useopen_projectmethod
        result = project_manager.open_project(project_dir)

        if result["status"] != "success":
            raise HTTPException(400, result["message"])

        logger.debug(f"✅ The recent project was successfully opened:")
        logger.debug(f"   session_id: {result['session_id']}")
        logger.debug(f"   Project name: {result['project_info']['name']}")

        return {
            "status": "success",
            "session_id": result["session_id"],
            "project_info": result["project_info"],
            "message": f"project '{result['project_info']['name']}' Opened",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"❌ Failed to open recent project: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(500, f"Failed to open recent project: {str(e)}")


@app.delete("/api/delete-project/{session_id}")
async def api_delete_project(session_id: str):
    """Delete project"""
    try:
        logger.debug(f"🗑️ Delete project: {session_id}")

        # 🔧 New：Clean the project first，in particularGitstorehouse
        logger.debug("🧹 Start cleaning project（releaseGitfile lock）...")
        cleanup_result = project_manager.cleanup_project_for_deletion(session_id)

        if not cleanup_result.get("success", False):
            logger.debug(
                f"⚠️ Project cleanup failed，but still trying to delete: {cleanup_result.get('message')}"
            )

        # 1. Get project data（Use original logic）
        project = project_manager.get_project_by_session(session_id)

        # 🔧 Revise：If there is project data in memory，clean up firstGitManager
        if project and session_id in project_manager.git_managers:
            try:
                del project_manager.git_managers[session_id]
                logger.debug(f"🗑️ Clean up the memoryGitManager: {session_id}")
            except:
                pass

        if not project:
            # 🔧 Alternatives：If there is no memory，Try deleting the directory directly
            app_data_dir = project_manager.get_app_data_dir()
            project_dir = os.path.join(app_data_dir, session_id)

            if not os.path.exists(project_dir):
                raise HTTPException(
                    404, f"Project directory does not exist: {session_id}"
                )

            # 🔧 Revise：Try cleaning again before deleting.gitTable of contents
            git_dir = os.path.join(project_dir, ".git")
            if os.path.exists(git_dir):
                logger.debug(f"🧹 detected.gitTable of contents，try to clean...")
                try:
                    # Try usingGitManagerclean up（if possible）
                    temp_git_manager = GitManager(project_dir)
                    temp_git_manager.cleanup_repository()

                    # A short delay to allow the system to release the file lock
                    import time

                    time.sleep(0.5)
                except Exception as e:
                    logger.debug(f"⚠️ temporaryGitManagerCleanup failed: {e}")

            # Read project name
            yaml_path = os.path.join(project_dir, "project.yaml")
            if os.path.exists(yaml_path):
                with open(yaml_path, "r", encoding="utf-8") as f:
                    project_data = yaml.safe_load(f)
                project_name = project_data.get("project", {}).get(
                    "name", "Unnamed project"
                )
            else:
                project_name = session_id[:8]  # before directory name8bit as name

            # delete directory
            try:
                # 🔧 Revise：Use a more robust removal method
                force_delete_directory(project_dir)
                logger.debug(f"✅ Delete project directory: {project_dir}")
            except Exception as e:
                logger.debug(f"❌ Failed to delete directory: {e}")
                raise HTTPException(500, f"Failed to delete directory: {str(e)}")

            return {"status": "success", "message": f"project '{project_name}' Deleted"}

        # 🔧 repair：Correctly obtain the project directory and name
        project_dir = project["project_dir"]
        project_data = project.get("project_data", {})
        project_name = project_data.get("project", {}).get("name", "Unnamed project")

        logger.debug(f"📋 Delete project information:")
        logger.debug(f"   Project directory: {project_dir}")
        logger.debug(f"   Project name: {project_name}")
        logger.debug(
            f"   projectID: {project_data.get('project', {}).get('id', 'N/A')}"
        )

        # 2. Verify project directory exists
        if not os.path.exists(project_dir):
            raise HTTPException(404, "Project directory does not exist")

        # 3. Delete project directory
        try:
            # 🔧 Revise：Use new force delete method
            force_delete_directory(project_dir)
            logger.debug(f"✅ Delete project directory: {project_dir}")
        except Exception as e:
            logger.debug(f"❌ Failed to delete directory: {e}")
            raise HTTPException(500, f"Failed to delete directory: {str(e)}")

        # 4. fromProjectManagerRemove sessions and data from
        try:
            # Remove session mapping
            if session_id in project_manager.sessions:
                del project_manager.sessions[session_id]
                # logger.debug(f"✅ Remove session mapping: {session_id}")

            # Remove project data（Need to find the correspondingproject_id）
            project_id = project_data.get("project", {}).get("id")
            if project_id and project_id in project_manager.projects:
                del project_manager.projects[project_id]
                # logger.debug(f"✅ Remove project data: {project_id}")
        except Exception as e:
            logger.debug(f"⚠️ An error occurred while clearing memory data: {e}")
            # Continue execution，Does not affect directory deletion

        return {
            "status": "success",
            "message": f"project '{project_name}' Deleted",
            "project_name": project_name,
            "session_id": session_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"❌ Failed to delete item: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(500, f"Failed to delete item: {str(e)}")


@app.get("/api/project/{session_id}/images")
async def get_project_images(session_id: str):
    """Get all images in the project"""
    try:
        images_info = project_manager.list_project_images(session_id)
        return {"status": "success", "session_id": session_id, "data": images_info}
    except Exception as e:
        logger.debug(f"❌ Failed to get image list: {e}")
        return JSONResponse(
            status_code=500, content={"status": "error", "message": str(e)}
        )


@app.get("/api/project/{session_id}/image/{image_filename}")
async def get_project_image(session_id: str, image_filename: str):
    """Get a single image file in the project（Simple extension matching）"""
    try:
        project = project_manager.get_project_by_session(session_id)
        if not project:
            raise HTTPException(404, "Project does not exist")

        project_dir = project["project_dir"]
        images_dir = os.path.join(project_dir, "assets", "images")

        if not os.path.exists(images_dir):
            raise HTTPException(404, "Picture directory does not exist")

        # 🔧 simple match：Remove requested extension，matches any extension
        main_name = os.path.splitext(image_filename)[0]

        # Find matching files
        for file in os.listdir(images_dir):
            if os.path.splitext(file)[0] == main_name:
                image_path = os.path.join(images_dir, file)

                # Determine media type
                ext = os.path.splitext(file)[1].lower()
                media_types = {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".gif": "image/gif",
                    ".bmp": "image/bmp",
                }
                media_type = media_types.get(ext, "application/octet-stream")

                return FileResponse(image_path, media_type=media_type, filename=file)

        raise HTTPException(404, f"Picture does not exist: {image_filename}")

    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"❌ Failed to get image: {e}")
        raise HTTPException(500, f"Failed to get image: {str(e)}")


@app.post("/api/project/{session_id}/upload-image")
async def upload_project_image(session_id: str, file: UploadFile = File(...)):
    """Upload images to project"""
    try:
        logger.debug(f"📤 Upload images to project: {session_id}")

        # Verify file type
        allowed_types = ["image/png", "image/jpeg", "image/gif", "image/bmp"]
        if file.content_type not in allowed_types:
            raise HTTPException(400, "Only supportsPNG,JPEG,GIF,BMPformat pictures")

        # Read file contents
        image_data = await file.read()

        # Verify file size（For example5MBlimit）
        if len(image_data) > 5 * 1024 * 1024:
            raise HTTPException(400, "Image size cannot exceed5MB")

        # Upload pictures
        result = project_manager.upload_image(session_id, file.filename, image_data)

        if not result.get("success", False):
            raise HTTPException(500, result.get("error", "Upload failed"))

        return {
            "status": "success",
            "message": "Image uploaded successfully",
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"❌ Failed to upload image: {e}")
        raise HTTPException(500, f"Failed to upload image: {str(e)}")


@app.post("/api/project/{session_id}/save-image-changes")
async def save_image_changes(session_id: str, changes: dict):
    """Save image modification information"""
    try:
        logger.debug(f"💾 Save image changes: {session_id}")
        logger.debug(f"  Modify quantity: {len(changes)}")

        project_data_obj = project_manager.get_project_by_session(session_id)
        if not project_data_obj:
            raise HTTPException(404, "Session does not exist")

        project_dir = project_data_obj.get("project_dir")
        if not project_dir:
            raise HTTPException(400, "This session has no associated project directory")

        # Save image modification information to file
        images_json_path = os.path.join(project_dir, "images.json")

        # Read existing image information
        existing_data = {}
        if os.path.exists(images_json_path):
            try:
                with open(images_json_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            except:
                existing_data = {}

        # Update data
        existing_data.update(changes)

        # save to file
        with open(images_json_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)

        logger.debug(f"✅ Image modification and saving completed: {images_json_path}")

        return {
            "status": "success",
            "message": f"saved {len(changes)} Picture modification",
            "file_path": images_json_path,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"❌ Failed to save image modification: {e}")
        raise HTTPException(500, f"Failed to save image modification: {str(e)}")


@app.get("/api/project/{session_id}/get-image-changes")
async def get_image_changes(session_id: str):
    """Get the image change history of the project"""
    try:
        logger.debug(f"🔍 Get image changes: {session_id}")

        project = project_manager.get_project_by_session(session_id)
        if not project:
            raise HTTPException(404, "Project does not exist")

        project_dir = project["project_dir"]
        images_json_path = os.path.join(project_dir, "images.json")

        image_changes = {}

        if os.path.exists(images_json_path):
            try:
                with open(images_json_path, "r", encoding="utf-8") as f:
                    image_changes = json.load(f)
                logger.debug(f"✅ load {len(image_changes)} pictures changed")
            except Exception as e:
                logger.debug(f"⚠️ Failed to read image changes: {e}")
                image_changes = {}

        return {
            "status": "success",
            "session_id": session_id,
            "data": image_changes,
            "count": len(image_changes),
        }

    except Exception as e:
        logger.debug(f"❌ Failed to get image changes: {e}")
        raise HTTPException(500, f"Failed to get image changes: {str(e)}")


@app.get("/api/project/{session_id}/git/snapshots")
async def get_git_snapshots(
    session_id: str,
    limit: int = Query(10, description="Number of snapshots returned", ge=1, le=50),
):
    """
    Get the projectGitSnapshot list
    Support for snapshot viewer sessions（Return empty list）
    """
    try:
        logger.debug(
            f"📋 GetGitSnapshot list - sessionID: {session_id}, limit: {limit}"
        )

        # 🔧 Check if it is a snapshot viewer session
        project_data_obj = project_manager.get_project_by_session(session_id)
        if not project_data_obj:
            raise HTTPException(404, "Session does not exist")

        if project_data_obj.get("is_snapshot_view"):
            # Snapshot viewer is read-only，Return empty list
            logger.debug(f"📸 Snapshot viewer mode，Returns an empty snapshot list")
            return {
                "status": "success",
                "message": "No snapshot list in snapshot viewer mode",
                "data": {
                    "snapshots": [],
                    "count": 0,
                    "limit": limit,
                    "is_snapshot_view": True,
                },
            }

        # Original conventional project processing logic
        result = project_manager.list_project_snapshots(session_id, limit=limit)

        # Make sure to return a standard format
        if result.get("success"):
            return {
                "status": "success",
                "message": result.get(
                    "message", "Obtaining snapshot list successfully"
                ),
                "data": {
                    "snapshots": result.get("snapshots", []),
                    "count": result.get("count", 0),
                    "limit": limit,
                    "has_more": result.get("count", 0) >= limit,
                },
            }
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": result.get("message", "Failed to get snapshot list"),
                },
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"❌ Get snapshot listAPImistake: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(500, f"Failed to get snapshot list: {str(e)}")


class CreateSnapshotRequest(BaseModel):
    message: str = Field(
        ..., min_length=1, max_length=500, description="Snapshot description"
    )
    user: Optional[str] = Field(None, description="username")


@app.post("/api/project/{session_id}/git/create-snapshot")
async def create_git_snapshot(session_id: str, request: CreateSnapshotRequest):
    """
    Create new for projectGitSnapshot
    """
    try:
        logger.debug(f"📸 createGitSnapshot - sessionID: {session_id}")
        logger.debug(f"   information: '{request.message}'")
        logger.debug(f"   user: {request.user}")

        result = project_manager.create_project_snapshot(session_id, request.message)

        # Return different responses based on result type
        if result.get("success"):
            return {
                "status": "success",
                "message": result.get("message", "Snapshot created successfully"),
                "data": {
                    "commit_hash": result.get("commit_hash"),
                    "short_hash": result.get("short_hash"),
                    "description": result.get("description"),
                    "timestamp": datetime.datetime.now().isoformat(),
                },
            }
        elif result.get("no_changes"):
            # No change is not an error，It's a prompt message
            return {
                "status": "info",
                "message": result.get("message", "No changes need to be submitted"),
                "data": {
                    "no_changes": True,
                    "suggestion": "Please modify the file content first before creating a snapshot",
                },
            }
        elif result.get("no_message"):
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "Snapshot description cannot be empty",
                },
            )
        else:
            # Other errors
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": result.get("message", "Failed to create snapshot"),
                },
            )

    except Exception as e:
        logger.debug(f"❌ Create snapshotAPImistake: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(500, f"Failed to create snapshot: {str(e)}")


@app.get("/api/project/{session_id}/git/snapshot/{commit_hash}")
async def view_git_snapshot(
    session_id: str,
    commit_hash: str,
    preview: bool = Query(
        True, description="Whether to return only preview information"
    ),
):
    """
    View the contents of a specified snapshot（for temporary sessions）
    """
    try:
        logger.debug(
            f"👀 CheckGitSnapshot - sessionID: {session_id}, submit: {commit_hash[:8]}"
        )

        # GetGitManager
        git_manager = project_manager.get_git_manager(session_id)
        if not git_manager:
            raise HTTPException(404, "project orGitManager does not exist")

        # Get snapshot content
        result = git_manager.get_snapshot_content(commit_hash)

        if not result.get("success"):
            raise HTTPException(404, result.get("message", "Snapshot does not exist"))

        content = result.get("content")

        if preview:
            # Return to preview information
            return {
                "status": "success",
                "message": "Snapshot content obtained successfully",
                "data": {
                    "commit_hash": commit_hash,
                    "short_hash": (
                        commit_hash[:8] if len(commit_hash) >= 8 else commit_hash
                    ),
                    "content_type": type(content).__name__,
                    "has_content": bool(content),
                    "preview": True,
                    "suggestion": "Use full view mode to get detailed content",
                },
            }
        else:
            # Return to full content（Notice：may be large）
            return {
                "status": "success",
                "message": "Snapshot content obtained successfully",
                "data": {
                    "commit_hash": commit_hash,
                    "short_hash": (
                        commit_hash[:8] if len(commit_hash) >= 8 else commit_hash
                    ),
                    "content": content,
                    "size_estimate": len(str(content)) if content else 0,
                },
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"❌ View snapshotAPImistake: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(500, f"Viewing snapshot failed: {str(e)}")


class RestoreSnapshotRequest(BaseModel):
    confirm: bool = Field(True, description="Do you want to confirm the rollback?")
    backup: bool = Field(True, description="Whether to create a backup snapshot")


@app.post("/api/project/{session_id}/git/restore/{commit_hash}")
async def restore_git_snapshot(
    session_id: str, commit_hash: str, request: RestoreSnapshotRequest
):
    """
    Roll back the project to the specified snapshot
    """
    try:
        logger.debug(
            f"↩️ rollback toGitSnapshot - sessionID: {session_id}, submit: {commit_hash[:8]}"
        )
        logger.debug(f"   confirm: {request.confirm}, backup: {request.backup}")

        # security check
        if not request.confirm:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "Need to confirm rollback operation",
                    "requires_confirmation": True,
                },
            )

        # if needed，Create a backup snapshot first
        backup_result = None
        if request.backup:
            logger.debug(f"🔒 Create a pre-rollback backup snapshot...")
            backup_result = project_manager.create_project_snapshot(
                session_id, f"Backup before rollback - Target: {commit_hash[:8]}"
            )
            if backup_result.get("success"):
                logger.debug(
                    f"✅ Backup snapshot created successfully: {backup_result.get('short_hash')}"
                )
            else:
                logger.debug(
                    f"⚠️ Backup snapshot creation failed: {backup_result.get('message')}"
                )

        # perform rollback
        result = project_manager.restore_project_snapshot(session_id, commit_hash)

        if result.get("success"):
            return {
                "status": "success",
                "message": result.get("message", "Rollback successful"),
                "data": {
                    "commit_hash": commit_hash,
                    "short_hash": (
                        commit_hash[:8] if len(commit_hash) >= 8 else commit_hash
                    ),
                    "restored": True,
                    "backup_created": (
                        backup_result.get("success") if backup_result else False
                    ),
                    "backup_hash": (
                        backup_result.get("short_hash") if backup_result else None
                    ),
                    "timestamp": datetime.datetime.now().isoformat(),
                },
            }
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": result.get("message", "Rollback failed"),
                    "data": {
                        "backup_created": (
                            backup_result.get("success") if backup_result else False
                        ),
                        "backup_hash": (
                            backup_result.get("short_hash") if backup_result else None
                        ),
                    },
                },
            )

    except Exception as e:
        logger.debug(f"❌ Rollback snapshotAPImistake: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(500, f"Rollback snapshot failed: {str(e)}")


@app.get("/api/project/{session_id}/git/status")
async def get_git_status(session_id: str):
    """
    Get the projectGitstate
    Support for snapshot viewer sessions
    """
    try:
        logger.debug(f"📊 GetGitstate - sessionID: {session_id}")

        # Check if it is a snapshot viewer session
        project_data_obj = project_manager.get_project_by_session(session_id)
        if not project_data_obj:
            raise HTTPException(404, "Session does not exist")

        if project_data_obj.get("is_snapshot_view"):
            # Snapshot viewer is read-only，Return a specific status
            return {
                "status": "success",
                "message": "Snapshot viewer mode",
                "data": {
                    "is_repository": True,
                    "has_changes": False,
                    "changes": [],
                    "staged_changes": [],
                    "unstaged_changes": [],
                    "change_count": 0,
                    "staged_count": 0,
                    "unstaged_count": 0,
                    "current_branch": "snapshot_view",
                    "commit_count": 1,
                    "is_snapshot_view": True,
                    "is_readonly": True,
                    "snapshot_info": project_data_obj.get("snapshot_info", {}),
                },
            }

        # Original conventional project processing logic
        result = project_manager.get_git_status(session_id)

        if result.get("success"):
            return {
                "status": "success",
                "message": "GitStatus obtained successfully",
                "data": result,
            }
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": result.get("message", "GetGitstatus failed"),
                },
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"❌ GetGitstateAPImistake: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(500, f"GetGitstatus failed: {str(e)}")


@app.post("/api/project/{session_id}/git/init")
async def init_git_repository(
    session_id: str,
    force: bool = Query(False, description="Whether to force reinitialization"),
):
    """
    Initialize the projectGitstorehouse
    """
    try:
        logger.debug(
            f"🔧 initializationGitstorehouse - sessionID: {session_id}, force: {force}"
        )

        result = project_manager.init_project_git(session_id, force=force)

        if result.get("success"):
            return {
                "status": "success",
                "message": result.get(
                    "message", "GitWarehouse initialization successful"
                ),
                "data": {
                    "repo_exists": result.get("repo_exists", True),
                    "git_dir": result.get("git_dir"),
                    "has_initial_commit": result.get("has_initial_commit", False),
                },
            }
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": result.get(
                        "message", "GitWarehouse initialization failed"
                    ),
                },
            )

    except Exception as e:
        logger.debug(f"❌ initializationGitstorehouseAPImistake: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(500, f"initializationGitWarehouse failed: {str(e)}")


@app.get("/api/project/{session_id}/git/has-changes")
async def check_git_changes(session_id: str):
    """
    Check the project for uncommitted changes
    """
    try:
        logger.debug(f"🔍 examineGitChange - sessionID: {session_id}")

        git_manager = project_manager.get_git_manager(session_id)
        if not git_manager:
            raise HTTPException(404, "project orGitManager does not exist")

        # useGitManagerofhas_changesmethod（If implemented）
        if hasattr(git_manager, "has_changes"):
            result = git_manager.has_changes()
        else:
            # Alternatives：passstatusexamine
            status_result = git_manager.get_status()
            if status_result.get("success"):
                result = {
                    "success": True,
                    "has_changes": status_result.get("has_changes", False),
                    "change_count": status_result.get("change_count", 0),
                    "changes": status_result.get("changes", []),
                }
            else:
                result = status_result

        if result.get("success"):
            return {
                "status": "success",
                "message": result.get("message", "Check completed"),
                "data": {
                    "has_changes": result.get("has_changes", False),
                    "change_count": result.get("change_count", 0),
                    "changes": result.get("changes", [])[
                        :10
                    ],  # Only return the previous10changes
                },
            }
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": result.get("message", "Checking for changes failed"),
                },
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"❌ examineGitChangeAPImistake: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(500, f"Checking for changes failed: {str(e)}")


@app.get("/api/project/{session_id}/git/export-full")
async def export_full_project(
    session_id: str,
    include_git: bool = Query(True, description="Does it contain.gitTable of contents"),
    format: str = Query("zip", description="Packaging format", regex="^(zip|tar)$"),
):
    """
    Package download complete project（IncludeGitRepositories and binaries）
    """
    import tempfile
    import shutil

    temp_archive = None

    try:
        logger.debug(f"📦 Package download complete project - sessionID: {session_id}")
        logger.debug(f"   IncludeGit: {include_git}, Format: {format}")

        project = project_manager.get_project_by_session(session_id)
        if not project:
            raise HTTPException(404, "Project does not exist")

        project_dir = project.get("project_dir")
        if not project_dir or not os.path.exists(project_dir):
            raise HTTPException(404, "Project directory does not exist")

        # Get project information
        project_data = project.get("project_data", {})
        project_name = project_data.get("project", {}).get("name", "Unnamed project")

        # Create a temporary directory for packaging
        with tempfile.TemporaryDirectory() as temp_dir:
            # 1. Copy project to temporary directory
            temp_project_dir = os.path.join(temp_dir, "project")
            shutil.copytree(
                project_dir,
                temp_project_dir,
                ignore=shutil.ignore_patterns(".git") if not include_git else None,
            )

            # 2. Add toREADMEDocumentation
            readme_path = os.path.join(
                temp_project_dir, "README-Export instructions.txt"
            )
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(
                    f"""PPTeXpress Project export
========================

Project name: {project_name}
Export time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
sessionID: {session_id}
projectID: {project_data.get('project', {}).get('id', 'N/A')}

Contains content:
- Project configuration file (project.yaml)
- slide data (slides/*.json)
- Image citation information (images.json)
- Resource file (assets/)
- template file (template_*.pptx)
{f"- GitVersion history (.git/)" if include_git else ""}

Instructions for use:
1. Unzip this file to any directory
2. use PPTeXpress Open project
{f"3. Can be used git log View version history" if include_git else ""}

Notice: This is a complete project backup，Contains all edit history.
"""
                )

            # 3. Create compressed package
            safe_project_name = "".join(
                c for c in project_name if c.isalnum() or c in (" ", "-", "_")
            ).strip()
            if not safe_project_name:
                safe_project_name = f"project_{session_id[:8]}"

            archive_filename = f"{safe_project_name}_full_backup.{format}"
            archive_path = os.path.join(temp_dir, archive_filename)

            if format == "zip":
                import zipfile

                with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(temp_project_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, temp_project_dir)
                            zipf.write(file_path, arcname)
            else:  # tar
                import tarfile

                with tarfile.open(archive_path, "w:gz") as tarf:
                    tarf.add(
                        temp_project_dir, arcname=os.path.basename(temp_project_dir)
                    )

            # 4. Create temporary file for download
            temp_archive = tempfile.NamedTemporaryFile(
                delete=False, suffix=f".{format}"
            )
            shutil.copy2(archive_path, temp_archive.name)

            logger.debug(
                f"✅ Packaging completed: {archive_filename}, size: {os.path.getsize(temp_archive.name)} bytes"
            )

            # 5. return file
            media_type = "application/zip" if format == "zip" else "application/gzip"
            return FileResponse(
                temp_archive.name, media_type=media_type, filename=archive_filename
            )

    except Exception as e:
        logger.debug(f"❌ Package download failed: {e}")
        import traceback

        traceback.print_exc()

        # Clean temporary files
        if temp_archive and os.path.exists(temp_archive.name):
            os.unlink(temp_archive.name)

        raise HTTPException(500, f"Package download failed: {str(e)}")


@app.post("/api/project/{session_id}/git/enter-snapshot/{commit_hash}")
async def enter_snapshot_view(
    session_id: str,
    commit_hash: str,
    backup_before_switch: bool = Query(
        True, description="Whether to create a backup snapshot before switching"
    ),
):
    """
    Enter snapshot viewing mode
    use git checkout Switch to the specified commit，Enter read-only view state
    """
    try:
        logger.debug(f"👀 Enter snapshot viewing mode: {session_id}/{commit_hash[:8]}")

        # 1. Verify projects and commits
        project = project_manager.get_project_by_session(session_id)
        if not project:
            raise HTTPException(404, "Project does not exist")

        git_manager = project_manager.get_git_manager(session_id)
        if not git_manager:
            raise HTTPException(404, "GitManager does not exist")

        # 2. Check if you are already in snapshot viewing mode
        current_status = git_manager.get_snapshot_view_status()
        if current_status.get("is_snapshot_view"):
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "Already in snapshot viewing mode",
                    "data": {
                        "current_snapshot": current_status.get("commit_hash"),
                        "short_hash": current_status.get("short_hash"),
                    },
                },
            )

        # 3. if needed，Create a backup snapshot
        backup_info = None
        if backup_before_switch:
            logger.debug(f"🔒 Create a backup snapshot before switching...")
            backup_result = git_manager.create_snapshot(
                "Backup before snapshot viewing"
            )
            if backup_result.get("success"):
                backup_info = {
                    "hash": backup_result.get("commit_hash"),
                    "short_hash": backup_result.get("short_hash"),
                    "message": backup_result.get("description"),
                }
                logger.debug(
                    f"✅ Backup snapshot created successfully: {backup_info['short_hash']}"
                )
            else:
                logger.debug(
                    f"⚠️ Backup snapshot creation failed: {backup_result.get('message')}"
                )

        # 4. 🔥 core：Switch to snapshot（git checkout）
        view_result = git_manager.view_snapshot(commit_hash)

        if not view_result.get("success"):
            # Switch failed，try to restore
            error_msg = view_result.get("message", "Switching to snapshot failed")
            logger.debug(f"❌ {error_msg}")

            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": error_msg,
                    "data": {
                        "backup_created": backup_info is not None,
                        "backup_info": backup_info,
                    },
                },
            )

        logger.debug(f"✅ Successfully entered snapshot viewing mode")
        logger.debug(f"   submit: {view_result.get('short_hash')}")
        logger.debug(
            f"   describe: {view_result.get('commit_info', {}).get('message', 'unknown')}"
        )

        # 5. Reload project data（Because the file content has changed）
        logger.debug(f"🔄 Reload project data...")
        project_manager.load_project_yaml(session_id)

        # 6. Return successful response
        return {
            "status": "success",
            "message": f"Entered snapshot viewing mode: {view_result.get('short_hash')}",
            "data": {
                "commit_hash": view_result.get("commit_hash"),
                "short_hash": view_result.get("short_hash"),
                "commit_info": view_result.get("commit_info", {}),
                "is_snapshot_view": True,
                "backup_created": backup_info is not None,
                "backup_info": backup_info,
                "should_refresh": True,
                "refresh_url": f"/editor/{session_id}?mode=snapshot",
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"❌ Failed to enter snapshot view mode: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(500, f"Failed to enter snapshot view mode: {str(e)}")


@app.post("/api/project/{session_id}/git/exit-snapshot")
async def exit_snapshot_view(
    session_id: str,
    create_recovery_snapshot: bool = Query(
        True,
        description="Whether to create a snapshot to record the current status before recovery",
    ),
):
    """
    Exit snapshot viewing mode，Restore original state
    """
    try:
        logger.debug(f"🔄 Exit snapshot viewing mode: {session_id}")

        # 1. Verification project
        project = project_manager.get_project_by_session(session_id)
        if not project:
            raise HTTPException(404, "Project does not exist")

        git_manager = project_manager.get_git_manager(session_id)
        if not git_manager:
            raise HTTPException(404, "GitManager does not exist")

        # 2. Check if you are in snapshot viewing mode
        current_status = git_manager.get_snapshot_view_status()
        if not current_status.get("is_snapshot_view"):
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "Not currently in snapshot viewing mode",
                    "data": {"is_snapshot_view": False},
                },
            )

        current_snapshot = current_status.get("commit_hash", "unknown")
        logger.debug(
            f"   current snapshot: {current_status.get('short_hash', 'unknown')}"
        )

        # 3. if needed，Create a snapshot of the current state
        recovery_snapshot_info = None
        if create_recovery_snapshot:
            logger.debug(
                f"📸 Create a recovery snapshot for the current snapshot state..."
            )
            snapshot_result = git_manager.create_snapshot(
                f"Snapshot view status record: {current_status.get('short_hash', 'unknown')}"
            )
            if snapshot_result.get("success"):
                recovery_snapshot_info = {
                    "hash": snapshot_result.get("commit_hash"),
                    "short_hash": snapshot_result.get("short_hash"),
                    "message": snapshot_result.get("description"),
                }
                logger.debug(
                    f"✅ Recovery snapshot created successfully: {recovery_snapshot_info['short_hash']}"
                )

        # 4. 🔥 core：Restore original state
        recover_result = git_manager.recover_from_snapshot()

        if not recover_result.get("success"):
            error_msg = recover_result.get("message", "Recovery failed")
            logger.debug(f"❌ {error_msg}")

            # Try force recovery
            logger.debug(f"⚠️ Try force recovery...")
            force_result = git_manager.force_recover()

            if force_result.get("success"):
                error_msg = "General recovery failed，Forced recovery"
                logger.debug(f"✅ {error_msg}")
            else:
                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "error",
                        "message": f"{error_msg}，Forced recovery also failed",
                        "data": {
                            "original_state": current_status.get("original_state"),
                            "recovery_snapshot": recovery_snapshot_info,
                        },
                    },
                )

        logger.debug(f"✅ Successfully exited snapshot viewing mode")

        # 5. Reload project data（Because the file contents have been restored）
        logger.debug(f"🔄 Reload project data...")
        project_manager.load_project_yaml(session_id)

        # 6. Return successful response
        return {
            "status": "success",
            "message": "Exited snapshot viewing mode",
            "data": {
                "original_state": recover_result.get("original_state", {}),
                "recovered": True,
                "recovery_snapshot": recovery_snapshot_info,
                "current_snapshot": current_snapshot,
                "short_hash": current_status.get("short_hash"),
                "should_refresh": True,
                "refresh_url": f"/editor/{session_id}",
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"❌ Failed to exit snapshot view mode: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(500, f"Failed to exit snapshot view mode: {str(e)}")


@app.get("/api/project/{session_id}/git/snapshot-status")
async def get_snapshot_status(session_id: str):
    """
    Get the current snapshot view status
    """
    try:
        logger.debug(f"📊 Get snapshot status: {session_id}")

        project = project_manager.get_project_by_session(session_id)
        if not project:
            raise HTTPException(404, "Project does not exist")

        git_manager = project_manager.get_git_manager(session_id)
        if not git_manager:
            raise HTTPException(404, "GitManager does not exist")

        status = git_manager.get_snapshot_view_status()

        # Get more details
        details = {}
        if status.get("is_snapshot_view"):
            # Get snapshot description
            commit_hash = status.get("commit_hash")
            if commit_hash:
                log_success, log_output = git_manager._run_git_command(
                    ["log", "--format=%s", "-n", "1", commit_hash]
                )
                if log_success:
                    details["description"] = log_output.strip()

            # Get file change information
            if commit_hash:
                diff_success, diff_output = git_manager._run_git_command(
                    ["diff", "--name-only", f"{commit_hash}~1", commit_hash]
                )
                if diff_success and diff_output.strip():
                    files = [
                        f.strip() for f in diff_output.strip().split("\n") if f.strip()
                    ]
                    details["changed_files"] = files
                    details["changed_count"] = len(files)

        return {
            "status": "success",
            "message": "Snapshot status obtained successfully",
            "data": {
                **status,
                "details": details,
                "project_id": project.get("project_data", {})
                .get("project", {})
                .get("id"),
                "project_name": project.get("project_data", {})
                .get("project", {})
                .get("name"),
            },
        }

    except Exception as e:
        logger.debug(f"❌ Failed to get snapshot status: {e}")
        raise HTTPException(500, f"Failed to get snapshot status: {str(e)}")


# Add a function to clean up abnormal statusAPI
@app.post("/api/project/{session_id}/git/cleanup-snapshot-state")
async def cleanup_snapshot_state(session_id: str):
    """
    Clean snapshot view status（Used to handle exceptions）
    """
    try:
        logger.debug(f"🧹 Clean up snapshot status: {session_id}")

        project = project_manager.get_project_by_session(session_id)
        if not project:
            raise HTTPException(404, "Project does not exist")

        git_manager = project_manager.get_git_manager(session_id)
        if not git_manager:
            raise HTTPException(404, "GitManager does not exist")

        # force recovery
        result = git_manager.force_recover()

        if result.get("success"):
            return {
                "status": "success",
                "message": "Snapshot status cleared",
                "data": {"force_recovered": True, "cleaned": True},
            }
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": result.get("message", "Cleanup failed"),
                },
            )

    except Exception as e:
        logger.debug(f"❌ Failed to clear snapshot status: {e}")
        raise HTTPException(500, f"Failed to clear snapshot status: {str(e)}")


@app.get("/api/export/{session_id}")
async def export_presentation(session_id: str):
    """Export the modifiedPPTX"""
    logger.debug(f"📤 PPTXExport request - sessionID: {session_id}")

    try:
        pptx_path = project_manager.generate_modified_pptx(session_id)
        logger.debug(f"✅ PPTXExport completed: {pptx_path}")

        return FileResponse(
            pptx_path,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            filename="presentation.pptx",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"❌ Export failed: {e}")
        raise HTTPException(500, f"Export failed: {str(e)}")


@app.get("/api/export-pdf/{session_id}")
async def export_presentation_pdf(session_id: str):
    """Export the modifiedPDF"""
    logger.debug(f"📤 PDFExport request - sessionID: {session_id}")

    pptx_path = None
    pdf_temp_file = None

    try:
        # 1. generatePPTXdocument
        logger.debug("🔄 GeneratingPPTXfile...")
        pptx_path = project_manager.generate_modified_pptx(session_id)

        # 2. createPDFdocument
        pdf_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        pdf_path = pdf_temp_file.name
        pdf_temp_file.close()

        # Add a short delay to ensure file writing is complete
        import time

        time.sleep(0.5)

        # 3. ConvertPPTXarrivePDF
        logger.debug("🔄 PPTXarrivePDFConvert...")
        success = convert_pptx_to_pdf(pptx_path, pdf_path)

        if not success:
            raise Exception("Conversion failed")

        logger.debug(f"✅ PDFFinish: {pdf_path}")

        return FileResponse(
            pdf_path, media_type="application/pdf", filename="presentation.pdf"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"❌ PDFExport failed: {e}")
        import traceback

        traceback.print_exc()

        # Clean temporary files
        try:
            if pptx_path and os.path.exists(pptx_path):
                os.unlink(pptx_path)
        except:
            pass

        try:
            if (
                pdf_temp_file
                and hasattr(pdf_temp_file, "name")
                and os.path.exists(pdf_temp_file.name)
            ):
                os.unlink(pdf_temp_file.name)
        except:
            pass

        raise HTTPException(500, f"PDFExport failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

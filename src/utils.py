import os
import hashlib
import time
import stat
import shutil
import sys
import logging


def setup_logger(name="app"):
    """Create and return a configuredlogger"""
    logger = logging.getLogger(name)

    # Avoid duplicate additionshandler（important！）
    if logger.handlers:
        return logger

    log_level = "INFO"
    logger.setLevel(getattr(logging, log_level.upper()))

    # console output
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


# create defaultloggerInstance and export
logger = setup_logger("PPTeXpress")


def cleanup_temp_files(pptx_temp_file, pdf_temp_file):
    """Clean temporary files"""
    try:
        if (
            pptx_temp_file
            and hasattr(pptx_temp_file, "name")
            and os.path.exists(pptx_temp_file.name)
        ):
            os.unlink(pptx_temp_file.name)
            print(f"🗑️ Temporary deletedPPTX: {pptx_temp_file.name}")
    except Exception as e:
        print(f"⚠️ Delete temporaryPPTXfail: {e}")

    try:
        if (
            pdf_temp_file
            and hasattr(pdf_temp_file, "name")
            and os.path.exists(pdf_temp_file.name)
        ):
            os.unlink(pdf_temp_file.name)
            print(f"🗑️ Temporary deletedPDF: {pdf_temp_file.name}")
    except Exception as e:
        print(f"⚠️ Delete temporaryPDFfail: {e}")


def convert_pptx_to_pdf(pptx_path, pdf_path):
    """useAspose.SlidesConvert，Add retry mechanism"""
    max_retries = 3
    retry_delay = 1  # Second

    for attempt in range(max_retries):
        try:
            print(f"🔄 conversion attempt {attempt + 1}/{max_retries}")

            # Check if file is accessible
            if not os.path.exists(pptx_path):
                print(f"❌ PPTXFile does not exist: {pptx_path}")
                return False

            import aspose.slides as slides

            # Use different loading methods
            with slides.Presentation(pptx_path) as presentation:
                presentation.save(pdf_path, slides.export.SaveFormat.PDF)

            # Verification results
            if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                print(
                    f"✅ Conversion successful! PDFsize: {os.path.getsize(pdf_path)} byte"
                )
                return True
            else:
                print("❌ generatedPDFFile is empty")
                # if attempt < max_retries - 1:
                #    time.sleep(retry_delay)
                #    continue
                # return False

        except Exception as e:
            print(f"❌ conversion attempt {attempt + 1} fail: {e}")

            if "being used by another process" in str(e):
                print(
                    f"💡 File is occupied，wait {retry_delay} Try again in seconds..."
                )
                """
                time.sleep(retry_delay)
                """
            else:
                # Other errors are returned directly
                return False

    return False


def calculate_template_hash(template_file):
    """Calculate the hash value of the current template file"""
    try:
        if os.path.exists(template_file):
            with open(template_file, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            print(f"🔐 template hash: {file_hash[:16]}...")
            return file_hash
        return ""
    except Exception as e:
        print(f"❌ Failed to calculate template hash: {e}")
        return ""


def force_delete_directory(directory: str, max_retries: int = 3, delay: float = 0.5):
    """
    Forcefully delete a directory，including beingGitlocked file

    Args:
        directory: directory path
        max_retries: Maximum number of retries
        delay: Retry interval（Second）
    """

    def on_rm_error(func, path, exc_info):
        """Handle deletion errors"""
        # path does not exist，Return directly
        if not os.path.exists(path):
            return

        # Try changing permissions
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except:
            # if still fails，Log error but continue
            print(f"⚠️ cannot be deleted {path}: {exc_info[1]}")

    for attempt in range(max_retries):
        try:
            if not os.path.exists(directory):
                return

            # Try recursive deletion
            shutil.rmtree(directory, onerror=on_rm_error)
            print(f"✅ Delete successfully (try {attempt + 1})")
            return

        except Exception as e:
            print(f"⚠️ Delete failed，Try again {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                # One last attempt at a more radical approach
                try:
                    # try to delete.gitDirectories are handled individually
                    git_dir = os.path.join(directory, ".git")
                    if os.path.exists(git_dir):
                        print(f"🧹 Handle separately.gitTable of contents...")
                        for root, dirs, files in os.walk(git_dir, topdown=False):
                            for name in files:
                                filepath = os.path.join(root, name)
                                try:
                                    os.chmod(filepath, stat.S_IWRITE)
                                    os.unlink(filepath)
                                except:
                                    pass
                            for name in dirs:
                                dirpath = os.path.join(root, name)
                                try:
                                    os.chmod(dirpath, stat.S_IWRITE)
                                    os.rmdir(dirpath)
                                except:
                                    pass
                        try:
                            os.rmdir(git_dir)
                        except:
                            pass

                    # Finally try deleting the entire directory
                    shutil.rmtree(directory, ignore_errors=True)
                    print(f"✅ Forced deletion completed")

                except Exception as final_error:
                    raise Exception(f"Even force deletion fails: {final_error}")

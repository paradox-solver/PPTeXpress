import { logger } from "./logger.js";
// navigation.js - Page navigation tools
logger.debug("📱 navigation.js Loaded");

// Check for unsaved changes
function hasUnsavedChanges() {
    try {
        let hasChanges = false;
        
        // 🎯 method1：Check if all text shapes have been edited
        const textShapes = document.querySelectorAll('.placeholder-shape, .textbox-shape');
        
        textShapes.forEach(shapeElement => {
            const shapeId = shapeElement.id;
            
            // from RunProcessor Get currentDOMstate
            const currentStructure = window.RunProcessor.reconstructFromDOM(shapeElement);
            
            // Get original state from cache
            const cachedData = window.RunProcessor.shapeCache.get(shapeId);
            if (!cachedData || !cachedData.textData) return;
            
            // compare eachrunthe text of
            for (let p = 0; p < cachedData.textData.length; p++) {
                const originalPara = cachedData.textData[p];
                const currentPara = currentStructure[p];
                
                if (!originalPara || !currentPara) continue;
                
                for (let r = 0; r < originalPara.runs.length; r++) {
                    const originalRun = originalPara.runs[r];
                    const currentRun = currentPara.runs[r];
                    
                    if (originalRun && currentRun && originalRun.text !== currentRun.text) {
                        hasChanges = true;
                        logger.debug(`📝 Found unsaved changes: ${shapeId} p${p}r${r}`);
                        return;
                    }
                }
            }
        });
        
        logger.debug("📝 Found unsaved changes check result:", hasChanges);
        return hasChanges;
        
    } catch (error) {
        console.error("❌ Failed to check for unsaved changes:", error);
        return false;
    }
}

// RevisereturnToHomefunction
function returnToHome() {
    if (hasUnsavedChanges()) {
        const confirmed = confirm('You have unsaved edits. Are you sure you want to leave?');
        if (!confirmed) {
            return;
        }
    }
    
    logger.debug("🏠 Return to homepage");
    // Jump directly to the root path
    window.location.href = '/';
}

// RevisesaveAndReturnToHomefunction
async function saveAndReturnToHome() {
    try {
        logger.debug("💾 Try saving and returning to homepage");
        
        // If there are modifications. Save first
        if (hasUnsavedChanges()) {
            if (typeof saveChanges === 'function') {
                await saveChanges();
                logger.debug("✅ Changes saved");
            }
        }
        
        // Return to homepage
        window.location.href = '/';
    } catch (error) {
        console.error("❌ Save and return failed:", error);
        alert('Save failed. Please save manually before leaving');
    }
}

// Confirmation when uploading template
function confirmTemplateUpload() {
    // This is just a front-end check. The real checking is in the backend
    const confirmed = confirm('New PPTXtemplate will be uploaded soon.\n\nIf the template file already exists. will be replaced.\nDo you want to continue?');
    return confirmed;
}

// Export function
window.hasUnsavedChanges = hasUnsavedChanges;
window.returnToHome = returnToHome;
window.confirmTemplateUpload = confirmTemplateUpload;
window.saveAndReturnToHome = saveAndReturnToHome;

logger.debug("✅ navigation.js Loading completed");
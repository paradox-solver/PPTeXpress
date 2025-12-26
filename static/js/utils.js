import { logger } from "./logger.js";
// static/js/utils.js
logger.debug("🔧 utils.js Loaded");

// Utility function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}


// Special functions for handling combinator elements
function createGroupChildElement(childShape, parentGroup) {
    const element = document.createElement('div');
    
    // Use relative coordinates
    element.style.left = childShape.relative_left + 'px';
    element.style.top = childShape.relative_top + 'px';
    element.style.width = childShape.relative_width + 'px';
    element.style.height = childShape.relative_height + 'px';
    element.style.position = 'absolute';
    
    // Set content（reuse existingsetupShapeContentlogic）
    setupShapeContent(element, childShape, childShape.relative_width, childShape.relative_height);
    
    return element;
}

// Compute combined transformation
function calculateGroupTransform(groupShape) {
    if (!groupShape.group_bounds) {
        return { css: '' };
    }
    
    const bounds = groupShape.group_bounds;
    const currentWidth = groupShape.width;
    const currentHeight = groupShape.height;
    
    // Calculate scaling
    const scaleX = currentWidth / bounds.width;
    const scaleY = currentHeight / bounds.height;
    const scale = Math.min(scaleX, scaleY); // keep proportions
    
    // Calculate offset（center）
    const offsetX = (currentWidth - bounds.width * scale) / 2;
    const offsetY = (currentHeight - bounds.height * scale) / 2;
    
    return {
        css: `translate(${offsetX}px, ${offsetY}px) scale(${scale})`,
        scale: scale,
        offset: { x: offsetX, y: offsetY }
    };
}

function setStatus(message, type = 'info', autoHide = true) {
    const colors = {
        success: {bg: '#d4edda', color: '#155724', icon: '✅'},
        error: {bg: '#f8d7da', color: '#721c24', icon: '❌'},
        warning: {bg: '#fff3cd', color: '#856404', icon: '⚠️'},
        info: {bg: '#d1ecf1', color: '#0c5460', icon: 'ℹ️'},
        loading: {bg: '#e2e3e5', color: '#383d41', icon: '⏳'}
    };
    
    const style = colors[type] || colors.info;
    const statusEl = document.getElementById('status');
    
    // Clear previous timer
    if (window.statusTimeout) {
        clearTimeout(window.statusTimeout);
        window.statusTimeout = null;
    }
    
    // reset style
    statusEl.style.opacity = '1';
    statusEl.style.display = 'block';
    statusEl.style.transition = 'opacity 0.3s ease';
    original_background = statusEl.style.background;
    original_content = statusEl.innerHTML;

    statusEl.style.background = style.bg;
    statusEl.innerHTML = `${style.icon} ${message}`;
    
    // in the case of loading type，Does not disappear automatically
    if (autoHide && type !== 'loading') {
        window.statusTimeout = setTimeout(() => {
            statusEl.style.opacity = '0';
            // Wait for the fade-out animation to complete before restoring the default content.
            setTimeout(() => {
                // Set default content here
                statusEl.innerHTML = original_content;
                statusEl.style.background = original_background;
                statusEl.style.opacity = '1';
            }, 300);
        }, 3000);
    }
}


window.setStatus = function() { setStatus };
window.calculateGroupTransform = function() { calculateGroupTransform };
window.createGroupChildElement = function() { createGroupChildElement };

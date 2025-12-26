import { logger } from "./logger.js";
// static/js/editor.js
logger.debug("🎯 editor.js Loaded");

// global variables
let currentSlide = 1;
let slidesData = [];
let sessionId = '';
let totalSlides = 0;
let currentZoom = 100; // default100%

let imageUploader = {
    currentShapeId: null,
    isUploading: false,
    supportedTypes: ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/bmp']
};

// initialization function
function initEditor(slides, session, total, projectInfo) {
    logger.debug("🔧 initEditorcalled", { 
        slides: slides,
        session: session,
        total: total,
        project: projectInfo
    });
    
    // Data format conversion：make sureslidesis an array format
    if (slides && slides.slides && Array.isArray(slides.slides)) {
        // If a nested structure is passed in {slides: [...]}，Extract array
        slides = slides.slides;
        logger.debug("🔄 Convert nested structure to flat array");
    }
    
    // Validation parameters
    if (!slides || !Array.isArray(slides)) {
        console.error("❌ Invalidslidesdata:", slides);
        showStatus('Data format error', 'error');
        return false;
    }
    
    // Make sure everyslideAllslide_number
    slides = slides.map((slide, index) => {
        if (!slide.slide_number) {
            slide.slide_number = index + 1;
        }
        return slide;
    });
    
    // 🔧 New：Save image directory information
    window.imageAssetsPath = projectInfo.images_dir;
    window.currentSessionId = session;
    
    // 🔧 New：Initialize picture event
    initImageEvents();

    slidesData = slides;
    sessionId = session;
    totalSlides = total || slides.length;
    
    // Save project information
    window.currentProject = projectInfo;
    
    logger.debug(`📊 Data verification completed: ${totalSlides}slides`);
    logger.debug("First slide example:", slidesData[0]);
    
    // Validation parameters
    if (!slides || !Array.isArray(slides)) {
        console.error("❌ Invalidslidesdata");
        showStatus('Data format error', 'error');
        return false;
    }
    
    slidesData = slides;
    sessionId = session;
    totalSlides = total;
    
    logger.debug(`📊 Data validation: ${totalSlides}slides, ${slidesData[0]?.shapes?.length || 0}shapes`);
    
    

    // Initialization interface
    try {
        initZoomControls();
        updateZoomDisplay();
        initNavigation();
        showSlide(1);
        checkFileSystem(sessionId)

        // 🔧 New：Load image changes
        setTimeout(async () => {
            await ImageChangeManager.load(session);
            
            // Re-render the current slide to apply picture changes
            if (currentSlide) {
                logger.debug("🔄 Apply image changes to current slide...");
                showSlide(currentSlide);
            }
        }, 500);


        showStatus('✅ Editor loading completed!', 'success');
        return true;
    } catch (error) {
        console.error("❌ Initialization failed:", error);
        showStatus('❌ Initialization failed: ' + error.message, 'error');
        return false;
    }
}

function initNavigation() {
    logger.debug("📋 Initialize navigation");
    const nav = document.getElementById('slide-navigation');
    if (!nav) {
        throw new Error("Slide-navigation element not found");
    }
    
    nav.innerHTML = '';
    for (let i = 1; i <= totalSlides; i++) {
        const btn = document.createElement('button');
        btn.className = 'slide-nav-btn' + (i === 1 ? ' active' : '');
        btn.textContent = i;
        btn.onclick = () => {
            if (i === currentSlide) return;
            if (hasUnsavedChanges()) {
                const confirmed = confirm('You have unsaved edits in this page. Continue anyway?');
                if (!confirmed) {
                    return;
                }
            }
            showSlide(i);
        };
        nav.appendChild(btn);
    }
    updateSlideCounter();
    updateNavButtons();
}

function updateSlideCounter() {
    const counter = document.getElementById('slide-counter');
    if (counter) {
        counter.textContent = `Page ${currentSlide}/${totalSlides}`;
    }
}

function updateNavButtons() {
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    if (prevBtn) prevBtn.disabled = currentSlide === 1;
    if (nextBtn) nextBtn.disabled = currentSlide === totalSlides;
}

async function showSlide(slideNumber) {
    logger.debug(`🔄 switch to slideshow ${slideNumber}`);
    
    if (slideNumber < 1 || slideNumber > totalSlides) {
        console.warn(`⚠️ Invalid slide number: ${slideNumber}`);
        return;
    }
    
    currentSlide = slideNumber;
    
    // Update navigation
    document.querySelectorAll('.slide-nav-btn').forEach((btn, index) => {
        btn.classList.toggle('active', index + 1 === slideNumber);
    });
    
    updateSlideCounter();
    updateNavButtons();
    
    try {
        // 🎯 only called once！
        const originalSlideData = slidesData[slideNumber - 1];
        const slideDataWithChanges = await loadSavedChanges(originalSlideData);
        
        // Render merged data
        renderSlide(slideDataWithChanges);
        
    } catch (error) {
        console.error("❌ Failed to show slide:", error);
        // Downgrade：Render using raw data
        renderSlide(slidesData[slideNumber - 1]);
    }
}

async function showPreviousSlide() {
    if (hasUnsavedChanges()) {
        const confirmed = confirm('You have unsaved edits in this page. Continue anyway?');
        if (!confirmed) {
            return;
        }
    }
    await showSlide(currentSlide - 1);
}

async function showNextSlide() {
    if (hasUnsavedChanges()) {
        const confirmed = confirm('You have unsaved edits in this page. Continue anyway?');
        if (!confirmed) {
            return;
        }
    }
    await showSlide(currentSlide + 1);
}

async function checkFileSystem(sessionId) {
    try {
        const response = await fetch(`/api/debug-filesystem/${sessionId}`);
        const data = await response.json();
        
        const debugDiv = document.getElementById('debug-info');
        const output = document.getElementById('debug-output');
        
        if (debugDiv && output) {
            debugDiv.style.display = 'block';
            output.textContent = JSON.stringify(data, null, 2);
        }
        
        logger.debug("📁 File system status:", data);
    } catch (error) {
        console.error("❌ Checking file system failed:", error);
        alert('Checking file system failed: ' + error.message);
    }
}

function renderSlide(slideData) {
    logger.debug("🎨 Render slides:", slideData?.slide_number);
    
    const slideContent = document.getElementById('slide-content');
    if (!slideContent) return;
    
    //slideContent.innerHTML = '';
    while (slideContent.firstChild) {
        slideContent.removeChild(slideContent.firstChild);
    }
    
    if (!slideData?.shapes?.length) {
        console.warn("⚠️ No shape data");
        return;
    }
    
    // Count various types of shapes
    const shapeStats = {};
    slideData.shapes.forEach(shape => {
        const type = shape.type.toLowerCase();
        shapeStats[type] = (shapeStats[type] || 0) + 1;
    });
    
    logger.debug(`📊 shape statistics:`, shapeStats);

    // Render all shapes
    slideData.shapes.forEach((shape, index) => {
        try {
            const element = createShapeElement(shape);
            if (element) {
                slideContent.appendChild(element);
            }
        } catch (error) {
            console.error(`❌ shape ${index} Rendering failed:`, error);
        }
    });
    
    logger.debug("✅ Slide rendering completed");
}

function loadSavedChanges(slideData) {
    return new Promise(async (resolve, reject) => {
        try {
            logger.debug("🔄 Loading saved changes (structured + tables)...");
            
            const response = await fetch(`/api/get-changes/${sessionId}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const changesData = await response.json();
            logger.debug(`📊 Loaded ${Object.keys(changesData).length} shapes with changes`);
            
            // Track statistics
            let textShapesUpdated = 0;
            let tableShapesUpdated = 0;
            let mixedShapesUpdated = 0;
            let totalCellsUpdated = 0;
            
            // Process all changes
            Object.entries(changesData).forEach(([shapeId, changeData]) => {
                const shape = slideData.shapes.find(s => s.id === shapeId);
                if (!shape) {
                    // logger.debug(`⚠️ Shape not found: ${shapeId}`);
                    return;
                }
                
                // 🎯 Case 2: New structured format with 'txt' property
                if (changeData && typeof changeData === 'object' && 'txt' in changeData) {
                    if (Array.isArray(changeData.txt)) {
                        shape.text = changeData.txt;
                        shape.hasSavedChanges = true;
                        textShapesUpdated++;
                        
                        logger.debug(`✅ Applied structured text to ${shapeId}`, {
                            paragraphs: changeData.txt.length
                        });
                    }
                }
                // 🎯 Case 3: Table data
                else if (changeData && typeof changeData === 'object' && changeData.type === 'table') {
                    // Initialize table data if not exists
                    if (!shape.tableData) {
                        shape.tableData = {
                            type: 'table',
                            rows: changeData.rows || 0,
                            cols: changeData.cols || 0,
                            data: [],
                            originalData: changeData.original_data || changeData.originalData || '[]',
                            changes: changeData.changes || {}
                        };
                    }
                    
                    // Parse and apply table data
                    applyTableChangesToShape(shape, changeData);
                    shape.hasSavedChanges = true;
                    shape.isTable = true;
                    tableShapesUpdated++;
                    
                    // Count modified cells
                    if (changeData.changes) {
                        totalCellsUpdated += Object.keys(changeData.changes).length;
                    }
                    
                    logger.debug(`✅ Applied table changes to ${shapeId}`, {
                        size: `${changeData.rows || 0}x${changeData.cols || 0}`,
                        cells: Object.keys(changeData.changes || {}).length
                    });
                }
                // 🎯 Case 4: Mixed data (both text and table)
                else if (changeData && typeof changeData === 'object' && 'table' in changeData) {
                    // Apply text data if exists
                    if ('txt' in changeData && Array.isArray(changeData.txt)) {
                        shape.text = changeData.txt;
                        shape.hasSavedChanges = true;
                    }
                    
                    // Apply table data
                    if (changeData.table && changeData.table.type === 'table') {
                        if (!shape.tableData) {
                            shape.tableData = {
                                type: 'table',
                                rows: changeData.table.rows || 0,
                                cols: changeData.table.cols || 0,
                                data: [],
                                originalData: changeData.table.original_data || changeData.table.originalData || '[]',
                                changes: changeData.table.changes || {}
                            };
                        }
                        
                        applyTableChangesToShape(shape, changeData.table);
                        shape.isTable = true;
                        mixedShapesUpdated++;
                        
                        if (changeData.table.changes) {
                            totalCellsUpdated += Object.keys(changeData.table.changes).length;
                        }
                        
                        logger.debug(`✅ Applied mixed changes to ${shapeId}`, {
                            textParagraphs: changeData.txt?.length || 0,
                            tableSize: `${changeData.table.rows || 0}x${changeData.table.cols || 0}`
                        });
                    }
                }
                // 🎯 Case 1: Text data (legacy format)
                else if (changeData && Array.isArray(changeData)) {
                    // Directly replace the entire structure
                    shape.text = changeData;
                    shape.hasSavedChanges = true;
                    textShapesUpdated++;
                    
                    logger.debug(`✅ Applied text changes to ${shapeId}`, {
                        paragraphs: changeData.length,
                        runs: changeData.reduce((sum, para) => sum + (para.runs?.length || 0), 0)
                    });
                }
                // 🎯 Case 5: Unsupported format
                else {
                    logger.debug(`⏭️ Skipped unsupported change format for ${shapeId}`, {
                        dataType: typeof changeData,
                        hasTxt: changeData && 'txt' in changeData,
                        hasType: changeData && 'type' in changeData,
                        isTable: changeData && changeData.type === 'table'
                    });
                }
            });
            
            // Log statistics
            logger.debug("📊 Change application statistics:", {
                textShapes: textShapesUpdated,
                tableShapes: tableShapesUpdated,
                mixedShapes: mixedShapesUpdated,
                totalCells: totalCellsUpdated,
                totalShapes: textShapesUpdated + tableShapesUpdated + mixedShapesUpdated
            });
            
            resolve(slideData);
        } catch (error) {
            console.error("❌ Failed to load saved changes:", error);
            // Return original data on error (no reject)
            resolve(slideData);
        }
    });
}

/**
 * Apply table changes to shape
 */
function applyTableChangesToShape(shape, tableChangeData) {
    if (!shape.tableData) {
        shape.tableData = {
            type: 'table',
            rows: tableChangeData.rows || 0,
            cols: tableChangeData.cols || 0,
            data: [],
            originalData: tableChangeData.original_data || tableChangeData.originalData || '[]',
            changes: tableChangeData.changes || {}
        };
    }
    
    try {
        // Parse original data
        let tableArray = [];
        if (tableChangeData.original_data || tableChangeData.originalData) {
            const originalDataStr = tableChangeData.original_data || tableChangeData.originalData;
            try {
                tableArray = JSON.parse(originalDataStr);
            } catch (e) {
                logger.debug(`⚠️ Failed to parse original table data for ${shape.id}:`, e);
            }
        }
        
        // If we have parsed data, apply changes
        if (Array.isArray(tableArray) && tableArray.length > 0) {
            // Apply saved changes to the table data
            if (tableChangeData.changes) {
                Object.values(tableChangeData.changes).forEach(cellChange => {
                    if (cellChange && typeof cellChange === 'object' && 
                        'row' in cellChange && 'col' in cellChange) {
                        
                        const row = cellChange.row;
                        const col = cellChange.col;
                        
                        // Ensure row exists
                        if (!tableArray[row]) {
                            tableArray[row] = [];
                        }
                        // Ensure cell exists
                        if (!tableArray[row][col]) {
                            tableArray[row][col] = {};
                        }
                        
                        // Apply text change
                        if ('text' in cellChange) {
                            // Preserve original text if not already stored
                            if (!tableArray[row][col].original_text && 'original_text' in cellChange) {
                                tableArray[row][col].original_text = cellChange.original_text;
                            }
                            tableArray[row][col].text = cellChange.text;
                        }
                        
                        // Apply other properties
                        if ('font_size' in cellChange) {
                            tableArray[row][col].font_size = cellChange.font_size;
                        }
                        if ('bold' in cellChange) {
                            tableArray[row][col].bold = cellChange.bold;
                        }
                        if ('italic' in cellChange) {
                            tableArray[row][col].italic = cellChange.italic;
                        }
                    }
                });
            }
            
            // Store the updated table data
            shape.tableData.data = tableArray;
            shape.tableData.changes = tableChangeData.changes || {};
            shape.tableData.rows = tableArray.length;
            shape.tableData.cols = tableArray[0] ? tableArray[0].length : 0;
            
            logger.debug(`🔄 Table data prepared for ${shape.id}:`, {
                rows: shape.tableData.rows,
                cols: shape.tableData.cols,
                changesApplied: Object.keys(tableChangeData.changes || {}).length
            });
        } else {
            // If no original data, create empty table
            const rows = tableChangeData.rows || 3;
            const cols = tableChangeData.cols || 3;
            
            tableArray = Array.from({ length: rows }, () => 
                Array.from({ length: cols }, () => ({ text: '' }))
            );
            
            shape.tableData.data = tableArray;
            shape.tableData.rows = rows;
            shape.tableData.cols = cols;
            
            logger.debug(`📋 Created empty table for ${shape.id}: ${rows}x${cols}`);
        }
        
    } catch (error) {
        logger.error(`❌ Failed to apply table changes to ${shape.id}:`, error);
    }
}

/**
 * Helper function to check if shape has table data
 */
function shapeHasTableData(shape) {
    return shape && shape.tableData && shape.tableData.type === 'table';
}

/**
 * Merge current table changes with saved changes
 */
function mergeTableChanges(currentTableData, savedChanges) {
    if (!currentTableData || !savedChanges) {
        return currentTableData || savedChanges;
    }
    
    const merged = {
        ...currentTableData,
        changes: { ...(currentTableData.changes || {}) }
    };
    
    // Apply saved changes (saved changes take precedence)
    if (savedChanges.changes) {
        Object.entries(savedChanges.changes).forEach(([cellKey, cellChange]) => {
            merged.changes[cellKey] = cellChange;
        });
    }
    
    // Update counts
    merged.rows = savedChanges.rows || currentTableData.rows;
    merged.cols = savedChanges.cols || currentTableData.cols;
    
    return merged;
}

/**
 * Initialize table editor for shapes with table data
 */
function initializeTableEditors(slideData) {
    slideData.shapes.forEach(shape => {
        if (shapeHasTableData(shape) && shape.isTable) {
            // Ensure table editor is initialized
            if (!shape.tableEditor) {
                shape.tableEditor = {
                    isEditing: false,
                    selectedCell: null,
                    editHistory: [],
                    currentEdit: null
                };
            }
            
            logger.debug(`🔄 Table editor initialized for ${shape.id}`);
        }
    });
}



// Add scaling adjustment function（existConsoleAvailable in）
window.adjustScale = function(scaleFactor) {
    //logger.debug(`🔄 Adjust scaling factor: ${scaleFactor}`);
    // Here you can re-render the slide to apply the new zoom
    showSlide(currentSlide);
};

function createShapeElement(shape) {
    
    // Use more aggressive scaling（Adjust this value based on your testing）
    const EMU_TO_PIXELS = 96 / 914400 * 16;
    const baseScale = EMU_TO_PIXELS * 0.05; // Basic scaling
    const zoomFactor = currentZoom / 100;   // Current zoom ratio
    const scale = baseScale * zoomFactor;   // final zoom
    
    const element = document.createElement('div');
    element.id = shape.id;
    
    // Apply zoom
    const scaledLeft = Math.round(shape.left * scale);
    const scaledTop = Math.round(shape.top * scale); 
    const scaledWidth = Math.max(10, Math.round(shape.width * scale));
    const scaledHeight = Math.max(5, Math.round(shape.height * scale));
    
    element.style.left = scaledLeft + 'px';
    element.style.top = scaledTop + 'px';
    element.style.width = scaledWidth + 'px';
    element.style.height = scaledHeight + 'px';
    element.style.fontSize = '12px';
    element.style.position = 'absolute';
    element.style.boxSizing = 'border-box';
    element.style.overflow = 'hidden';
    element.style.padding = '4px';
    
    

    // Set style and content based on shape type
    setupShapeContent(element, shape, scaledWidth, scaledHeight);
    
    // if there is rotation，Apply rotation
    if (shape.rotation && shape.rotation !== 0) {
        element.style.transform = `rotate(${shape.rotation}deg)`;
        element.style.transformOrigin = 'center center';
    }
    
    return element;
}

function setupShapeContent(element, shape, width, height) {
    const type = shape.type.toLowerCase();
    
    // Call specialized rendering functions based on type
    switch(true) {
        case type.includes('picture') || shape.has_image:
            return renderPicture(element, shape, width, height);
        
        case type.includes('group') || shape.is_group:
            return renderGroup(element, shape, width, height);
        
        case type.includes('table') || shape.is_table:
            return renderTable(element, shape, width, height);
        
        case type.includes('chart') || shape.is_chart:
            return renderChart(element, shape, width, height);
        
        case type.includes('smartart'):
            return renderSmartArt(element, shape, width, height);
        
        case type.includes('placeholder'):
            return renderPlaceholder(element, shape, width, height);
        
        case type.includes('text') || type.includes('textbox'):
            return renderTextBox(element, shape, width, height);
        
        case type.includes('auto_shape') || type.includes('shape'):
            return renderAutoShape(element, shape, width, height);
        
        case type.includes('line'):
            return renderLine(element, shape, width, height);
        
        default:
            return renderUnknownShape(element, shape, width, height);
    }
}


// ============================================
// Shape rendering function library
// ============================================

function renderPicture(element, shape, width, height) {
    logger.debug(`🖼️ Render image: ${shape.id}`);
    
    element.className = 'picture-shape';
    element.contentEditable = false;
    element.style.backgroundColor = 'rgba(135, 206, 250, 0.6)';
    element.style.border = '2px dashed #17a2b8';
    
    // 🔧 Revise：Prioritize image changes
    let imageUrl = null;
    let imageAlt = shape.name || 'picture';
    let imageRef = shape.image_ref;
    
    if (imageRef) {
        // Remove extension，Let the backend match
        imageRef = imageRef.replace(/\.(jpg|jpeg|png|gif|bmp)$/i, '');
    }

    const sessionId = window.currentSessionId || sessionId;
    
    // Check if there are any image changes
    if (ImageChangeManager.loaded) {
        const change = ImageChangeManager.getChange(shape.id);
        if (change && change.image_ref) {
            // Use changed image
            imageRef = change.image_ref;
            imageUrl = `/api/project/${sessionId}/image/${change.image_ref}`;
            logger.debug(`✅ Use image changes: ${shape.id} -> ${change.image_ref}`);
        }
    }
    
    // if no changes，Use original image
    if (!imageUrl && imageRef) {
        imageUrl = `/api/project/${sessionId}/image/${imageRef}`;
    }
    
    // 🔧 Save current image reference（for subsequent operations）
    element.dataset.originalImageRef = shape.image_ref || '';
    element.dataset.currentImageRef = imageRef || '';
    
    if (imageUrl) {
        element.innerHTML = `
            <img src="${imageUrl}" 
                style="width:100%; height:100%; object-fit:contain; cursor:pointer;"
                alt="${imageAlt}"
                onerror="handleImageError(this, '${shape.id}')"
                title="Click to perform image manipulation">
        `;
    } else {
        // Show placeholder
        element.innerHTML = `
            <div style="width:100%; height:100%; display:flex; flex-direction:column; 
                        align-items:center; justify-content:center; text-align:center;
                        color:#0c5460; font-size:12px; background:#e3f2fd; cursor:pointer;"
                 title="Click to upload image">
                <div style="font-size:24px; margin-bottom:5px;">🖼️</div>
                <strong>${imageAlt}</strong>
                <small style="color:#666; margin-top:5px;">Double click or click to upload image</small>
            </div>
        `;
    }
    
    // If there are picture changes，Add tag
    if (ImageChangeManager.hasChange(shape.id)) {
        element.style.boxShadow = '0 0 0 2px #28a745'; // A green border indicates that it has been modified
        element.title += ' (Modified)';
    }
    
    element.title = `picture | ${imageAlt}`;
}

function renderGroup(element, shape, width, height) {
    logger.debug(`🧩 render combination: ${shape.id} (${shape.child_shapes?.length || 0}subshape)`);
    
    element.className = 'group-shape';
    element.style.backgroundColor = 'rgba(111, 66, 193, 0.1)';
    element.style.border = '2px dashed #6f42c1';
    element.style.overflow = 'visible';
    element.contentEditable = false;
    
    if (shape.child_shapes && shape.child_shapes.length > 0) {
        // Clear element content
        element.innerHTML = '';
        element.style.backgroundColor = 'transparent';
        
        // Render all subshapes
        shape.child_shapes.forEach((childShape, index) => {
            try {
                const childElement = createShapeElement(childShape);
                if (childElement) {
                    // Make sure child elements use absolute positioning
                    childElement.style.position = 'absolute';
                    
                    // Calculate position relative to combination
                    const childLeft = Math.round(childShape.left - shape.left);
                    const childTop = Math.round(childShape.top - shape.top);
                    
                    childElement.style.left = childLeft + 'px';
                    childElement.style.top = childTop + 'px';
                    
                    element.appendChild(childElement);
                }
            } catch (error) {
                console.error(`❌ combinator shape ${index} Rendering failed:`, error);
            }
        });
    } else {
        element.innerHTML = `
            <div style="width:100%; height:100%; display:flex; align-items:center; 
                       justify-content:center; color:#4a3c8c; font-size:12px;">
                🧩 Combined shapes
                <small>(${shape.child_shapes ? shape.child_shapes.length : 0}child)</small>
            </div>
        `;
    }
    
    element.title = `combination | ${shape.name || 'Unnamed'} | ${shape.child_shapes?.length || 0}child`;
}

function renderTable(element, shape, width, height) {
    logger.debug(`📊 Render table: ${shape.id}`);
    
    element.className = 'table-shape';
    element.style.backgroundColor = 'rgba(173, 216, 230, 0.6)';
    element.style.border = '2px solid #007bff';
    element.contentEditable = false;
    
    try {
        // 🎯 new logic：Prefer using tabular data loaded from file
        let tableData;
        let originalDataStr = '';
        
        // 1. First check if there is table data loaded from file（shape.tableData）
        if (shape.tableData && shape.tableData.type === 'table') {
            logger.debug(`📊 Using loaded table data for ${shape.id}`);
            
            // Use loaded data
            tableData = shape.tableData.data || [];
            originalDataStr = shape.tableData.originalData || '';
            
            // Mark this shape as loaded with saved changes
            shape.hasSavedChanges = true;
            
        }
        // 4. There is no data at all
        else {
            tableData = [];
            originalDataStr = '[]';
        }
        
        logger.debug(`📊 Table data prepared: ${tableData.length} rows`);
        
        // Store raw data for later saving
        element.dataset.originalTableData = originalDataStr;
        element.dataset.shapeId = shape.id;
        
        const table = document.createElement('table');
        table.style.width = '100%';
        table.style.height = '100%';
        table.style.fontSize = '10px';
        table.style.borderCollapse = 'collapse';
        table.dataset.shapeId = shape.id;
        
        // 🎯 Apply loaded changes（if there is）
        const cellChanges = shape.tableData?.changes || {};
        
        tableData.forEach((row, rowIndex) => {
            const tr = document.createElement('tr');
            tr.dataset.row = rowIndex;
            
            // Make sure rows are arrays
            if (!Array.isArray(row)) {
                row = [];
            }
            
            for (let cellIndex = 0; cellIndex < (row.length || 0); cellIndex++) {
                const td = document.createElement('td');
                td.style.border = '1px solid #999';
                td.style.padding = '2px';
                td.style.verticalAlign = 'top';
                
                const cellKey = `row${rowIndex}_col${cellIndex}`;
                td.dataset.cellId = `${shape.id}_${cellKey}`;
                td.dataset.row = rowIndex;
                td.dataset.col = cellIndex;
                td.dataset.shapeId = shape.id;
                td.dataset.cellKey = cellKey;
                
                // 🎯 Get cell content：Prioritize changes，Secondly use the original data
                let cellText = '';
                let originalText = '';
                
                // Get from raw data
                if (row[cellIndex] && typeof row[cellIndex] === 'object') {
                    cellText = row[cellIndex].text || '';
                    originalText = row[cellIndex].original_text || cellText;
                } else if (row[cellIndex] !== undefined) {
                    cellText = String(row[cellIndex]);
                    originalText = cellText;
                }
                
                // Check if there are any saved changes
                if (cellChanges[cellKey]) {
                    const savedChange = cellChanges[cellKey];
                    td.dataset.hasSavedChange = 'true';
                    td.dataset.originalText = savedChange.original_text || originalText;
                    cellText = savedChange.text || cellText;
                    
                    // Highlight modified cells
                    td.style.backgroundColor = 'rgba(144, 238, 144, 0.7)';
                } else {
                    td.dataset.originalText = originalText;
                    td.style.backgroundColor = 'rgba(255, 255, 224, 0.7)';
                }
                
                td.contentEditable = true;
                td.className = 'editable-cell';
                td.style.cursor = 'text';
                
                // 🎯 Edit event
                td.addEventListener('input', function() {
                    const currentText = this.textContent.trim();
                    const originalText = this.dataset.originalText;
                    
                    if (currentText !== originalText) {
                        this.style.backgroundColor = 'rgba(255, 165, 0, 0.7)'; // Orange means editing is in progress
                        this.dataset.isModified = 'true';
                    } else {
                        // If you change it back to the original value，Restoration
                        if (this.dataset.hasSavedChange === 'true') {
                            this.style.backgroundColor = 'rgba(144, 238, 144, 0.7)';
                        } else {
                            this.style.backgroundColor = 'rgba(255, 255, 224, 0.7)';
                        }
                        delete this.dataset.isModified;
                    }
                });
                
                td.addEventListener('blur', function() {
                    const currentText = this.textContent.trim();
                    const originalText = this.dataset.originalText;
                    
                    if (currentText !== originalText) {
                        this.style.backgroundColor = 'rgba(255, 215, 0, 0.7)'; // Gold means modified
                        this.dataset.isModified = 'true';
                    } else {
                        // Change back to original value
                        if (this.dataset.hasSavedChange === 'true') {
                            this.style.backgroundColor = 'rgba(144, 238, 144, 0.7)';
                        } else {
                            this.style.backgroundColor = 'rgba(255, 255, 224, 0.7)';
                        }
                        delete this.dataset.isModified;
                    }
                });
                
                td.textContent = cellText;
                tr.appendChild(td);
            }
            table.appendChild(tr);
        });
        
        element.innerHTML = '';
        element.appendChild(table);
        
    } catch (e) {
        logger.error(`❌ Table rendering error for ${shape.id}:`, e);
        element.innerHTML = `
            <div style="width:100%; height:100%; display:flex; align-items:center; 
                       justify-content:center; color:#721c24; background:rgba(220,53,69,0.2); 
                       font-size:12px; flex-direction: column; padding: 10px;">
                📊 Table rendering error
                <br><small>${e.message}</small>
                <br><button onclick="retryRenderTable('${shape.id}')" 
                      style="margin-top: 10px; padding: 5px 10px; background: #007bff; 
                      color: white; border: none; border-radius: 3px; cursor: pointer;">
                    Retry
                </button>
            </div>
        `;
    }
    
    element.title = `sheet | ${shape.name || 'Unnamed'} | Click cells to edit`;
}

function renderChart(element, shape, width, height) {
    logger.debug(`📈 Render chart: ${shape.id}`);
    
    element.className = 'chart-shape';
    element.style.backgroundColor = 'rgba(255, 209, 220, 0.6)';
    element.style.border = '2px solid #e91e63';
    element.style.borderRadius = '4px';
    element.contentEditable = false;
    
    const chartTitle = shape.chart_title || shape.name || 'chart';
    element.innerHTML = `
        <div style="width:100%; height:100%; display:flex; flex-direction:column; 
                   align-items:center; justify-content:center; text-align:center;
                   color:#880e4f; font-size:12px;">
            <div style="font-size:16px; margin-bottom:5px;">📈</div>
            <strong>${chartTitle}</strong>
            <small>${shape.chart_type || 'chart'}</small>
            ${shape.chart_error ? `<div style="color:red; font-size:10px;">mistake: ${shape.chart_error}</div>` : ''}
        </div>
    `;
    
    element.title = `chart | ${chartTitle} | ${shape.chart_type || 'unknown type'}`;
}

function renderSmartArt(element, shape, width, height) {
    logger.debug(`🎨 Rendering SmartArt: ${shape.id}`, {
        hasTxt: !!shape.text,
        name: shape.name
    });
    
    element.className = 'smartart-shape';
    element.style.backgroundColor = 'rgba(102, 187, 106, 0.6)';
    element.style.border = '2px solid #388e3c';
    element.style.borderRadius = '8px';
    element.contentEditable = false;
    
    // Check if there is structured text
    let textPreview = '';
    if (shape.text && Array.isArray(shape.text)) {
        // Extract text preview
        textPreview = shape.text.map(para => 
            para.runs?.map(run => run.text).join('')
        ).join(' ');
        
        // Truncate preview text
        if (textPreview.length > 50) {
            textPreview = textPreview.substring(0, 47) + '...';
        }
    }
    
    element.innerHTML = `
        <div style="width:100%; height:100%; display:flex; flex-direction:column; 
                   align-items:center; justify-content:center; text-align:center;
                   color:#1b5e20; font-size:12px; padding: 10px;">
            <div style="font-size:16px; margin-bottom:5px;">🎨</div>
            <strong>SmartArt</strong>
            <small>${shape.name || 'graphics'}</small>
            ${textPreview ? `<div style="margin-top:5px; font-size:10px; color:#2e7d32;">${textPreview}</div>` : ''}
        </div>
    `;
    
    // Update title to include structured information
    const runCount = shape.text ? shape.text.reduce((sum, para) => sum + (para.runs?.length || 0), 0) : 0;
    element.title = `SmartArt | ${shape.name || 'Unnamed'} | ` +
                   `${runCount > 0 ? `${runCount} text runs` : 'No text'}`;
}

function renderPlaceholder(element, shape, width, height) {
    element.className = 'placeholder-shape';
    
    // Use new run-based renderer
    const html = window.RunProcessor.renderFromStructure(shape);
    element.innerHTML = html;
    
    element.title = `${shape.type} | ${shape.name || 'Unnamed'}`;
}

function renderTextBox(element, shape, width, height) {
    element.className = 'textbox-shape';
    
    // Original style settings
    element.style.backgroundColor = 'rgba(224, 242, 241, 0.8)';
    element.style.border = '2px solid #00897b';
    element.style.borderRadius = '4px';
    
    // Use new run-based renderer
    const html = window.RunProcessor.renderFromStructure(shape);
    element.innerHTML = html;

    
    element.title = `text box | ${shape.name || 'Unnamed'}`;
}

function renderAutoShape(element, shape, width, height) {
    element.className = 'autoshape-shape';
    element.contentEditable = false;
    
    // Style settings
    element.style.backgroundColor = 'rgba(255, 165, 0, 0.6)';
    element.style.border = '2px solid #fd7e14';
    element.style.borderRadius = '8px';
    element.style.padding = '8px';
    
    // Only handle structured text
    if (shape.text && Array.isArray(shape.text)) {
        // Render with new processor
        try {
            const html = window.RunProcessor.renderFromStructure(shape);
            element.innerHTML = html;
        } catch (error) {
            console.error(`❌ Auto shape rendering failed: ${shape.id}`, error);
            element.innerHTML = '<div style="padding: 10px; color: #721c24;">◇ [Rendering error]</div>';
        }
    } else {
        // unstructured text：Show empty status
        element.innerHTML = `
            <div style="width:100%; height:100%; display:flex; align-items:center; 
                       justify-content:center; color:#856404; font-size:12px;">
                ◇ shape
            </div>
        `;
    }
    
    // concise title
    element.title = `Auto shape | ${shape.name || 'Unnamed'}`;
}

function renderLine(element, shape, width, height) {
    //logger.debug(`─ render lines: ${shape.id}`);
    
    element.className = 'line-shape';
    element.contentEditable = false;
    element.style.backgroundColor = 'rgba(108, 117, 125, 0.6)';
    element.style.border = 'none';
    
    element.innerHTML = `
        <div style="width:100%; height:100%; display:flex; align-items:center; 
                   justify-content:center; 
                   background:linear-gradient(to right, #6c757d, #6c757d);
                   color:white; font-size:10px;">
            ─ line ─
        </div>
    `;
    
    element.title = `line | ${shape.name || 'Unnamed'}`;
}

function renderUnknownShape(element, shape, width, height) {
    element.className = 'unknown-shape';
    element.contentEditable = false;
    
    // Style settings
    element.style.backgroundColor = 'rgba(220, 53, 69, 0.6)';
    element.style.border = '2px dashed #dc3545';
    element.style.padding = '8px';
    
    // Only handle structured text
    if (shape.text && Array.isArray(shape.text)) {
        try {
            const html = window.RunProcessor.renderFromStructure(shape);
            element.innerHTML = html;
        } catch (error) {
            console.error(`❌ Unknown shape rendering failed: ${shape.id}`, error);
            element.innerHTML = '<div style="padding: 10px; color: #721c24;">❓ [Rendering error]</div>';
        }
    } else {
        // unstructured text
        element.innerHTML = `
            <div style="width:100%; height:100%; display:flex; align-items:center; 
                       justify-content:center; color:#721c24; font-size:12px;">
                ❓ ${shape.type || 'unknown'}
            </div>
        `;
    }
    
    // concise title
    element.title = `Unknown shape [${shape.type || '?'}] | ${shape.name || 'Unnamed'}`;
}

// Image error handling function（Need to be available globally）
window.handleImageError = function(img, shapeId) {
    console.error(`❌ Image loading failed: ${shapeId}`);
    img.style.display = 'none';
    const parent = img.parentElement;
    parent.innerHTML = `
        <div style="width:100%; height:100%; display:flex; flex-direction:column; 
                   align-items:center; justify-content:center; background:#ffebee; 
                   color:#c62828; text-align:center; font-size:12px;">
            ❌ Image loading failed
            <small>${shapeId}</small>
        </div>
    `;
};


// existwindowAdd an error handling function to the object
window.handleImageError = function(img, shapeId) {
    console.error(`❌ Image loading failed: ${shapeId}`);
    img.style.display = 'none';
    const parent = img.parentElement;
    parent.innerHTML = `
        <div style="width:100%; height:100%; display:flex; align-items:center; 
                   justify-content:center; background:#ffebee; color:#c62828;">
            ❌ Image loading failed<br>
            <small>${shapeId}</small>
        </div>
    `;
};

// existwindowAdd an error handling function to the object
window.handleImageError = function(img, shapeId) {
    console.error(`❌ Image loading failed: ${shapeId}`);
    img.style.display = 'none';
    const parent = img.parentElement;
    parent.innerHTML = `
        <div style="width:100%; height:100%; display:flex; align-items:center; 
                   justify-content:center; background:#ffebee; color:#c62828;">
            ❌ Image loading failed<br>
            <small>${shapeId}</small>
        </div>
    `;
};

function showStatus(message, type = 'info') {
    const statusDiv = document.getElementById('create-status');
    if (!statusDiv) return;
    
    // Clear all existing messages
    statusDiv.innerHTML = '';
    
    // Set styles based on type
    let className = 'alert ';
    switch (type) {
        case 'success':
            className += 'alert-success';
            break;
        case 'error':
            className += 'alert-danger';
            break;
        case 'warning':
            className += 'alert-warning';
            break;
        case 'info':
            className += 'alert-info';
            break;
        default:
            className += 'alert-info';
    }
    
    // Create message element
    const messageDiv = document.createElement('div');
    messageDiv.className = className;
    messageDiv.style.cssText = `
        padding: 12px;
        margin: 10px 0;
        border-radius: 4px;
        white-space: pre-line;
    `;
    messageDiv.innerHTML = message;
    
    // Add to status area
    statusDiv.appendChild(messageDiv);
    
    // Automatically scroll to message area
    messageDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function saveChanges() {
    const changes = {};
    const shapeChanges = {}; // New: structured changes
  
    // 1. Collect all text shapes
    const textShapes = document.querySelectorAll('.placeholder-shape, .textbox-shape');
    
    textShapes.forEach(shapeElement => {
        const shapeId = shapeElement.id;
        
        // 2. Reconstruct structured data from DOM
        const reconstructedData = window.RunProcessor.reconstructFromDOM(shapeElement);
        
        // 3. Store both flat and structured versions
        changes[shapeId] = window.RunProcessor.getFlatText(shapeElement);
        shapeChanges[shapeId] = {
            txt: reconstructedData, // 🎯 Structured data
            structureType: 'run_based',
            flat_text: changes[shapeId]
        };
        
        logger.debug(`📝 Collected changes for ${shapeId}:`, {
            flatLength: changes[shapeId].length,
            structuredRuns: reconstructedData.reduce((sum, para) => sum + para.runs.length, 0)
        });
    });
    
    const tableShapes = document.querySelectorAll('.table-shape');
    tableShapes.forEach(tableElement => {
        const shapeId = tableElement.id;
        const tableChanges = extractTableChanges(tableElement);
        
        if (Object.keys(tableChanges).length > 0) {
            shapeChanges[shapeId] = {
                type: 'table',
                changes: tableChanges,
                original_data: tableElement.dataset.originalTableData || '[]'
            };
            logger.debug(`📊 Table modification: ${shapeId}`, tableChanges);
        }
    });

    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                shape_changes: shapeChanges,  // 🎯 must
                session_id: sessionId,
                current_slide: currentSlide
            })
        });
        
        if (!response.ok) {
            throw new Error(`Save failed: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showStatus('✅ ' + result.message, 'success');
            
        } else {
            showStatus('❌ ' + result.message, 'error');
        }
        
    } catch (error) {
        console.error('❌ Save failed:', error);
        showStatus('❌ Save failed: ' + error.message, 'error');
    }
}

function extractTableChanges(tableElement) {
    const changes = {};
    const cells = tableElement.querySelectorAll('td[contenteditable="true"]');
    
    cells.forEach(cell => {
        const cellId = cell.dataset.cellId;
        const originalText = cell.dataset.originalText || '';
        const currentText = cell.textContent || '';
        
        if (currentText !== originalText) {
            changes[cellId] = {
                text: currentText,
                row: parseInt(cell.dataset.row),
                col: parseInt(cell.dataset.col)
            };
        }
    });
    
    return changes;
}

function exportToPptx() {
    logger.debug("📥 ExportPPTX");
    window.open(`/api/export/${sessionId}`, '_blank');
}

function exportToPDF() {
    logger.debug("📥 ExportPDF");
    // Save changes first，then exportPDF
    saveChanges().then(() => {
        window.open(`/api/export-pdf/${sessionId}`, '_blank');
    });
}

function exportToZip() {
    logger.debug("📥 ExportZIP");
    const includeGit = confirm('Should it contain .git table of contents？');
    const params = new URLSearchParams({
        include_git: includeGit,
        format: 'zip'
    });
    
    saveChanges().then(() => {
        window.open(`/api/project/${sessionId}/git/export-full?${params}`, '_blank');
    });
}

// Also save to local storage when saving
function saveToLocalStorage(changes) {
    try {
        localStorage.setItem(`ppt-editor-${sessionId}`, JSON.stringify(changes));
        setStatus("Changes saved", 'success')
        logger.debug("💾 Modifications saved to local storage");
    } catch (error) {
        console.error("❌ Local storage failed to save:", error);
    }
}

function updateZoomDisplay() {
    const zoomInput = document.getElementById('zoom-input');
    if (zoomInput) {
        zoomInput.value = currentZoom;
    }
    logger.debug(`🔍 Current zoom: ${currentZoom}%`);
}

function applyZoom() {
    // Save current slide
    const currentSlideBeforeZoom = currentSlide;
    
    // Re-render the current slide（will use the new scaling）
    showSlide(currentSlideBeforeZoom);
    
    // Show status
    showStatus(`The zoom has been adjusted to ${currentZoom}%`, 'info');
}

function zoomIn() {
    if (currentZoom < 500) {
        currentZoom += 5;
        updateZoomDisplay();
        applyZoom();
    } else {
        showStatus('Maximum zoom ratio reached (500%)', 'error');
    }
}

function zoomOut() {
    if (currentZoom > 10) {
        currentZoom -= 5;
        updateZoomDisplay();
        applyZoom();
    } else {
        showStatus('Minimum zoom ratio reached (10%)', 'error');
    }
}

function resetZoom() {
    currentZoom = 100;
    updateZoomDisplay();
    applyZoom();
}

function handleZoomInputChange() {
    const zoomInput = document.getElementById('zoom-input');
    if (!zoomInput) return;
    
    let value = parseInt(zoomInput.value);
    
    // Validate input
    if (isNaN(value)) {
        value = 100;
    }
    
    // Limit range
    if (value < 10) value = 10;
    if (value > 500) value = 500;
    
    // Apply zoom
    currentZoom = value;
    updateZoomDisplay();
    applyZoom();
}

// Initialize zoom function
function initZoomControls() {
    const zoomInput = document.getElementById('zoom-input');
    if (zoomInput) {
        // Monitor input box changes
        zoomInput.addEventListener('change', handleZoomInputChange);
        zoomInput.addEventListener('blur', handleZoomInputChange);
        
        // Listen for keyboard events
        zoomInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                handleZoomInputChange();
            }
        });
        
        logger.debug("🔍 The zoom control has been initialized");
    }
}

// Double click event handler
function handleDoubleClick(e) {
    e.preventDefault();
    e.stopPropagation();
    
    const element = e.target.closest('.slide-content > div, [class*="shape"]');
    if (!element) {
        logger.debug('⏸️ Double click event blocked');
        return;
    }
    
    logger.debug(`⏸️ double click ${element.id}，Direct editing disabled`);
    
    // If it is a picture，Can trigger image editing
    if (element.classList.contains('picture-shape')) {
        logger.debug(`🖼️ Double click on the picture ${element.id} - Can trigger picture editing dialog box`);
    }
    
    // if it is text，Tips to use click to edit
    if (element.classList.contains('text-run') || 
        element.closest('.text-paragraph')) {
        logger.debug(`📝 Text elements should be edited using click（click textrunPop up edit box）`);
    }
};

// Helper function：passIDFind shapes（Support nested search）
function findShapeById(shapes, shapeId) {
    for (const shape of shapes) {
        if (shape.id === shapeId) return shape;
        
        // Find subshapes recursively（If it is a combination）
        if (shape.child_shapes && shape.child_shapes.length > 0) {
            const found = findShapeById(shape.child_shapes, shapeId);
            if (found) return found;
        }
    }
    return null;
}



// 🔧 New：Initialize picture related events
function initImageEvents() {
    logger.debug("🖼️ Initialize image event handler");
    
    // Listen to click events on all image elements
    document.addEventListener('click', function(e) {
        const shapeElement = e.target.closest('.picture-shape');
        if (shapeElement) {
            e.preventDefault();
            e.stopPropagation();
            
            const shapeId = shapeElement.id;
            logger.debug(`🖼️ Click on the image shape: ${shapeId}`);
            
            // Show picture operation menu
            showImageActions(shapeElement, shapeId);
        }
        
        // Click the image action button
        if (e.target.closest('.image-action-btn')) {
            const btn = e.target.closest('.image-action-btn');
            const action = btn.dataset.action;
            const shapeId = btn.dataset.shapeId;
            
            handleImageAction(action, shapeId, btn);
        }
    });
    
    // Monitor image upload related events
    initImageUploadDialog();
}

// 🔧 New：Show picture operation menu
function showImageActions(shapeElement, shapeId) {
    // Remove existing action menu
    hideImageActions();
    
    // Get picturesURL（if there is）
    const img = shapeElement.querySelector('img');
    const hasImage = img && img.src && !img.src.includes('placehold.co');
    
    // Create action menu
    const menu = document.createElement('div');
    menu.className = 'image-actions-menu';
    menu.dataset.shapeId = shapeId;
    
    menu.innerHTML = `
        <div class="image-actions-header">
            <strong>Picture manipulation</strong>
            <button class="close-menu-btn" onclick="hideImageActions()">×</button>
        </div>
        <div class="image-actions-body">
            ${hasImage ? `
                <button class="image-action-btn" data-action="view" data-shape-id="${shapeId}">
                    👁️ View large image
                </button>
                <button class="image-action-btn" data-action="replace" data-shape-id="${shapeId}">
                    🔄 Replace picture
                </button>
                <button class="image-action-btn" data-action="info" data-shape-id="${shapeId}">
                    ℹ️ Picture information
                </button>
            ` : `
                <button class="image-action-btn" data-action="upload" data-shape-id="${shapeId}">
                    📤 Upload pictures
                </button>
                <button class="image-action-btn" data-action="url" data-shape-id="${shapeId}">
                    🔗 useURL
                </button>
            `}
            <button class="image-action-btn" data-action="cancel" data-shape-id="${shapeId}">
                ❌ Cancel
            </button>
        </div>
    `;
    
    // Locate menu
    const rect = shapeElement.getBoundingClientRect();
    menu.style.position = 'fixed';
    menu.style.left = (rect.left + rect.width / 2) + 'px';
    menu.style.top = (rect.top + rect.height) + 'px';
    menu.style.transform = 'translateX(-50%)';
    menu.style.zIndex = '10000';
    
    document.body.appendChild(menu);
    
    // Click outside to close menu
    setTimeout(() => {
        document.addEventListener('click', closeMenuOnClickOutside);
    }, 100);
}

// 🔧 New：Hide picture action menu
function hideImageActions() {
    const menu = document.querySelector('.image-actions-menu');
    if (menu) {
        menu.remove();
    }
    document.removeEventListener('click', closeMenuOnClickOutside);
}

function closeMenuOnClickOutside(e) {
    const menu = document.querySelector('.image-actions-menu');
    if (menu && !menu.contains(e.target) && !e.target.closest('.picture-shape')) {
        hideImageActions();
    }
}

// 🔧 New：Process image operations
function handleImageAction(action, shapeId, btn) {
    logger.debug(`🖼️ Picture manipulation: ${action} for ${shapeId}`);
    
    hideImageActions();
    
    switch(action) {
        case 'view':
            viewImage(shapeId);
            break;
        case 'replace':
            openImageUploader(shapeId, true);
            break;
        case 'upload':
            openImageUploader(shapeId, false);
            break;
        case 'url':
            useImageUrl(shapeId);
            break;
        case 'info':
            showImageInfo(shapeId);
            break;
        case 'cancel':
            // do nothing
            break;
    }
}

// 🔧 New：Initialize image upload dialog box
function initImageUploadDialog() {
    // Create upload dialog container
    const dialogContainer = document.createElement('div');
    dialogContainer.id = 'image-upload-dialog';
    dialogContainer.style.display = 'none';
    dialogContainer.innerHTML = `
        <div class="image-upload-modal">
            <div class="modal-header">
                <h3>Upload pictures</h3>
                <button class="close-btn" onclick="closeImageUploader()">×</button>
            </div>
            <div class="modal-body">
                <div class="upload-zone" id="image-drop-zone">
                    <div class="upload-icon">📤</div>
                    <p>Drag and drop image files here，Or click to select</p>
                    <input type="file" id="image-file-input" accept="image/*" style="display: none;">
                    <button class="btn btn-primary" onclick="document.getElementById('image-file-input').click()">
                        Select file
                    </button>
                </div>
                
                
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="closeImageUploader()">Cancel</button>
                <button class="btn btn-primary" id="upload-confirm-btn" onclick="confirmImageUpload()" disabled>
                    Upload pictures
                </button>
            </div>
            <div class="progress-area" id="upload-progress" style="display: none;">
                    <div class="progress-bar">
                        <div class="progress-fill"></div>
                    </div>
                    <p>Uploading: <span id="progress-percent">0%</span></p>
                </div>
                <div class="preview-area" id="image-preview" style="display: none;">
                    <img id="preview-image" style="max-width: 100%; max-height: 300px;">
                    <div class="preview-info">
                        <p>file name: <span id="preview-filename"></span></p>
                        <p>size: <span id="preview-size"></span></p>
                    </div>
                </div>
        </div>
    `;
    
    document.body.appendChild(dialogContainer);
    
    // Monitor file selection
    document.getElementById('image-file-input')?.addEventListener('change', function(e) {
        if (this.files.length > 0) {
            handleFileSelect(this.files[0]);
        }
    });
    
    // Drag and drop support
    const dropZone = document.getElementById('image-drop-zone');
    if (dropZone) {
        dropZone.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.stopPropagation();
            this.style.backgroundColor = '#e8f4fd';
        });
        
        dropZone.addEventListener('dragleave', function(e) {
            e.preventDefault();
            e.stopPropagation();
            this.style.backgroundColor = '';
        });
        
        dropZone.addEventListener('drop', function(e) {
            e.preventDefault();
            e.stopPropagation();
            this.style.backgroundColor = '';
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileSelect(files[0]);
            }
        });
    }
}

// 🔧 New：Handle file selection
function handleFileSelect(file) {
    if (!file) return;
    
    // Verify file type
    const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/bmp'];
    if (!validTypes.includes(file.type)) {
        alert('Please select image file（PNG,JPEG,GIF,BMPFormat）');
        return;
    }
    
    // Verify file size（5MBlimit）
    if (file.size > 5 * 1024 * 1024) {
        alert('Image file size cannot exceed5MB');
        return;
    }
    
    // Show preview
    const reader = new FileReader();
    reader.onload = function(e) {
        const preview = document.getElementById('image-preview');
        const img = document.getElementById('preview-image');
        const filename = document.getElementById('preview-filename');
        const size = document.getElementById('preview-size');
        
        img.src = e.target.result;
        filename.textContent = file.name;
        size.textContent = formatFileSize(file.size);
        
        preview.style.display = 'block';
        
        // Enable upload button
        const uploadBtn = document.getElementById('upload-confirm-btn');
        uploadBtn.disabled = false;
        
        // Save file data
        window.currentImageFile = file;
    };
    
    reader.readAsDataURL(file);
}

// 🔧 New：Open image uploader
function openImageUploader(shapeId, isReplace = false) {
    imageUploader.currentShapeId = shapeId;
    imageUploader.isReplace = isReplace;
    window.currentUploadShapeId = shapeId;
    const dialog = document.getElementById('image-upload-dialog');
    if (dialog) {
        // Reset form
        document.getElementById('image-file-input').value = '';
        document.getElementById('image-preview').style.display = 'none';
        document.getElementById('upload-progress').style.display = 'none';
        document.getElementById('upload-confirm-btn').disabled = true;
        
        // Update title
        const title = dialog.querySelector('h3');
        if (title) {
            title.textContent = isReplace ? 'Replace picture' : 'Upload pictures';
        }
        
        dialog.style.display = 'block';
    }
}

// 🔧 New：Close image uploader
function closeImageUploader() {
    const dialog = document.getElementById('image-upload-dialog');
    if (dialog) {
        dialog.style.display = 'none';
        imageUploader.currentShapeId = null;
        window.currentImageFile = null;
    }
}

async function confirmImageUpload() {
    const shapeId = imageUploader.currentShapeId;
    if (!shapeId || !window.currentImageFile) return;
    
    const shapeElement = document.getElementById(shapeId);
    if (!shapeElement) return;
    
    try {
        // show progress
        document.getElementById('upload-progress').style.display = 'block';
        updateUploadProgress(0);
        
        // createFormData
        const formData = new FormData();
        formData.append('file', window.currentImageFile);
        
        // Send a request to upload an image
        const response = await fetch(`/api/project/${window.currentSessionId}/upload-image`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`Upload failed: ${response.status}`);
        }
        
        const result = await response.json();
        logger.debug('📤 Upload results:', result);
        
        if (result.status === 'success') {
            // Update picture display
            updateImageElement(shapeElement, result.data);
            
            // 🔧 New：Save image modification information to the backend
            const imageChange = {
                [shapeId]: {
                    image_ref: result.data.filename,
                    image_url: result.data.url_path,
                    uploaded_at: new Date().toISOString(),
                    original_filename: result.data.original_filename,
                    size_bytes: result.data.size_bytes
                }
            };
            
            // Save image modification information
            await saveImageChanges(imageChange);
            
            ImageChangeManager.changes[shapeId] = imageChange[shapeId];
        
            // Add to picture"Modified"mark
            shapeElement.style.boxShadow = '0 0 0 2px #28a745';
            shapeElement.title += ' (Modified)';
            // Show success message
            showStatus('✅ Image uploaded successfully', 'success');
            
            // Update upload progress
            updateUploadProgress(100);
        } else {
            throw new Error(result.message || 'Upload failed');
        }
        
    } catch (error) {
        console.error('❌ Image upload failed:', error);
        showStatus(`❌ Image upload failed: ${error.message}`, 'error');
    } finally {
        closeImageUploader();
    }
}

// 🔧 New：Save image modification information to the backend
async function saveImageChanges(imageChanges) {
    try {
        logger.debug('💾 Save image modification information:', imageChanges);
        
        const response = await fetch(`/api/project/${window.currentSessionId}/save-image-changes`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(imageChanges)
        });
        
        if (!response.ok) {
            throw new Error(`Failed to save picture information: ${response.status}`);
        }
        
        const result = await response.json();
        logger.debug('✅ Image modification information saving results:', result);
        
        return result;
        
    } catch (error) {
        console.error('❌ Failed to save image modification information:', error);
        // You can choose not to throw an error here，Because the picture has been uploaded successfully
    }
}

// 🔧 New：update externalURLSave the picture
async function saveExternalImageChange(shapeId, imageUrl) {
    try {
        const imageChange = {
            [shapeId]: {
                image_url: imageUrl,
                is_external: true,
                updated_at: new Date().toISOString()
            }
        };
        
        await saveImageChanges(imageChange);
        
    } catch (error) {
        console.error('❌ Failed to save external image information:', error);
    }
}

// 🔧 New：Update image elements
function updateImageElement(shapeElement, imageData) {
    const img = shapeElement.querySelector('img');
    if (img) {
        // Update existing image
        img.src = imageData.url_path;
        img.alt = imageData.original_filename;
    } else {
        // Create new picture
        shapeElement.innerHTML = `
            <img src="${imageData.url_path}" 
                 style="width:100%; height:100%; object-fit:contain;"
                 alt="${imageData.original_filename}"
                 onerror="handleImageError(this, '${shapeElement.id}')">
        `;
    }
    
    // Save image reference information to data attributes
    shapeElement.dataset.imageRef = imageData.filename;
    shapeElement.dataset.imageUrl = imageData.url_path;
}

// 🔧 New：View pictures
function viewImage(shapeId) {
    const shapeElement = document.getElementById(shapeId);
    if (!shapeElement) return;
    
    const img = shapeElement.querySelector('img');
    if (!img || !img.src) {
        alert('No images to view');
        return;
    }
    
    // Create an image viewer
    const viewer = document.createElement('div');
    viewer.className = 'image-viewer';
    viewer.innerHTML = `
        <div class="viewer-overlay" onclick="closeImageViewer()"></div>
        <div class="viewer-content">
            <div class="viewer-header">
                <button class="close-viewer" onclick="closeImageViewer()">×</button>
            </div>
            <div class="viewer-body">
                <img src="${img.src}" alt="Preview picture" style="max-width: 90vw; max-height: 80vh;">
            </div>
            <div class="viewer-footer">
                <p>pictureID: ${shapeId}</p>
                <button class="btn btn-secondary" onclick="downloadImage('${img.src}', '${shapeId}')">
                    💾 download
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(viewer);
}

// 🔧 New：Close image viewer
function closeImageViewer() {
    const viewer = document.querySelector('.image-viewer');
    if (viewer) {
        viewer.remove();
    }
}

// 🔧 New：Download pictures
function downloadImage(url, shapeId) {
    const a = document.createElement('a');
    a.href = url;
    a.download = `shape_${shapeId}_${Date.now()}.jpg`;
    a.click();
}

// 🔧 New：useURLLoad images
function useImageUrl(shapeId) {
    const url = prompt('Please enter a pictureURL:', 'https://placehold.co/600x400?text=Sample image');
    if (!url) return;
    
    const shapeElement = document.getElementById(shapeId);
    if (!shapeElement) return;
    
    // Update picture
    shapeElement.innerHTML = `
        <img src="${url}" 
             style="width:100%; height:100%; object-fit:contain;"
             alt="external pictures"
             onerror="handleImageError(this, '${shapeId}')">
    `;
    
    shapeElement.dataset.imageUrl = url;
    shapeElement.dataset.imageRef = 'external_url';
    
    // Save external image information
    saveExternalImageChange(shapeId, url);
    
    showStatus('✅ External image usedURL', 'success');
}

// 🔧 New：Show picture information
function showImageInfo(shapeId) {
    const shapeElement = document.getElementById(shapeId);
    if (!shapeElement) return;
    
    const img = shapeElement.querySelector('img');
    if (!img) {
        alert('No picture information');
        return;
    }
    
    const info = {
        shapeId: shapeId,
        src: img.src.substring(0, 100) + (img.src.length > 100 ? '...' : ''),
        alt: img.alt,
        width: shapeElement.style.width,
        height: shapeElement.style.height,
        imageRef: shapeElement.dataset.imageRef || 'unknown',
        imageUrl: shapeElement.dataset.imageUrl || 'unknown'
    };
    
    alert(`Picture information:\n${Object.entries(info).map(([k, v]) => `${k}: ${v}`).join('\n')}`);
}

// 🔧 New：Helper function
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function updateUploadProgress(percent) {
    const progressFill = document.querySelector('.progress-fill');
    const progressPercent = document.getElementById('progress-percent');
    
    if (progressFill) {
        progressFill.style.width = percent + '%';
    }
    if (progressPercent) {
        progressPercent.textContent = percent + '%';
    }
}


// Export functions for global use
window.initEditor = initEditor;
window.showSlide = showSlide;
window.saveChanges = saveChanges;
window.exportToPptx = exportToPptx;
window.exportToZip = exportToZip;
window.exportToPDF = exportToPDF;

window.showStatus = showStatus;

window.showPreviousSlide = showPreviousSlide;
window.showNextSlide = showNextSlide;

window.zoomIn = zoomIn;
window.zoomOut = zoomOut;
window.resetZoom = resetZoom;
window.handleZoomInputChange = handleZoomInputChange;

// Export these functions to the global（if needed）
window.renderPlaceholder = renderPlaceholder;
window.renderPicture = renderPicture;
window.renderTextBox = renderTextBox;
window.renderAutoShape = renderAutoShape;
window.renderGroup = renderGroup;
window.renderChart = renderChart;
window.renderTable = renderTable;
window.renderSmartArt = renderSmartArt;
window.renderUnknownShape = renderUnknownShape;
window.renderLine = renderLine;

logger.debug("✅ editor.js Loading completed，The function has been registered globally");


// 🔧 New：Picture change manager
const ImageChangeManager = {
    changes: {},  // shapeId -> {image_ref, ...}
    loaded: false,
    
    // Load image changes from backend
    async load(sessionId) {
        try {
            logger.debug("🔄 Load image change history...");
            const response = await fetch(`/api/project/${sessionId}/get-image-changes`);
            
            if (response.ok) {
                const result = await response.json();
                if (result.status === 'success' && result.data) {
                    this.changes = result.data;
                    this.loaded = true;
                    logger.debug(`✅ load ${Object.keys(this.changes).length} pictures changed`);
                }
            }
        } catch (error) {
            console.error("❌ Failed to load image changes:", error);
        }
    },
    
    // Get image changes of specified shape
    getChange(shapeId) {
        return this.changes[shapeId];
    },
    
    // Check if there are any image changes
    hasChange(shapeId) {
        return !!this.changes[shapeId];
    },
    
    // Get picturesURL（Use the changed image first）
    getImageUrl(shapeId, originalImageRef, sessionId) {
        const change = this.getChange(shapeId);
        
        if (change && change.image_ref) {
            // Use changed image
            const url = `/api/project/${sessionId}/image/${change.image_ref}`;
            logger.debug(`🔄 Use changed image: ${shapeId} -> ${change.image_ref}`);
            return url;
        }
        
        // Use original image
        if (originalImageRef) {
            return `/api/project/${sessionId}/image/${originalImageRef}`;
        }
        
        return null;
    }
};

// export to global
window.ImageChangeManager = ImageChangeManager;
window.closeImageViewer = closeImageViewer;
window.downloadImage = downloadImage;
window.confirmImageUpload = confirmImageUpload;
window.closeImageUploader = closeImageUploader;
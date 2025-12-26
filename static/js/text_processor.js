import { logger } from "./logger.js";
// ============================================
// run-processor.js - Direct Run-based renderer
// ============================================

logger.debug("📝 Run-based text processor loaded");

class RunBasedProcessor {
    constructor() {
        this.shapeCache = new Map(); // shapeId -> original data
        logger.debug("🎯 Run-based processor initialized");
    }
    
    // ==================== DIRECT RENDERING ====================
    
    /**
     * Direct rendering from backend structured data
     * @param {Object} shape - Shape with txt array structure
     * @returns {string} HTML string
     */
    renderFromStructure(shape) {
        const shapeId = shape.id;
        const textData = shape.text; // ✅ your unified field
        
        logger.debug(`🎨 Rendering structured data for ${shapeId}`, {
            paragraphs: textData.length,
            hasBoundary: textData[0]?.runs?.[0]?.boundary ? 'yes' : 'no'
        });
        
        // 🎯 Verification data containsboundary
        if (textData.length > 0 && textData[0].runs && textData[0].runs[0]) {
            if (!textData[0].runs[0].boundary) {
                logger.warn(`⚠️ missing databoundaryField: ${shapeId}`);
            }
        }
        
        // Store raw data（Includeboundary）
        this.shapeCache.set(shapeId, { textData, shape });
        
        // Render paragraphs
        let html = '<div class="text-frame" data-shape-id="' + shapeId + '">';
        
        textData.forEach((paragraph, paraIndex) => {
            html += this._renderParagraph(paragraph, paraIndex, shapeId);
        });
        
        html += '</div>';
        
        return html;
            
    }
    
    /**
     * Render a single paragraph
     */
    _renderParagraph(paragraph, paraIndex, shapeId) {
        if (!paragraph.runs || !Array.isArray(paragraph.runs)) {
            return '<div class="text-paragraph">[No runs]</div>';
        }
        
        let paraHtml = `<div class="text-paragraph" data-para-index="${paraIndex}">`;
        
        paragraph.runs.forEach((run, runIndex) => {
            paraHtml += this._renderRun(run, paraIndex, runIndex, shapeId);
        });
        
        paraHtml += '</div>';
        return paraHtml;
    }
    
    /**
     * Render a single text run
     */
    _renderRun(run, paraIndex, runIndex, shapeId) {
        const runId = `${shapeId}_para${paraIndex}_run${runIndex}`;
        const text = run.text || '';
        const format = run.format || {};
        
        // Generate CSS style from format
        const style = this._getRunStyle(format);
        
        // Determine if editable
        const isEditable = true; // Default to true unless explicitly false
        const editableClass = isEditable ? 'editable-run' : 'readonly-run';
        
        return `<span class="text-run ${editableClass}" data-run-id="${runId}" data-shape-id="${shapeId}" data-para-index="${paraIndex}" data-run-index="${runIndex}" style="${style}" onclick="window.RunProcessor.startEditRun(this)" title="Click to edit ${isEditable ? '(format preserved)' : '(read-only)'}">${this._escapeHtml(text)}</span>`;
    }
    
    /**
     * Generate CSS style from run format
     */
    _getRunStyle(format) {
        const styles = [];
        
        // Font styles
        if (format.bold) styles.push('font-weight: bold');
        if (format.italic) styles.push('font-style: italic');
        if (format.underline) styles.push('text-decoration: underline');
        if (format.strike) styles.push('text-decoration: line-through');
        
        // Font properties
        if (format.font) {
            const fontName = format.font.replace(/^[+-]/, ''); // Remove leading +/-
            styles.push(`font-family: '${fontName}', Arial, sans-serif`);
        }
        
        if (format.size) styles.push(`font-size: ${format.size}pt`);
        
        // Color
        if (format.color) {
            styles.push(`color: ${format.color}`);
        }
        
        // Special formatting
        if (format.superscript) {
            styles.push('vertical-align: super', 'font-size: smaller');
        } else if (format.subscript) {
            styles.push('vertical-align: sub', 'font-size: smaller');
        }
        
        return styles.join('; ');
    }
    
    /**
     * Fallback: render plain text
     */
    _renderPlainText(text, shapeId) {
        logger.warn(`⚠️ Using plain text fallback for ${shapeId}`);
        
        if (!text.trim()) {
            return '<div class="text-frame"><div class="text-paragraph">[Empty]</div></div>';
        }
        
        const paragraphs = text.split('\n');
        let html = '<div class="text-frame" data-shape-id="' + shapeId + '">';
        
        paragraphs.forEach((paraText, paraIndex) => {
            html += `<div class="text-paragraph" data-para-index="${paraIndex}">
                <span class="text-run editable-run"
                      data-run-id="${shapeId}_para${paraIndex}_run0"
                      data-shape-id="${shapeId}"
                      data-para-index="${paraIndex}"
                      data-run-index="0"
                      onclick="window.RunProcessor.startEditRun(this)">
                    ${this._escapeHtml(paraText)}
                </span>
            </div>`;
        });
        
        html += '</div>';
        return html;
    }
    
    /**
     * Escape HTML special characters
     */
    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // ==================== EDITING ====================
    
    /**
     * Start editing a run
     */
    startEditRun(runElement) {
        // Check if editable
        if (runElement.classList.contains('readonly-run')) {
            logger.debug(`⏸️ Run is read-only: ${runElement.dataset.runId}`);
            return;
        }
        
        const runId = runElement.dataset.runId;
        const currentText = runElement.textContent;
        
        logger.debug(`✏️ Start editing ${runId}`, { text: currentText });
        
        // 🎯 Restore dialog editing
        const newText = prompt('Edit text:', currentText);
        
        if (newText !== null && newText !== currentText) {
            // Update DOM
            runElement.textContent = newText;
            
            // Dispatch change event
            this._dispatchChangeEvent(runElement, newText, currentText);
            
            logger.debug(`✅ updated ${runElement.dataset.runId}: "${newText}"`);
        }
    }
    
    
    /**
     * Dispatch change event
     */
    _dispatchChangeEvent(runElement, newText, originalText) {
        const event = new CustomEvent('text-run-changed', {
            detail: {
                shapeId: runElement.dataset.shapeId,
                runId: runElement.dataset.runId,
                paraIndex: runElement.dataset.paraIndex,
                runIndex: runElement.dataset.runIndex,
                newText: newText,
                originalText: originalText,
                timestamp: new Date().toISOString()
            },
            bubbles: true
        });
        
        runElement.dispatchEvent(event);
    }
    
    // ==================== DATA EXTRACTION ====================
    
    /**
     * Reconstruct structured data from DOM
     */
    reconstructFromDOM(shapeElement) {
        const shapeId = shapeElement.id;
        const cachedData = this.shapeCache.get(shapeId);
        
        if (!cachedData || !cachedData.textData) {
            return this._reconstructFromDOMTraversal(shapeElement);
        }
        
        // Deep copy raw data（keep allmetadata）
        const reconstructed = JSON.parse(JSON.stringify(cachedData.textData));
        const paragraphs = shapeElement.querySelectorAll('.text-paragraph');
        
        paragraphs.forEach((paraElement, paraIndex) => {
            if (paraIndex < reconstructed.length) {
                const runs = paraElement.querySelectorAll('.text-run');
                const paraData = reconstructed[paraIndex];
                
                runs.forEach((runElement, runIndex) => {
                    if (runIndex < paraData.runs.length) {
                        // 🎯 critical fix：Update onlytextField，Keepboundaryandformat
                        paraData.runs[runIndex].text = runElement.textContent;
                        // boundaryandformatremain unchanged！
                    }
                });
            }
        });
        
        return reconstructed;
    }
    
    /**
     * Fallback: reconstruct from DOM traversal
     */
    _reconstructFromDOMTraversal(shapeElement) {
        const paragraphs = shapeElement.querySelectorAll('.text-paragraph');
        const result = [];
        
        paragraphs.forEach((paraElement, paraIndex) => {
            const runs = paraElement.querySelectorAll('.text-run');
            const paraData = {
                paragraph_index: paraIndex,
                runs: []
            };
            
            runs.forEach((runElement, runIndex) => {
                paraData.runs.push({
                    run_index: runIndex,
                    text: runElement.textContent,
                    // We lose format info in this fallback
                    format: {}
                });
            });
            
            result.push(paraData);
        });
        
        return result;
    }
    
    /**
     * Get flat text for compatibility
     */
    getFlatText(shapeElement) {
        const structured = this.reconstructFromDOM(shapeElement);
        return structured.map(para => 
            para.runs.map(run => run.text).join('')
        ).join('\n');
    }
    
    // ==================== DEBUG ====================
    
    /**
     * Debug shape structure
     */
    debugShape(shapeId) {
        const cached = this.shapeCache.get(shapeId);
        if (!cached) {
            logger.debug(`❌ No cached data for ${shapeId}`);
            return;
        }
        
        logger.debug(`🔍 Structure for ${shapeId}:`);
        cached.textData.forEach((para, pIdx) => {
            logger.debug(`  Paragraph ${pIdx} (${para.runs?.length || 0} runs):`);
            if (para.runs) {
                para.runs.forEach((run, rIdx) => {
                    const formatStr = Object.entries(run.format || {})
                        .filter(([k, v]) => v && typeof v !== 'object')
                        .map(([k, v]) => `${k}:${v}`)
                        .join(', ');
                    
                    logger.debug(`    Run ${rIdx}: "${run.text}"${formatStr ? ` [${formatStr}]` : ''}`);
                });
            }
        });
    }
}

// Create singleton instance
const runProcessor = new RunBasedProcessor();

// Export to global
window.RunProcessor = runProcessor;

// Add CSS styles
const styles = `
.text-run {
    cursor: text;
    border-radius: 2px;
    padding: 0 1px;
    margin: 0;
    display: inline;
    white-space: pre-wrap;
    word-break: break-word;
}

.text-run.editable-run:hover {
    background-color: rgba(0, 123, 255, 0.1);
    outline: 1px dashed rgba(0, 123, 255, 0.5);
}

.text-run.editable-run.editing-active {
    background-color: rgba(255, 193, 7, 0.2);
    outline: 2px solid #ffc107;
}

.text-run.readonly-run {
    cursor: default;
    color: #666;
    opacity: 0.9;
}

.text-run.readonly-run:hover {
    background-color: rgba(108, 117, 125, 0.1);
}

.text-paragraph {
    margin-bottom: 0.5em;
    line-height: 1.4;
    min-height: 1.2em;
}

.text-frame {
    width: 100%;
    height: 100%;
    overflow: hidden;
}

.run-edit-input {
    font-family: inherit !important;
    line-height: inherit !important;
    z-index: 10000 !important;
}
`;

// Add styles to document
if (document && document.head) {
    const styleElement = document.createElement('style');
    styleElement.textContent = styles;
    document.head.appendChild(styleElement);
}

logger.debug("✅ Run-based text processor loaded successfully");

// Test function
window.testRunProcessor = function(shapeId) {
    if (!shapeId) {
        shapeId = document.querySelector('[data-shape-id]')?.dataset.shapeId;
    }
    
    if (shapeId) {
        window.RunProcessor.debugShape(shapeId);
    } else {
        logger.debug("❌ No shape found for testing");
    }
};
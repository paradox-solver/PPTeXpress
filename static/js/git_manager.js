import { logger } from "./logger.js";
/**
 * GitVersion management module - front end
 * Handle snapshot creation, list display, rollback and other functions
 */

class GitManagerUI {
    /**
     * initializationGitManager
     * @param {string} sessionId - project sessionID
     * @param {Object} projectInfo - Project information
     */
    constructor(sessionId, projectInfo) {
        this.sessionId = sessionId;
        this.projectInfo = projectInfo || {};
        this.apiBase = `/api/project/${sessionId}/git`;
        
        // state
        this.snapshots = [];
        this.isLoading = false;
        this.lastError = null;
        
        // UIelement reference
        this.ui = {
            container: null,
            list: null,
            createBtn: null,
            status: null
        };
        
        logger.debug(`🔧 GitManagerUIinitialization: ${sessionId}`);
    }
    
    // ==================== APIcommunication ====================
    
    /**
     * callGit API
     */
    async _callApi(endpoint, method = 'GET', data = null) {
        const url = `${this.apiBase}${endpoint}`;
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin'
        };
        
        if (data && method !== 'GET') {
            options.body = JSON.stringify(data);
        }
        
        try {
            logger.debug(`🔧 callGit API: ${method} ${url}`);
            
            this.isLoading = true;
            const response = await fetch(url, options);
            const result = await response.json();
            
            this.isLoading = false;
            
            // Handle different states
            if (result.status === 'error') {
                this.lastError = result.message;
                console.error(`❌ Git APImistake: ${this.lastError}`);
                return { success: false, message: result.message };
            }
            
            logger.debug(`✅ Git APIresponse: ${result.status}`);
            return { success: true, ...result };
            
        } catch (error) {
            this.isLoading = false;
            this.lastError = error.message;
            console.error(`❌ Git APIcall failed: ${error.message}`);
            return { 
                success: false, 
                message: `network error: ${error.message}` 
            };
        }
    }
    
    // ==================== Snapshot management ====================
    
    /**
     * Get snapshot list
     */
    async getSnapshots(limit = 10) {
        try {
            const result = await this._callApi(`/snapshots?limit=${limit}`);
            
            if (result.success) {
                this.snapshots = result.data?.snapshots || [];
                logger.debug(`📋 Get ${this.snapshots.length} snapshots`);
                return {
                    success: true,
                    snapshots: this.snapshots,
                    count: result.data?.count || 0
                };
            }
            return result;
            
        } catch (error) {
            console.error(`❌ Failed to get snapshot list: ${error.message}`);
            return {
                success: false,
                message: `Failed to get snapshot list: ${error.message}`
            };
        }
    }
    
    /**
     * Create snapshot
     */
    async createSnapshot(message) {
        if (!message || message.trim() === '') {
            return {
                success: false,
                message: 'Snapshot description cannot be empty'
            };
        }
        
        try {
            const result = await this._callApi('/create-snapshot', 'POST', {
                message: message.trim()
            });
            
            // deal with"no change"special circumstances
            if (result.status === 'info' && result.data?.no_changes) {
                return {
                    success: false,
                    noChanges: true,
                    message: result.message || 'No changes need to be submitted'
                };
            }
            
            return result;
            
        } catch (error) {
            console.error(`❌ Failed to create snapshot: ${error.message}`);
            return {
                success: false,
                message: `Failed to create snapshot: ${error.message}`
            };
        }
    }
    
    /**
     * Roll back to the specified snapshot
     */
    async restoreSnapshot(commitHash, options = {}) {
        if (!commitHash) {
            return { success: false, message: 'Need to specify snapshot hash' };
        }
        
        const { confirm = true, backup = true } = options;
        
        try {
            const result = await this._callApi(`/restore/${commitHash}`, 'POST', {
                confirm: confirm,
                backup: backup
            });
            
            return result;
            
        } catch (error) {
            console.error(`❌ Rollback snapshot failed: ${error.message}`);
            return {
                success: false,
                message: `Rollback failed: ${error.message}`
            };
        }
    }
    
    /**
     * getGitstate
     */
    async getStatus() {
        try {
            return await this._callApi('/status');
        } catch (error) {
            console.error(`❌ getGitstatus failed: ${error.message}`);
            return {
                success: false,
                message: `Failed to get status: ${error.message}`
            };
        }
    }
    
    // ==================== UIrendering ====================
    
    /**
     * createGitToolbarUI
     */
    createToolbar() {
        // Create container
        const container = document.createElement('div');
        container.className = 'git-toolbar';
        container.style.cssText = `
            margin: 20px auto;
            max-width: 1200px;
            padding: 0 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        `;
        
        // title bar
        const header = document.createElement('div');
        header.style.cssText = `
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #eaeaea;
        `;
        
        const title = document.createElement('h3');
        title.textContent = '📸 Project Snapshot';
        title.style.cssText = `
            margin: 0;
            color: #333;
            font-size: 18px;
            display: flex;
            align-items: center;
            gap: 10px;
        `;
        
        const controls = document.createElement('div');
        controls.style.cssText = `
            display: flex;
            gap: 10px;
            align-items: center;
        `;
        
        // Create snapshot button
        const createBtn = document.createElement('button');
        createBtn.id = 'git-create-snapshot-btn';
        createBtn.textContent = '📸 Create a new snapshot';
        createBtn.style.cssText = `
            background: #4CAF50;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 5px;
            transition: background 0.2s;
        `;
        createBtn.addEventListener('mouseenter', () => {
            createBtn.style.background = '#45a049';
        });
        createBtn.addEventListener('mouseleave', () => {
            createBtn.style.background = '#4CAF50';
        });
        
        // refresh button
        const refreshBtn = document.createElement('button');
        refreshBtn.textContent = '🔄 Refresh';
        refreshBtn.style.cssText = `
            background: #2196F3;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 5px;
            transition: background 0.2s;
        `;
        refreshBtn.addEventListener('mouseenter', () => {
            refreshBtn.style.background = '#1976D2';
        });
        refreshBtn.addEventListener('mouseleave', () => {
            refreshBtn.style.background = '#2196F3';
        });
        
        // status indicator
        const status = document.createElement('div');
        status.id = 'git-status';
        status.style.cssText = `
            font-size: 14px;
            color: #666;
            margin-top: 10px;
            min-height: 20px;
            text-align: center;
        `;
        
        // Snapshot list container
        const listContainer = document.createElement('div');
        listContainer.id = 'git-snapshots-list-container';
        listContainer.style.cssText = `
            margin-top: 15px;
        `;
        
        // Empty status prompt
        const emptyState = document.createElement('div');
        emptyState.id = 'git-empty-state';
        emptyState.className = 'empty-state';
        emptyState.innerHTML = `
            <div style="text-align: center; padding: 40px 20px; color: #888;">
                <div style="font-size: 48px; margin-bottom: 15px;">📭</div>
                <h3 style="margin: 0 0 10px 0; color: #666;">No snapshot yet</h3>
                <p style="margin: 0;">Create the first snapshot to record the project status</p>
            </div>
        `;
        
        // Loading status
        const loadingState = document.createElement('div');
        loadingState.id = 'git-loading-state';
        loadingState.style.cssText = `
            text-align: center;
            padding: 30px;
            color: #666;
            display: none;
        `;
        loadingState.innerHTML = `
            <div style="font-size: 24px; margin-bottom: 10px;">⏳</div>
            <p>Loading snapshot...</p>
        `;
        
        // snapshot grid container
        const gridContainer = document.createElement('div');
        gridContainer.id = 'git-snapshots-grid';
        gridContainer.style.cssText = `
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 15px;
        `;
        
        // AssembleUI
        controls.appendChild(refreshBtn);
        controls.appendChild(createBtn);
        
        header.appendChild(title);
        header.appendChild(controls);
        
        listContainer.appendChild(emptyState);
        listContainer.appendChild(loadingState);
        listContainer.appendChild(gridContainer);
        
        container.appendChild(header);
        container.appendChild(status);
        container.appendChild(listContainer);
        
        // Store reference
        this.ui.container = container;
        this.ui.list = gridContainer;
        this.ui.createBtn = createBtn;
        this.ui.status = status;
        this.ui.emptyState = emptyState;
        this.ui.loadingState = loadingState;
        
        // Add event listener
        this._setupEventListeners(refreshBtn, createBtn);
        
        return container;
    }
    
    setupSnapshotViewMode() {
        if (!window.editorData?.projectInfo?.is_snapshot_view) {
            return;
        }
        
        logger.debug('🔒 Set snapshot viewing modeUI');
        
        // 1. Modify page title
        const snapshotDesc = window.editorData.projectInfo.snapshot_description || 'Snapshot view';
        document.title = `📸 ${snapshotDesc} - PPTXSnapshot viewer`;
        
        // 2. Add snapshot view prompt bar
        this._addSnapshotViewBanner();
        
        // 3. Disable editing
        this._disableEditingInSnapshotView();
        
        // 4. ReviseGittoolbar title
        this._modifyGitToolbarForSnapshotView();
    }

    _addSnapshotViewBanner() {
        const snapshotInfo = window.editorData.projectInfo;
        const banner = document.createElement('div');
        banner.id = 'snapshot-view-banner';
        banner.style.cssText = `
            position: sticky;
            top: 0;
            z-index: 1000;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 20px;
            margin: -20px -20px 20px -20px;
            border-radius: 0 0 10px 10px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        `;
        
        // Information on the left
        const infoSection = document.createElement('div');
        infoSection.style.cssText = `
            display: flex;
            align-items: center;
            gap: 15px;
        `;
        
        const icon = document.createElement('div');
        icon.textContent = '📸';
        icon.style.cssText = `
            font-size: 24px;
        `;
        
        const textSection = document.createElement('div');
        const snapshotDesc = snapshotInfo.snapshot_description || 'Snapshot view';
        const shortHash = snapshotInfo.short_hash || 'unknown';
        textSection.innerHTML = `
            <div style="font-weight: bold; font-size: 16px;">Snapshot viewing mode</div>
            <div style="font-size: 14px; opacity: 0.9; margin-top: 2px;">
                <code style="background: rgba(255, 255, 255, 0.2); padding: 2px 8px; border-radius: 10px; font-size: 12px;">
                    ${shortHash}
                </code>
                <span style="margin-left: 10px;">${snapshotDesc}</span>
            </div>
        `;
        
        infoSection.appendChild(icon);
        infoSection.appendChild(textSection);
        
        // Right operation button
        const actionSection = document.createElement('div');
        const recoverBtn = document.createElement('button');
        recoverBtn.textContent = '↩️ Revert edit';
        recoverBtn.style.cssText = `
            background: rgba(255, 255, 255, 0.9);
            color: #333;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        `;
        recoverBtn.addEventListener('mouseenter', () => {
            recoverBtn.style.transform = 'translateY(-2px)';
            recoverBtn.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.2)';
        });
        recoverBtn.addEventListener('mouseleave', () => {
            recoverBtn.style.transform = 'translateY(0)';
            recoverBtn.style.boxShadow = 'none';
        });
        recoverBtn.addEventListener('click', async () => {
            const confirmed = confirm('Are you sure you want to restore editing mode?？\n\nWill exit snapshot viewing mode，Return to the latest status of the current project.');
            if (confirmed) {
                await this.exitSnapshotView();
            }
        });
        
        actionSection.appendChild(recoverBtn);
        
        banner.appendChild(infoSection);
        banner.appendChild(actionSection);
        
        // Insert intoGitbefore toolbar
        const gitSection = document.getElementById('git-snapshots-section');
        if (gitSection && gitSection.parentNode) {
            gitSection.parentNode.insertBefore(banner, gitSection);
        } else {
            document.body.insertBefore(banner, document.body.firstChild);
        }
    }

    _disableEditingInSnapshotView() {
        // Add toCSSRule disabled editing
        const style = document.createElement('style');
        style.id = 'snapshot-view-css';
        style.textContent = `
            /* Disable all text input */
            .slide-editor input,
            .slide-editor textarea,
            .slide-editor [contenteditable="true"] {
                pointer-events: none !important;
                opacity: 0.7 !important;
                cursor: not-allowed !important;
                background-color: #f8f9fa !important;
                border-color: #dee2e6 !important;
            }
            
            /* Hide editing buttons such as save and export */
            .controls button:not(#snapshot-recover-btn):not(.snapshot-control-btn) {
                display: none !important;
            }
            
            /* Hide image upload area */
            .image-upload-area {
                display: none !important;
            }
            
            /* Prompt text */
            .slide-editor .text-editable::after {
                content: "（read-only mode）";
                font-size: 12px;
                color: #999;
                margin-left: 5px;
            }
        `;
        document.head.appendChild(style);
    }
    
    /**
     * ReviseGittoolbar title
     */
    _modifyGitToolbarForSnapshotView() {
        const toolbarTitle = document.querySelector('.git-toolbar h3');
        if (toolbarTitle) {
            toolbarTitle.textContent = '📸 Snapshot history（read-only mode）';
        }
    }

    /**
     * Set event listener
     */
    _setupEventListeners(toggleBtn, refreshBtn, createBtn) {
        // Toggle display/hide
        let isExpanded = true;
        toggleBtn.addEventListener('click', () => {
            const content = document.getElementById('git-toolbar-content');
            if (isExpanded) {
                content.style.maxHeight = '0';
                content.style.overflow = 'hidden';
                toggleBtn.textContent = '▶ Expand';
            } else {
                content.style.maxHeight = '300px';
                content.style.overflow = 'auto';
                toggleBtn.textContent = '▼ close';
            }
            isExpanded = !isExpanded;
        });
        
        // Refresh snapshot list
        refreshBtn.addEventListener('click', () => {
            this.refreshSnapshots();
        });
        
        // Create snapshot
        createBtn.addEventListener('click', () => {
            this.showCreateSnapshotDialog();
        });
    }
    
    /**
     * Render snapshot list
     */
    renderSnapshotList(snapshots) {
        if (!this.ui.list) return;
        
        this.ui.list.innerHTML = '';
        
        // show/Hide empty state
        if (!snapshots || snapshots.length === 0) {
            this.ui.emptyState.style.display = 'block';
            this.ui.list.style.display = 'none';
            return;
        }
        
        this.ui.emptyState.style.display = 'none';
        this.ui.list.style.display = 'grid';
        
        // Sort in reverse chronological order（latest first）
        const sortedSnapshots = [...snapshots].sort((a, b) => {
            return new Date(b.date || b.timestamp) - new Date(a.date || a.timestamp);
        });
        
        sortedSnapshots.forEach((snap, index) => {
            const card = this._createSnapshotItem(snap, index);
            this.ui.list.appendChild(card);
        });
    }
    
    /**
     * Create a single snapshot item
     */
    _createSnapshotItem(snap, index) {
        const card = document.createElement('div');
        card.className = 'snapshot-card';
        card.style.cssText = `
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            transition: all 0.2s ease;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            position: relative;
        `;
        
        card.addEventListener('mouseenter', () => {
            card.style.transform = 'translateY(-2px)';
            card.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
            card.style.borderColor = '#4CAF50';
        });
        
        card.addEventListener('mouseleave', () => {
            card.style.transform = 'translateY(0)';
            card.style.boxShadow = '0 2px 4px rgba(0,0,0,0.05)';
            card.style.borderColor = '#e0e0e0';
        });
        
        // snapshot header
        const header = document.createElement('div');
        header.style.cssText = `
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
        `;
        
        // Hash tag
        const hashBadge = document.createElement('div');
        hashBadge.style.cssText = `
            background: #E3F2FD;
            color: #1976D2;
            padding: 4px 10px;
            border-radius: 12px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            font-weight: 600;
        `;
        hashBadge.textContent = `#${snap.short_hash || snap.hash?.slice(0, 8) || '???'}`;
        
        // date label
        const dateBadge = document.createElement('div');
        dateBadge.style.cssText = `
            color: #757575;
            font-size: 12px;
            background: #F5F5F5;
            padding: 4px 10px;
            border-radius: 12px;
        `;
        dateBadge.textContent = this._formatDateShort(snap.date || snap.timestamp);
        
        header.appendChild(hashBadge);
        header.appendChild(dateBadge);
        
        // Snapshot description
        const description = document.createElement('h4');
        description.style.cssText = `
            margin: 0 0 10px 0;
            color: #333;
            font-size: 16px;
            line-height: 1.4;
            min-height: 45px;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        `;
        description.textContent = snap.description || 'No description';
        
        // File information
        const fileInfo = document.createElement('div');
        fileInfo.style.cssText = `
            display: flex;
            align-items: center;
            gap: 8px;
            color: #666;
            font-size: 13px;
            margin-bottom: 15px;
        `;
        fileInfo.innerHTML = `
            <span>📄 ${snap.file_count || 0} files</span>
            <span style="color: #ddd">•</span>
            <span>⏱️ ${this._formatTimeAgo(snap.date || snap.timestamp)}</span>
        `;
        
        // Action button
        const actions = document.createElement('div');
        actions.style.cssText = `
            display: flex;
            gap: 10px;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #f0f0f0;
        `;
        
        // 🔥 Revise：Show different buttons based on current status
        const isSnapshotView = window.editorData?.projectInfo?.is_snapshot_view;
        const currentSnapshotHash = window.editorData?.projectInfo?.commit_hash;
        const isCurrentSnapshot = snap.hash === currentSnapshotHash;
        
        if (isSnapshotView && isCurrentSnapshot) {
            // Currently viewing this snapshot，show"Revert edit"button
            const recoverBtn = document.createElement('button');
            recoverBtn.textContent = '↩️ Revert edit';
            recoverBtn.style.cssText = `
                flex: 1;
                background: #4CAF50;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 13px;
                transition: background 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 5px;
            `;
            recoverBtn.addEventListener('mouseenter', () => {
                recoverBtn.style.background = '#45a049';
            });
            recoverBtn.addEventListener('mouseleave', () => {
                recoverBtn.style.background = '#4CAF50';
            });
            recoverBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const confirmed = confirm('Are you sure you want to restore editing mode?？\n\nWill exit snapshot viewing mode，Return to the latest status of the current project.');
                if (confirmed) {
                    await this.exitSnapshotView();
                }
            });
            
            actions.appendChild(recoverBtn);
        } else {
            // normal state，show"Check"and"rollback"button
            
            // View button
            const viewBtn = document.createElement('button');
            viewBtn.textContent = '👁️ Check';
            viewBtn.style.cssText = `
                flex: 1;
                background: #2196F3;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 13px;
                transition: background 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 5px;
            `;
            viewBtn.addEventListener('mouseenter', () => {
                viewBtn.style.background = '#1976D2';
            });
            viewBtn.addEventListener('mouseleave', () => {
                viewBtn.style.background = '#2196F3';
            });
            viewBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const confirmed = confirm(`Are you sure you want to view this snapshot?？\n\nSnapshot: ${snap.short_hash}\ndescribe: ${snap.description || 'No description'}\n\nAfter entering viewing mode，Content will not be editable.`);
                if (confirmed) {
                    await this.enterSnapshotView(snap.hash);
                }
            });
            
            // rollback button
            const restoreBtn = document.createElement('button');
            restoreBtn.textContent = '↩️ Rollback';
            restoreBtn.style.cssText = `
                flex: 1;
                background: #FF9800;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 13px;
                transition: background 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 5px;
            `;
            restoreBtn.addEventListener('mouseenter', () => {
                restoreBtn.style.background = '#F57C00';
            });
            restoreBtn.addEventListener('mouseleave', () => {
                restoreBtn.style.background = '#FF9800';
            });
            restoreBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.showRestoreDialog(snap);
            });
            
            actions.appendChild(viewBtn);
            actions.appendChild(restoreBtn);
        }
        
        // Assemble the cards
        card.appendChild(header);
        card.appendChild(description);
        card.appendChild(fileInfo);
        card.appendChild(actions);
        
        return card;
    }
    
    /**
     * Format date
     */
    _formatDate(dateStr) {
        if (!dateStr) return '';
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
        } catch {
            return dateStr;
        }
    }
    
    /**
     * Update status display
     */
    updateStatus(message, type = 'info') {
        if (!this.ui.status) return;
        
        const colors = {
            info: '#3498db',
            success: '#27ae60',
            error: '#e74c3c',
            warning: '#f39c12'
        };
        
        this.ui.status.textContent = message;
        this.ui.status.style.color = colors[type] || colors.info;
        
        // 3Clear normal messages after seconds
        if (type === 'info') {
            setTimeout(() => {
                if (this.ui.status.textContent === message) {
                    this.ui.status.textContent = '';
                }
            }, 3000);
        }
    }
    
    // ==================== dialog box ====================
    
    /**
     * Display the Create Snapshot dialog box
     */
    showCreateSnapshotDialog() {
        const dialog = document.createElement('div');
        dialog.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            z-index: 2000;
            min-width: 400px;
        `;
        
        dialog.innerHTML = `
            <h3 style="margin-top: 0; color: #2c3e50;">📸 Create new snapshot</h3>
            <div style="margin-bottom: 15px;">
                <label style="display: block; margin-bottom: 5px; font-weight: bold;">
                    Snapshot description：
                </label>
                <input type="text" id="git-snapshot-message" 
                       placeholder="Please enter a snapshot description..." 
                       style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
            </div>
            <div style="display: flex; justify-content: flex-end; gap: 10px;">
                <button id="git-snapshot-cancel" style="padding: 8px 16px; border: 1px solid #ddd; background: #f5f5f5; border-radius: 4px; cursor: pointer;">
                    Cancel
                </button>
                <button id="git-snapshot-confirm" style="padding: 8px 16px; background: #27ae60; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">
                    Create snapshot
                </button>
            </div>
        `;
        
        document.body.appendChild(dialog);
        
        // Focus on input box
        setTimeout(() => {
            const input = dialog.querySelector('#git-snapshot-message');
            if (input) input.focus();
        }, 100);
        
        // event listening
        dialog.querySelector('#git-snapshot-cancel').addEventListener('click', () => {
            document.body.removeChild(dialog);
        });
        
        dialog.querySelector('#git-snapshot-confirm').addEventListener('click', async () => {
            const input = dialog.querySelector('#git-snapshot-message');
            const message = input?.value?.trim();
            
            if (!message) {
                alert('Please enter a snapshot description');
                return;
            }
            
            const confirmBtn = dialog.querySelector('#git-snapshot-confirm');
            confirmBtn.disabled = true;
            confirmBtn.textContent = 'Creating...';
            
            const result = await this.createSnapshot(message);
            
            confirmBtn.disabled = false;
            confirmBtn.textContent = 'Create snapshot';
            
            if (result.success) {
                this.updateStatus(`✅ Snapshot created successfully: ${result.data?.short_hash || ''}`, 'success');
                document.body.removeChild(dialog);
                await this.refreshSnapshots();
            } else if (result.noChanges) {
                this.updateStatus(`ℹ️ ${result.message}`, 'info');
                document.body.removeChild(dialog);
            } else {
                this.updateStatus(`❌ ${result.message}`, 'error');
            }
        });
        
        // ESCkey off
        const keyHandler = (e) => {
            if (e.key === 'Escape') {
                document.body.removeChild(dialog);
                document.removeEventListener('keydown', keyHandler);
            }
        };
        document.addEventListener('keydown', keyHandler);
        
        // Click outside to close
        const clickHandler = (e) => {
            if (!dialog.contains(e.target)) {
                document.body.removeChild(dialog);
                document.removeEventListener('click', clickHandler);
                document.removeEventListener('keydown', keyHandler);
            }
        };
        setTimeout(() => document.addEventListener('click', clickHandler), 100);
    }
    
    /**
     * Show rollback confirmation dialog
     */
    showRestoreDialog(snapshot) {
        const dialog = document.createElement('div');
        dialog.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            z-index: 2000;
            min-width: 450px;
            max-width: 500px;
        `;
        
        const hash = snapshot.short_hash || snapshot.hash?.slice(0, 8) || '???';
        const date = this._formatDate(snapshot.date || snapshot.timestamp);
        const desc = snapshot.description || 'No description';
        
        dialog.innerHTML = `
            <h3 style="margin-top: 0; color: #e74c3c;">⚠️ Confirm rollback</h3>
            <div style="background: #fff8e1; padding: 15px; border-radius: 5px; margin-bottom: 15px; border-left: 4px solid #ff9800;">
                <p style="margin: 0 0 10px 0; font-weight: bold;">About to roll back to the following snapshot：</p>
                <div style="font-family: 'Courier New', monospace; background: #f5f5f5; padding: 8px; border-radius: 3px; margin-bottom: 10px;">
                    ${hash} - ${desc}
                </div>
                <p style="margin: 0; font-size: 14px; color: #666;">
                    📅 ${date}<br>
                    📄 ${snapshot.file_count || 0} files
                </p>
            </div>
            
            <div style="margin-bottom: 15px;">
                <label style="display: flex; align-items: center; cursor: pointer;">
                    <input type="checkbox" id="git-restore-backup" checked style="margin-right: 8px;">
                    <span>Create a pre-rollback backup snapshot</span>
                </label>
                <p style="margin: 5px 0 0 20px; font-size: 12px; color: #666;">
                    （suggestion：Automatically create backups before rollback，so that it can be restored if needed）
                </p>
            </div>
            
            <div style="background: #ffebee; padding: 10px; border-radius: 4px; margin-bottom: 15px; border-left: 3px solid #f44336;">
                <p style="margin: 0; font-size: 14px; color: #d32f2f;">
                    ⚠️ warn：Rolling back will lose all current unsaved changes！
                </p>
            </div>
            
            <div style="display: flex; justify-content: flex-end; gap: 10px;">
                <button id="git-restore-cancel" style="padding: 8px 16px; border: 1px solid #ddd; background: #f5f5f5; border-radius: 4px; cursor: pointer;">
                    Cancel
                </button>
                <button id="git-restore-confirm" style="padding: 8px 16px; background: #e74c3c; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">
                    Confirm rollback
                </button>
            </div>
        `;
        
        document.body.appendChild(dialog);
        
        // event listening
        dialog.querySelector('#git-restore-cancel').addEventListener('click', () => {
            document.body.removeChild(dialog);
        });
        
        dialog.querySelector('#git-restore-confirm').addEventListener('click', async () => {
            const backup = dialog.querySelector('#git-restore-backup').checked;
            
            const confirmBtn = dialog.querySelector('#git-restore-confirm');
            confirmBtn.disabled = true;
            confirmBtn.textContent = 'Rolling back...';
            
            const result = await this.restoreSnapshot(snapshot.hash, {
                confirm: true,
                backup: backup
            });
            
            if (result.success) {
                this.updateStatus(`✅ Rollback successful to ${hash}`, 'success');
                document.body.removeChild(dialog);
                
                // Rollback successful，Refresh the page or prompt the user
                setTimeout(() => {
                    if (confirm('Rollback successful！The page needs to be refreshed to load the data after the rollback. Whether to refresh immediately？')) {
                        window.location.reload();
                    }
                }, 500);
                
            } else {
                this.updateStatus(`❌ Rollback failed: ${result.message}`, 'error');
                confirmBtn.disabled = false;
                confirmBtn.textContent = 'Confirm rollback';
            }
        });
        
        // ESCkey off
        const keyHandler = (e) => {
            if (e.key === 'Escape') {
                document.body.removeChild(dialog);
                document.removeEventListener('keydown', keyHandler);
            }
        };
        document.addEventListener('keydown', keyHandler);
    }
    
    async enterSnapshotView(commitHash) {
        this.updateStatus('Entering snapshot viewing mode...', 'info');
        
        try {
            // Check if already in view mode
            if (window.editorData?.projectInfo?.is_snapshot_view) {
                this.updateStatus('Already in snapshot view mode', 'warning');
                return {
                    success: false,
                    message: 'Already in snapshot view mode'
                };
            }
            
            // Get snapshot information
            const snapshot = this.snapshots.find(s => s.hash === commitHash || s.short_hash === commitHash);
            if (!snapshot) {
                this.updateStatus('The specified snapshot could not be found', 'error');
                return {
                    success: false,
                    message: 'The specified snapshot could not be found'
                };
            }
            
            logger.debug(`📸 Enter snapshot viewing mode: ${snapshot.description || commitHash.slice(0, 8)}`);
            
            // 🔥 key：call newAPI
            const response = await fetch(`${this.apiBase}/enter-snapshot/${commitHash}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin'
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                this.updateStatus(`✅ Entered snapshot viewing mode: ${result.data?.short_hash}`, 'success');
                
                // Show success message
                setTimeout(() => {
                    alert(`✅ Entered snapshot viewing mode\n\nSnapshot: ${result.data?.short_hash}\ndescribe: ${result.data?.commit_info?.message || 'No description'}\n\nThe page will be refreshed soon...`);
                    
                    // refresh page
                    if (result.data?.should_refresh) {
                        window.location.reload();
                    }
                }, 300);
                
                return {
                    success: true,
                    data: result.data
                };
            } else {
                this.updateStatus(`❌ Failed to enter snapshot view mode: ${result.message}`, 'error');
                return {
                    success: false,
                    message: result.message
                };
            }
            
        } catch (error) {
            console.error('❌ Failed to enter snapshot view mode:', error);
            this.updateStatus(`Entry failed: ${error.message}`, 'error');
            return {
                success: false,
                message: error.message
            };
        }
    }
    
    /**
     * Exit snapshot viewing mode
     */
    async exitSnapshotView() {
        this.updateStatus('Exiting snapshot viewing mode...', 'info');
        
        try {
            // 🔥 key：call newAPI
            const response = await fetch(`${this.apiBase}/exit-snapshot`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin'
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                this.updateStatus('✅ Exited snapshot viewing mode', 'success');
                
                // Show success message
                setTimeout(() => {
                    alert(`✅ Exited snapshot viewing mode\n\nThe page will be refreshed soon...`);
                    
                    // refresh page
                    if (result.data?.should_refresh) {
                        window.location.reload();
                    }
                }, 300);
                
                return {
                    success: true,
                    data: result.data
                };
            } else {
                this.updateStatus(`❌ Failed to exit snapshot view mode: ${result.message}`, 'error');
                return {
                    success: false,
                    message: result.message
                };
            }
            
        } catch (error) {
            console.error('❌ Failed to exit snapshot view mode:', error);
            this.updateStatus(`Exit failed: ${error.message}`, 'error');
            return {
                success: false,
                message: error.message
            };
        }
    }
    
    /**
     * Get a snapshot to view status
     */
    async getSnapshotStatus() {
        try {
            const response = await fetch(`${this.apiBase}/snapshot-status`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin'
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                return {
                    success: true,
                    data: result.data
                };
            } else {
                return {
                    success: false,
                    message: result.message
                };
            }
            
        } catch (error) {
            console.error('❌ Failed to get snapshot status:', error);
            return {
                success: false,
                message: error.message
            };
        }
    }
    /**
     * View snapshot contents
     */
    /**
     * View snapshot contents
     */
    async viewSnapshot(commitHash) {
        // 🔥 No longer open new windows directly，Instead call newAPI
        return await this.enterSnapshotView(commitHash);
    }

    _createSnapshotViewerUrl(commitHash, snapshot) {
        const baseUrl = window.location.origin;
        const sessionId = this.sessionId;
        
        // 🔥 critical modifications：Use the correct snapshot viewer routing
        return `${baseUrl}/snapshot-viewer/${sessionId}/${commitHash}`;
    }
    
    // ==================== public method ====================
    
    /**
     * Initialize and mount to the page
     */
    async mount() {
        try {
            // Create and add toolbars
            const toolbar = this.createToolbar();
            document.body.appendChild(toolbar);
            
            // Initial loading snapshot
            await this.refreshSnapshots();
            
            logger.debug('✅ GitToolbar is mounted');
            return true;
            
        } catch (error) {
            console.error('❌ mountGitToolbar failed:', error);
            return false;
        }
    }
    
    /**
     * Refresh snapshot list
     */
    async refreshSnapshots() {
        this.updateStatus('Loading snapshot...', 'info');
        
        // show loading status
        if (this.ui.loadingState) {
            this.ui.loadingState.style.display = 'block';
            this.ui.list.style.display = 'none';
            this.ui.emptyState.style.display = 'none';
        }
        
        const result = await this.getSnapshots(10);
        
        // Hide loading status
        if (this.ui.loadingState) {
            this.ui.loadingState.style.display = 'none';
        }
        
        if (result.success) {
            this.renderSnapshotList(result.snapshots);
            this.updateStatus(`Loaded ${result.snapshots.length} snapshots`, 'success');
        } else {
            this.renderSnapshotList([]);
            this.updateStatus(`Loading failed: ${result.message}`, 'error');
        }
        
        return result;
    }
    
    /**
     * Destroy and clean up
     */
    destroy() {
        if (this.ui.container && this.ui.container.parentNode) {
            this.ui.container.parentNode.removeChild(this.ui.container);
        }
        logger.debug('🗑️ GitToolbar has been destroyed');
    }

    /**
     * Format short date
     */
    _formatDateShort(dateStr) {
        if (!dateStr) return '';
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString('zh-CN', {
                month: 'short',
                day: 'numeric'
            });
        } catch {
            return dateStr.slice(0, 10);
        }
    }

    /**
     * Format relative time（like"2hours ago"）
     */
    _formatTimeAgo(dateStr) {
        if (!dateStr) return '';
        try {
            const date = new Date(dateStr);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);
            
            if (diffMins < 1) return 'just';
            if (diffMins < 60) return `${diffMins}minutes ago`;
            if (diffHours < 24) return `${diffHours}hours ago`;
            if (diffDays < 30) return `${diffDays}days ago`;
            
            return date.toLocaleDateString('zh-CN', {
                month: 'short',
                day: 'numeric'
            });
        } catch {
            return dateStr;
        }
    }

    /**
     * Set event listener
     */
    _setupEventListeners(refreshBtn, createBtn) {
        // Refresh snapshot list
        refreshBtn.addEventListener('click', () => {
            this.refreshSnapshots();
        });
        
        // Create snapshot
        createBtn.addEventListener('click', () => {
            this.showCreateSnapshotDialog();
        });
        
        // Responsive processing
        this._setupResponsive();
    }

    /**
     * Set up a responsive layout
     */
    _setupResponsive() {
        const updateGrid = () => {
            if (!this.ui.list) return;
            
            const width = window.innerWidth;
            let columns = 3;
            
            if (width < 768) {
                columns = 1;
            } else if (width < 1024) {
                columns = 2;
            }
            
            this.ui.list.style.gridTemplateColumns = `repeat(auto-fill, minmax(${columns === 1 ? '100%' : '300px'}, 1fr))`;
        };
        
        updateGrid();
        window.addEventListener('resize', updateGrid);
    }
}

// global access
window.GitManagerUI = GitManagerUI;



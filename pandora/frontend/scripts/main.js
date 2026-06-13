const decoyContainer = document.getElementById('decoy-container');
const vaultContainer = document.getElementById('vault-container');
const setupContainer = document.getElementById('setup-container');

const passInput = document.getElementById('master-password');
const loginBtn = document.getElementById('login-btn');
const errorDiv = document.getElementById('login-error');

const setupPassInput = document.getElementById('setup-password');
const setupDirInput = document.getElementById('setup-vault-dir');
const setupAdvancedToggle = document.getElementById('setup-advanced-toggle');
const setupAdvancedFields = document.getElementById('setup-advanced-fields');
const setupBlobDirInput = document.getElementById('setup-blob-dir');
const setupBtn = document.getElementById('setup-btn');
const setupErrorDiv = document.getElementById('setup-error');

if (setupAdvancedToggle) {
    setupAdvancedToggle.onchange = () => {
        setupAdvancedFields.style.display = setupAdvancedToggle.checked ? 'block' : 'none';
    };
}


const fileInput = document.getElementById('file-input');
const galleryGrid = document.getElementById('gallery-grid');

const importModal = document.getElementById('import-modal');
const closeImportBtn = document.getElementById('close-import');
const importModalTitle = document.getElementById('import-modal-title');
const importFilenameInput = document.getElementById('import-filename');
const importCategoryGrid = document.getElementById('import-category-grid');
const importTagInput = document.getElementById('import-tag-input');
const importTagsList = document.getElementById('import-tags-list');
const importSelectedTagsDiv = document.getElementById('import-selected-tags');
const importConfirmBtn = document.getElementById('import-confirm-btn');
const importPreviewContainer = document.getElementById('import-preview-container');
const importPreviewThumb = document.getElementById('import-preview-thumb');
const importProgress = document.getElementById('import-progress');
const importProgressBar = document.getElementById('import-progress-bar');
const importStatusText = document.getElementById('import-status-text');

const importUrlInput = document.getElementById('import-url-input');
const importUrlBtn = document.getElementById('import-url-btn');

const playerModal = document.getElementById('player-modal');
const videoPlayer = document.getElementById('video-player');
const imageViewer = document.getElementById('image-viewer');
const closeModal = document.getElementById('close-modal');
const panicBtn = document.getElementById('panic-btn');

const settingsBtn = document.getElementById('settings-btn');
const settingsModal = document.getElementById('settings-modal');
const closeSettings = document.getElementById('close-settings');
const restartBtn = document.getElementById('restart-server-btn');
const shutdownBtn = document.getElementById('shutdown-server-btn');

const categoryList = document.getElementById('category-list');
const newCategoryInput = document.getElementById('new-category-name');
const addCategoryBtn = document.getElementById('add-category-btn');
const searchInput = document.getElementById('search-input');
const sortSelect = document.getElementById('sort-select');
const paginationControls = document.getElementById('pagination-controls');

const sidebar = document.getElementById('sidebar');
const sidebarToggle = document.getElementById('sidebar-toggle');
const sidebarTagsList = document.getElementById('sidebar-tags-list');
const openTagManagerBtn = document.getElementById('open-tag-manager');
const tagManagerModal = document.getElementById('tag-manager-modal');
const closeTagManager = document.getElementById('close-tag-manager');
const tagManagerList = document.getElementById('tag-manager-list');

const selectionBar = document.getElementById('selection-bar');
const selectedCountSpan = document.getElementById('selected-count');
const bulkTagBtn = document.getElementById('bulk-tag-btn');
const bulkUntagBtn = document.getElementById('bulk-untag-btn');
const bulkCatBtn = document.getElementById('bulk-cat-btn');
const bulkDeleteBtn = document.getElementById('bulk-delete-btn');
const clearSelectionBtn = document.getElementById('clear-selection-btn');

const renameModal = document.getElementById('rename-modal');
const closeRenameBtn = document.getElementById('close-rename');
const renameInput = document.getElementById('rename-input');
const renameConfirmBtn = document.getElementById('rename-confirm-btn');
const renameModalTitle = document.getElementById('rename-modal-title');

let renameCallback = null;

function openRenameModal(title, initialValue, callback) {
    renameModalTitle.textContent = title;
    renameInput.value = initialValue;
    renameCallback = callback;
    renameModal.classList.add('active');
    setTimeout(() => renameInput.focus(), 100);
}

closeRenameBtn.onclick = () => renameModal.classList.remove('active');
renameConfirmBtn.onclick = async () => {
    const val = renameInput.value.trim();
    if (val && renameCallback) {
        await renameCallback(val);
    }
    renameModal.classList.remove('active');
};
renameInput.onkeypress = (e) => { if (e.key === 'Enter') renameConfirmBtn.click(); };

let currentCategoryId = 'all';
let currentTagFilter = null;
let currentPage = 1;
let categories = [];
let allTags = [];
let searchTimeout = null;
let selectedFileIds = new Set();
let isSelectionMode = false;

function isImage(filename) {
    return /\.(jpg|jpeg|png|gif|webp)$/i.test(filename);
}

function escapeHTML(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// --- Auth Flow ---
async function checkSetupStatus() {
    try {
        const res = await fetch('/api/setup/status');
        if (res.ok) {
            const data = await res.json();
            if (!data.initialized) {
                decoyContainer.classList.remove('active');
                setupContainer.classList.add('active');
                
                // Auto-fill suggested paths
                if (data.suggested_config_dir) {
                    setupDirInput.value = data.suggested_config_dir;
                }
                if (data.suggested_blob_dir) {
                    setupBlobDirInput.value = data.suggested_blob_dir;
                    // If mass storage is different from config, show the split fields
                    if (data.suggested_blob_dir !== data.suggested_config_dir + '/data') {
                        setupAdvancedToggle.checked = true;
                        setupAdvancedFields.style.display = 'block';
                    }
                }
                
                if (data.is_env_forced) {
                    setupDirInput.disabled = true;
                    setupBlobDirInput.disabled = true;
                    setupAdvancedToggle.disabled = true;
                    setupDirInput.style.opacity = '0.6';
                    setupBlobDirInput.style.opacity = '0.6';
                }
            }
        }
    } catch (e) { console.error('Failed to check setup status', e); }
}

async function authenticate() {
    const password = passInput.value;
    if (!password) return;
    
    errorDiv.textContent = 'Authenticating...';
    try {
        let res = await fetch('/api/unlock', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({password})
        });
        
        if (res.ok) {
            showVault();
        } else {
            const data = await res.json();
            errorDiv.textContent = data.detail || 'Authentication failed';
        }
    } catch (e) { errorDiv.textContent = 'Network error'; }
}

async function runSetup() {
    const password = setupPassInput.value;
    const vault_dir = setupDirInput.value.trim();
    const blob_dir = setupAdvancedToggle.checked ? setupBlobDirInput.value.trim() : null;

    if (!password) { setupErrorDiv.textContent = 'Password required'; return; }
    
    setupErrorDiv.textContent = 'Initializing vault...';
    try {
        const res = await fetch('/api/init', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                password, 
                vault_dir: vault_dir || null,
                blob_dir: blob_dir || null
            })
        });
        if (res.ok) {
            setupContainer.classList.remove('active');
            showVault();
        } else {
            const data = await res.json();
            setupErrorDiv.textContent = data.detail || 'Setup failed';
        }
    } catch (e) { setupErrorDiv.textContent = 'Network error'; }
}

loginBtn.addEventListener('click', authenticate);
passInput.addEventListener('keypress', e => { if (e.key === 'Enter') authenticate(); });
setupBtn.addEventListener('click', runSetup);

// --- Vault Flow ---
async function showVault() {
    decoyContainer.classList.remove('active');
    vaultContainer.classList.add('active');
    passInput.value = '';
    errorDiv.textContent = '';
    await Promise.all([loadCategories(), loadTags()]);
    await loadFiles();
}

let categoryData = { categories: [], total: 0, uncategorized: 0 };

async function loadCategories() {
    try {
        const res = await fetch('/api/categories');
        if (!res.ok) return;
        categoryData = await res.json();
        categories = categoryData.categories; // Keep global categories list for other logic
        renderCategoryList();
    } catch (e) { console.error(e); }
}

function renderCategoryList() {
    categoryList.innerHTML = `
        <li data-id="all" class="${currentCategoryId === 'all' ? 'active' : ''}">
            <span>All Files</span>
            <span class="category-count">${categoryData.total}</span>
        </li>
        <li data-id="uncategorized" class="${currentCategoryId === 'uncategorized' ? 'active' : ''}">
            <span>Uncategorized</span>
            <span class="category-count">${categoryData.uncategorized}</span>
        </li>
    `;
    categories.forEach(c => {
        const li = document.createElement('li');
        li.dataset.id = c.id;
        li.className = currentCategoryId == c.id ? 'active' : '';
        
        const isAuto = ['Video', 'Image', 'Document', 'Other'].includes(c.name);
        
        li.innerHTML = `
            <span>${c.name}</span>
            <span class="category-count">${c.count || 0}</span>
            ${!isAuto ? `
                <div class="category-actions">
                    <button class="edit-cat-btn" title="Rename">✏️</button>
                    <button class="delete-cat-btn" title="Delete">🗑️</button>
                </div>
            ` : ''}
        `;

        const span = li.querySelector('span');
        span.onclick = () => {
            currentCategoryId = c.id;
            currentTagFilter = null;
            currentPage = 1;
            document.getElementById('current-category-title').textContent = c.name;
            renderCategoryList();
            renderSidebarTags();
            loadFiles();
            if (window.innerWidth <= 768) sidebar.classList.remove('active');
        };

        if (!isAuto) {
            li.querySelector('.edit-cat-btn').onclick = (e) => {
                e.stopPropagation();
                openRenameModal('Rename Category', c.name, async (newName) => {
                    if (newName === c.name) return;
                    try {
                        const res = await fetch(`/api/categories/${c.id}`, {
                            method: 'PUT',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({name: newName})
                        });
                        if (res.ok) {
                            await loadCategories();
                            if (currentCategoryId == c.id) document.getElementById('current-category-title').textContent = newName;
                        } else {
                            alert('Failed to rename category');
                        }
                    } catch(e) { console.error(e); }
                });
            };

            li.querySelector('.delete-cat-btn').onclick = async (e) => {
                e.stopPropagation();
                if (!confirm(`Delete category "${c.name}"? Files will be moved to Uncategorized.`)) return;
                try {
                    const res = await fetch(`/api/categories/${c.id}`, { method: 'DELETE' });
                    if (res.ok) {
                        if (currentCategoryId == c.id) currentCategoryId = 'all';
                        await loadCategories();
                        await loadFiles();
                    }
                } catch(e) {}
            };
        }

        categoryList.appendChild(li);
    });
    
    // Set up listeners for static items
    const allLi = categoryList.querySelector('[data-id="all"]');
    allLi.onclick = () => {
        currentCategoryId = 'all';
        currentTagFilter = null;
        currentPage = 1;
        document.getElementById('current-category-title').textContent = 'All Files';
        renderCategoryList();
        renderSidebarTags();
        loadFiles();
        if (window.innerWidth <= 768) sidebar.classList.remove('active');
    };

    const uncatLi = categoryList.querySelector('[data-id="uncategorized"]');
    uncatLi.onclick = () => {
        currentCategoryId = 'uncategorized';
        currentTagFilter = null;
        currentPage = 1;
        document.getElementById('current-category-title').textContent = 'Uncategorized';
        renderCategoryList();
        renderSidebarTags();
        loadFiles();
        if (window.innerWidth <= 768) sidebar.classList.remove('active');
    };
}

async function loadTags() {
    try {
        const res = await fetch('/api/tags');
        if (!res.ok) return;
        allTags = await res.json();
        renderSidebarTags();
    } catch (e) { console.error(e); }
}

function renderSidebarTags() {
    sidebarTagsList.innerHTML = '';
    allTags.sort().forEach(tag => {
        const span = document.createElement('span');
        span.className = `sidebar-tag ${currentTagFilter === tag ? 'active' : ''}`;
        span.textContent = tag;
        span.onclick = () => {
            if (currentTagFilter === tag) currentTagFilter = null;
            else currentTagFilter = tag;
            currentPage = 1; // Reset pagination
            renderSidebarTags();
            loadFiles();
            if (window.innerWidth <= 768) sidebar.classList.remove('active');
        };
        sidebarTagsList.appendChild(span);
    });
}

addCategoryBtn.addEventListener('click', async () => {
    const name = newCategoryInput.value.trim();
    if (!name) return;
    try {
        const res = await fetch('/api/categories', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name})
        });
        if (res.ok) {
            newCategoryInput.value = '';
            await loadCategories();
            await loadFiles();
        }
    } catch (e) { console.error(e); }
});

searchInput.addEventListener('input', () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        currentPage = 1;
        loadFiles();
    }, 300);
});

sortSelect.addEventListener('change', () => {
    currentPage = 1;
    loadFiles();
});

function formatDuration(seconds) {
    if (!seconds) return '';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    return `${m}:${s.toString().padStart(2, '0')}`;
}

async function loadFiles() {
    try {
        let url = '/api/files?';
        if (currentCategoryId !== 'all' && currentCategoryId !== 'uncategorized') {
            url += `category_id=${currentCategoryId}&`;
        }
        let q = searchInput.value.trim();
        if (currentTagFilter) {
            q = q ? `${q} tag:${currentTagFilter}` : `tag:${currentTagFilter}`;
        }
        if (q) {
            url += `q=${encodeURIComponent(q)}&`;
        }

        const [sort_by, sort_dir] = sortSelect.value.split(':');
        url += `sort_by=${sort_by}&sort_dir=${sort_dir}&page=${currentPage}&per_page=50`;

        const res = await fetch(url);
        if (res.status === 401) { lockVault(); return; }
        const data = await res.json();
        let files = data.results;
        
        if (currentCategoryId === 'uncategorized') files = files.filter(f => f.category_id === null);
        
        galleryGrid.innerHTML = '';
        renderPagination(data.total, data.per_page);

        // Update result count display
        const resultCountSpan = document.getElementById('search-result-count');
        if (q || currentTagFilter || (currentCategoryId !== 'all' && currentCategoryId !== 'uncategorized')) {
            resultCountSpan.textContent = `${data.total} files found`;
        } else {
            resultCountSpan.textContent = '';
        }

        files.forEach(f => {
            const card = document.createElement('div');
            card.className = `media-card ${selectedFileIds.has(f.id) ? 'selected' : ''}`;
            card.dataset.id = f.id;
            
            const icon = isImage(f.filename) ? '🖼️' : '🎬';
            let optionsHTML = `<option value="">Uncategorized</option>`;
            categories.forEach(c => {
                const selected = c.id === f.category_id ? 'selected' : '';
                optionsHTML += `<option value="${c.id}" ${selected}>${c.name}</option>`;
            });

            const durationHTML = f.duration ? `<div class="duration-badge">${formatDuration(f.duration)}</div>` : '';
            const thumbnailHTML = f.thumbnail_data ? 
                `<div class="thumbnail-container"><img src="${f.thumbnail_data}" class="thumbnail" />${durationHTML}</div>` : 
                `<div class="thumbnail-container"><div class="icon">${icon}</div>${durationHTML}</div>`;
            
            const tagsHTML = f.tags && f.tags.length > 0 ? 
                `<div class="tag-container">${f.tags.map(t => `<span class="tag-badge">${t}</span>`).join('')}</div>` : '';

            card.innerHTML = `
                <div class="card-menu" onclick="event.stopPropagation()">
                    <button class="menu-btn" onclick="toggleMenu('${f.id}')">⋮</button>
                    <div class="menu-dropdown" id="menu-${f.id}">
                        <div class="menu-item-rename" data-id="${f.id}">Rename</div>
                        <div class="menu-item-tags" data-id="${f.id}">Manage Tags</div>
                        <div class="menu-item-delete danger" data-id="${f.id}">Delete</div>
                    </div>
                </div>
                ${thumbnailHTML}
                <div class="title" title="${escapeHTML(f.filename)}">${escapeHTML(f.filename)}</div>
                <div class="category-assign" onclick="event.stopPropagation()">
                    <select class="category-select" data-id="${f.id}">
                        ${optionsHTML}
                    </select>
                </div>
                ${tagsHTML}
            `;
            
            // Professional event listeners instead of onclick strings to avoid quoting bugs
            card.querySelector('.menu-item-rename').onclick = () => window.renameFile(f.id, f.filename);
            card.querySelector('.menu-item-tags').onclick = () => window.manageTags(f.id, f.tags.join(', '));
            card.querySelector('.menu-item-delete').onclick = () => window.deleteFile(f.id);

            const select = card.querySelector('.category-select');
            select.addEventListener('change', async (e) => {
                const newCatId = e.target.value ? parseInt(e.target.value) : null;
                await fetch(`/api/files/${f.id}/category`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({category_id: newCatId})
                });
                await loadCategories(); // Update counts
                if (currentCategoryId !== 'all') loadFiles();
            });

            card.onclick = (e) => {
                if (e.ctrlKey || e.metaKey || isSelectionMode) {
                    toggleSelection(f.id);
                } else {
                    playFile(f.id, f.filename);
                }
            };
            
            // Long press for mobile selection
            let pressTimer;
            card.onmousedown = () => { pressTimer = window.setTimeout(() => { toggleSelection(f.id); isSelectionMode = true; }, 500); };
            card.onmouseup = () => { clearTimeout(pressTimer); };
            card.ontouchstart = () => { pressTimer = window.setTimeout(() => { toggleSelection(f.id); isSelectionMode = true; }, 500); };
            card.ontouchend = () => { clearTimeout(pressTimer); };

            galleryGrid.appendChild(card);
        });
    } catch (e) { console.error(e); }
}

function renderPagination(total, perPage) {
    paginationControls.innerHTML = '';
    const totalPages = Math.ceil(total / perPage);
    if (totalPages <= 1) return;

    const maxButtons = 5;
    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, startPage + maxButtons - 1);
    
    if (endPage - startPage < maxButtons - 1) {
        startPage = Math.max(1, endPage - maxButtons + 1);
    }

    if (currentPage > 1) {
        const btn = document.createElement('button');
        btn.className = 'btn btn-outline btn-small';
        btn.textContent = '←';
        btn.onclick = () => { currentPage--; loadFiles(); window.scrollTo(0,0); };
        paginationControls.appendChild(btn);
    }

    for (let i = startPage; i <= endPage; i++) {
        const btn = document.createElement('button');
        btn.className = `btn btn-small ${i === currentPage ? '' : 'btn-outline'}`;
        btn.textContent = i;
        btn.onclick = () => { currentPage = i; loadFiles(); window.scrollTo(0,0); };
        paginationControls.appendChild(btn);
    }

    if (currentPage < totalPages) {
        const btn = document.createElement('button');
        btn.className = 'btn btn-outline btn-small';
        btn.textContent = '→';
        btn.onclick = () => { currentPage++; loadFiles(); window.scrollTo(0,0); };
        paginationControls.appendChild(btn);
    }
}

function toggleSelection(id) {
    if (selectedFileIds.has(id)) {
        selectedFileIds.delete(id);
    } else {
        selectedFileIds.add(id);
    }
    updateSelectionUI();
}

function updateSelectionUI() {
    document.querySelectorAll('.media-card').forEach(card => {
        if (selectedFileIds.has(card.dataset.id)) card.classList.add('selected');
        else card.classList.remove('selected');
    });
    
    if (selectedFileIds.size > 0) {
        selectionBar.classList.add('active');
        selectedCountSpan.textContent = selectedFileIds.size;
    } else {
        selectionBar.classList.remove('active');
        isSelectionMode = false;
    }
}

clearSelectionBtn.onclick = () => {
    selectedFileIds.clear();
    updateSelectionUI();
};

// --- Batch Actions ---
bulkTagBtn.onclick = () => {
    openRenameModal('Add Tags to Selection (comma separated)', '', async (tagStr) => {
        const tags = tagStr.split(',').map(t => t.trim()).filter(t => t.length > 0);
        await batchRequest('/api/files/batch/tags', { file_ids: Array.from(selectedFileIds), tags, action: 'add' });
    });
};

bulkUntagBtn.onclick = () => {
    openRenameModal('Remove Tags from Selection (comma separated)', '', async (tagStr) => {
        const tags = tagStr.split(',').map(t => t.trim()).filter(t => t.length > 0);
        await batchRequest('/api/files/batch/tags', { file_ids: Array.from(selectedFileIds), tags, action: 'remove' });
    });
};

bulkCatBtn.onclick = () => {
    let options = "0: Uncategorized\n";
    categories.forEach(c => options += `${c.id}: ${c.name}\n`);
    openRenameModal(`Set Category (Enter ID):\n${options}`, '', async (catIdStr) => {
        const category_id = parseInt(catIdStr) || null;
        await batchRequest('/api/files/batch/category', { file_ids: Array.from(selectedFileIds), category_id }, 'PUT');
    });
};

bulkDeleteBtn.onclick = async () => {
    if (!confirm(`Permanently delete ${selectedFileIds.size} files?`)) return;
    await batchRequest('/api/files/batch/delete', { file_ids: Array.from(selectedFileIds) });
};

async function batchRequest(url, body, method = 'POST') {
    try {
        const res = await fetch(url, {
            method,
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        });
        if (res.ok) {
            selectedFileIds.clear();
            updateSelectionUI();
            await Promise.all([loadFiles(), loadCategories(), loadTags()]);
        }
    } catch (e) { console.error(e); }
}

// --- Tag Manager ---
openTagManagerBtn.onclick = () => {
    renderTagManager();
    tagManagerModal.classList.add('active');
};
closeTagManager.onclick = () => tagManagerModal.classList.remove('active');

async function renderTagManager() {
    tagManagerList.innerHTML = '<div style="padding: 2rem; text-align: center; opacity: 0.7;">Loading tags...</div>';
    try {
        const res = await fetch('/api/tags');
        const tags = await res.json();
        tagManagerList.innerHTML = '';
        if (tags.length === 0) {
            tagManagerList.innerHTML = '<div style="padding: 2rem; text-align: center; opacity: 0.5;">No tags found</div>';
            return;
        }
        tags.sort().forEach(tag => {
            const item = document.createElement('div');
            item.className = 'tag-manager-item';
            item.innerHTML = `
                <div style="flex:1; overflow:hidden; text-overflow:ellipsis;">${tag}</div>
                <button class="btn btn-outline btn-small rename-btn" style="min-width: 80px;">Rename</button>
                <button class="btn btn-danger btn-small delete-btn" title="Delete globally">🗑️</button>
            `;
            
            const renameBtn = item.querySelector('.rename-btn');
            const deleteBtn = item.querySelector('.delete-btn');

            renameBtn.onclick = (e) => {
                e.stopPropagation();
                openRenameModal(`Rename Tag: ${tag}`, tag, async (newName) => {
                    if (newName === tag) return;
                    try {
                        const res = await fetch(`/api/tags/${encodeURIComponent(tag)}`, {
                            method: 'PUT',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({name: newName})
                        });
                        if (res.ok) { 
                            await Promise.all([loadTags(), loadFiles()]);
                            renderTagManager(); 
                        } else {
                            alert('Failed to rename tag');
                        }
                    } catch(e) { console.error(e); }
                });
            };

            deleteBtn.onclick = async (e) => {
                e.stopPropagation();
                if (!confirm(`Delete tag "${tag}" from all files?`)) return;
                
                deleteBtn.disabled = true;
                try {
                    const res = await fetch(`/api/tags/${encodeURIComponent(tag)}`, { method: 'DELETE' });
                    if (res.ok) { 
                        await Promise.all([loadTags(), loadFiles()]);
                        renderTagManager(); 
                    } else {
                        alert('Failed to delete tag');
                        deleteBtn.disabled = false;
                    }
                } catch(e) {
                    console.error(e);
                    deleteBtn.disabled = false;
                }
            };

            tagManagerList.appendChild(item);
        });
    } catch(e) {
        console.error(e);
        tagManagerList.innerHTML = '<div style="padding: 2rem; text-align: center; color: var(--danger);">Error loading tags</div>';
    }
}

// --- Rest of UI ---
sidebarToggle.onclick = () => sidebar.classList.toggle('active');

window.manageTags = async (id, currentTags) => {
    openRenameModal('Manage Tags (comma separated)', currentTags, async (newTagsStr) => {
        const tags = newTagsStr.split(',').map(t => t.trim()).filter(t => t.length > 0);
        try {
            const res = await fetch(`/api/files/${id}/tags`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({tags})
            });
            if (res.ok) { await loadFiles(); await loadTags(); }
            else alert('Failed to update tags');
        } catch(e) { console.error(e); }
    });
};

// --- Settings Flow ---
settingsBtn.onclick = async () => {
    settingsModal.classList.add('active');
    try {
        const res = await fetch('/api/settings/storage');
        if (res.ok) {
            const data = await res.json();
            document.getElementById('settings-config-dir').textContent = data.config_dir;
            document.getElementById('settings-blob-dir').textContent = data.blob_dir;
        }
    } catch (e) { console.error(e); }
};
closeSettings.onclick = () => settingsModal.classList.remove('active');

restartBtn.onclick = async () => {
    if (!confirm('Restart server?')) return;
    try { await fetch('/api/server/restart', {method: 'POST'}); alert('Server restarting...'); location.reload(); } catch(e) {}
};

shutdownBtn.onclick = async () => {
    if (!confirm('Shutdown server?')) return;
    try { 
        await fetch('/api/server/shutdown', {method: 'POST'}); 
        document.body.innerHTML = `
            <div style="display:flex;justify-content:center;align-items:center;height:100vh;flex-direction:column;font-family:sans-serif;background:#1a1a1a;color:white;">
                <h1 style="color:#ff4444;">Server Shutting Down</h1>
                <p>The vault has been locked and the server is stopping.</p>
                <p>You can close this tab now.</p>
            </div>
        `;
    } catch(e) {}
};

async function generateThumbnail(file) {
    return new Promise((resolve) => {
        const url = URL.createObjectURL(file);
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        const maxSize = 200;
        let resolved = false;
        const safeResolve = (val) => { if (!resolved) { resolved = true; resolve(val); } };
        setTimeout(() => { URL.revokeObjectURL(url); safeResolve(null); }, 3000);
        if (file.type.startsWith('image/')) {
            const img = new Image();
            img.onload = () => {
                const scale = Math.min(maxSize / img.width, maxSize / img.height);
                canvas.width = img.width * scale; canvas.height = img.height * scale;
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                URL.revokeObjectURL(url); safeResolve(canvas.toDataURL('image/jpeg', 0.6));
            };
            img.onerror = () => { URL.revokeObjectURL(url); safeResolve(null); };
            img.src = url;
        } else if (file.type.startsWith('video/')) {
            const video = document.createElement('video');
            video.muted = true; video.preload = 'metadata'; video.playsInline = true;
            video.onloadedmetadata = () => { video.currentTime = Math.min(1, video.duration / 2 || 1); };
            video.onseeked = () => {
                const scale = Math.min(maxSize / video.videoWidth, maxSize / video.videoHeight);
                canvas.width = video.videoWidth * scale; canvas.height = video.videoHeight * scale;
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                URL.revokeObjectURL(url); safeResolve(canvas.toDataURL('image/jpeg', 0.6));
            };
            video.onerror = () => { URL.revokeObjectURL(url); safeResolve(null); };
            video.src = url; video.load();
        } else safeResolve(null);
    });
}

// --- Import Flow ---
let importMode = 'upload'; // 'upload' or 'url'
let importFiles = [];
let importUrl = '';
let importSelectedCategoryId = null;
let importSelectedTags = new Set();

function openImportModal(mode, data) {
    importMode = mode;
    importSelectedTags.clear();
    importSelectedCategoryId = null;
    importProgress.style.display = 'none';
    importConfirmBtn.disabled = false;
    importConfirmBtn.style.display = 'block';
    
    if (mode === 'upload') {
        importFiles = Array.from(data);
        importModalTitle.textContent = importFiles.length > 1 ? `Import ${importFiles.length} Files` : 'Confirm Import';
        importFilenameInput.value = importFiles.length === 1 ? importFiles[0].name : '';
        importFilenameInput.disabled = importFiles.length > 1;
        importPreviewContainer.style.display = 'none';
    } else {
        importUrl = data.url;
        importModalTitle.textContent = 'Import from URL';
        importFilenameInput.value = `${data.title || 'video'}.${data.ext || 'mp4'}`;
        importFilenameInput.disabled = false;
        if (data.thumbnail_url) {
            importPreviewThumb.src = data.thumbnail_url;
            importPreviewContainer.style.display = 'block';
        } else {
            importPreviewContainer.style.display = 'none';
        }
        // Pre-select tags if any
        if (data.tags) {
            data.tags.slice(0, 5).forEach(t => importSelectedTags.add(t));
        }
    }
    
    renderImportCategories();
    renderImportTags();
    importModal.classList.add('active');
}

function renderImportCategories() {
    importCategoryGrid.innerHTML = categories.map(cat => `
        <button class="btn btn-outline btn-small ${importSelectedCategoryId === cat.id ? 'active' : ''}" 
                onclick="selectImportCategory(${cat.id})">
            ${escapeHTML(cat.name)}
        </button>
    `).join('');
}

window.selectImportCategory = (id) => {
    importSelectedCategoryId = id;
    renderImportCategories();
};

function renderImportTags() {
    // Current tags from system
    importTagsList.innerHTML = allTags.map(tag => `
        <span class="tag-chip ${importSelectedTags.has(tag) ? 'selected' : ''}" onclick="toggleImportTag('${tag.replace(/'/g, "\\'")}')">
            ${escapeHTML(tag)}
        </span>
    `).join('');
    
    // Selected tags display (with remove button)
    importSelectedTagsDiv.innerHTML = Array.from(importSelectedTags).map(tag => `
        <span class="tag-chip selected">
            ${escapeHTML(tag)} <span style="margin-left: 5px; cursor: pointer;" onclick="toggleImportTag('${tag.replace(/'/g, "\\'")}')">&times;</span>
        </span>
    `).join('');
}

window.toggleImportTag = (tag) => {
    if (importSelectedTags.has(tag)) importSelectedTags.delete(tag);
    else importSelectedTags.add(tag);
    renderImportTags();
};

importTagInput.onkeypress = (e) => {
    if (e.key === 'Enter') {
        const val = importTagInput.value.trim();
        if (val) {
            importSelectedTags.add(val);
            importTagInput.value = '';
            renderImportTags();
        }
    }
};

closeImportBtn.onclick = () => importModal.classList.remove('active');

importConfirmBtn.onclick = async () => {
    importConfirmBtn.disabled = true;
    importConfirmBtn.style.display = 'none';
    importProgress.style.display = 'block';
    importProgressBar.style.width = '0%';
    
    const tagsArr = Array.from(importSelectedTags);
    
    if (importMode === 'upload') {
        for (let i = 0; i < importFiles.length; i++) {
            const file = importFiles[i];
            importStatusText.textContent = `Processing ${i+1}/${importFiles.length}: ${file.name}`;
            
            const thumbnailData = await generateThumbnail(file);
            
            const formData = new FormData();
            formData.append('file', file);
            if (importFiles.length === 1) {
                formData.append('filename', importFilenameInput.value);
            }
            if (thumbnailData) formData.append('thumbnail', thumbnailData);
            if (importSelectedCategoryId) formData.append('category_id', importSelectedCategoryId);
            if (tagsArr.length) formData.append('tags', JSON.stringify(tagsArr));
            
            importStatusText.textContent = `Encrypting ${i+1}/${importFiles.length}: ${file.name}`;
            
            await new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                xhr.open('POST', '/api/files');
                xhr.upload.onprogress = (e) => {
                    if (e.lengthComputable) {
                        const pct = (e.loaded / e.total) * 100;
                        importProgressBar.style.width = `${pct}%`;
                    }
                };
                xhr.onload = () => xhr.status === 200 ? resolve() : reject(new Error('Upload failed'));
                xhr.onerror = () => reject(new Error('Network error'));
                xhr.send(formData);
            });
        }
    } else {
        importStatusText.textContent = 'Streaming from URL into Vault...';
        importProgressBar.style.width = '50%';
        try {
            const res = await fetch('/api/import/url', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    url: importUrl,
                    filename: importFilenameInput.value,
                    category_id: importSelectedCategoryId,
                    tags: tagsArr
                })
            });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || 'Download failed');
            }
        } catch (e) {
            alert('Error: ' + e.message);
            importConfirmBtn.disabled = false;
            importConfirmBtn.style.display = 'block';
            importProgress.style.display = 'none';
            return;
        }
    }
    
    importModal.classList.remove('active');
    fileInput.value = '';
    document.getElementById('file-name-display').textContent = '';
    await Promise.all([loadFiles(), loadCategories(), loadTags()]);
};

importUrlBtn.onclick = async () => {
    const url = importUrlInput.value.trim();
    if (!url) return;
    
    importUrlBtn.disabled = true;
    importUrlBtn.textContent = 'Fetching...';
    try {
        const res = await fetch(`/api/import/preview?url=${encodeURIComponent(url)}`);
        if (res.ok) {
            const data = await res.json();
            data.url = url;
            openImportModal('url', data);
            importUrlInput.value = '';
        } else {
            const data = await res.json();
            alert('Failed: ' + (data.detail || 'Check URL'));
        }
    } catch (e) { console.error(e); alert('Network error'); }
    importUrlBtn.disabled = false;
    importUrlBtn.textContent = 'Fetch Metadata';
};

fileInput.onchange = () => {
    if (fileInput.files.length > 0) {
        openImportModal('upload', fileInput.files);
    }
};

function playFile(id, filename) {
    if (isImage(filename)) {
        videoPlayer.style.display = 'none'; videoPlayer.pause(); videoPlayer.src = '';
        imageViewer.style.display = 'block'; imageViewer.src = `/api/files/${id}`;
    } else {
        imageViewer.style.display = 'none'; imageViewer.src = '';
        videoPlayer.style.display = 'block'; videoPlayer.src = `/api/files/${id}`;
    }
    playerModal.classList.add('active');
}

closeModal.onclick = () => { playerModal.classList.remove('active'); videoPlayer.pause(); videoPlayer.src = ''; imageViewer.src = ''; };

async function lockVault() {
    await fetch('/api/lock', { method: 'POST' });
    vaultContainer.classList.remove('active'); decoyContainer.classList.add('active');
    if (playerModal.classList.contains('active')) closeModal.click();
    if (settingsModal.classList.contains('active')) closeSettings.click();
}

panicBtn.onclick = lockVault;

let escTimer = null;
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
        if (escTimer) { clearTimeout(escTimer); escTimer = null; lockVault(); }
        else {
            escTimer = setTimeout(() => { escTimer = null; }, 500);
            if (playerModal.classList.contains('active')) closeModal.click();
            if (settingsModal.classList.contains('active')) closeSettings.click();
            if (tagManagerModal.classList.contains('active')) closeTagManager.click();
        }
    }
});

window.toggleMenu = (id) => document.getElementById(`menu-${id}`).classList.toggle('active');
document.onclick = () => document.querySelectorAll('.menu-dropdown.active').forEach(el => el.classList.remove('active'));

window.renameFile = async (id, oldName) => {
    openRenameModal('Rename File', oldName, async (newName) => {
        if (!newName || newName === oldName) return;
        try {
            const res = await fetch(`/api/files/${id}/rename`, { 
                method: 'PUT', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify({filename: newName}) 
            });
            if (res.ok) await loadFiles();
            else alert('Failed to rename file');
        } catch(e) { console.error(e); }
    });
};

window.deleteFile = async (id) => {
    if (!confirm('Permanently delete?')) return;
    try {
        const res = await fetch(`/api/files/${id}`, { method: 'DELETE' });
        if (res.ok) await Promise.all([loadFiles(), loadCategories()]);
    } catch(e) {}
};
checkSetupStatus();

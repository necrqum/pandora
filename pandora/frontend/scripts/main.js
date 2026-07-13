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

let autoScrapeEnabled = localStorage.getItem('pandora_autoscrape') !== 'false';
const settingAutoScrape = document.getElementById('setting-autoscrape');
if (settingAutoScrape) {
    settingAutoScrape.checked = autoScrapeEnabled;
    settingAutoScrape.addEventListener('change', (e) => {
        autoScrapeEnabled = e.target.checked;
        localStorage.setItem('pandora_autoscrape', autoScrapeEnabled);
    });
}

const activeTasksIndicator = document.getElementById('active-tasks-indicator');
const activeTasksText = document.getElementById('active-tasks-text');
let activeTasks = [];

function updateTasksUI() {
    if (activeTasks.length > 0) {
        activeTasksIndicator.style.display = 'block';
        activeTasksText.textContent = `${activeTasks.length} downloading...`;
    } else {
        activeTasksIndicator.style.display = 'none';
    }
}

async function pollTasks() {
    if (activeTasks.length === 0) return;
    
    let hasChanges = false;
    for (let i = activeTasks.length - 1; i >= 0; i--) {
        const task = activeTasks[i];
        try {
            const res = await fetch(`/api/import/status/${task.id}`);
            if (res.ok) {
                const data = await res.json();
                if (data.status === 'completed' || data.status === 'error') {
                    activeTasks.splice(i, 1);
                    hasChanges = true;
                }
            } else {
                activeTasks.splice(i, 1);
                hasChanges = true;
            }
        } catch (e) {
            console.error('Error polling task', e);
        }
    }
    
    updateTasksUI();
    
    if (hasChanges) {
        loadFiles();
    }
    
    if (activeTasks.length > 0) {
        setTimeout(pollTasks, 2000);
    }
}

function trackTask(taskId, filename) {
    activeTasks.push({ id: taskId, filename });
    updateTasksUI();
    if (activeTasks.length === 1) {
        pollTasks();
    }
}

const importQueueList = document.getElementById('import-queue-list');
const importQueueCount = document.getElementById('import-queue-count');
const importSelectAllBtn = document.getElementById('import-select-all');
const importSingleFields = document.getElementById('import-single-fields');
const importArtistInput = document.getElementById('import-artist');
const importSourceUrlInput = document.getElementById('import-source-url');

const exportPathInput = document.getElementById('export-path');
const exportBtn = document.getElementById('export-btn');
const purgeMassBtn = document.getElementById('purge-mass-btn');
const purgeEverythingBtn = document.getElementById('purge-everything-btn');

const secureModal = document.getElementById('secure-modal');
const secureModalTitle = document.getElementById('secure-modal-title');
const secureModalText = document.getElementById('secure-modal-text');
const securePassInput = document.getElementById('secure-password-input');
const secureCancelBtn = document.getElementById('secure-cancel-btn');
const secureConfirmBtn = document.getElementById('secure-confirm-btn');

const playerModal = document.getElementById('player-modal');
const videoPlayer = document.getElementById('video-player');
const imageViewer = document.getElementById('image-viewer');
const playerFilename = document.getElementById('player-filename');
const playerNotes = document.getElementById('player-notes');
const playerArtist = document.getElementById('player-artist');
const playerSourceUrl = document.getElementById('player-source-url');
const playerTagsList = document.getElementById('player-tags-list');
const saveNotesBtn = document.getElementById('save-notes-btn');
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
const viewGridBtn = document.getElementById('view-grid-btn');
const viewFolderBtn = document.getElementById('view-folder-btn');
const folderExplorer = document.getElementById('folder-explorer');
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
const bulkScrapeBtn = document.getElementById('bulk-scrape-btn');
const clearSelectionBtn = document.getElementById('clear-selection-btn');
const selectAllBtn = document.getElementById('select-all-btn');
const selectAllGlobalBtn = document.getElementById('select-all-global-btn');

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
let loadedFiles = [];
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
        <li data-id="favorites" class="${currentCategoryId === 'favorites' ? 'active' : ''}">
            <span>⭐ Favorites</span>
            <span class="category-count">${categoryData.favorites || '0'}</span>
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

    const favLi = categoryList.querySelector('[data-id="favorites"]');
    if (favLi) {
        favLi.onclick = () => {
            currentCategoryId = 'favorites';
            currentTagFilter = null;
            currentPage = 1;
            document.getElementById('current-category-title').textContent = 'Favorites';
            renderCategoryList();
            renderSidebarTags();
            loadFiles();
            if (window.innerWidth <= 768) sidebar.classList.remove('active');
        };
    }
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

// --- View Management ---
let currentView = 'grid'; // 'grid' or 'folder'
let folderPath = []; // Breadcrumbs: ["Category", "Tag1", ...]
let folderData = null; // Nested tree from API

viewGridBtn.onclick = () => {
    currentView = 'grid';
    viewGridBtn.classList.add('active');
    viewFolderBtn.classList.remove('active');
    galleryGrid.style.display = 'grid';
    folderExplorer.style.display = 'none';
    paginationControls.style.display = 'flex';
    loadFiles();
};

viewFolderBtn.onclick = async () => {
    currentView = 'folder';
    viewFolderBtn.classList.add('active');
    viewGridBtn.classList.remove('active');
    galleryGrid.style.display = 'none';
    folderExplorer.style.display = 'block';
    paginationControls.style.display = 'none';
    folderPath = [];
    await loadFolderHierarchy();
};

async function loadFolderHierarchy() {
    try {
        const res = await fetch('/api/browse/folders');
        if (res.ok) {
            folderData = await res.json();
            renderFolderExplorer();
        }
    } catch (e) { console.error(e); }
}

function renderFolderExplorer() {
    if (!folderData) return;
    
    let curr = folderData;
    // Traverse to current path
    for (const p of folderPath) {
        if (curr.children && curr.children[p]) {
            curr = curr.children[p];
        } else {
            console.warn("Path not found in hierarchy:", p);
            break;
        }
    }

    folderExplorer.innerHTML = '';
    
    // Render Breadcrumbs
    const bcContainer = document.createElement('div');
    bcContainer.className = 'folder-breadcrumb';
    
    const rootItem = document.createElement('span');
    rootItem.className = 'breadcrumb-item';
    rootItem.textContent = 'Root';
    rootItem.onclick = () => navigateToPath([]);
    bcContainer.appendChild(rootItem);
    
    folderPath.forEach((p, i) => {
        const sep = document.createElement('span');
        sep.className = 'breadcrumb-sep';
        sep.textContent = '/';
        bcContainer.appendChild(sep);
        
        const item = document.createElement('span');
        item.className = 'breadcrumb-item';
        item.textContent = p;
        const targetPath = folderPath.slice(0, i + 1);
        item.onclick = () => navigateToPath(targetPath);
        bcContainer.appendChild(item);
    });
    
    folderExplorer.appendChild(bcContainer);

    const children = Object.values(curr.children || {});
    const files = curr.files || [];
    
    // Render Folders
    children.forEach(c => {
        const row = document.createElement('div');
        row.className = 'folder-row';
        row.innerHTML = `
            <span class="icon">📁</span>
            <span class="name">${escapeHTML(c.name)}</span>
            <span class="count">${Object.keys(c.children || {}).length + (c.files || []).length} items</span>
        `;
        row.onclick = () => navigateToPath([...folderPath, c.name]);
        folderExplorer.appendChild(row);
    });

    // Render Files
    files.forEach(f => {
        const row = document.createElement('div');
        row.className = 'folder-row';
        row.innerHTML = `
            <span class="icon">${isImage(f.filename) ? '🖼️' : '🎬'}</span>
            <span class="name">${escapeHTML(f.filename)}</span>
            <span class="count">${f.is_favorite ? '⭐' : ''}</span>
        `;
        row.onclick = () => playFile(f.id, f.filename);
        folderExplorer.appendChild(row);
    });

    if (children.length === 0 && files.length === 0) {
        const empty = document.createElement('div');
        empty.style.opacity = '0.5';
        empty.style.padding = '2rem';
        empty.textContent = 'Folder is empty';
        folderExplorer.appendChild(empty);
    }
}

window.navigateToPath = (path) => {
    folderPath = path;
    renderFolderExplorer();
};

async function loadFiles() {
    try {
        let url = '/api/files?';
        if (currentCategoryId !== 'all' && currentCategoryId !== 'uncategorized' && currentCategoryId !== 'favorites') {
            url += `category_id=${currentCategoryId}&`;
        }
        if (currentCategoryId === 'favorites') {
            url += `favorite=true&`;
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
        loadedFiles = files; // Store globally for player access
        
        if (currentCategoryId === 'uncategorized') files = files.filter(f => f.category_id === null);
        
        galleryGrid.innerHTML = '';
        renderPagination(data.total, data.per_page);

        // Update result count display
        const resultCountSpan = document.getElementById('search-result-count');
        if (q || currentTagFilter || (currentCategoryId !== 'all' && currentCategoryId !== 'uncategorized' && currentCategoryId !== 'favorites')) {
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
                <div class="card-top-actions" onclick="event.stopPropagation()">
                    <button class="fav-btn ${f.is_favorite ? 'active' : ''}" data-id="${f.id}" title="Toggle Favorite">⭐</button>
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
            
            // Event listeners
            card.querySelector('.fav-btn').onclick = (e) => {
                e.stopPropagation();
                toggleFavorite(f.id);
            };
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
    
    // Jump to page feature
    const jumpContainer = document.createElement('div');
    jumpContainer.style.display = 'flex';
    jumpContainer.style.alignItems = 'center';
    jumpContainer.style.gap = '0.5rem';
    jumpContainer.style.marginLeft = '1rem';
    
    const jumpLabel = document.createElement('span');
    jumpLabel.textContent = `of ${totalPages}`;
    jumpLabel.style.fontSize = '0.9rem';
    jumpLabel.style.color = 'var(--text-muted)';
    
    const jumpInput = document.createElement('input');
    jumpInput.type = 'number';
    jumpInput.min = 1;
    jumpInput.max = totalPages;
    jumpInput.value = currentPage;
    jumpInput.className = 'search-input';
    jumpInput.style.width = '60px';
    jumpInput.style.padding = '4px 8px';
    jumpInput.style.marginBottom = '0';
    jumpInput.style.textAlign = 'center';
    
    const jumpBtn = document.createElement('button');
    jumpBtn.className = 'btn btn-outline btn-small';
    jumpBtn.textContent = 'Go';
    
    const doJump = () => {
        let target = parseInt(jumpInput.value);
        if (isNaN(target)) return;
        target = Math.max(1, Math.min(totalPages, target));
        if (target !== currentPage) {
            currentPage = target;
            loadFiles();
            window.scrollTo(0,0);
        }
    };
    
    jumpBtn.onclick = doJump;
    jumpInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') doJump();
    });
    
    jumpContainer.appendChild(jumpInput);
    jumpContainer.appendChild(jumpLabel);
    jumpContainer.appendChild(jumpBtn);
    paginationControls.appendChild(jumpContainer);
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

selectAllBtn.onclick = () => {
    const cards = Array.from(galleryGrid.querySelectorAll('.media-card'));
    if (cards.length === 0) return;
    
    let allSelected = true;
    for (const card of cards) {
        if (!selectedFileIds.has(card.dataset.id)) {
            allSelected = false;
            break;
        }
    }
    
    if (allSelected) {
        cards.forEach(card => selectedFileIds.delete(card.dataset.id));
    } else {
        cards.forEach(card => selectedFileIds.add(card.dataset.id));
    }
    
    updateSelectionUI();
};

selectAllGlobalBtn.onclick = async () => {
    selectAllGlobalBtn.disabled = true;
    selectAllGlobalBtn.textContent = 'Loading...';
    try {
        let url = '/api/files/ids?';
        if (currentCategoryId !== 'all' && currentCategoryId !== 'uncategorized' && currentCategoryId !== 'favorites') {
            url += `category_id=${currentCategoryId}&`;
        }
        if (currentCategoryId === 'favorites') {
            url += `favorite=true&`;
        }
        let q = searchInput.value.trim();
        if (currentTagFilter) {
            q = q ? `${q} tag:${currentTagFilter}` : `tag:${currentTagFilter}`;
        }
        if (q) {
            url += `q=${encodeURIComponent(q)}&`;
        }

        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to fetch IDs');
        const data = await res.json();
        
        if (data.ids.length === 0) return;
        
        let allSelected = true;
        for (const id of data.ids) {
            if (!selectedFileIds.has(id)) {
                allSelected = false;
                break;
            }
        }

        if (allSelected) {
            data.ids.forEach(id => selectedFileIds.delete(id));
        } else {
            data.ids.forEach(id => selectedFileIds.add(id));
        }

        updateSelectionUI();
    } catch (err) {
        console.error(err);
        alert('Failed to select all files globally.');
    } finally {
        selectAllGlobalBtn.disabled = false;
        selectAllGlobalBtn.textContent = 'Select All (Global)';
    }
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

bulkScrapeBtn.onclick = async () => {
    if (!confirm(`Scrape metadata from source URLs for ${selectedFileIds.size} files?`)) return;
    bulkScrapeBtn.disabled = true;
    bulkScrapeBtn.textContent = '...';
    try {
        await batchRequest('/api/files/batch/scrape', { file_ids: Array.from(selectedFileIds) });
    } catch(e) {
        alert('Scrape failed: ' + e);
    } finally {
        bulkScrapeBtn.disabled = false;
        bulkScrapeBtn.textContent = 'Scrape Metadata';
    }
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
    // Load duplicate mode setting
    try {
        const res = await fetch('/api/settings/duplicate-mode');
        if (res.ok) {
            const data = await res.json();
            document.getElementById('setting-duplicate-mode').value = data.mode;
        }
    } catch (e) { console.error(e); }
};

document.getElementById('setting-duplicate-mode').addEventListener('change', async (e) => {
    try {
        await fetch('/api/settings/duplicate-mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: e.target.value })
        });
    } catch (err) { console.error(err); }
});

closeSettings.onclick = () => settingsModal.classList.remove('active');

// --- Backfill hashes for old files ---
document.getElementById('backfill-btn').addEventListener('click', async () => {
    const btn = document.getElementById('backfill-btn');
    const wrap = document.getElementById('backfill-progress-wrap');
    const bar = document.getElementById('backfill-bar');
    const statusText = document.getElementById('backfill-status-text');

    btn.disabled = true;
    wrap.style.display = 'block';
    statusText.textContent = 'Starting scan...';
    bar.style.width = '0%';

    try {
        const startRes = await fetch('/api/settings/backfill-hashes', { method: 'POST' });
        if (!startRes.ok) {
            const err = await startRes.json();
            statusText.textContent = 'Error: ' + (err.detail || 'Failed to start');
            btn.disabled = false;
            return;
        }
    } catch (e) {
        statusText.textContent = 'Network error starting backfill.';
        btn.disabled = false;
        return;
    }

    // Poll for progress
    const pollInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/settings/backfill-hashes/status');
            if (!res.ok) return;
            const data = await res.json();
            const pct = data.total > 0 ? Math.round((data.done / data.total) * 100) : 0;
            bar.style.width = `${pct}%`;
            statusText.textContent = `Scanning: ${data.done} / ${data.total} files (${pct}%)${data.errors > 0 ? ` — ${data.errors} error(s)` : ''}`;

            if (!data.running) {
                clearInterval(pollInterval);
                bar.style.width = '100%';
                statusText.textContent = `✅ Done! ${data.done} files fingerprinted.${data.errors > 0 ? ` ${data.errors} error(s) — check logs.` : ''}`;
                btn.disabled = false;
                btn.textContent = '✅ Scan Complete';
            }
        } catch (e) { console.error(e); }
    }, 1000);
});

async function openSecurePrompt(title, text) {
    return new Promise((resolve) => {
        secureModalTitle.textContent = title;
        secureModalText.textContent = text;
        securePassInput.value = '';
        secureModal.classList.add('active');
        securePassInput.focus();
        
        secureCancelBtn.onclick = () => {
            secureModal.classList.remove('active');
            resolve(null);
        };
        
        secureConfirmBtn.onclick = () => {
            const pw = securePassInput.value;
            secureModal.classList.remove('active');
            resolve(pw);
        };
        
        securePassInput.onkeypress = (e) => {
            if (e.key === 'Enter') secureConfirmBtn.click();
        };
    });
}

exportBtn.onclick = async () => {
    const target = exportPathInput.value.trim();
    if (!target) return alert('Target path required');
    const password = await openSecurePrompt('Export Box', 'Confirm Master Password to begin decryption/export to: ' + target);
    if (!password) return;

    exportBtn.disabled = true;
    exportBtn.textContent = 'Exporting...';
    try {
        const res = await fetch('/api/settings/export', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ password, target_path: target })
        });
        if (res.ok) {
            const data = await res.json();
            alert(`Export successful! ${data.exported_count} files decrypted.`);
        } else {
            const data = await res.json();
            alert('Export failed: ' + (data.detail || 'Check password/path'));
        }
    } catch (e) { alert('Network error during export'); }
    exportBtn.disabled = false;
    exportBtn.textContent = 'Start Export';
};

purgeMassBtn.onclick = async () => {
    const password = await openSecurePrompt('Wipe All Media', 'DANGER: This will permanently delete ALL encrypted media files. Metadata will also be cleared.');
    if (!password) return;

    try {
        const res = await fetch('/api/settings/purge', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ password, purge_type: 'mass' })
        });
        if (res.ok) { alert('All media has been wiped.'); location.reload(); }
        else { alert('Failed: Invalid password'); }
    } catch (e) { alert('Network error'); }
};

purgeEverythingBtn.onclick = async () => {
    const password = await openSecurePrompt('NUCLEAR RESET', 'ULTIMATE DANGER: This will delete EVERYTHING (Database, Keys, Files) and shutdown the server.');
    if (!password) return;

    try {
        const res = await fetch('/api/settings/purge', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ password, purge_type: 'everything' })
        });
        if (res.ok) { alert('System wiped. Server is shutting down.'); window.close(); }
        else { alert('Failed: Invalid password'); }
    } catch (e) { alert('Network error'); }
};

restartBtn.onclick = async () => {
    if (!confirm('Restart server?')) return;
    try { 
        const res = await fetch('/api/server/restart', {method: 'POST'}); 
        if (!res.ok) throw new Error(await res.text());
        alert('Server restarting...'); 
        location.reload(); 
    } catch(e) {
        alert('Restart failed: ' + e);
    }
};

shutdownBtn.onclick = async () => {
    if (!confirm('Shutdown server?')) return;
    try { 
        const res = await fetch('/api/server/shutdown', {method: 'POST'}); 
        if (!res.ok) throw new Error(await res.text());
        document.body.innerHTML = `
            <div style="display:flex;justify-content:center;align-items:center;height:100vh;flex-direction:column;font-family:sans-serif;background:#1a1a1a;color:white;">
                <h1 style="color:#ff4444;">Server Shutting Down</h1>
                <p>The vault has been locked and the server is stopping.</p>
                <p>You can close this tab now.</p>
            </div>
        `;
    } catch(e) {
        alert('Shutdown failed: ' + e);
    }
};

async function generateThumbnail(file) {
    return new Promise((resolve) => {
        // Skip client-side generation for videos to prevent browser memory exhaustion/freezes during mass imports.
        // The backend uses FFmpeg which is much safer and faster for large media files.
        if (!file.type.startsWith('image/')) {
            resolve(null);
            return;
        }

        const url = URL.createObjectURL(file);
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        const maxSize = 200;
        let resolved = false;
        const safeResolve = (val) => { if (!resolved) { resolved = true; resolve(val); } };
        
        setTimeout(() => { URL.revokeObjectURL(url); safeResolve(null); }, 3000);
        
        const img = new Image();
        img.onload = () => {
            const scale = Math.min(maxSize / img.width, maxSize / img.height);
            canvas.width = img.width * scale; canvas.height = img.height * scale;
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            URL.revokeObjectURL(url); 
            safeResolve(canvas.toDataURL('image/jpeg', 0.6));
        };
        img.onerror = () => { URL.revokeObjectURL(url); safeResolve(null); };
        img.src = url;
    });
}

// --- Import Flow ---
let importQueue = [];

function openImportModal(mode, data) {
    importQueue = [];
    importProgress.style.display = 'none';
    importConfirmBtn.disabled = false;
    importConfirmBtn.style.display = 'block';
    
    if (mode === 'upload') {
        const files = Array.from(data);
        importQueue = files.map((f, i) => ({
            id: i,
            file: f,
            filename: f.name,
            categoryId: null,
            tags: new Set(),
            artist: '',
            source_url: '',
            selected: true,
            mode: 'upload',
            fileThumbnail: null
        }));
        importModalTitle.textContent = `Import Files (${importQueue.length})`;
        
        // Async generate thumbnails for the queue
        importQueue.forEach(item => {
            generateThumbnail(item.file).then(t => {
                item.fileThumbnail = t;
                renderImportQueue();
            });
        });
    } else {
        if (data.is_playlist) {
            importQueue = data.entries.map((entry, i) => ({
                id: i,
                url: data.url,
                playlist_index: entry.playlist_index,
                filename: autoScrapeEnabled ? `${entry.title || 'video'}.${entry.ext || 'mp4'}` : `video_${i+1}.${entry.ext || 'mp4'}`,
                categoryId: null,
                tags: autoScrapeEnabled ? new Set(entry.tags ? entry.tags.slice(0, 5) : []) : new Set(),
                artist: autoScrapeEnabled ? (entry.uploader || '') : '',
                source_url: entry.webpage_url || data.url,
                selected: true,
                mode: 'url',
                thumbnail: entry.thumbnail_url
            }));
            importModalTitle.textContent = `Import Playlist (${importQueue.length})`;
        } else {
            importQueue = [{
                id: 0,
                url: data.url,
                filename: autoScrapeEnabled ? `${data.title || 'video'}.${data.ext || 'mp4'}` : `video.${data.ext || 'mp4'}`,
                categoryId: null,
                tags: autoScrapeEnabled ? new Set(data.tags ? data.tags.slice(0, 5) : []) : new Set(),
                artist: autoScrapeEnabled ? (data.uploader || '') : '',
                source_url: data.url,
                selected: true,
                mode: 'url',
                thumbnail: data.thumbnail_url
            }];
            importModalTitle.textContent = 'Import from URL';
        }
    }
    
    renderImportQueue();
    updateBulkUI();
    importModal.classList.add('active');
}

function renderImportQueue() {
    importQueueCount.textContent = importQueue.length;
    importQueueList.innerHTML = importQueue.map(item => {
        const thumb = item.thumbnail || (item.fileThumbnail ? item.fileThumbnail : '');
        const isSkipped = item._skipped;
        const isReplaced = item._replaced;

        let statusBadge = '';
        if (isSkipped) {
            statusBadge = `<span title="Already in vault — will be skipped" style="font-size:0.65rem; background: rgba(180,150,0,0.25); color: #f0c040; border: 1px solid rgba(240,192,64,0.4); border-radius: 4px; padding: 1px 5px; flex-shrink:0;">⚠ EXISTS</span>`;
        } else if (isReplaced) {
            statusBadge = `<span title="Already in vault — will be replaced" style="font-size:0.65rem; background: rgba(220,100,0,0.25); color: #ff8c42; border: 1px solid rgba(255,140,66,0.4); border-radius: 4px; padding: 1px 5px; flex-shrink:0;">↩ REPLACE</span>`;
        }

        return `
            <div class="queue-item ${item.selected ? 'selected' : ''}" onclick="toggleQueueItem(${item.id})" style="${isSkipped ? 'opacity:0.45; pointer-events: none;' : ''}">
                <input type="checkbox" ${item.selected ? 'checked' : ''} ${isSkipped ? 'disabled' : ''} onclick="event.stopPropagation(); toggleQueueItem(${item.id})">
                <div style="width: 40px; height: 40px; border-radius: 4px; overflow: hidden; background: #000; flex-shrink: 0;">
                    ${thumb ? `<img src="${thumb}" style="width: 100%; height: 100%; object-fit: cover;" />` : `<div style="display:flex;align-items:center;justify-content:height:100%;font-size:1.2rem;">${isImage(item.filename) ? '🖼️' : '🎬'}</div>`}
                </div>
                <div style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.8rem;">
                    ${escapeHTML(item.filename)}
                </div>
                ${statusBadge}
                ${!isSkipped && item.categoryId ? `<span class="category-count" style="font-size: 0.6rem; opacity: 1;">${categories.find(c=>c.id===item.categoryId)?.name || ''}</span>` : ''}
            </div>
        `;
    }).join('');
}


window.toggleQueueItem = (id) => {
    const item = importQueue.find(i => i.id === id);
    if (item) {
        item.selected = !item.selected;
        renderImportQueue();
        updateBulkUI();
    }
};

importSelectAllBtn.onclick = () => {
    const allSelected = importQueue.every(i => i.selected);
    importQueue.forEach(i => i.selected = !allSelected);
    renderImportQueue();
    updateBulkUI();
};

window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
        if (importModal.classList.contains('active')) {
            e.preventDefault();
            importSelectAllBtn.click();
        }
    }
});

function updateBulkUI() {
    const selected = importQueue.filter(i => i.selected);
    if (selected.length === 1 && selected[0].mode === 'url' && selected[0].thumbnail) {
        importPreviewThumb.src = selected[0].thumbnail;
        importPreviewContainer.style.display = 'block';
    } else {
        importPreviewContainer.style.display = 'none';
    }
    
    if (selected.length === 1) {
        importFilenameInput.value = selected[0].filename;
        importArtistInput.value = selected[0].artist || '';
        importSourceUrlInput.value = selected[0].source_url || '';
        importSingleFields.style.display = 'block';
    } else {
        importSingleFields.style.display = 'none';
    }

    renderImportCategories();
    renderImportTags();
}

function renderImportCategories() {
    const selected = importQueue.filter(i => i.selected);
    const firstCatId = selected.length > 0 ? selected[0].categoryId : null;

    importCategoryGrid.innerHTML = categories.map(cat => `
        <button class="btn btn-outline btn-small ${firstCatId === cat.id ? 'active' : ''}" 
                onclick="selectImportCategory(${cat.id})">
            ${escapeHTML(cat.name)}
        </button>
    `).join('');
}

window.selectImportCategory = (id) => {
    importQueue.filter(i => i.selected).forEach(i => i.categoryId = id);
    renderImportQueue();
    renderImportCategories();
};

function renderImportTags() {
    const selected = importQueue.filter(i => i.selected);
    const activeTags = selected.length > 0 ? selected[0].tags : new Set();

    // Intersection of all existing tags + any NEW tags added in this session
    const sessionTags = new Set(allTags);
    importQueue.forEach(item => {
        item.tags.forEach(t => sessionTags.add(t));
    });

    importTagsList.innerHTML = Array.from(sessionTags).map(tag => `
        <span class="tag-chip ${activeTags.has(tag) ? 'selected' : ''}" onclick="toggleImportTag('${tag.replace(/'/g, "\\'")}')">
            ${escapeHTML(tag)}
        </span>
    `).join('');
    
    importSelectedTagsDiv.innerHTML = Array.from(activeTags).map(tag => `
        <span class="tag-chip selected">
            ${escapeHTML(tag)} <span style="margin-left: 5px; cursor: pointer;" onclick="toggleImportTag('${tag.replace(/'/g, "\\'")}')">&times;</span>
        </span>
    `).join('');
}

window.toggleImportTag = (tag) => {
    importQueue.filter(i => i.selected).forEach(i => {
        if (i.tags.has(tag)) i.tags.delete(tag);
        else i.tags.add(tag);
    });
    renderImportTags();
};

importTagInput.onkeypress = (e) => {
    if (e.key === 'Enter') {
        const val = importTagInput.value.trim();
        if (val) {
            importQueue.filter(i => i.selected).forEach(i => i.tags.add(val));
            importTagInput.value = '';
            renderImportTags();
        }
    }
};

closeImportBtn.onclick = () => importModal.classList.remove('active');

importConfirmBtn.onclick = async () => {
    // Capture any unsaved tag in the input field
    const pendingTag = importTagInput.value.trim();
    if (pendingTag) {
        importQueue.filter(i => i.selected).forEach(i => i.tags.add(pendingTag));
        importTagInput.value = '';
    }

    const selectedItems = importQueue.filter(i => i.selected);
    if (selectedItems.length === 0) return alert('No files selected');

    if (selectedItems.length === 1) {
        selectedItems[0].filename = importFilenameInput.value.trim();
        selectedItems[0].artist = importArtistInput.value.trim();
        selectedItems[0].source_url = importSourceUrlInput.value.trim();
    }

    importConfirmBtn.disabled = true;
    importConfirmBtn.style.display = 'none';
    importProgress.style.display = 'block';
    
    let pendingUploads = [];
    let pendingUrls = [];
    
    for (const item of selectedItems) {
        if (item.mode === 'upload') pendingUploads.push(item);
        else pendingUrls.push(item);
    }
    
    // Dispatch URL tasks (they return immediately)
    if (pendingUrls.length > 0) {
        importStatusText.textContent = `Dispatching URL downloads...`;
        importProgressBar.style.width = '30%';
        for (const item of pendingUrls) {
            const tagsArr = Array.from(item.tags);
            try {
                const res = await fetch('/api/import/url', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        url: item.url,
                        playlist_index: item.playlist_index,
                        filename: item.filename,
                        category_id: item.categoryId,
                        tags: tagsArr,
                        artist: item.artist,
                        source_url: item.source_url
                    })
                });
                if (res.ok) {
                    const data = await res.json();
                    if (data.task_id) {
                        trackTask(data.task_id, item.filename);
                    }
                }
            } catch (e) { console.error(e); }
        }
    }
    
    // Process physical uploads
    for (let i = 0; i < pendingUploads.length; i++) {
        const item = pendingUploads[i];
        const tagsArr = Array.from(item.tags);
        const pct = ((i) / pendingUploads.length) * 100;
        importProgressBar.style.width = `${pct}%`;
        importStatusText.textContent = `Uploading ${i+1}/${pendingUploads.length}: ${item.filename}`;

        const thumbnailData = await generateThumbnail(item.file);
        const formData = new FormData();
        formData.append('file', item.file);
        formData.append('filename', item.filename);
        if (thumbnailData) formData.append('thumbnail', thumbnailData);
        if (item.categoryId) formData.append('category_id', item.categoryId);
        if (tagsArr.length) formData.append('tags', JSON.stringify(tagsArr));
        if (item.artist) formData.append('artist', item.artist);
        if (item.source_url) formData.append('source_url', item.source_url);
        
        try {
            await new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                xhr.open('POST', '/api/files');
                xhr.onload = () => {
                    if (xhr.status === 200) {
                        resolve();
                    } else if (xhr.status === 409) {
                        // Duplicate detected
                        try {
                            const resp = JSON.parse(xhr.responseText);
                            item._duplicateOf = resp.existing_filename || 'existing file';
                        } catch {}
                        // In 'replace' mode the server processes it, so this shouldn't happen
                        // but if mode changed mid-import, treat as skipped
                        item._skipped = true;
                        resolve();
                    } else {
                        reject(new Error(`Upload failed (${xhr.status})`));
                    }
                };
                xhr.onerror = () => reject(new Error('Network error'));
                xhr.send(formData);
            });
        } catch (e) { console.error(e); }

        // Re-render queue live so user sees status badges update
        renderImportQueue();
    }
    
    importProgressBar.style.width = '100%';
    const skipped = selectedItems.filter(i => i._skipped);
    if (skipped.length > 0) {
        importStatusText.textContent = `Complete! ${skipped.length} duplicate(s) skipped. Check settings to change this.`;
    } else {
        importStatusText.textContent = 'Complete! Background tasks running...';
    }
    setTimeout(() => {
        importModal.classList.remove('active');
        fileInput.value = '';
        document.getElementById('file-name-display').textContent = '';
        Promise.all([loadFiles(), loadCategories(), loadTags()]);
    }, skipped.length > 0 ? 3000 : 1000);
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
    const file = loadedFiles.find(f => f.id === id);
    playerFilename.textContent = filename;
    playerNotes.value = file ? (file.notes || '') : '';
    playerArtist.value = file ? (file.artist || '') : '';
    playerSourceUrl.value = file ? (file.source_url || '') : '';
    let tempTags = file ? [...file.tags] : [];

    const playerFetchMetaBtn = document.getElementById('player-fetch-meta-btn');
    playerFetchMetaBtn.onclick = async () => {
        const url = playerSourceUrl.value.trim();
        if (!url) { alert('Please enter a source URL first.'); return; }
        playerFetchMetaBtn.disabled = true;
        playerFetchMetaBtn.textContent = '...';
        try {
            const res = await fetch(`/api/import/preview?url=${encodeURIComponent(url)}`);
            if (res.ok) {
                const meta = await res.json();
                if (meta.uploader) playerArtist.value = meta.uploader;
                if (meta.tags) {
                    const currentTagSet = new Set(tempTags);
                    meta.tags.slice(0, 5).forEach(t => {
                        if (!currentTagSet.has(t)) tempTags.push(t);
                    });
                    renderPlayerTags();
                }
            } else {
                alert('Failed to fetch metadata: ' + await res.text());
            }
        } catch(e) {
            alert('Error fetching metadata: ' + e);
        } finally {
            playerFetchMetaBtn.disabled = false;
            playerFetchMetaBtn.textContent = 'Scrape';
        }
    };

    function renderPlayerTags() {
        playerTagsList.innerHTML = tempTags.map((t, i) => `
            <div class="folder-row" style="padding: 0.4rem 0.75rem; background: rgba(255,255,255,0.05);">
                <span style="flex: 1; font-size: 0.85rem;">${escapeHTML(t)}</span>
                <div style="display: flex; gap: 4px;">
                    <button class="btn btn-outline btn-xs" onclick="moveTag(${i}, -1)" ${i === 0 ? 'disabled' : ''}>↑</button>
                    <button class="btn btn-outline btn-xs" onclick="moveTag(${i}, 1)" ${i === tempTags.length - 1 ? 'disabled' : ''}>↓</button>
                </div>
            </div>
        `).join('');
    }

    window.moveTag = (idx, dir) => {
        const target = idx + dir;
        if (target < 0 || target >= tempTags.length) return;
        const arr = [...tempTags];
        [arr[idx], arr[target]] = [arr[target], arr[idx]];
        tempTags = arr;
        renderPlayerTags();
    };

    saveNotesBtn.onclick = async () => {
        const notes = playerNotes.value;
        const artist = playerArtist.value;
        const source_url = playerSourceUrl.value;
        
        saveNotesBtn.disabled = true;
        saveNotesBtn.textContent = 'Saving...';
        try {
            // Save Metadata (Notes, Artist, URL)
            await fetch(`/api/files/${id}/metadata`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({notes, artist, source_url})
            });
            // Save Ordered Tags
            await fetch(`/api/files/${id}/tags`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({tags: tempTags})
            });
            
            if (file) {
                file.notes = notes;
                file.artist = artist;
                file.source_url = source_url;
                file.tags = tempTags;
            }
            alert('Metadata saved!');
            loadFiles(); // Refresh gallery to show new tag order
        } catch (e) { console.error(e); }
        saveNotesBtn.disabled = false;
        saveNotesBtn.textContent = 'Save Metadata';
    };

    renderPlayerTags();
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

window.toggleFavorite = async (id) => {
    try {
        const res = await fetch(`/api/files/${id}/favorite`, { method: 'POST' });
        if (res.ok) {
            const data = await res.json();
            const btn = document.querySelector(`.media-card[data-id="${id}"] .fav-btn`);
            if (btn) btn.classList.toggle('active', data.is_favorite);
        }
    } catch (e) { console.error(e); }
};

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
        if (res.ok) {
            await Promise.all([loadFiles(), loadCategories()]);
        } else {
            alert('Delete failed: ' + await res.text());
        }
    } catch(e) {
        alert('Delete failed: ' + e);
    }
};
checkSetupStatus();

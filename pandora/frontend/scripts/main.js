const decoyContainer = document.getElementById('decoy-container');
const vaultContainer = document.getElementById('vault-container');
const passInput = document.getElementById('master-password');
const loginBtn = document.getElementById('login-btn');
const errorDiv = document.getElementById('login-error');

const fileInput = document.getElementById('file-input');
const uploadBtn = document.getElementById('upload-btn');
const galleryGrid = document.getElementById('gallery-grid');

const playerModal = document.getElementById('player-modal');
const videoPlayer = document.getElementById('video-player');
const closeModal = document.getElementById('close-modal');
const panicBtn = document.getElementById('panic-btn');

// --- Auth Flow ---
async function authenticate() {
    const password = passInput.value;
    if (!password) return;
    
    errorDiv.textContent = 'Authenticating...';
    
    try {
        // Try unlock first
        let res = await fetch('/api/unlock', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({password})
        });
        
        if (res.status === 400) {
            // Not initialized, try init
            res = await fetch('/api/init', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({password})
            });
        }
        
        if (res.ok) {
            showVault();
        } else {
            const data = await res.json();
            errorDiv.textContent = data.detail || 'Authentication failed';
        }
    } catch (e) {
        errorDiv.textContent = 'Network error';
    }
}

loginBtn.addEventListener('click', authenticate);
passInput.addEventListener('keypress', e => {
    if (e.key === 'Enter') authenticate();
});

// --- Vault Flow ---
function showVault() {
    decoyContainer.classList.remove('active');
    vaultContainer.classList.add('active');
    passInput.value = '';
    errorDiv.textContent = '';
    loadFiles();
}

async function loadFiles() {
    try {
        const res = await fetch('/api/files');
        if (res.status === 401) {
            lockVault();
            return;
        }
        const files = await res.json();
        galleryGrid.innerHTML = '';
        
        files.forEach(f => {
            const card = document.createElement('div');
            card.className = 'media-card';
            card.innerHTML = `
                <div class="icon">🎬</div>
                <div class="title" title="${f.filename}">${f.filename}</div>
            `;
            card.onclick = () => playFile(f.id);
            galleryGrid.appendChild(card);
        });
    } catch (e) {
        console.error(e);
    }
}

// --- Upload Flow ---
uploadBtn.addEventListener('click', async () => {
    const file = fileInput.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    uploadBtn.textContent = 'Encrypting...';
    uploadBtn.disabled = true;
    
    try {
        const res = await fetch('/api/files', {
            method: 'POST',
            body: formData
        });
        
        if (res.ok) {
            fileInput.value = '';
            loadFiles();
        } else {
            alert('Upload failed');
        }
    } catch (e) {
        console.error(e);
    } finally {
        uploadBtn.textContent = 'Encrypt & Store';
        uploadBtn.disabled = false;
    }
});

// --- Player Flow ---
function playFile(id) {
    // We stream the decrypted bytes directly from the server
    videoPlayer.src = `/api/files/${id}`;
    playerModal.classList.add('active');
}

closeModal.addEventListener('click', () => {
    playerModal.classList.remove('active');
    videoPlayer.pause();
    videoPlayer.src = '';
});

// --- Panic / Lock Flow ---
async function lockVault() {
    await fetch('/api/lock', { method: 'POST' });
    vaultContainer.classList.remove('active');
    decoyContainer.classList.add('active');
    
    if (playerModal.classList.contains('active')) {
        playerModal.classList.remove('active');
        videoPlayer.pause();
        videoPlayer.src = '';
    }
}

panicBtn.addEventListener('click', lockVault);

// Double Esc to Panic
let escTimer = null;
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
        if (escTimer) {
            clearTimeout(escTimer);
            escTimer = null;
            lockVault();
        } else {
            escTimer = setTimeout(() => { escTimer = null; }, 500);
            // Single escape closes modal if open
            if (playerModal.classList.contains('active')) {
                closeModal.click();
            }
        }
    }
});

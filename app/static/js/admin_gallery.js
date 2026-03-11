document.addEventListener('DOMContentLoaded', async () => {
    const galleryGrid = document.getElementById('gallery-grid');
    const galleryFilter = document.getElementById('gallery-filter');
    const refreshBtn = document.getElementById('btn-refresh-gallery');
    const galleryLoading = document.getElementById('gallery-loading');
    const galleryEmpty = document.getElementById('gallery-empty');

    // Upload Elements
    const uploadBtn = document.getElementById('btn-upload-gallery');
    const uploadModalEl = document.getElementById('galleryUploadModal');
    let uploadModal;
    if (uploadModalEl && window.bootstrap) {
        uploadModal = new bootstrap.Modal(uploadModalEl);
    }
    const fileInput = document.getElementById('gallery-file-input');
    const filenameInput = document.getElementById('gallery-filename-input');
    const confirmUploadBtn = document.getElementById('btn-gallery-upload-confirm');

    // Folder Upload Elements
    const uploadFolderBtn = document.getElementById('btn-upload-folder-gallery');
    const folderModalEl = document.getElementById('galleryFolderUploadModal');
    let folderModal;
    if (folderModalEl && window.bootstrap) {
        folderModal = new bootstrap.Modal(folderModalEl);
    }
    const folderInput = document.getElementById('gallery-folder-input');
    const folderOptions = document.getElementById('folder-upload-options');
    const nameRenameRadio = document.getElementById('nameRename');
    const prefixContainer = document.getElementById('folder-prefix-container');
    const prefixInput = document.getElementById('gallery-folder-prefix');
    const progressContainer = document.getElementById('folder-upload-progress-container');
    const progressBar = document.getElementById('folder-upload-progress-bar');
    const progressStats = document.getElementById('folder-upload-stats');
    const progressStatus = document.getElementById('folder-upload-status');
    const confirmFolderUploadBtn = document.getElementById('btn-gallery-folder-upload-confirm');

    if (!galleryGrid) return; // Only run if element exists

    let allPhotos = [];

    async function loadGallery() {
        if (!galleryGrid) return;

        galleryLoading.classList.remove('d-none');
        galleryGrid.innerHTML = '';
        galleryEmpty.classList.add('d-none');

        try {
            const res = await fetch('/api/admin/gallery');
            if (res.ok) {
                allPhotos = await res.json();
                renderGallery();
            } else {
                console.error('Failed to load gallery');
                galleryGrid.innerHTML = '<div class="alert alert-danger w-100">Failed to load gallery.</div>';
            }
        } catch (err) {
            console.error(err);
            galleryGrid.innerHTML = '<div class="alert alert-danger w-100">Network error.</div>';
        } finally {
            galleryLoading.classList.add('d-none');
        }
    }

    async function renderGallery() {
        galleryGrid.innerHTML = '';
        const filter = galleryFilter.value; // all, unused, linked

        const filtered = allPhotos.filter(p => {
            if (filter === 'all') return true;
            if (filter === 'unused') return !p.is_linked;
            if (filter === 'linked') return p.is_linked;
            return true;
        });

        if (filtered.length === 0) {
            galleryEmpty.classList.remove('d-none');
            return;
        } else {
            galleryEmpty.classList.add('d-none');
        }

        filtered.forEach(photo => {
            const col = document.createElement('div');
            col.className = 'col-6 col-md-4 col-lg-3 col-xl-2';

            const card = document.createElement('div');
            card.className = 'card h-100 shadow-sm position-relative';

            // Status Badge
            const badge = document.createElement('span');
            badge.className = `position-absolute top-0 end-0 badge rounded-pill m-2 ${photo.is_linked ? 'bg-success' : 'bg-warning text-dark'}`;
            badge.textContent = photo.is_linked ? 'Linked' : 'Unused';
            card.appendChild(badge);

            // Image Container
            const imgContainer = document.createElement('div');
            imgContainer.style.height = '150px';
            imgContainer.style.overflow = 'hidden';
            imgContainer.className = 'bg-light d-flex align-items-center justify-content-center';

            const img = document.createElement('img');
            img.src = photo.url; // Use icon?
            // Actually, backend returns generic URL. Let's try to use icon if possible to save bandwidth,
            // but the backend list currently returns 'url'.
            // We can try to append _icon to display, but fallback to main.
            // Let's just use the url provided.
            img.className = 'card-img-top';
            img.style.width = '100%';
            img.style.height = '100%';
            img.style.objectFit = 'cover';
            img.alt = photo.filename;

            imgContainer.appendChild(img);
            card.appendChild(imgContainer);

            // Body
            const body = document.createElement('div');
            body.className = 'card-body p-2 d-flex flex-column';

            const title = document.createElement('small');
            title.className = 'text-truncate fw-bold mb-1 d-block';
            title.textContent = photo.filename;
            title.title = photo.filename;
            body.appendChild(title);

            // Linked Info
            if (photo.is_linked && photo.linked_to.length > 0) {
                const info = document.createElement('div');
                info.className = 'small text-muted mb-2 overflow-auto';
                info.style.maxHeight = '60px';

                // Show first link + count
                const first = photo.linked_to[0];
                const count = photo.linked_to.length;

                const linkText = document.createElement('div');
                linkText.innerHTML = `<i class="fas fa-link"></i> ${first.name} (${first.sku})`;
                info.appendChild(linkText);

                if (count > 1) {
                    const more = document.createElement('div');
                    more.className = 'fst-italic';
                    more.textContent = `+ ${count - 1} more`;
                    info.appendChild(more);
                }

                // Tooltip logic could go here
                card.title = photo.linked_to.map(l => `${l.type}: ${l.name} (${l.sku})`).join('\n');

                body.appendChild(info);
            } else {
                const spacer = document.createElement('div');
                spacer.className = 'flex-grow-1';
                body.appendChild(spacer);
            }

            // Actions
            const actions = document.createElement('div');
            actions.className = 'mt-auto d-flex justify-content-between align-items-center pt-2 border-top';

            // View Button (Open in new tab)
            const viewBtn = document.createElement('a');
            viewBtn.href = photo.url;
            viewBtn.target = '_blank';
            viewBtn.className = 'btn btn-sm btn-link text-decoration-none p-0';
            viewBtn.innerHTML = '<i class="fas fa-eye"></i> View';

            // Copy Button
            const copyBtn = document.createElement('button');
            copyBtn.className = 'btn btn-sm btn-link text-decoration-none p-0 mx-2 text-secondary';
            copyBtn.innerHTML = '<i class="fas fa-copy"></i> Copy';
            copyBtn.title = 'Copy image path';
            copyBtn.onclick = (e) => {
                e.preventDefault();
                // Copy relative path (photo.url)
                navigator.clipboard.writeText(photo.url).then(() => {
                    const originalHTML = copyBtn.innerHTML;
                    copyBtn.innerHTML = '<i class="fas fa-check"></i> Copied!';
                    copyBtn.classList.remove('text-secondary');
                    copyBtn.classList.add('text-success');
                    setTimeout(() => {
                        copyBtn.innerHTML = originalHTML;
                        copyBtn.classList.remove('text-success');
                        copyBtn.classList.add('text-secondary');
                    }, 2000);
                }).catch(err => {
                    console.error('Failed to copy: ', err);
                });
            };

            // Delete Button
            const delBtn = document.createElement('button');
            delBtn.className = 'btn btn-sm btn-outline-danger py-0 px-2';
            delBtn.innerHTML = '<i class="fas fa-trash"></i>';
            delBtn.title = photo.is_linked ? 'Cannot delete linked photo' : 'Delete photo';

            if (photo.is_linked) {
                delBtn.disabled = true;
            } else {
                delBtn.onclick = () => deletePhoto(photo.filename);
            }

            actions.appendChild(viewBtn);
            actions.appendChild(copyBtn);
            actions.appendChild(delBtn);
            body.appendChild(actions);

            card.appendChild(body);
            col.appendChild(card);
            galleryGrid.appendChild(col);
        });
    }

    async function deletePhoto(filename) {
        if (!await confirm(`Delete ${filename}? This includes _icon and _big variants.`)) return;

        try {
            const headers = {};
            const csrfToken = document.querySelector('meta[name="csrf-token"]');
            if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

            const res = await fetch(`/api/admin/gallery/${encodeURIComponent(filename)}`, {
                method: 'DELETE',
                headers: headers
            });

            if (res.ok) {
                // Remove from array and re-render
                allPhotos = allPhotos.filter(p => p.filename !== filename);
                renderGallery();
            } else {
                const data = await res.json();
                await alert(data.error || 'Delete failed');
            }
        } catch (err) {
            console.error(err);
            await alert('Delete failed');
        }
    }

    // --- Upload Logic ---
    if (uploadBtn && uploadModal) {
        uploadBtn.addEventListener('click', async () => {
            fileInput.value = '';
            filenameInput.value = '';
            uploadModal.show();
        });
    }

    if (fileInput && filenameInput) {
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                let name = fileInput.files[0].name;
                // Strip extension
                if (name.includes('.')) {
                    name = name.split('.').slice(0, -1).join('.');
                }
                // Only auto-fill if empty
                if (!filenameInput.value) {
                    filenameInput.value = name;
                }
            }
        });
    }

    // --- Folder Upload Logic ---
    if (uploadFolderBtn && folderModal) {
        uploadFolderBtn.addEventListener('click', async () => {
            folderInput.value = '';
            folderOptions.classList.add('d-none');
            progressContainer.classList.add('d-none');
            confirmFolderUploadBtn.disabled = true;
            confirmFolderUploadBtn.textContent = 'Start Upload';
            isFolderUploadFinished = false;
            folderModal.show();
        });
    }

    if (folderInput) {
        folderInput.addEventListener('change', () => {
            const files = Array.from(folderInput.files).filter(f => f.type.startsWith('image/'));
            if (files.length > 0) {
                folderOptions.classList.remove('d-none');
                confirmFolderUploadBtn.disabled = false;
                progressStatus.textContent = `${files.length} images selected.`;
            } else {
                folderOptions.classList.add('d-none');
                confirmFolderUploadBtn.disabled = true;
                progressStatus.textContent = 'No images found in folder.';
            }
        });
    }

    // Toggle prefix container
    document.querySelectorAll('input[name="folderNamingMode"]').forEach(radio => {
        radio.addEventListener('change', () => {
            if (nameRenameRadio.checked) {
                prefixContainer.classList.remove('d-none');
            } else {
                prefixContainer.classList.add('d-none');
            }
        });
    });

    let isFolderUploadFinished = false;

    if (confirmFolderUploadBtn) {
        confirmFolderUploadBtn.addEventListener('click', async () => {
            if (isFolderUploadFinished) {
                folderModal.hide();
                return;
            }

            const allFiles = Array.from(folderInput.files).filter(f => f.type.startsWith('image/'));
            if (allFiles.length === 0) return;

            const namingMode = document.querySelector('input[name="folderNamingMode"]:checked').value;
            const prefix = prefixInput.value.trim();

            if (namingMode === 'rename' && !prefix) {
                await alert("Please enter a prefix for renaming.");
                return;
            }

            confirmFolderUploadBtn.disabled = true;
            progressContainer.classList.remove('d-none');

            const total = allFiles.length;
            let successCount = 0;
            let errorCount = 0;

            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

            for (let i = 0; i < total; i++) {
                const file = allFiles[i];
                let customName = "";

                if (namingMode === 'rename') {
                    // prefix_01, prefix_02...
                    const index = (i + 1).toString().padStart(Math.max(2, total.toString().length), '0');
                    customName = `${prefix}_${index}`;
                } else {
                    // Original name without extension
                    customName = file.name.split('.').slice(0, -1).join('.');
                }

                progressStatus.textContent = `Uploading ${file.name}...`;

                const formData = new FormData();
                formData.append('file', file);
                formData.append('custom_name', customName);

                try {
                    const headers = {};
                    if (csrfToken) headers['X-CSRFToken'] = csrfToken;

                    const res = await fetch('/api/admin/upload-image', {
                        method: 'POST',
                        headers: headers,
                        body: formData
                    });

                    if (res.ok) {
                        successCount++;
                    } else {
                        errorCount++;
                    }
                } catch (err) {
                    console.error(err);
                    errorCount++;
                }

                // Update Progress
                const percent = Math.round(((i + 1) / total) * 100);
                progressBar.style.width = `${percent}%`;
                progressStats.textContent = `${i + 1}/${total}`;
            }

            progressStatus.textContent = `Upload complete. ${successCount} success, ${errorCount} failed.`;
            confirmFolderUploadBtn.textContent = 'Done';
            confirmFolderUploadBtn.disabled = false;
            isFolderUploadFinished = true;

            // Reload gallery
            loadGallery();
        });
    }

    if (confirmUploadBtn) {
        confirmUploadBtn.addEventListener('click', async () => {
            const file = fileInput.files[0];
            if (!file) {
                await alert("Please select a file");
                return;
            }

            const customName = filenameInput.value.trim();
            const formData = new FormData();
            formData.append('file', file);
            if (customName) {
                formData.append('custom_name', customName);
            }

            confirmUploadBtn.disabled = true;
            confirmUploadBtn.textContent = 'Uploading...';

            try {
                const headers = {};
                const csrfToken = document.querySelector('meta[name="csrf-token"]');
                if (csrfToken) headers['X-CSRFToken'] = csrfToken.content;

                const res = await fetch('/api/admin/upload-image', {
                    method: 'POST',
                    headers: headers,
                    body: formData
                });

                const data = await res.json();
                if (res.ok) {
                    uploadModal.hide();
                    // Reload gallery
                    loadGallery();
                } else {
                    await alert(data.error || 'Upload failed');
                }
            } catch (err) {
                console.error(err);
                await alert('Upload error');
            } finally {
                confirmUploadBtn.disabled = false;
                confirmUploadBtn.textContent = 'Upload';
            }
        });
    }

    if (galleryFilter) {
        galleryFilter.addEventListener('change', renderGallery);
    }

    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadGallery);
    }

    // Initial load logic handles by checking active tab or just loading if present?
    // Admin tabs usually hide content. We can load on click of tab or just load initially.
    // Let's load initially if tab is active, or lazy load.
    // Ideally hooking into tab switch event in admin.html, but simple load works too.

    // Check if gallery tab is active
    if (document.getElementById('gallery-tab').classList.contains('active')) {
        loadGallery();
    }

    // Also listen for tab show
    document.querySelectorAll('button[data-tab="gallery"]').forEach(btn => {
        btn.addEventListener('click', () => {
            if (allPhotos.length === 0) loadGallery();
        });
    });
});

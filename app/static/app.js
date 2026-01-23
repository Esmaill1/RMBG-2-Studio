document.addEventListener('DOMContentLoaded', () => {
    // ================= REMOVE BACKGROUND LOGIC =================
    const uploadZone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('file-input');
    const resultsGrid = document.getElementById('results-grid');
    const loadingContainer = document.getElementById('loading-bar-container');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');

    const resultsHeader = document.getElementById('results-header');
    const downloadAllBtn = document.getElementById('download-all-btn');
    const clearAllBtn = document.getElementById('clear-all-btn');

    // Drag & Drop
    uploadZone.addEventListener('click', () => fileInput.click());
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.style.borderColor = 'var(--primary)';
        uploadZone.style.backgroundColor = '#f8fbff';
    });
    uploadZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadZone.style.borderColor = 'var(--border)';
        uploadZone.style.backgroundColor = '#ffffff';
    });
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.style.borderColor = 'var(--border)';
        uploadZone.style.backgroundColor = '#ffffff';
        if (e.dataTransfer.files.length) {
            handleUpload(e.dataTransfer.files);
        }
    });
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) handleUpload(e.target.files);
    });

    async function handleUpload(files) {
        if (files.length === 0) return;

        // UI Setup
        loadingContainer.style.display = 'flex';
        progressBar.style.width = '0%';
        resultsHeader.style.display = 'flex';
        
        let processedCount = 0;
        const totalFiles = files.length;
        
        // Process sequentially for accurate progress
        for (let i = 0; i < totalFiles; i++) {
            const file = files[i];
            
            // Skip non-images
            if (!file.type.startsWith('image/')) continue;
            
            progressText.textContent = `جاري المعالجة ${i + 1}/${totalFiles}: ${file.name}`;
            
            const formData = new FormData();
            formData.append('images', file); // API expects list but we act like size 1 batch

            try {
                const response = await fetch('/api/remove-bg', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();

                if (data.success && data.results) {
                    data.results.forEach(result => createResultCard(result));
                }
            } catch (error) {
                console.error(`Error processing ${file.name}:`, error);
                showToast(`فشل معالجة ${file.name}`, 'error');
            }

            // Update Progress
            processedCount++;
            const percent = (processedCount / totalFiles) * 100;
            progressBar.style.width = `${percent}%`;
        }

        progressText.textContent = 'اكتملت المعالجة!';
        setTimeout(() => {
             loadingContainer.style.display = 'none';
        }, 1500);
        showToast(`تمت معالجة ${processedCount} صورة!`);
    }

    function createResultCard(result) {
        const card = document.createElement('div');
        card.className = 'result-card';
        card.dataset.filename = result.filename; // Store for zip download logic
        card.innerHTML = `
            <div class="result-image-wrapper">
                <img src="${result.url}" alt="${result.original_name}">
                <button class="delete-btn" title="حذف الصورة">
                    <i class="ph ph-x"></i>
                </button>
            </div>
            <div class="result-footer">
                <div class="file-name" title="${result.original_name}">${result.original_name}</div>
                <a href="${result.url}" download="${result.filename}" class="btn btn-primary" style="padding: 0.4rem 0.8rem; font-size: 0.8rem;">
                    <i class="ph ph-download-simple"></i> حفظ
                </a>
            </div>
        `;
        
        // Add delete logic
        card.querySelector('.delete-btn').addEventListener('click', () => {
            card.remove();
            checkEmptyGrid();
        });
        
        resultsGrid.prepend(card); // Newest first
    }

    function checkEmptyGrid() {
        if (resultsGrid.children.length === 0) {
            resultsHeader.style.display = 'none';
        }
    }

    // Clear All Logic
    clearAllBtn.addEventListener('click', async () => {
        if(confirm('هل أنت متأكد من مسح جميع الصور المعالجة؟ (سيتم حذفها من الخادم أيضاً)')) {
            try {
                const response = await fetch('/api/delete-all', { method: 'POST' });
                const data = await response.json();
                
                if (data.success) {
                    resultsGrid.innerHTML = '';
                    resultsHeader.style.display = 'none';
                    showToast(`تم حذف ${data.count} صورة بنجاح`);
                } else {
                    showToast('فشل حذف الصور', 'error');
                }
            } catch (error) {
                console.error(error);
                showToast('خطأ في الاتصال', 'error');
            }
        }
    });

    // Download All Logic
    downloadAllBtn.addEventListener('click', async () => {
        const cards = document.querySelectorAll('.result-card');
        if (cards.length === 0) return;

        downloadAllBtn.disabled = true;
        downloadAllBtn.innerHTML = '<div class="spinner" style="width:16px;height:16px;border-width:2px;display:inline-block"></div> جاري الضغط...';

        const filenames = Array.from(cards).map(card => card.dataset.filename);

        try {
            const response = await fetch('/api/zip', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filenames })
            });
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `rmbg_batch_${new Date().getTime()}.zip`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                a.remove();
                showToast('بدأ تحميل الملف المضغوط!');
            } else {
                showToast('فشل إنشاء الملف المضغوط', 'error');
            }
        } catch (error) {
            console.error(error);
            showToast('خطأ في الشبكة', 'error');
        } finally {
            downloadAllBtn.disabled = false;
            downloadAllBtn.innerHTML = '<i class="ph ph-download-simple"></i> تحميل الكل (ZIP)';
        }
    });

    // ================= TOAST UI =================
    function showToast(message, type = 'success') {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.style.backgroundColor = type === 'error' ? '#d0342c' : '#0969da';
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 3000);
    }
});

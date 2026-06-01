document.addEventListener('DOMContentLoaded', () => {
    const uploadZone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('file-input');
    const resultsGrid = document.getElementById('results-grid');
    const loadingContainer = document.getElementById('loading-bar-container');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');

    const resultsHeader = document.getElementById('results-header');
    const downloadAllBtn = document.getElementById('download-all-btn');
    const clearAllBtn = document.getElementById('clear-all-btn');

    uploadZone.addEventListener('click', () => fileInput.click());
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('drag-over');
    });
    uploadZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('drag-over');
    });
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('drag-over');
        if (e.dataTransfer.files.length) {
            handleUpload(e.dataTransfer.files);
        }
    });
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) handleUpload(e.target.files);
    });

    async function handleUpload(files) {
        if (files.length === 0) return;

        const imageFiles = Array.from(files).filter(f => f.type.startsWith('image/'));
        if (imageFiles.length === 0) {
            showToast('لا توجد صور صالحة للمعالجة', 'error');
            return;
        }

        loadingContainer.style.display = 'flex';
        progressBar.style.width = '5%';
        resultsHeader.style.display = 'flex';
        progressText.textContent = `جاري المعالجة... (0/${imageFiles.length})`;

        const formData = new FormData();
        imageFiles.forEach(file => formData.append('images', file));

        let processedCount = 0;
        const totalCount = imageFiles.length;

        try {
            progressBar.style.width = '20%';
            const response = await fetch('/api/remove-bg', {
                method: 'POST',
                body: formData
            });

            if (response.status === 400) {
                const data = await response.json();
                showToast(data.error || 'خطأ في الطلب', 'error');
                progressText.textContent = 'اكتملت المعالجة!';
                setTimeout(() => {
                    loadingContainer.style.display = 'none';
                }, 1500);
                return;
            }

            if (!response.ok) {
                showToast('فشل معالجة الصور', 'error');
                progressText.textContent = 'اكتملت المعالجة!';
                setTimeout(() => {
                    loadingContainer.style.display = 'none';
                }, 1500);
                return;
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                let boundaryIndex;
                while ((boundaryIndex = buffer.indexOf('\n\n')) !== -1) {
                    const eventText = buffer.substring(0, boundaryIndex);
                    buffer = buffer.substring(boundaryIndex + 2);

                    const dataLines = eventText.split('\n').filter(line => line.startsWith('data:'));
                    for (const line of dataLines) {
                        const jsonStr = line.substring(5).trim();
                        try {
                            const parsed = JSON.parse(jsonStr);

                            if (parsed.done) {
                                progressBar.style.width = '100%';
                                showToast(`تمت معالجة ${parsed.success_count} صورة!`);
                            } else if (parsed.error) {
                                showToast(parsed.error, 'error');
                                processedCount++;
                                progressText.textContent = `جاري المعالجة... (${processedCount}/${totalCount})`;
                                progressBar.style.width = `${20 + (processedCount / totalCount) * 70}%`;
                            } else if (parsed.filename) {
                                processedCount++;
                                createResultCard(parsed);
                                progressText.textContent = `جاري المعالجة... (${processedCount}/${totalCount})`;
                                progressBar.style.width = `${20 + (processedCount / totalCount) * 70}%`;
                            }
                        } catch (e) {
                            console.error('SSE parse error:', e);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Stream processing error:', error);
            showToast('فشل معالجة الصور', 'error');
        }

        progressText.textContent = 'اكتملت المعالجة!';
        setTimeout(() => {
            loadingContainer.style.display = 'none';
        }, 1500);
    }

    function createResultCard(result) {
        const card = document.createElement('div');
        card.className = 'result-card card-enter';
        card.dataset.filename = result.filename;
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
        
        card.querySelector('.delete-btn').addEventListener('click', () => {
            card.style.opacity = '0';
            card.style.transform = 'scale(0.9)';
            setTimeout(() => {
                card.remove();
                checkEmptyGrid();
            }, 300);
        });
        
        resultsGrid.prepend(card);
    }

    function checkEmptyGrid() {
        if (resultsGrid.children.length === 0) {
            resultsHeader.style.display = 'none';
        }
    }

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
                a.download = `rmbg_results_${new Date().getTime()}.zip`;
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

    function showToast(message, type = 'success') {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.className = 'toast';
        toast.classList.add(type === 'error' ? 'toast-error' : 'toast-success');
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }
});
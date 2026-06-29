document.addEventListener('DOMContentLoaded', () => {
    const uploadZone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('file-input');
    const resultsGrid = document.getElementById('results-grid');
    const progressSection = document.getElementById('progress-section');
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

    function handleUpload(files) {
        if (files.length === 0) return;

        const imageFiles = Array.prototype.slice.call(files).filter(f => f.type.indexOf('image/') === 0);
        if (imageFiles.length === 0) return;

        progressSection.style.display = 'flex';
        progressBar.style.width = '0%';
        resultsHeader.style.display = 'flex';

        const totalImages = imageFiles.length;

        // Send ALL images in a single batch request for GPU batching
        const formData = new FormData();
        imageFiles.forEach(file => formData.append('images', file));

        progressText.textContent = `يرفع ${totalImages} صورة...`;

        const uploadPromise = new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();

            // Track upload progress (file transfer to server)
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const uploadPercent = Math.round((e.loaded / e.total) * 50);
                    progressBar.style.width = `${uploadPercent}%`;
                    if (uploadPercent < 50) {
                        const mb = (e.loaded / (1024 * 1024)).toFixed(1);
                        const totalMb = (e.total / (1024 * 1024)).toFixed(1);
                        progressText.textContent = `يرفع ${mb}/${totalMb} MB — ${totalImages} صورة`;
                    }
                }
            });

            // Upload complete — now server is processing
            xhr.upload.addEventListener('load', () => {
                progressBar.style.width = '50%';
                progressText.textContent = `يعالج ${totalImages} صورة على GPU...`;
                // Animate progress bar slowly during processing
                animateProcessing();
            });

            xhr.addEventListener('load', () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        resolve(JSON.parse(xhr.responseText));
                    } catch (e) {
                        reject(new Error('Invalid JSON response'));
                    }
                } else {
                    reject(new Error(`Server error: ${xhr.status}`));
                }
            });

            xhr.addEventListener('error', () => reject(new Error('Network error')));
            xhr.addEventListener('abort', () => reject(new Error('Upload aborted')));

            xhr.open('POST', '/api/remove-bg');
            xhr.send(formData);
        });

        uploadPromise
            .then(result => {
                // Processing complete
                progressBar.style.width = '100%';
                stopProcessingAnimation();

                if (result.success && result.results) {
                    result.results.forEach(r => createResultCard(r));
                    const elapsed = result.processing_time
                        ? ` (${result.processing_time})`
                        : '';
                    progressText.textContent = `انتهت المعالجة — ${result.results.length} صورة${elapsed}`;
                    showToast(`تمت معالجة ${result.results.length} صورة${elapsed}`);
                } else {
                    progressText.textContent = 'فشلت المعالجة';
                    showToast(result.error || 'فشلت المعالجة', 'error');
                }
            })
            .catch(error => {
                console.error('Batch upload error:', error);
                progressBar.style.width = '100%';
                stopProcessingAnimation();
                progressText.textContent = 'حدث خطأ';
                showToast('خطأ في معالجة الصور', 'error');
            })
            .then(() => {
                setTimeout(() => {
                    progressSection.style.display = 'none';
                }, 1500);

                // Reset file input so the same files can be re-uploaded
                fileInput.value = '';
            });
    }

    // Smoothly animate progress bar during GPU processing
    let processingInterval = null;
    let processingProgress = 50;

    function animateProcessing() {
        processingProgress = 50;
        processingInterval = setInterval(() => {
            // Slowly approach 95% but never reach it
            processingProgress += (95 - processingProgress) * 0.03;
            progressBar.style.width = `${processingProgress}%`;
        }, 200);
    }

    function stopProcessingAnimation() {
        if (processingInterval) {
            clearInterval(processingInterval);
            processingInterval = null;
        }
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
                <span class="file-name" title="${result.original_name}">${result.original_name}</span>
                <a href="${result.url}" download="${result.filename}" class="btn btn-primary btn-sm">
                    <i class="ph ph-download-simple"></i> حفظ الصورة
                </a>
            </div>
        `;

        card.querySelector('.delete-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            card.style.opacity = '0';
            card.style.transform = 'scale(0.95)';
            card.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
            setTimeout(() => {
                if (card.parentNode) card.parentNode.removeChild(card);
                checkEmptyGrid();
            }, 250);
        });

        resultsGrid.insertBefore(card, resultsGrid.firstChild);
    }

    function checkEmptyGrid() {
        if (resultsGrid.children.length === 0) {
            resultsHeader.style.display = 'none';
        }
    }

    clearAllBtn.addEventListener('click', () => {
        if (confirm('سيتم حذف جميع الصور المعالجة نهائياً. متأكد؟')) {
            fetch('/api/delete-all', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        resultsGrid.innerHTML = '';
                        resultsHeader.style.display = 'none';
                        showToast(`تم حذف ${data.count} صورة`);
                    } else {
                        showToast('فشل حذف الصور', 'error');
                    }
                })
                .catch(error => {
                    console.error(error);
                    showToast('خطأ في الاتصال', 'error');
                });
        }
    });

    downloadAllBtn.addEventListener('click', () => {
        const cards = document.querySelectorAll('.result-card');
        if (cards.length === 0) return;

        downloadAllBtn.disabled = true;
        downloadAllBtn.innerHTML = '<div class="spinner" style="width:16px;height:16px;border-width:2px;display:inline-block"></div> جاري الضغط...';

        const filenames = Array.prototype.slice.call(cards).map(card => card.dataset.filename);

        const cleanup = () => {
            downloadAllBtn.disabled = false;
            downloadAllBtn.innerHTML = '<i class="ph ph-file-archive"></i> تحميل الكل';
        };

        fetch('/api/zip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filenames })
        })
        .then(response => {
            if (response.ok) {
                return response.blob().then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `rmbg_batch_${new Date().getTime()}.zip`;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    a.remove();
                    showToast('بدأ تحميل الملف المضغوط');
                });
            } else {
                showToast('فشل إنشاء الملف المضغوط', 'error');
            }
        })
        .then(() => {
            cleanup();
        })
        .catch(error => {
            console.error(error);
            showToast('خطأ في الاتصال', 'error');
            cleanup();
        });
    });

    function showToast(message, type = 'success') {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.className = 'toast';
        toast.classList.add(type === 'error' ? 'toast-error' : 'toast-success');
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
        }, 2500);
    }
});

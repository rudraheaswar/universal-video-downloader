document.addEventListener('DOMContentLoaded', () => {
    const urlInput = document.getElementById('url-input');
    const fetchBtn = document.getElementById('fetch-btn');
    const loader = document.getElementById('loader');
    const errorMessage = document.getElementById('error-message');
    const errorText = document.getElementById('error-text');
    const resultSection = document.getElementById('result-section');
    const videoThumbnail = document.getElementById('video-thumbnail');
    const videoTitle = document.getElementById('video-title');
    const downloadBtn = document.getElementById('download-btn');
    const downloadLoader = document.getElementById('download-loader');

    // Timeline elements
    const timelineWrapper = document.getElementById('timeline-wrapper');
    const startSlider = document.getElementById('start-slider');
    const endSlider = document.getElementById('end-slider');
    const sliderRangeColor = document.getElementById('slider-range-color');
    const startLabel = document.getElementById('start-label');
    const endLabel = document.getElementById('end-label');

    let currentVideoUrl = '';

    function formatTime(seconds) {
        const d = Number(seconds);
        const h = Math.floor(d / 3600);
        const m = Math.floor((d % 3600) / 60);
        const s = Math.floor(d % 3600 % 60);
        let mDisplay = m < 10 ? "0" + m : m;
        let sDisplay = s < 10 ? "0" + s : s;
        if (h > 0) {
            let hDisplay = h < 10 ? "0" + h : h;
            return hDisplay + ":" + mDisplay + ":" + sDisplay;
        }
        return mDisplay + ":" + sDisplay;
    }

    function updateSliderUI() {
        let startVal = parseInt(startSlider.value);
        let endVal = parseInt(endSlider.value);

        startLabel.textContent = formatTime(startVal);
        endLabel.textContent = formatTime(endVal);

        const max = parseInt(startSlider.max);
        const leftPercent = (startVal / max) * 100;
        const rightPercent = 100 - ((endVal / max) * 100);

        sliderRangeColor.style.left = leftPercent + '%';
        sliderRangeColor.style.right = rightPercent + '%';
    }

    startSlider.addEventListener('input', () => {
        if (parseInt(startSlider.value) >= parseInt(endSlider.value)) {
            startSlider.value = parseInt(endSlider.value) - 1;
        }
        updateSliderUI();
    });

    endSlider.addEventListener('input', () => {
        if (parseInt(endSlider.value) <= parseInt(startSlider.value)) {
            endSlider.value = parseInt(startSlider.value) + 1;
        }
        updateSliderUI();
    });

    fetchBtn.addEventListener('click', async () => {
        const url = urlInput.value.trim();
        if (!url) {
            showError("Please enter a valid YouTube URL");
            return;
        }

        // Reset UI
        hideError();
        resultSection.classList.add('hidden');
        loader.classList.remove('hidden');

        try {
            const response = await fetch('/api/info', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ url })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to fetch video information');
            }

            // Update UI with video details
            currentVideoUrl = data.url;
            videoTitle.textContent = data.title;
            videoThumbnail.src = data.thumbnail;
            
            // Setup Timeline
            const duration = data.length || 0;
            if (duration > 0) {
                timelineWrapper.style.opacity = '1';
                timelineWrapper.style.pointerEvents = 'auto';
                startSlider.max = duration;
                endSlider.max = duration;
                startSlider.value = 0;
                endSlider.value = duration;
                updateSliderUI();
            } else {
                timelineWrapper.style.opacity = '0.5';
                timelineWrapper.style.pointerEvents = 'none';
            }

            // Show result
            loader.classList.add('hidden');
            resultSection.classList.remove('hidden');

        } catch (error) {
            loader.classList.add('hidden');
            showError(error.message);
        }
    });

    downloadBtn.addEventListener('click', async () => {
        if (!currentVideoUrl) return;

        // Get selected resolution
        const selectedRes = document.querySelector('input[name="resolution"]:checked').value;
        const duration = parseInt(startSlider.max);
        let startTime = '';
        let endTime = '';

        if (timelineWrapper.style.pointerEvents !== 'none') {
            const currentStart = parseInt(startSlider.value);
            const currentEnd = parseInt(endSlider.value);
            if (currentStart > 0) startTime = currentStart.toString();
            if (currentEnd < duration) endTime = currentEnd.toString();
        }

        // Visual feedback
        downloadBtn.classList.add('hidden');
        downloadLoader.classList.remove('hidden');

        // Construct download URL
        let downloadUrl = `/api/download?url=${encodeURIComponent(currentVideoUrl)}&res=${selectedRes}`;
        if (startTime) downloadUrl += `&start=${encodeURIComponent(startTime)}`;
        if (endTime) downloadUrl += `&end=${encodeURIComponent(endTime)}`;

        // Check if we are running inside the native Desktop wrapper (pywebview)
        // pywebview injects a global window.pywebview object
        const isDesktop = typeof window.pywebview !== 'undefined';

        if (isDesktop) {
            downloadUrl += "&mode=desktop";
            try {
                const response = await fetch(downloadUrl);
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || "Download failed");
                alert(result.message);
            } catch (e) {
                showError(e.message);
            } finally {
                downloadBtn.classList.remove('hidden');
                downloadLoader.classList.add('hidden');
            }
        } else {
            // Standard Web / PWA Mode
            // Let the browser's native download manager handle the file stream.
            // Fetching a large video into a Blob will crash mobile browsers.
            const iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.src = downloadUrl;
            document.body.appendChild(iframe);
            
            // Remove iframe and reset UI after a reasonable delay
            setTimeout(() => {
                document.body.removeChild(iframe);
                downloadBtn.classList.remove('hidden');
                downloadLoader.classList.add('hidden');
            }, 5000);
        }
    });

    function showError(msg) {
        errorText.textContent = msg;
        errorMessage.classList.remove('hidden');
    }

    function hideError() {
        errorMessage.classList.add('hidden');
    }

    // Allow Enter key to trigger fetch
    urlInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            fetchBtn.click();
        }
    });
});

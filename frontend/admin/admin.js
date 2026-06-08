const API_BASE = window.location.origin + '/api';

const token = localStorage.getItem('access_token');
if (!token) {
    window.location.href = window.location.origin + '/admin';
}

const loading = document.getElementById('loading');
const loadingText = document.getElementById('loadingText');
const toast = document.getElementById('toast');

document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById('crawlBtn').addEventListener('click', startCrawl);
    document.getElementById('clearBtn').addEventListener('click', clearIndex);
}

function getAuthHeaders() {
    const token = localStorage.getItem('access_token');
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    };
}

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/admin/stats`, {
            headers: getAuthHeaders()
        });
        
        if (response.status === 401 || response.status === 403) {
            logout();
            return;
        }
        
        if (!response.ok) {
            throw new Error(`Server error (${response.status})`);
        }
        
        const data = await response.json();
        
        document.getElementById('docCount').textContent = data.total_documents;
        document.getElementById('searchCount').textContent = data.total_searches;
        document.getElementById('vocabCount').textContent = data.vocabulary_size;
        document.getElementById('avgTime').textContent = data.avg_response_time_ms + 'ms';
        
    } catch (error) {
        showToast('Failed to load stats', 'error');
    }
}

async function startCrawl() {
    const url = document.getElementById('crawlUrl').value.trim();
    if (!url) {
        showToast('Enter a URL', 'error');
        return;
    }
    
    showLoading('Crawling...');
    document.getElementById('crawlStatus').textContent = 'Starting crawl...';
    
    try {
        const response = await fetch(`${API_BASE}/crawl`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ url, max_pages: 50 })
        });
        
        if (response.status === 401 || response.status === 403) {
            logout();
            return;
        }
        
        if (!response.ok) {
            let detail = 'Crawl failed';
            try {
                const error = await response.json();
                detail = error.detail || detail;
            } catch {
                detail = `Server error (${response.status})`;
            }
            throw new Error(detail);
        }
        
        const data = await response.json();
        showToast(data.message, 'success');
        pollJobStatus(data.job_id);
        
    } catch (error) {
        showToast(error.message, 'error');
        document.getElementById('crawlStatus').textContent = 'Crawl failed: ' + error.message;
    } finally {
        setTimeout(hideLoading, 1000);
    }
}

async function clearIndex() {
    if (!confirm('Clear all indexed documents? This cannot be undone.')) return;
    
    showLoading('Clearing...');
    
    try {
        const response = await fetch(`${API_BASE}/index`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        
        if (response.status === 401 || response.status === 403) {
            logout();
            return;
        }
        
        if (!response.ok) throw new Error(`Server error (${response.status})`);
        
        showToast('Index cleared', 'success');
        loadStats();
        
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        hideLoading();
    }
}

function pollJobStatus(jobId) {
    let attempts = 0;
    const interval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/crawl/status/${jobId}`, {
                headers: getAuthHeaders()
            });
            if (response.status === 401 || response.status === 403) {
                logout();
                clearInterval(interval);
                return;
            }
            if (!response.ok) {
                throw new Error(`Server error (${response.status})`);
            }
            const data = await response.json();
            document.getElementById('crawlStatus').textContent =
                `Status: ${data.status}${data.pages_crawled ? ` (${data.pages_crawled} pages)` : ''}`;

            if (data.status === 'completed') {
                clearInterval(interval);
                document.getElementById('crawlStatus').textContent =
                    `Completed: ${data.pages_crawled} pages indexed`;
                loadStats();
            } else if (data.status === 'failed') {
                clearInterval(interval);
                document.getElementById('crawlStatus').textContent =
                    `Failed: ${data.error || 'Unknown error'}`;
                showToast('Crawl failed', 'error');
            }
            attempts++;
            if (attempts > 60) {
                clearInterval(interval);
                document.getElementById('crawlStatus').textContent = 'Timed out waiting for completion';
            }
        } catch (error) {
            clearInterval(interval);
            document.getElementById('crawlStatus').textContent = 'Error checking status';
        }
    }, 5000);
}

function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_role');
    window.location.href = window.location.origin;
}

function showLoading(text) {
    loadingText.textContent = text;
    loading.classList.remove('hidden');
}

function hideLoading() {
    loading.classList.add('hidden');
}

function showToast(message, type = 'success') {
    toast.textContent = message;
    toast.className = `toast ${type}`;
    setTimeout(() => toast.classList.add('hidden'), 4000);
}

const API_BASE = 'http://localhost:8000/api';

const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const crawlUrl = document.getElementById('crawlUrl');
const crawlBtn = document.getElementById('crawlBtn');
const clearBtn = document.getElementById('clearBtn');
const resultsContainer = document.getElementById('resultsContainer');
const emptyState = document.getElementById('emptyState');
const loading = document.getElementById('loading');
const loadingText = document.getElementById('loadingText');
const toast = document.getElementById('toast');
const stats = document.getElementById('stats');

let searchTimeout = null;

document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    setupEventListeners();
});

function setupEventListeners() {
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });
    
    searchBtn.addEventListener('click', performSearch);
    
    document.querySelectorAll('.hint').forEach(hint => {
        hint.addEventListener('click', () => {
            searchInput.value = hint.dataset.query;
            performSearch();
        });
    });
    
    crawlBtn.addEventListener('click', startCrawl);
    clearBtn.addEventListener('click', clearIndex);
    
    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        if (searchInput.value.length > 2) {
            searchTimeout = setTimeout(performSearch, 300);
        }
    });
}

async function performSearch() {
    const query = searchInput.value.trim();
    if (!query) return;
    
    showLoading('Searching...');
    
    try {
        const response = await fetch(`${API_BASE}/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, top_k: 10 })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Search failed');
        }
        
        const results = await response.json();
        displayResults(results, query);
        
    } catch (error) {
        showToast(error.message, 'error');
        showEmptyState();
    } finally {
        hideLoading();
    }
}

function displayResults(results, query) {
    if (!results || results.length === 0) {
        resultsContainer.innerHTML = `
            <div class="empty-state">
                <h2>No results found</h2>
                <p>No matches for "${escapeHtml(query)}". Try different keywords or crawl more pages.</p>
            </div>
        `;
        return;
    }
    
    resultsContainer.innerHTML = results.map((result, index) => `
        <article class="result-card" style="animation-delay: ${index * 0.05}s">
            <div class="result-header">
                <a href="${escapeHtml(result.url)}" target="_blank" rel="noopener" class="result-title">
                    ${escapeHtml(result.title) || 'Untitled'}
                </a>
                <span class="result-score">Score: ${result.score}</span>
            </div>
            <a href="${escapeHtml(result.url)}" target="_blank" rel="noopener" class="result-url">
                ${escapeHtml(result.url)}
            </a>
            <p class="result-snippet">${escapeHtml(result.snippet)}</p>
        </article>
    `).join('');
}

function showEmptyState() {
    resultsContainer.innerHTML = '';
    resultsContainer.appendChild(emptyState);
}

async function startCrawl() {
    const url = crawlUrl.value.trim();
    if (!url) {
        showToast('Please enter a URL to crawl', 'error');
        return;
    }
    
    showLoading('Crawling in progress... This may take a minute.');
    
    try {
        const response = await fetch(`${API_BASE}/crawl`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, max_pages: 50 })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Crawl failed');
        }
        
        const data = await response.json();
        showToast(data.message + ' Check stats for progress.', 'success');
        
        pollStats();
        
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        setTimeout(hideLoading, 1000);
    }
}

async function clearIndex() {
    if (!confirm('Are you sure you want to clear all indexed documents?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/index`, { method: 'DELETE' });
        if (!response.ok) throw new Error('Failed to clear index');
        
        showToast('Index cleared successfully', 'success');
        loadStats();
        showEmptyState();
        
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/stats`);
        const data = await response.json();
        
        stats.textContent = data.index_built 
            ? `${data.total_documents} documents indexed | ${data.vocabulary_size} unique terms`
            : 'No documents indexed yet - crawl a site to begin';
            
    } catch (error) {
        stats.textContent = 'API unavailable - is the backend running?';
    }
}

function pollStats() {
    let attempts = 0;
    const interval = setInterval(async () => {
        await loadStats();
        attempts++;
        if (attempts > 30) clearInterval(interval);
    }, 10000);
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
    
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 4000);
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

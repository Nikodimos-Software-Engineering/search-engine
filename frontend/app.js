const API_BASE = window.location.origin + '/api';

const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
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
                <p>No matches for "${escapeHtml(query)}". Try different keywords.</p>
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

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/stats`);
        const data = await response.json();
        
        stats.textContent = data.index_built 
            ? `${data.total_documents} documents indexed | ${data.vocabulary_size} unique terms`
            : 'No documents indexed yet - admin needs to crawl a site first';
            
    } catch (error) {
        stats.textContent = 'API unavailable';
    }
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

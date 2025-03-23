// API URL (adjust if needed)
const API_URL = window.location.origin;

// DOM Elements
const searchForm = document.getElementById('search-form');
const jobsContainer = document.getElementById('jobs-container');
const jobTemplate = document.getElementById('job-template');

// State
let jobs = [];
let polling = false;
let pollingIntervalId = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    // Fetch initial jobs
    fetchJobs();
    
    // Set up form submission
    searchForm.addEventListener('submit', handleFormSubmit);
});

/**
 * Handle form submission to start a new scraping job
 * @param {Event} event - Form submit event
 */
async function handleFormSubmit(event) {
    event.preventDefault();
    
    // Get form values
    const query = document.getElementById('query').value.trim();
    const location = document.getElementById('location').value.trim();
    const maxResults = parseInt(document.getElementById('max-results').value, 10);
    const includeEmails = document.getElementById('include-emails').checked;
    const includeEmailTemplates = document.getElementById('include-email-templates').checked;
    
    // Validate input
    if (!query || !location) {
        alert('Please enter both a business type and location.');
        return;
    }
    
    try {
        // Disable form during submission
        toggleFormEnabled(false);
        
        // Create request payload
        const payload = {
            query,
            location,
            max_results: maxResults,
            include_emails: includeEmails,
            include_email_templates: includeEmailTemplates
        };
        
        // Send API request
        const response = await fetch(`${API_URL}/scrape`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        // Handle response
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to start scraping job');
        }
        
        // Success - add new job to list
        fetchJobs();
        
        // Start polling if not already started
        startPolling();
        
        // Reset form
        searchForm.reset();
        document.getElementById('query').value = '';
        document.getElementById('location').value = '';
        document.getElementById('max-results').value = '20';
        document.getElementById('include-emails').checked = true;
        document.getElementById('include-email-templates').checked = true;
        
    } catch (error) {
        console.error('Error starting scraping job:', error);
        alert(`Error: ${error.message}`);
    } finally {
        // Re-enable form
        toggleFormEnabled(true);
    }
}

/**
 * Toggle form enabled/disabled state
 * @param {boolean} enabled - Whether the form should be enabled
 */
function toggleFormEnabled(enabled) {
    const formElements = searchForm.querySelectorAll('input, button');
    formElements.forEach(element => {
        element.disabled = !enabled;
    });
    
    // Update button text
    const submitButton = searchForm.querySelector('button[type="submit"]');
    submitButton.textContent = enabled ? 'Start Scraping' : 'Starting...';
}

/**
 * Fetch all jobs from the API
 */
async function fetchJobs() {
    try {
        const response = await fetch(`${API_URL}/jobs`);
        
        if (!response.ok) {
            throw new Error('Failed to fetch jobs');
        }
        
        const data = await response.json();
        
        // Update jobs list
        jobs = data;
        
        // Render jobs
        renderJobs();
        
        // Check if we need to start/stop polling
        const activeJobs = jobs.filter(job => 
            job.status === 'queued' || job.status === 'running'
        );
        
        if (activeJobs.length > 0) {
            startPolling();
        } else {
            stopPolling();
        }
        
    } catch (error) {
        console.error('Error fetching jobs:', error);
        jobsContainer.innerHTML = `<div class="error-message">Error loading jobs: ${error.message}</div>`;
    }
}

/**
 * Render jobs list in the UI
 */
function renderJobs() {
    // Clear current content
    jobsContainer.innerHTML = '';
    
    if (jobs.length === 0) {
        jobsContainer.innerHTML = `<div class="empty-message">No jobs found. Start a new scraping job to see results here.</div>`;
        return;
    }
    
    // Sort jobs by creation time (latest first)
    const sortedJobs = [...jobs].reverse();
    
    // Create job elements
    sortedJobs.forEach(job => {
        const jobElement = createJobElement(job);
        jobsContainer.appendChild(jobElement);
    });
}

/**
 * Create a job element from the template
 * @param {Object} job - Job data
 * @returns {HTMLElement} - Job element
 */
function createJobElement(job) {
    // Clone template
    const jobElement = document.importNode(jobTemplate.content, true).children[0];
    
    // Set job data
    const title = jobElement.querySelector('.job-title');
    const status = jobElement.querySelector('.job-status');
    const progressBar = jobElement.querySelector('.job-progress');
    const progressText = jobElement.querySelector('.job-progress-text');
    const message = jobElement.querySelector('.job-message');
    const jsonBtn = jobElement.querySelector('.download-json');
    const csvBtn = jobElement.querySelector('.download-csv');
    
    // Extract query and location from results file name or job ID
    let jobTitle = job.job_id;
    
    if (job.results_file) {
        const parts = job.results_file.split('_');
        if (parts.length >= 2) {
            jobTitle = `${parts[0]} in ${parts[1]}`;
        }
    }
    
    title.textContent = jobTitle;
    
    // Set status and style
    status.textContent = job.status;
    status.classList.add(job.status);
    
    // Set progress
    if (job.progress !== null) {
        const progressPercent = Math.round(job.progress * 100);
        progressBar.style.width = `${progressPercent}%`;
        progressText.textContent = `${progressPercent}%`;
    } else {
        progressBar.style.width = '0%';
        progressText.textContent = '';
    }
    
    // Set message
    message.textContent = job.message || '';
    
    // Configure download buttons
    if (job.status === 'completed' && job.results_file) {
        jsonBtn.href = `${API_URL}/download/${job.job_id}/json`;
        csvBtn.href = `${API_URL}/download/${job.job_id}/csv`;
    } else {
        // Hide download buttons if job not completed
        jsonBtn.style.display = 'none';
        csvBtn.style.display = 'none';
    }
    
    return jobElement;
}

/**
 * Start polling for job updates
 */
function startPolling() {
    // Don't start if already polling
    if (polling) return;
    
    polling = true;
    pollingIntervalId = setInterval(fetchJobs, 3000);
}

/**
 * Stop polling for job updates
 */
function stopPolling() {
    if (!polling) return;
    
    clearInterval(pollingIntervalId);
    polling = false;
    pollingIntervalId = null;
}

/**
 * Render a job in the jobs container
 * @param {Object} job - Job data
 */
function renderJob(job) {
    // Clone the template
    const jobElement = document.importNode(jobTemplate.content, true);
    
    // Set job title
    const titleElement = jobElement.querySelector('.job-title');
    titleElement.textContent = job.query ? `${job.query} in ${job.location}` : job.job_id;
    
    // Set job status and color
    const statusElement = jobElement.querySelector('.job-status');
    statusElement.textContent = job.status;
    statusElement.classList.add(`status-${job.status}`);
    
    // Set progress bar (if applicable)
    const progressBar = jobElement.querySelector('.job-progress');
    const progressText = jobElement.querySelector('.job-progress-text');
    
    if (job.progress !== null && job.status === 'running') {
        const percent = Math.round(job.progress * 100);
        progressBar.style.width = `${percent}%`;
        progressText.textContent = `${percent}%`;
    } else if (job.status === 'completed') {
        progressBar.style.width = '100%';
        progressText.textContent = '100%';
    } else if (job.status === 'failed') {
        progressBar.style.width = '0%';
        progressText.textContent = 'Failed';
    } else {
        progressText.textContent = 'Pending';
    }
    
    // Set message
    const messageElement = jobElement.querySelector('.job-message');
    messageElement.textContent = job.message || '';
    
    // Set download links (if completed)
    const jsonLink = jobElement.querySelector('.download-json');
    const csvLink = jobElement.querySelector('.download-csv');
    const jobCard = jobElement.querySelector('.job-card');
    
    // Add Excel download link
    const excelLink = document.createElement('a');
    excelLink.className = 'btn download-excel';
    excelLink.href = '#';
    excelLink.textContent = 'Download Excel';
    excelLink.target = '_blank';
    
    // Add all download links to job actions section
    const jobActions = jobElement.querySelector('.job-actions');
    jobActions.appendChild(excelLink);
    
    if (job.status === 'completed' && job.results_file) {
        jsonLink.href = `${API_URL}/jobs/${job.job_id}/download/json`;
        csvLink.href = `${API_URL}/jobs/${job.job_id}/download/csv`;
        excelLink.href = `${API_URL}/jobs/${job.job_id}/download/excel`;
    } else {
        jsonLink.style.display = 'none';
        csvLink.style.display = 'none';
        excelLink.style.display = 'none';
    }
    
    // Set id for the job element
    jobCard.id = `job-${job.job_id}`;
    
    // Add to jobs container
    jobsContainer.appendChild(jobElement);
} 
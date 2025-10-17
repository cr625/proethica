/**
 * Authentication Redirect Utility
 *
 * Provides a reusable function to handle 401 Unauthorized responses
 * and redirect users to the login page.
 */

/**
 * Enhanced fetch wrapper that automatically handles 401 responses
 * by redirecting to login page.
 *
 * Usage:
 *   authFetch('/api/endpoint', { method: 'POST', ... })
 *     .then(data => console.log(data))
 *     .catch(error => console.error(error));
 *
 * @param {string} url - The URL to fetch
 * @param {object} options - Fetch options (headers, method, body, etc.)
 * @returns {Promise} Promise that resolves to parsed JSON or rejects with error
 */
function authFetch(url, options = {}) {
    return fetch(url, options)
        .then(response => {
            // Check for authentication required
            if (response.status === 401) {
                // Redirect to login page with return URL
                const returnUrl = window.location.pathname + window.location.search;
                window.location.href = '/auth/login?next=' + encodeURIComponent(returnUrl);
                throw new Error('Authentication required - redirecting to login');
            }

            // Check for other error statuses
            if (!response.ok && response.status !== 401) {
                // For non-401 errors, try to parse error message
                return response.json().then(data => {
                    throw new Error(data.error || `HTTP ${response.status}: ${response.statusText}`);
                }).catch(parseError => {
                    // If JSON parsing fails, throw generic error
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                });
            }

            // Parse successful response as JSON
            return response.json();
        });
}

/**
 * Check if a fetch response indicates authentication is required.
 * Redirects to login if true.
 *
 * Usage in .then() chain:
 *   fetch(url, options)
 *     .then(response => {
 *       if (checkAuthRequired(response)) return;
 *       return response.json();
 *     })
 *     .then(data => ...)
 *
 * @param {Response} response - The fetch Response object
 * @returns {boolean} True if auth required and redirect initiated, false otherwise
 */
function checkAuthRequired(response) {
    if (response.status === 401) {
        const returnUrl = window.location.pathname + window.location.search;
        window.location.href = '/auth/login?next=' + encodeURIComponent(returnUrl);
        return true;
    }
    return false;
}

/**
 * Get CSRF token from meta tag
 * @returns {string} CSRF token or empty string
 */
function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
}

/**
 * Helper to make authenticated POST requests
 * Automatically includes CSRF token and handles 401
 *
 * @param {string} url - The URL to POST to
 * @param {object} data - Data to send as JSON
 * @returns {Promise} Promise that resolves to parsed JSON
 */
function authPost(url, data) {
    return authFetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify(data)
    });
}

// Export for use in modules if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { authFetch, checkAuthRequired, getCsrfToken, authPost };
}

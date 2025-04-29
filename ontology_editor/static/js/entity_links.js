/**
 * Entity Links JavaScript
 * 
 * This script handles the interaction with ontology entity links, enabling
 * users to view RDF data for specific entities.
 */

document.addEventListener('DOMContentLoaded', function() {
    // Add click handlers to all entity URI links
    setupEntityUriLinks();
});

/**
 * Set up click handlers for entity URI links
 */
function setupEntityUriLinks() {
    // Set up format badges for all entity URI elements
    setupFormatBadges();
    
    // Find all entity URI links
    document.querySelectorAll('.entity-uri-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Get the URI from the link
            const uri = this.getAttribute('href');
            
            // Open the URI in a new tab with the default format (Turtle)
            const formattedUri = formatEntityUri(uri, 'ttl');
            window.open(formattedUri, '_blank');
        });
    });
}

/**
 * Set up format badges for entity URI elements
 */
function setupFormatBadges() {
    document.querySelectorAll('.entity-uri').forEach(el => {
        const link = el.querySelector('.entity-uri-link');
        
        if (link) {
            // Get the URI from the link
            const uri = link.getAttribute('href');
            
            // Create format badge
            const badge = document.createElement('div');
            badge.className = 'format-badge';
            badge.innerHTML = `
                <span class="format-option" data-format="ttl">Turtle</span> | 
                <span class="format-option" data-format="xml">XML</span> | 
                <span class="format-option" data-format="json">JSON-LD</span> | 
                <span class="format-option" data-format="html">HTML</span>
            `;
            
            // Add badge to parent element
            el.style.position = 'relative';
            el.appendChild(badge);
            
            // Add click handlers to format options
            badge.querySelectorAll('.format-option').forEach(option => {
                option.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    // Get format
                    const format = this.dataset.format;
                    
                    // Format URI and open in new tab
                    const formattedUri = formatEntityUri(uri, format);
                    window.open(formattedUri, '_blank');
                });
            });
        }
    });
}

/**
 * Function to format entity URIs for content negotiation
 * Can be used by other scripts that need to generate entity links
 * 
 * @param {string} uri - The entity URI
 * @param {string} format - Optional format parameter ('ttl', 'xml', 'json', 'html')
 * @returns {string} - Formatted URI with content negotiation parameters
 */
function formatEntityUri(uri, format) {
    // If no format specified, return the URI as is
    if (!format) {
        return uri;
    }
    
    // Add format parameter
    return `${uri}?format=${format}`;
}

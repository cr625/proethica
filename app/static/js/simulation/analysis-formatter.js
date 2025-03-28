/**
 * Analysis Formatter
 * Handles parsing and formatting of LLM analyses including entity highlighting
 */

/**
 * Format entities within an analysis element
 * @param {HTMLElement} element - The analysis element
 * @param {Array} entities - List of entities to highlight
 */
function formatEntities(element, entities) {
  if (!element || !entities || !entities.length) return;
  
  // Get all text nodes within the element
  const textNodes = getTextNodes(element);
  
  // For each text node, check and replace entity mentions
  textNodes.forEach(node => {
    let content = node.nodeValue;
    if (!content || !content.trim()) return;
    
    let replacements = [];
    
    // Check for each entity
    entities.forEach(entity => {
      const regex = new RegExp('\\b' + escapeRegExp(entity.name) + '\\b', 'g');
      let match;
      
      while ((match = regex.exec(content)) !== null) {
        replacements.push({
          start: match.index,
          end: match.index + match[0].length,
          entity: entity
        });
      }
    });
    
    // If no replacements, skip this node
    if (replacements.length === 0) return;
    
    // Sort replacements in reverse order (to avoid offsets changing)
    replacements.sort((a, b) => b.start - a.start);
    
    // Apply replacements
    for (const replacement of replacements) {
      const before = content.substring(0, replacement.start);
      const after = content.substring(replacement.end);
      const entityHTML = `<span class="entity entity-${replacement.entity.type}" data-entity-id="${replacement.entity.id}">${replacement.entity.name}</span>`;
      
      // Create new nodes
      const parent = node.parentNode;
      const beforeTextNode = document.createTextNode(before);
      const entityElement = document.createElement('span');
      entityElement.innerHTML = entityHTML;
      const afterTextNode = document.createTextNode(after);
      
      // Replace the node
      parent.insertBefore(beforeTextNode, node);
      parent.insertBefore(entityElement.firstChild, node);
      parent.insertBefore(afterTextNode, node);
      parent.removeChild(node);
      
      // Update for next iteration
      content = after;
      node = afterTextNode;
    }
  });
}

/**
 * Get all text nodes within an element
 */
function getTextNodes(element) {
  let textNodes = [];
  const walker = document.createTreeWalker(
    element,
    NodeFilter.SHOW_TEXT,
    null,
    false
  );
  
  let node;
  while ((node = walker.nextNode())) {
    textNodes.push(node);
  }
  
  return textNodes;
}

/**
 * Escape special characters for RegExp
 */
function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Parse LLM analysis text into structured sections
 */
function parseAnalysisText(analysisText) {
  const sections = [];
  const optionPattern = /Option (\d+)(?::|\.)(.*?)(?=Option \d+|$)/gs;
  let generalText = analysisText;
  
  // Extract options
  let match;
  let optionPattern1 = new RegExp(optionPattern);
  while ((match = optionPattern1.exec(analysisText)) !== null) {
    const optionNum = match[1];
    const optionContent = match[2].trim();
    
    // Extract option text and content
    const lines = optionContent.split('\n', 1);
    const optionText = lines[0].trim();
    const content = lines.length > 1 ? optionContent.substring(lines[0].length).trim() : "";
    
    sections.push({
      type: 'option',
      option_number: optionNum,
      option_text: optionText,
      content: content,
      // Add formatted label with bold styling
      formatted_label: `<strong>Option ${optionNum}</strong>`
    });
    
    // Remove this option from general text
    generalText = generalText.replace(match[0], "");
  }
  
  // Process remaining general text
  const generalParas = generalText.trim().split(/\n\n+/);
  for (const para of generalParas) {
    if (para.trim()) {
      sections.push({
        type: 'paragraph',
        content: para.trim()
      });
    }
  }
  
  return sections;
}

// Make functions available globally
window.formatEntities = formatEntities;
window.parseAnalysisText = parseAnalysisText;

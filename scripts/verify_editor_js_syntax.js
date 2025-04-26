// Script to verify editor.js syntax
const fs = require('fs');
const path = require('path');

// Path to the editor.js file
const editorJsPath = path.join(__dirname, '..', 'ontology_editor', 'static', 'js', 'editor.js');

try {
  // Read the file
  const content = fs.readFileSync(editorJsPath, 'utf8');
  
  // Try to parse it to check for syntax errors
  try {
    // This will throw an error if there's a syntax issue
    eval('(function() { ' + content + ' })()');
    console.log('✅ editor.js syntax is valid!');
  } catch (syntaxError) {
    console.error('❌ Syntax error found:', syntaxError.message);
    
    // Find the approximate line number
    const lines = content.split('\n');
    const errorLine = syntaxError.lineNumber || 
      (syntaxError.stack && syntaxError.stack.match(/at .+:(\d+):\d+\)$/)?.[1]);
    
    if (errorLine && errorLine <= lines.length) {
      console.error(`Error around line ${errorLine}:`);
      // Show context around the error
      const start = Math.max(0, errorLine - 3);
      const end = Math.min(lines.length, parseInt(errorLine) + 3);
      for (let i = start; i < end; i++) {
        const lineNum = i + 1;
        const marker = lineNum === parseInt(errorLine) ? '>>> ' : '    ';
        console.error(`${marker}${lineNum}: ${lines[i]}`);
      }
    }
  }
} catch (err) {
  console.error('Error reading editor.js file:', err);
}

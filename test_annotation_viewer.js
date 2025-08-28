// Test script to manually check annotation viewer
// Run this in browser console on the guideline page

console.log("Testing Annotation Viewer...");

// Check if annotation viewer is initialized
if (window.annotationViewer) {
    console.log("✅ Annotation viewer is initialized");
    console.log(`Document ID: ${window.annotationViewer.documentId}`);
    console.log(`Document Type: ${window.annotationViewer.documentType}`);
    console.log(`Annotations loaded: ${window.annotationViewer.annotations.length}`);
    
    // Force reload annotations if needed
    console.log("🔄 Forcing annotation reload...");
    window.annotationViewer.loadAnnotations().then(() => {
        console.log(`✅ Reloaded ${window.annotationViewer.annotations.length} annotations`);
        
        // Show first few annotations
        if (window.annotationViewer.annotations.length > 0) {
            console.log("Sample annotations:");
            window.annotationViewer.annotations.slice(0, 5).forEach((ann, i) => {
                console.log(`  ${i+1}. "${ann.text_segment}" -> ${ann.concept_label} (${ann.confidence})`);
            });
        }
    });
} else {
    console.log("❌ Annotation viewer not found");
    console.log("Available global variables:", Object.keys(window).filter(k => k.includes('annotation')));
    
    // Check if required elements exist
    const contentContainer = document.querySelector('#documentContent, .document-content');
    const documentData = document.querySelector('[data-document-type][data-document-id]');
    
    console.log("Content container found:", !!contentContainer);
    console.log("Document data found:", !!documentData);
    
    if (documentData) {
        console.log("Document type:", documentData.dataset.documentType);
        console.log("Document ID:", documentData.dataset.documentId);
    }
}

// Test API directly
console.log("🔍 Testing API directly...");
fetch('/annotations/api/guideline/45')
    .then(response => response.json())
    .then(data => {
        console.log(`✅ API returned ${data.annotations.length} annotations`);
        if (data.annotations.length > 0) {
            console.log("Sample API annotations:");
            data.annotations.slice(0, 3).forEach((ann, i) => {
                console.log(`  ${i+1}. "${ann.text_segment}" -> ${ann.concept_label}`);
            });
        }
    })
    .catch(error => {
        console.error("❌ API error:", error);
    });
// This is a direct JavaScript fix that can be loaded in the browser
// to fix the ACE editor options on the fly

// Wait for the editor to be initialized
window.addEventListener('DOMContentLoaded', function() {
    // Wait a bit for ACE to initialize
    setTimeout(function() {
        if (typeof editor !== 'undefined') {
            console.log('Fixing ACE editor options...');
            
            // The correct option names according to ACE documentation
            editor.setOptions({
                enableBasicAutocompletion: true,
                enableLiveAutocompletion: true,
                fontSize: "14px",
                tabSize: 2
            });
            
            console.log('ACE editor options fixed!');
        } else {
            console.error('Could not find editor object to fix options');
        }
    }, 1000); // Wait 1 second
});

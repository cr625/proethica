function reloadDomains() {
    fetch((window.DOMAINS_TEST || {}).reloadUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            alert('Domain configurations reloaded successfully!');
            location.reload();
        } else {
            alert('Error reloading domains: ' + data.message);
        }
    })
    .catch(error => {
        alert('Error: ' + error);
    });
}

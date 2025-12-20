function showLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    if (!overlay) {
        return;
    }
    if (show) {
        overlay.classList.add('active');
    } else {
        overlay.classList.remove('active');
    }
}

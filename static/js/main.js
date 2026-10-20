// PMS Client-Side Script
document.addEventListener('DOMContentLoaded', () => {
    // Auto-dismiss alerts after 5 seconds if not error
    const alerts = document.querySelectorAll('.alert:not(.alert-danger)');
    alerts.forEach((alert) => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 5000);
    });
});

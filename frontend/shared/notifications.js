/**
 * Toast notifications shared by Pro and Lite frontends.
 */
(function (global) {
  function getNotificationIcon(type) {
    const icons = {
      success:
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>',
      error:
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
      warning:
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
      info:
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>',
    };
    return icons[type] || icons.info;
  }

  function getNotificationColor(type) {
    const colors = {
      success: "linear-gradient(135deg, #22c55e, #16a34a)",
      error: "linear-gradient(135deg, #f43f5e, #e11d48)",
      warning: "linear-gradient(135deg, #f59e0b, #d97706)",
      info: "linear-gradient(135deg, #6366f1, #4f46e5)",
    };
    return colors[type] || colors.info;
  }

  function show(message, type = "info") {
    const existing = document.querySelector(".notification");
    if (existing) {
      existing.remove();
    }

    const notification = document.createElement("div");
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-icon">
            ${getNotificationIcon(type)}
        </div>
        <div class="notification-message">${message}</div>
    `;

    notification.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 14px 20px;
        background: ${getNotificationColor(type)};
        border-radius: 10px;
        color: white;
        font-size: 14px;
        font-weight: 500;
        box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        z-index: 9999;
        animation: slideIn 0.3s ease-out;
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
      notification.style.animation = "slideOut 0.3s ease-out forwards";
      setTimeout(() => notification.remove(), 300);
    }, 3000);
  }

  global.DocuVisionNotify = {
    show,
    getNotificationIcon,
    getNotificationColor,
  };
})(typeof window !== "undefined" ? window : globalThis);

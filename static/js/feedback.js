'use strict';

function showFeedback(message, type = 'success') {
  let container = document.getElementById('feedbackContainer');

  // Create the container the first time a message is shown
  if (!container) {
    container = document.createElement('div');
    container.id = 'feedbackContainer';
    container.className = 'feedback-container';
    document.body.appendChild(container);
  }

  // Create the notification
  const notification = document.createElement('div');
  notification.className = `feedback-message feedback-${type}`;

  // Accessibility
  notification.setAttribute(
    'role',
    type === 'error' ? 'alert' : 'status'
  );

  const text = document.createElement('span');
  text.textContent = message;

  const closeButton = document.createElement('button');
  closeButton.type = 'button';
  closeButton.className = 'feedback-close';
  closeButton.setAttribute('aria-label', 'Close notification');
  closeButton.textContent = '×';

  closeButton.addEventListener('click', () => {
    notification.remove();
  });

  notification.appendChild(text);
  notification.appendChild(closeButton);

  container.appendChild(notification);

  // Automatically hide after 3.5 seconds
  setTimeout(() => {
    notification.classList.add('feedback-out');

    setTimeout(() => {
      notification.remove();
    }, 300);
  }, 3500);
}
if (typeof module !== 'undefined') {
  module.exports = {
    showFeedback
  };
}
/**
 * @jest-environment jsdom
 */

describe('Reusable feedback messages', () => {
  let showFeedback;

  beforeEach(() => {
    document.body.innerHTML = '';

    jest.resetModules();

    const feedback = require('../static/js/feedback.js');
    showFeedback = feedback.showFeedback;
  });

  test('creates a success notification', () => {
    showFeedback('Added to wishlist', 'success');

    const message = document.querySelector('.feedback-message');

    expect(message).not.toBeNull();
    expect(message.textContent).toContain('Added to wishlist');
    expect(message.classList.contains('feedback-success')).toBe(true);
  });

  test('creates an error notification', () => {
    showFeedback('Unable to complete request', 'error');

    const message = document.querySelector('.feedback-message');

    expect(message).not.toBeNull();
    expect(message.textContent).toContain('Unable to complete request');
    expect(message.classList.contains('feedback-error')).toBe(true);
  });

  test('creates the feedback container automatically', () => {
    showFeedback('Test message', 'success');

    const container = document.getElementById('feedbackContainer');

    expect(container).not.toBeNull();
  });

  test('close button removes notification', () => {
    showFeedback('Test message', 'success');

    const closeButton = document.querySelector('.feedback-close');

    closeButton.click();

    expect(
      document.querySelector('.feedback-message')
    ).toBeNull();
  });
});
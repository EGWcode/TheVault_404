/**
 * @jest-environment jsdom
 */

describe('Browse page states', () => {
  let discover;

  beforeEach(() => {
    document.body.innerHTML = `
      <div id="results"></div>
    `;

    document.body.dataset.page = 'test';

    jest.resetModules();

    discover = require('../static/js/discover.js');
  });

  test('shows loading state', () => {
    discover.showState(
      'Loading listings...',
      'loading'
    );

    const state = document.querySelector('.state-message');

    expect(state).not.toBeNull();
    expect(state.textContent).toContain('Loading listings...');
    expect(state.classList.contains('state-loading')).toBe(true);
  });

  test('shows empty state', () => {
    discover.showState(
      'No listings found.',
      'empty'
    );

    const state = document.querySelector('.state-message');

    expect(state.textContent).toContain('No listings found.');
    expect(state.classList.contains('state-empty')).toBe(true);
  });

  test('shows error state', () => {
    discover.showState(
      'Unable to load listings. Please try again.',
      'error'
    );

    const state = document.querySelector('.state-message');

    expect(state.textContent).toContain(
      'Unable to load listings. Please try again.'
    );

    expect(state.classList.contains('state-error')).toBe(true);
  });

  // tests

  test('shows empty state when API returns no listings', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => []
    });

    await discover.loadProducts();

    const state = document.querySelector('.state-message');

    expect(state).not.toBeNull();
    expect(state.classList.contains('state-empty')).toBe(true);
  });

  test('shows error state when API request fails', async () => {
    global.fetch = jest.fn().mockRejectedValue(
      new Error('Network error')
    );

    await discover.loadProducts();

    const state = document.querySelector('.state-message');

    expect(state).not.toBeNull();
    expect(state.classList.contains('state-error')).toBe(true);
  });

});
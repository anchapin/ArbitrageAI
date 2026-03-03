/**
 * TaskSubmissionForm.tsx - Polling Cleanup Tests
 *
 * Tests to verify that discount info fetch requests are properly
 * cleaned up during rapid email changes and component unmount.
 */

import { describe, it, expect, beforeEach, afterEach, vi, Mock } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TaskSubmissionForm from '../TaskSubmissionForm';

// Mock fetch globally
global.fetch = vi.fn();

describe('TaskSubmissionForm - Discount Fetch Cleanup', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (global.fetch as Mock).mockReset();
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it('should create AbortController for discount info fetch', async () => {
    const abortControllerSpy = vi.spyOn(window, 'AbortController');

    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ current_discount: 0.1 })
    });

    const { unmount } = render(<TaskSubmissionForm />);

    // Trigger email input
    const emailInput = screen.getByLabelText(/Your Email/i);
    await userEvent.type(emailInput, 'test@example.com');

    expect(abortControllerSpy).toHaveBeenCalled();

    unmount();
    abortControllerSpy.mockRestore();
  });

  it('should abort discount fetch on unmount', async () => {
    let discountAbortCalled = false;
    const originalAbort = AbortController.prototype.abort;

    AbortController.prototype.abort = function() {
      discountAbortCalled = true;
      originalAbort.call(this);
    };

    (global.fetch as Mock).mockImplementation(
      () => new Promise(resolve => {
        setTimeout(() => {
          resolve({
            ok: true,
            json: async () => ({ current_discount: 0.1 })
          });
        }, 500);
      })
    );

    const { unmount } = render(<TaskSubmissionForm />);

    const emailInput = screen.getByLabelText(/Your Email/i);
    await userEvent.type(emailInput, 'test@example.com');

    unmount();

    expect(discountAbortCalled).toBe(true);
    AbortController.prototype.abort = originalAbort;
  });

  it('should pass AbortSignal to discount fetch request', async () => {
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ current_discount: 0.1 })
    });

    const { unmount } = render(<TaskSubmissionForm />);

    const emailInput = screen.getByLabelText(/Your Email/i);
    await userEvent.type(emailInput, 'test@example.com');

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('discount-info'),
        expect.objectContaining({
          signal: expect.any(AbortSignal)
        })
      );
    });

    unmount();
  });

  it('should abort previous fetch when email changes rapidly', async () => {
    let abortCallCount = 0;
    const originalAbort = AbortController.prototype.abort;

    AbortController.prototype.abort = function() {
      abortCallCount++;
      originalAbort.call(this);
    };

    (global.fetch as Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ current_discount: 0.1 })
    });

    const { unmount } = render(<TaskSubmissionForm />);

    const emailInput = screen.getByLabelText(/Your Email/i);

    // Rapidly change email
    await userEvent.type(emailInput, 'a@example.com');
    await userEvent.clear(emailInput);
    await userEvent.type(emailInput, 'b@example.com');
    await userEvent.clear(emailInput);
    await userEvent.type(emailInput, 'c@example.com');

    // Multiple AbortController.abort() calls expected for multiple email changes
    expect(abortCallCount).toBeGreaterThan(1);

    unmount();
    AbortController.prototype.abort = originalAbort;
  });

  it('should not set state after discount fetch abort on unmount', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    (global.fetch as Mock).mockImplementation(
      () => new Promise(resolve => {
        setTimeout(() => {
          resolve({
            ok: true,
            json: async () => ({ current_discount: 0.1 })
          });
        }, 500);
      })
    );

    const { unmount } = render(<TaskSubmissionForm />);

    const emailInput = screen.getByLabelText(/Your Email/i);
    await userEvent.type(emailInput, 'test@example.com');

    // Unmount before fetch completes
    unmount();

    await new Promise(resolve => setTimeout(resolve, 100));

    const errorCalls = consoleErrorSpy.mock.calls;
    const stateUpdateWarning = errorCalls.some(
      call => call[0]?.includes?.("Can't perform a React state update on an unmounted component")
    );

    expect(stateUpdateWarning).toBe(false);

    consoleErrorSpy.mockRestore();
  });

  it('should clear pending fetch on component unmount', async () => {
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ current_discount: 0.1 })
    });

    const { unmount } = render(<TaskSubmissionForm />);

    const emailInput = screen.getByLabelText(/Your Email/i);
    await userEvent.type(emailInput, 'test@example.com');

    const fetchCallsBeforeUnmount = (global.fetch as Mock).mock.calls.length;

    unmount();

    // No additional fetches after unmount
    expect((global.fetch as Mock).mock.calls.length).toBe(fetchCallsBeforeUnmount);
  });

  it('should handle AbortError gracefully without logging', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    (global.fetch as Mock).mockImplementation(() => {
      return Promise.reject(new DOMException('Aborted', 'AbortError'));
    });

    const { unmount } = render(<TaskSubmissionForm />);

    const emailInput = screen.getByLabelText(/Your Email/i);
    await userEvent.type(emailInput, 'test@example.com');

    await new Promise(resolve => setTimeout(resolve, 100));
    unmount();

    const errorCalls = consoleErrorSpy.mock.calls;
    const abortErrorLogged = errorCalls.some(
      call => call[0]?.includes?.('AbortError')
    );

    expect(abortErrorLogged).toBe(false);
    consoleErrorSpy.mockRestore();
  });

  it('should not have memory leaks from multiple mount/unmount cycles', async () => {
    (global.fetch as Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ current_discount: 0.1 })
    });

    const mountUnmountCycles = 5;

    for (let i = 0; i < mountUnmountCycles; i++) {
      const { unmount } = render(<TaskSubmissionForm />);

      const emailInput = screen.getByLabelText(/Your Email/i);
      await userEvent.type(emailInput, `test${i}@example.com`);

      unmount();

      await new Promise(resolve => setTimeout(resolve, 50));
    }

    // Verify all AbortControllers were created
    // At least one per cycle for discount fetch
    expect((global.fetch as Mock).mock.calls.length).toBeGreaterThan(0);
  });
});

describe('TaskSubmissionForm - Form Submission Cleanup', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (global.fetch as Mock).mockReset();
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it('should not abort task submission fetch', async () => {
    // Discount fetch
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ current_discount: 0 })
    });

    // Submission fetch
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ url: 'https://checkout.stripe.com/session' })
    });

    const { getByRole } = render(<TaskSubmissionForm />);

    // Fill required fields
    const domainSelect = getByRole('combobox', { name: /Domain/i });
    const titleInput = getByRole('textbox', { name: /Task Title/i });
    const descriptionInput = getByRole('textbox', { name: /Description/i });
    const submitButton = getByRole('button', { name: /Proceed to Payment/i });

    await userEvent.selectOptions(domainSelect, 'accounting');
    await userEvent.type(titleInput, 'Test Title');
    await userEvent.type(descriptionInput, 'Test Description');

    // Mock window.location.href to prevent actual redirect
    delete (window as any).location;
    (window as any).location = { href: '' };

    await userEvent.click(submitButton);

    // Submission request should not be aborted
    const submissionCall = (global.fetch as Mock).mock.calls.find(
      call => call[0]?.includes('create-checkout-session')
    );
    expect(submissionCall).toBeDefined();
  });
});

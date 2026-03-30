import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ErrorBoundary from '../components/ErrorBoundary';

// Suppress console.error for these tests since we're testing error handling
const originalError = console.error;
beforeEach(() => {
  console.error = vi.fn();
});

afterEach(() => {
  console.error = originalError;
});

// Component that throws an error
function ErrorThrowingComponent() {
  throw new Error('Test error');
}

describe('ErrorBoundary', () => {
  it('renders children normally when there is no error', () => {
    render(
      <ErrorBoundary>
        <div>Test content</div>
      </ErrorBoundary>
    );

    expect(screen.getByText('Test content')).toBeInTheDocument();
  });

  it('renders error fallback UI when an error is caught', () => {
    render(
      <ErrorBoundary>
        <ErrorThrowingComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText(/unexpected error/i)).toBeInTheDocument();
  });

  it('displays the Try Again button', () => {
    render(
      <ErrorBoundary>
        <ErrorThrowingComponent />
      </ErrorBoundary>
    );

    const button = screen.getByRole('button', { name: /try again/i });
    expect(button).toBeInTheDocument();
  });

  it('resets the error state when Try Again button is clicked', async () => {
    const user = userEvent.setup();

    // Component that conditionally throws - won't throw on rerender
    let shouldThrow = true;
    function ConditionalErrorComponent() {
      if (shouldThrow) {
        throw new Error('Test error');
      }
      return <div>Test content after reset</div>;
    }

    const { rerender } = render(
      <ErrorBoundary>
        <ConditionalErrorComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();

    const button = screen.getByRole('button', { name: /try again/i });
    shouldThrow = false;

    // Rerender after setting shouldThrow to false
    rerender(
      <ErrorBoundary>
        <ConditionalErrorComponent />
      </ErrorBoundary>
    );

    await user.click(button);

    // After clicking Try Again, error state should be cleared
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
  });
});

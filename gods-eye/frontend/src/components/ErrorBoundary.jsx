import React from 'react'

// FE-M4: ErrorBoundary only catches synchronous render errors.
// Async errors (promises, event handlers) need window.onerror or
// window.addEventListener('unhandledrejection', ...) — not handled here.

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, attemptKey: 0 }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  handleRetry = () => {
    // FE-M5: Increment attemptKey to force a full remount of children,
    // preventing infinite error loops if the child throws immediately on render.
    this.setState((prev) => ({ hasError: false, error: null, attemptKey: prev.attemptKey + 1 }))
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#e74c3c' }}>
          <h2 style={{ marginBottom: '1rem' }}>Something went wrong</h2>
          <p style={{ color: '#666', marginBottom: '1rem' }}>
            The application encountered an unexpected error.
          </p>
          <button
            onClick={this.handleRetry}
            style={{
              padding: '0.5rem 1.5rem',
              background: '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '0.9rem',
            }}
          >
            Try Again
          </button>
        </div>
      )
    }
    return <React.Fragment key={this.state.attemptKey}>{this.props.children}</React.Fragment>
  }
}

export default ErrorBoundary

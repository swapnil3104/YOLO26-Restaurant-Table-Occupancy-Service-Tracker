import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallbackTitle?: string;
  onReset?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an unhandled error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '24px',
          background: '#fff1f2',
          border: '1px solid #fecdd3',
          borderRadius: 'var(--radius-lg, 12px)',
          color: '#9f1239',
          margin: '16px 0',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-start',
          gap: '12px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <AlertTriangle size={20} color="#e11d48" />
            <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700 }}>
              {this.props.fallbackTitle || 'Component Encountered an Error'}
            </h4>
          </div>
          <p style={{ margin: 0, fontSize: '0.82rem', color: '#be123c', maxWidth: '600px' }}>
            {this.state.error?.message || 'An unexpected rendering error occurred while mounting this view.'}
          </p>
          <button
            onClick={this.handleReset}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              background: '#e11d48',
              color: '#ffffff',
              border: 'none',
              borderRadius: 'var(--radius-md, 8px)',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              marginTop: '4px',
            }}
          >
            <RefreshCw size={13} />
            <span>Retry Component</span>
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;

'use client';

import { Component } from 'react';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="auth-shell flex min-h-screen items-center justify-center p-6">
          <div className="glass-auth-card w-full max-w-md rounded-xl border border-white/80 p-7 text-center">
            <div className="mx-auto mb-4 grid h-11 w-11 place-items-center rounded-full bg-rose-50 text-lg font-bold text-rose-700">!</div>
            <h2 className="mb-2 text-xl font-semibold text-slate-950">Something went wrong</h2>
            <p className="mb-5 text-sm leading-6 text-slate-500">
              {this.state.error?.message || 'An unexpected error occurred.'}
            </p>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="ui-primary"
            >
              Try again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

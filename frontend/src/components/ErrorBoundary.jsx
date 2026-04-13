import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(err) {
    return { error: err };
  }

  componentDidCatch(err, info) {
    console.error("[ErrorBoundary]", err, info.componentStack);
  }

  render() {
    if (this.state.error) {
      const { fallback } = this.props;
      if (fallback) return fallback(this.state.error);
      return (
        <div className="rounded-2xl border border-red-500/30 bg-red-950/30 p-5 text-sm text-red-300">
          <div className="font-bold mb-1">Erreur de rendu</div>
          <pre className="text-xs opacity-70 whitespace-pre-wrap">
            {this.state.error.message}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}

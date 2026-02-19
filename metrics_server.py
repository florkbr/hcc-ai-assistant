"""Separate Prometheus metrics server on port 9000."""

import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

# Import the metrics from lightspeed-stack
try:
    import lightspeed_stack.metrics as ls_metrics
except ImportError:
    print("Warning: Could not import lightspeed-stack metrics")
    ls_metrics = None


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for Prometheus metrics endpoint."""

    def do_GET(self):
        """Handle GET requests to /metrics."""
        if self.path == '/metrics':
            # Generate Prometheus metrics
            metrics_data = generate_latest()

            self.send_response(200)
            self.send_header('Content-Type', CONTENT_TYPE_LATEST)
            self.send_header('Content-Length', str(len(metrics_data)))
            self.end_headers()
            self.wfile.write(metrics_data)
        elif self.path == '/health':
            # Health check endpoint
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "healthy"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Override to reduce log noise."""
        pass


def start_metrics_server():
    """Start the Prometheus metrics HTTP server."""
    server = HTTPServer(('0.0.0.0', 9000), MetricsHandler)
    print("Prometheus metrics server starting on port 9000...")
    print("Access metrics at: http://localhost:9000/metrics")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Metrics server shutting down...")
        server.shutdown()


if __name__ == "__main__":
    start_metrics_server()
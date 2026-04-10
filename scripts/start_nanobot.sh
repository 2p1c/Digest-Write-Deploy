#!/bin/bash
set -e

# Generate nanobot config from template with environment variable substitution
envsubst < /app/configs/nanobot.${AGENT_NAME}.json > /root/.nanobot/config.json

echo "Starting nanobot gateway for ${AGENT_NAME}..."

# Run nanobot gateway in background
nanobot gateway &
NANOBOT_PID=$!

# Simple health check server on port 8000
python3 -c "
import http.server
import socketserver
import os

PORT = int(os.environ.get('AGENT_PORT', 8000))

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

with socketserver.TCPServer(('', PORT), Handler) as httpd:
    httpd.serve_forever()
" &
HEALTH_PID=$!

# Wait for both processes
trap "kill $NANOBOT_PID $HEALTH_PID 2>/dev/null" EXIT
wait

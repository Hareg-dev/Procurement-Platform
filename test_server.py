#!/usr/bin/env python3
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Hello Railway')

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    print(f"Starting server on port {port}")
    server = HTTPServer(('0.0.0.0', port), Handler)
    server.serve_forever()
import http.server
import socketserver
import argparse
import os

class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('port', nargs='?', type=int, default=8000, help='Port to serve on')
    parser.add_argument('-d', '--directory', default=os.getcwd(), help='Directory to serve')
    parser.add_argument('--bind', default='0.0.0.0', help='Specify alternate bind address [default: all interfaces]')
    args = parser.parse_args()

    os.chdir(args.directory)

    with socketserver.TCPServer((args.bind, args.port), CORSRequestHandler) as httpd:
        print(f"Serving CORS-enabled HTTP on port {args.port} (dir: {args.directory})")
        httpd.serve_forever()

if __name__ == '__main__':
    main()
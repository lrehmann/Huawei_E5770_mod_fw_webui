#!/usr/bin/env python3
"""Loopback-only visual preview. No device access and no settings writes."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import argparse

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/'system/www/cozy'


class Preview(BaseHTTPRequestHandler):
    def do_GET(self):
        path=urlsplit(self.path).path
        if path in ('/','/cgi-bin/ui.cgi'):
            data=(ROOT/'system/etc/cozy/ui.html').read_bytes();mime='text/html; charset=utf-8'
        elif path in ('/style.css','/app.js','/pixels.js','/glyphs.js'):
            data=(PUBLIC/path[1:]).read_bytes();mime='text/css' if path.endswith('.css') else 'text/javascript'
        else:
            self.send_error(404);return
        self.send_response(200)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.send_header('X-Frame-Options','DENY')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers();self.wfile.write(data)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=18765)
    args=parser.parse_args()
    print(f'Preview: http://127.0.0.1:{args.port}/cgi-bin/ui.cgi?preview=1',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Preview).serve_forever()

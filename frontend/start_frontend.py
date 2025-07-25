#!/usr/bin/env python3
"""
启动前端服务器
"""
import http.server
import socketserver
import os
import webbrowser

PORT = 8081
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

print("=" * 50)
print("KUAVO Studio 前端服务器")
print("=" * 50)
print(f"\n服务目录: {DIRECTORY}")
print(f"访问地址: http://localhost:{PORT}")
print("\n按 Ctrl+C 停止服务器\n")

# 自动打开浏览器
webbrowser.open(f'http://localhost:{PORT}')

with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
    httpd.serve_forever()
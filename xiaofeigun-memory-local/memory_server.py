#!/usr/bin/env python3
"""
小飞棍记忆搜索 HTTP 服务
为 OpenClaw 提供 memory_search API
作者：小飞棍 🪄
"""

import json
import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import urllib.parse

# 导入记忆索引
sys.path.insert(0, str(Path(__file__).parent))
from memory_index import MemoryIndex

class MemoryHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""
    
    indexer = None
    
    def log_message(self, format, *args):
        """禁用默认日志"""
        pass
    
    def _send_json(self, data, status=200):
        """发送 JSON 响应"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def do_GET(self):
        """处理 GET 请求"""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        
        if path == '/health':
            self._send_json({"status": "ok", "version": "2.0", "author": "xiaofeigun"})
        
        elif path == '/search':
            q = query.get('q', [''])[0]
            top_k = int(query.get('top_k', ['5'])[0])
            
            if not q:
                self._send_json({"error": "Missing query parameter 'q'"}, 400)
                return
            
            results = self.indexer.search(q, top_k=top_k)
            self._send_json({
                "query": q,
                "results": results,
                "total": len(results)
            })
        
        elif path == '/stats':
            self._send_json({
                "version": self.indexer.index.get("version"),
                "stats": self.indexer.index.get("stats"),
                "updated_at": self.indexer.index.get("updated_at"),
                "author": "xiaofeigun"
            })
        
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        """处理 POST 请求"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode()
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
            return
        
        if self.path == '/search':
            q = data.get('query', '')
            top_k = data.get('top_k', 5)
            
            if not q:
                self._send_json({"error": "Missing query"}, 400)
                return
            
            results = self.indexer.search(q, top_k=top_k)
            self._send_json({
                "query": q,
                "results": results,
                "total": len(results)
            })
        
        elif self.path == '/update':
            incremental = data.get('incremental', True)
            self.indexer.build_index(incremental=incremental)
            self._send_json({
                "status": "ok",
                "message": "Index updated",
                "stats": self.indexer.index.get("stats")
            })
        
        else:
            self._send_json({"error": "Not found"}, 404)


def run_server(port=8787, workspace="/root/.openclaw/workspace"):
    """运行 HTTP 服务"""
    # 初始化索引
    MemoryHandler.indexer = MemoryIndex(workspace)
    
    # 确保索引已建立
    if not MemoryHandler.indexer.index.get("files"):
        print("🔄 初始化索引...")
        MemoryHandler.indexer.build_index()
    
    # 启动监控
    MemoryHandler.indexer.start_watcher(interval=30)
    
    # 启动 HTTP 服务
    server = HTTPServer(('127.0.0.1', port), MemoryHandler)
    print(f"🚀 xiaofeigun-memory-local 服务已启动: http://127.0.0.1:{port}")
    print(f"📁 工作目录: {workspace}")
    print("\nAPI 端点:")
    print(f"  GET  /health         - 健康检查")
    print(f"  GET  /search?q=xxx   - 搜索记忆")
    print(f"  GET  /stats          - 索引统计")
    print(f"  POST /search         - 搜索记忆 (JSON)")
    print(f"  POST /update         - 更新索引")
    print("\n按 Ctrl+C 停止服务...")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 停止服务...")
        MemoryHandler.indexer.stop_watcher()
        server.shutdown()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='小飞棍记忆搜索服务')
    parser.add_argument('--port', type=int, default=8787, help='服务端口')
    parser.add_argument('--workspace', default='/root/.openclaw/workspace', help='工作目录')
    args = parser.parse_args()
    
    run_server(port=args.port, workspace=args.workspace)

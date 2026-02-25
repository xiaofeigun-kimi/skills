#!/usr/bin/env python3
"""
小飞棍轻量级记忆搜索系统 v2.0
基于 BM25 + 关键词索引，无需 embedding 模型
新增：自动监控、增量更新、权重优化、同义词支持
作者：小飞棍 🪄
"""

import os
import json
import re
import hashlib
import time
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from collections import defaultdict
import math

class MemoryIndex:
    """轻量级记忆索引器 v2.0"""
    
    # 同义词词典（双向映射）
    SYNONYMS = {
        # 中文同义词
        "小蝎子": ["用户", "主人", "朋友"],
        "用户": ["小蝎子", "主人", "朋友"],
        "小飞棍": ["我", "助手", "AI", "ai"],
        "我": ["小飞棍", "助手"],
        "记忆": ["记录", "日志", "笔记"],
        "记录": ["记忆", "日志"],
        "文件": ["文档", "资料"],
        "文档": ["文件", "资料"],
        # 英文同义词
        "user": ["human", "person", "friend"],
        "ai": ["assistant", "bot", "agent"],
        "memory": ["record", "log", "note"],
        "file": ["document", "doc"],
    }
    
    # BM25 参数
    BM25_K1 = 1.5  # 词频饱和度
    BM25_B = 0.75  # 文档长度归一化
    
    def __init__(self, workspace_path: str):
        self.workspace = Path(workspace_path)
        self.memory_dir = self.workspace / "memory"
        self.index_dir = self.workspace / ".memory-index"
        self.index_file = self.index_dir / "index.json"
        self.watcher_file = self.index_dir / "watcher.json"
        
        # 确保目录存在
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载索引
        self.index = self._load_index()
        self.watcher_state = self._load_watcher()
        
        # 监控线程
        self._watcher_thread = None
        self._watcher_running = False
    
    def _load_index(self) -> Dict:
        """加载索引文件"""
        if self.index_file.exists():
            with open(self.index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "version": "2.0",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "files": {},
            "keywords": {},
            "stats": {"total_files": 0, "total_chunks": 0, "total_keywords": 0}
        }
    
    def _load_watcher(self) -> Dict:
        """加载监控状态"""
        if self.watcher_file.exists():
            with open(self.watcher_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"last_check": 0, "file_mtimes": {}}
    
    def _save_index(self):
        """保存索引文件"""
        self.index["updated_at"] = datetime.now().isoformat()
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)
    
    def _save_watcher(self):
        """保存监控状态"""
        with open(self.watcher_file, 'w', encoding='utf-8') as f:
            json.dump(self.watcher_state, f, ensure_ascii=False, indent=2)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词（中文+英文）"""
        text = text.lower()
        
        # 提取英文单词
        english_words = re.findall(r'[a-z]+', text)
        
        # 提取中文词语（简单分词：2-4字词组）
        chinese_words = []
        for i in range(len(text)):
            for length in [4, 3, 2]:
                if i + length <= len(text):
                    word = text[i:i+length]
                    if '\u4e00' <= word[0] <= '\u9fff':
                        chinese_words.append(word)
        
        # 合并并去重
        all_words = list(set(english_words + chinese_words))
        
        # 停用词
        stopwords = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                     'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been',
                     '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', 
                     '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', 
                     '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '个',
                     '能', '可以', '把', '让', '给', '被', '跟', '对', '向', '从'}
        
        return [w for w in all_words if len(w) > 1 and w not in stopwords]
    
    def _expand_query(self, keywords: List[str]) -> List[str]:
        """扩展查询词（加入同义词）"""
        expanded = set(keywords)
        for kw in keywords:
            if kw in self.SYNONYMS:
                expanded.update(self.SYNONYMS[kw])
        return list(expanded)
    
    def _chunk_text(self, text: str) -> List[Dict]:
        """将文本分块（按标题）"""
        chunks = []
        lines = text.split('\n')
        
        current_chunk = []
        current_start = 0
        
        for i, line in enumerate(lines):
            if line.startswith('#') and current_chunk:
                chunk_text = '\n'.join(current_chunk)
                chunks.append({
                    "text": chunk_text,
                    "start_line": current_start + 1,
                    "end_line": i,
                    "hash": hashlib.md5(chunk_text.encode()).hexdigest()[:8]
                })
                current_chunk = [line]
                current_start = i
            else:
                current_chunk.append(line)
        
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append({
                "text": chunk_text,
                "start_line": current_start + 1,
                "end_line": len(lines),
                "hash": hashlib.md5(chunk_text.encode()).hexdigest()[:8]
            })
        
        return chunks
    
    def _calculate_bm25_score(self, term: str, doc_freq: int, total_docs: int, 
                               term_freq: int, doc_length: int, avg_doc_length: float) -> float:
        """计算 BM25 分数"""
        # IDF 计算
        idf = math.log((total_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1)
        
        # 词频归一化
        tf = (term_freq * (self.BM25_K1 + 1)) / \
             (term_freq + self.BM25_K1 * (1 - self.BM25_B + self.BM25_B * (doc_length / avg_doc_length)))
        
        return idf * tf
    
    def _index_single_file(self, file_path: Path) -> bool:
        """索引单个文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            chunks = self._chunk_text(content)
            rel_path = str(file_path.relative_to(self.workspace))
            file_stat = file_path.stat()
            
            file_info = {
                "path": rel_path,
                "mtime": file_stat.st_mtime,
                "size": file_stat.st_size,
                "chunks": []
            }
            
            for chunk in chunks:
                keywords = self._extract_keywords(chunk["text"])
                chunk_info = {
                    "hash": chunk["hash"],
                    "start_line": chunk["start_line"],
                    "end_line": chunk["end_line"],
                    "keywords": keywords,
                    "keyword_freq": {kw: keywords.count(kw) for kw in set(keywords)},
                    "length": len(chunk["text"]),
                    "preview": chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"]
                }
                file_info["chunks"].append(chunk_info)
                
                # 更新关键词索引
                for kw in set(keywords):
                    if kw not in self.index["keywords"]:
                        self.index["keywords"][kw] = []
                    self.index["keywords"][kw].append({
                        "file": rel_path,
                        "hash": chunk["hash"],
                        "freq": keywords.count(kw)
                    })
            
            self.index["files"][rel_path] = file_info
            return True
            
        except Exception as e:
            print(f"❌ 索引文件失败 {file_path}: {e}")
            return False
    
    def build_index(self, incremental: bool = False):
        """重建或增量更新索引"""
        if incremental:
            print("🔄 开始增量更新索引...")
        else:
            print("🔄 开始重建完整索引...")
            self.index = {
                "version": "2.0",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "files": {},
                "keywords": {},
                "stats": {}
            }
        
        # 收集需要索引的文件
        memory_files = list(self.memory_dir.glob("*.md"))
        memory_md = self.workspace / "MEMORY.md"
        if memory_md.exists():
            memory_files.append(memory_md)
        
        indexed_count = 0
        skipped_count = 0
        
        for file_path in memory_files:
            rel_path = str(file_path.relative_to(self.workspace))
            mtime = file_path.stat().st_mtime
            
            # 增量更新：跳过未修改的文件
            if incremental and rel_path in self.index["files"]:
                if self.index["files"][rel_path].get("mtime") == mtime:
                    skipped_count += 1
                    continue
            
            print(f"  📄 索引: {file_path.name}")
            if self._index_single_file(file_path):
                indexed_count += 1
        
        # 清理已删除的文件
        if incremental:
            current_files = {str(f.relative_to(self.workspace)) for f in memory_files}
            deleted_files = set(self.index["files"].keys()) - current_files
            for deleted in deleted_files:
                print(f"  🗑️  移除: {deleted}")
                del self.index["files"][deleted]
        
        # 更新统计
        total_chunks = sum(len(f["chunks"]) for f in self.index["files"].values())
        self.index["stats"] = {
            "total_files": len(self.index["files"]),
            "total_chunks": total_chunks,
            "total_keywords": len(self.index["keywords"])
        }
        
        self._save_index()
        
        if incremental:
            print(f"✅ 增量更新完成！新增/更新: {indexed_count}, 跳过: {skipped_count}, 删除: {len(deleted_files) if incremental else 0}")
        else:
            print(f"✅ 重建完成！文件: {self.index['stats']['total_files']}, 块: {total_chunks}, 关键词: {len(self.index['keywords'])}")
    
    def _is_hot_memory(self, file_path: str) -> bool:
        """判断是否为热记忆（今天或昨天的文件）"""
        from datetime import datetime, timedelta
        
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # 检查文件名是否包含今天或昨天的日期
        if today in file_path or yesterday in file_path:
            return True
        
        # MEMORY.md 始终是热记忆
        if "MEMORY.md" in file_path:
            return True
        
        return False
    
    def _search_in_hot_memory(self, query_keywords: List[str], top_k: int) -> List[Dict]:
        """在热记忆中搜索（今天+昨天的文件）"""
        hot_scores = defaultdict(lambda: {"score": 0, "matched_keywords": [], "term_freqs": {}})
        
        # 只遍历热记忆文件
        for file_path, file_info in self.index["files"].items():
            if not self._is_hot_memory(file_path):
                continue
            
            for chunk in file_info["chunks"]:
                chunk_text = chunk.get("text", "").lower()
                
                for kw in query_keywords:
                    if kw in chunk_text:
                        # 简化评分：关键词匹配次数
                        freq = chunk_text.count(kw)
                        if freq > 0:
                            key = (file_path, chunk["hash"])
                            hot_scores[key]["score"] += freq * 2.0  # 热记忆加权
                            hot_scores[key]["matched_keywords"].append(kw)
        
        if not hot_scores:
            return []
        
        # 按分数排序
        sorted_scores = sorted(hot_scores.items(), key=lambda x: x[1]["score"], reverse=True)
        
        # 组装结果
        results = []
        for (file_path, chunk_hash), data in sorted_scores[:top_k]:
            file_info = self.index["files"].get(file_path)
            if file_info:
                for chunk in file_info["chunks"]:
                    if chunk["hash"] == chunk_hash:
                        results.append({
                            "path": file_path,
                            "start_line": chunk["start_line"],
                            "end_line": chunk["end_line"],
                            "preview": chunk["preview"],
                            "score": round(data["score"], 4),
                            "matched_keywords": list(set(data["matched_keywords"])),
                            "is_hot": True
                        })
                        break
        
        return results
    
    def search(self, query: str, top_k: int = 5, use_hot_memory_first: bool = True) -> List[Dict]:
        """BM25 搜索记忆（支持热记忆快速通道）"""
        if not self.index["files"]:
            return []
        
        # 提取并扩展查询词
        query_keywords = self._extract_keywords(query)
        query_keywords = self._expand_query(query_keywords)
        
        if not query_keywords:
            return []
        
        # 热记忆快速通道：先搜今天+昨天的记忆
        if use_hot_memory_first:
            hot_results = self._search_in_hot_memory(query_keywords, top_k)
            if hot_results and hot_results[0]["score"] > 1.0:  # 如果热记忆有高质量匹配
                return hot_results[:top_k]
        
        # 计算平均文档长度
        total_length = sum(
            sum(c["length"] for c in f["chunks"]) 
            for f in self.index["files"].values()
        )
        total_chunks = self.index["stats"].get("total_chunks", 1)
        avg_doc_length = total_length / total_chunks if total_chunks > 0 else 1
        
        total_docs = total_chunks
        
        # 计算每个块的 BM25 分数
        scores = defaultdict(lambda: {"score": 0, "matched_keywords": [], "term_freqs": {}})
        
        for kw in query_keywords:
            if kw in self.index["keywords"]:
                doc_freq = len(self.index["keywords"][kw])
                
                for match in self.index["keywords"][kw]:
                    key = (match["file"], match["hash"])
                    
                    # 获取块信息
                    file_info = self.index["files"].get(match["file"])
                    if not file_info:
                        continue
                    
                    chunk_info = None
                    for c in file_info["chunks"]:
                        if c["hash"] == match["hash"]:
                            chunk_info = c
                            break
                    
                    if chunk_info:
                        term_freq = match["freq"]
                        doc_length = chunk_info["length"]
                        
                        # 计算 BM25 分数
                        score = self._calculate_bm25_score(
                            kw, doc_freq, total_docs, term_freq, doc_length, avg_doc_length
                        )
                        
                        scores[key]["score"] += score
                        scores[key]["matched_keywords"].append(kw)
                        scores[key]["term_freqs"][kw] = term_freq
        
        # 按分数排序
        sorted_scores = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
        
        # 组装结果
        results = []
        for (file_path, chunk_hash), data in sorted_scores[:top_k]:
            file_info = self.index["files"].get(file_path)
            if file_info:
                for chunk in file_info["chunks"]:
                    if chunk["hash"] == chunk_hash:
                        results.append({
                            "path": file_path,
                            "start_line": chunk["start_line"],
                            "end_line": chunk["end_line"],
                            "preview": chunk["preview"],
                            "score": round(data["score"], 4),
                            "matched_keywords": list(set(data["matched_keywords"]))
                        })
                        break
        
        return results
    
    def check_for_changes(self) -> bool:
        """检查文件是否有变化"""
        memory_files = list(self.memory_dir.glob("*.md"))
        memory_md = self.workspace / "MEMORY.md"
        if memory_md.exists():
            memory_files.append(memory_md)
        
        current_mtimes = {}
        for file_path in memory_files:
            rel_path = str(file_path.relative_to(self.workspace))
            current_mtimes[rel_path] = file_path.stat().st_mtime
        
        # 对比旧状态
        old_mtimes = self.watcher_state.get("file_mtimes", {})
        
        # 检查是否有变化
        has_changes = False
        
        # 新文件或修改的文件
        for path, mtime in current_mtimes.items():
            if path not in old_mtimes or old_mtimes[path] != mtime:
                has_changes = True
                break
        
        # 删除的文件
        if not has_changes:
            for path in old_mtimes:
                if path not in current_mtimes:
                    has_changes = True
                    break
        
        # 更新监控状态
        self.watcher_state["file_mtimes"] = current_mtimes
        self.watcher_state["last_check"] = time.time()
        self._save_watcher()
        
        return has_changes
    
    def start_watcher(self, interval: int = 30):
        """启动文件监控线程"""
        if self._watcher_running:
            print("⚠️ 监控已在运行")
            return
        
        self._watcher_running = True
        
        def watch_loop():
            while self._watcher_running:
                try:
                    if self.check_for_changes():
                        print(f"\n📝 检测到记忆文件变化，自动更新索引...")
                        self.build_index(incremental=True)
                        print("💡 可以继续输入命令\n> ", end="", flush=True)
                except Exception as e:
                    print(f"❌ 监控错误: {e}")
                
                time.sleep(interval)
        
        self._watcher_thread = threading.Thread(target=watch_loop, daemon=True)
        self._watcher_thread.start()
        print(f"👁️ 文件监控已启动（每 {interval} 秒检查一次）")
    
    def stop_watcher(self):
        """停止文件监控"""
        self._watcher_running = False
        if self._watcher_thread:
            self._watcher_thread.join(timeout=1)
        print("🛑 文件监控已停止")


def main():
    """命令行入口"""
    import sys
    
    workspace = os.environ.get("OPENCLAW_WORKSPACE", "/root/.openclaw/workspace")
    indexer = MemoryIndex(workspace)
    
    if len(sys.argv) < 2:
        print("🪄 小飞棍记忆搜索系统 v2.0")
        print("\n用法: python memory_index.py <command> [args]")
        print("\n命令:")
        print("  build              - 重建完整索引")
        print("  update             - 增量更新索引")
        print("  search <query>     - 搜索记忆")
        print("  watch              - 启动文件监控")
        print("  stop               - 停止文件监控")
        print("  stats              - 显示索引统计")
        print("  check              - 检查文件变化")
        return
    
    command = sys.argv[1]
    
    if command == "build":
        indexer.build_index(incremental=False)
    
    elif command == "update":
        indexer.build_index(incremental=True)
    
    elif command == "search":
        query = " ".join(sys.argv[2:])
        results = indexer.search(query)
        print(f"\n🔍 搜索: '{query}'")
        print(f"找到 {len(results)} 个结果:\n")
        for i, r in enumerate(results, 1):
            print(f"{i}. {r['path']} (行 {r['start_line']}-{r['end_line']}, 分数: {r['score']})")
            print(f"   匹配: {', '.join(r['matched_keywords'])}")
            print(f"   {r['preview'][:150]}...")
            print()
    
    elif command == "watch":
        indexer.start_watcher()
        print("按 Ctrl+C 停止监控...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            indexer.stop_watcher()
    
    elif command == "stop":
        indexer.stop_watcher()
    
    elif command == "stats":
        print(f"📊 索引统计:")
        print(f"  版本: {indexer.index['version']}")
        print(f"  创建时间: {indexer.index['created_at']}")
        print(f"  更新时间: {indexer.index['updated_at']}")
        print(f"  文件数: {indexer.index['stats'].get('total_files', 0)}")
        print(f"  块数: {indexer.index['stats'].get('total_chunks', 0)}")
        print(f"  关键词数: {indexer.index['stats'].get('total_keywords', 0)}")
    
    elif command == "check":
        if indexer.check_for_changes():
            print("📝 检测到文件变化")
        else:
            print("✅ 文件无变化")
    
    else:
        print(f"❌ 未知命令: {command}")


if __name__ == "__main__":
    main()

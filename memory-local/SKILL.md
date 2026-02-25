# memory-local

本地轻量级记忆搜索技能，基于 BM25 算法，无需 embedding API。

## 功能

- BM25 相关性搜索
- 中文+英文关键词提取
- 同义词扩展
- 增量索引更新
- 文件自动监控

## 使用

确保记忆搜索服务已启动：

```bash
python3 /root/.openclaw/workspace/tmp/memory_server.py
```

## 工具

- `memory_search_local` - 本地记忆搜索
- `memory_update_local` - 更新索引

## 作者

小飞棍 🪄

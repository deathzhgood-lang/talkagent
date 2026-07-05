# TalkAgent LightRAG-lite 优化路线

本文记录 TalkAgent 向 LightRAG 思路靠拢的轻量化实现路径。目标不是完整复刻 LightRAG，而是在保持本地、轻量、易演示的前提下，引入混合检索、轻量图谱和可观测检索。

## 当前已落地

- 混合检索：将 Chroma 向量检索、BM25 风格关键词检索、轻量实体图谱召回合并排序。
- 检索调试：来源中返回 `score`、`methods`、`vector_score`、`keyword_score`、`graph_score`。
- 检索测试：Gradio 侧边栏增加 Retrieval Test；API 增加 `/api/retrieval-test`。
- 轻量图谱：上传文档后从 chunk 中抽取实体、关键词和邻近关系，索引写入 `data/light_graph/index.json`。
- 路由模式：保留 `general/document/hybrid/missing_evidence`，同时支持 `naive/local/global/mix`。

## 与 LightRAG 的对应关系

| LightRAG 思路 | TalkAgent 轻量实现 |
| --- | --- |
| `naive` 向量 chunk 检索 | Chroma 向量召回 + 关键词召回 |
| `local` 实体局部检索 | 轻量图谱实体/关键词命中 |
| `global` 全局关系/主题检索 | 文档摘要目录 + 图谱关系召回 |
| `mix` 综合检索 | 向量、关键词、图谱三路融合 |
| references/citations | 来源 snippet + chunk_index + score + methods |

## 后续建议

1. 引入真正 reranker，例如 `BAAI/bge-reranker-base`，将 top 30 召回结果重排到 top 6。
2. 将轻量图谱从启发式抽取升级为 LLM 结构化抽取，字段包括 `entities`、`relations`、`facts`。
3. 为 Markdown、PDF、接口文档分别设计 chunk 策略，减少固定字符切块造成的语义断裂。
4. 实现 parent-child chunk：小块用于召回，父块用于补足回答上下文。
5. 增加检索评测集，记录 hit@k、正确文件命中率、答案引用完整度。

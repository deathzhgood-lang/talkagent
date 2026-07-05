# 测试说明

当前测试优先覆盖不依赖外部服务的核心逻辑，确保在没有 Ollama、没有真实 ChromaDB 查询、没有完整 BGE-M3 权重时也能快速回归。

## 运行方式

```bash
python -m pytest -q
```

## 覆盖范围

- `chat_store`：会话创建、消息追加、最近历史格式化。
- `question_router`：路由结果归一化规则。
- `text_splitter`：中文分块和 `chunk_index` metadata。
- `rag_chain` 辅助逻辑：回答标签归一化、来源展示规则、必选参数补全逻辑。
- `hybrid_retrieval`：向量、关键词、图谱召回融合后的排序和 metadata 输出。
- `light_graph`：轻量图谱构建、实体统计、图谱搜索和删除同步。

## 未覆盖范围

以下能力依赖外部服务或大模型效果，建议作为集成测试补充：

- Ollama 模型可用性和回答质量。
- ChromaDB 真实向量检索质量。
- 真实 reranker 或生产 embedding 模型的排序质量。
- OCR 对扫描 PDF、图片、DOCX 内嵌图片的识别效果。
- Gradio 和 Tk UI 的端到端交互。

## 集成测试建议

1. 启动 Ollama，并拉取 `.env` 中配置的模型。
2. 准备一份小型 Markdown 或 TXT 文档。
3. 通过 Web UI 上传入库。
4. 提问一个文档内明确存在的问题。
5. 在 Web UI 的 Retrieval Test 中用 `mix`、`naive`、`local`、`global` 对比召回片段。
6. 检查回答是否以 `【基于文档】` 或 `【综合回答】` 开头，并且来源区域有命中文档片段、score 和 methods。

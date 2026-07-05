# TalkAgent 项目交接文档

## 一、项目概述

在 `E:\talkagent` 构建一个基于 RAG 的 AI 智能问答客服系统。用户上传文档构建私有知识库，通过本地开源大模型回答基于文档的问题。

## 二、环境与选型

| 项目 | 选择 |
|------|------|
| 大模型 | Qwen3 1.8B (Ollama) — CPU 推理 |
| 向量数据库 | ChromaDB (持久化到 `data/chroma/`) |
| Embedding | BAAI/bge-m3 (sentence-transformers 本地加载) |
| 前端 | Gradio |
| 后端 | FastAPI |
| 部署 | Docker 容器化 (docker-compose 编排 Ollama + TalkAgent) |
| 项目结构 | 单体项目 |
| 包含功能 | 多格式上传(PDF/Word/TXT/MD)、多文件上传、多轮对话记忆、答案溯源、知识库管理、对话记录 |
| 不包含 | 流式输出 |

### 系统信息
- CPU: AMD Ryzen 5 5600 (6核)
- 内存: 16GB
- 无 NVIDIA GPU
- Python 3.14.5, Node.js v24.15.0
- 已安装: langchain-core 1.4.0, ollama 0.6.2, torch 2.12.0, sentence-transformers 5.5.1

## 三、已完成工作

### 目录结构
```
talkagent/
├── app/
│   ├── __init__.py          # 空白
│   ├── config.py            # ✅ 配置集中管理（从 .env 读取）
│   ├── embedder.py          # ✅ BGE-M3 embedding 封装 (BGEEmbeddings 类)
│   ├── document_loader.py   # ✅ 文档加载 (PDF/Word/TXT/MD)
│   ├── text_splitter.py     # ✅ 中文优化分块 (chunk_size=500, overlap=100)
│   └── vector_store.py      # ✅ ChromaDB CRUD (增删查改+统计)
├── app/rag_chain.py         # ❌ 未创建
├── app/chat_store.py        # ❌ 未创建
├── app/api.py               # ❌ 未创建
├── app/ui.py                # ❌ 未创建
├── app/main.py              # ❌ 未创建
├── data/uploads/            # ✅ 空目录
├── data/chroma/             # ✅ 空目录
├── data/conversations/      # ✅ 空目录
├── models/                  # ⚠️ BGE-M3 部分下载 (缺 pytorch_model.bin)
├── requirements.txt         # ✅
├── .env / .env.example      # ✅
├── Dockerfile               # ✅
└── docker-compose.yml       # ✅
```

### 已验证通过的模块
- `config.py` — 配置正确加载 ✅
- `requirements.txt` — 所有依赖安装成功 ✅
- `sentence-transformers` — 5.5.1 版本安装成功 ✅

### ⚠️ 未完成验证的模块
- `embedder.py` — BGE-M3 模型未完全下载，**无法验证**

## 四、当前阻塞：BGE-M3 模型下载

### 进度
- 已通过 ModelScope 下载到 `E:\talkagent\models\BAAI\bge-m3\`
- **已下载**：配置文件、tokenizer、onnx 文件等 28 个小文件
- **缺失**：`pytorch_model.bin` (约 2.12GB) — 模型权重文件
- 当前 models 目录大小: 2.7GB（主要是 onnx 文件）

### 下载命令（继续下载）
```bash
cd E:/talkagent
python -c "
from modelscope import snapshot_download
snapshot_download('BAAI/bge-m3', cache_dir='./models')
print('BGE-M3 下载完成')
"
```

ModelScope 使用阿里云镜像，国内速度稳定。预计大文件还需 20-40 分钟。

### 验证命令（下载完成后执行）
```bash
cd E:/talkagent
python -c "
from app.embedder import get_embedding
emb = get_embedding()
v = emb.embed_query('测试中文句子')
print('维度:', len(v))        # 期望: 1024
print('前5个值:', [round(x,4) for x in v[:5]])
print('Embedding OK')
"
```

## 五、待完成任务（按顺序）

### 任务 4: RAG 引擎 (`rag_chain.py`)
- 组合 embedding + ChromaDB 检索 + Ollama LLM 生成
- Prompt 模板（中文）:
```
你是一个基于文档知识库的问答助手。请严格根据以下提供的文档片段回答问题。
如果文档中没有相关信息，请如实回答"文档中未找到相关信息"。
不要编造文档中没有的内容。

历史对话：{chat_history}
参考文档：{context}
用户问题：{question}
```
- 使用 `langchain.chat_models.ChatOllama` 连接 Ollama
- 返回 `{answer, sources: [{file_name, chunk_index, snippet}]}`
- 验证: 先确保 Ollama 有 `qwen3:1.8b` 模型 (`ollama pull qwen3:1.8b`)

### 任务 5: 对话管理 (`chat_store.py`)
- JSON 持久化到 `data/conversations/{id}.json`
- 数据结构: `{id, title, created_at, messages: [{role, content, timestamp}]}`
- 多轮上下文: RAG prompt 注入最近 10 轮

### 任务 6: 后端 API (`api.py` + `main.py`)
- FastAPI 路由:
  - POST `/api/upload` — 多文件上传
  - GET `/api/documents` — 文档列表
  - DELETE `/api/documents/{id}` — 删除
  - POST `/api/chat` — 对话
  - GET `/api/conversations` — 对话列表
  - GET/DELETE `/api/conversations/{id}` — 对话详情/删除

### 任务 7: Gradio 界面 (`ui.py`)
- 两栏布局: 左侧知识库管理，右侧智能问答
- 左侧: 多文件上传、文档列表(含删除按钮)、知识库统计
- 右侧: 聊天气泡、输入框、答案溯源折叠区
- 顶部: 新建对话/切换对话/删除对话

### 任务 8: Docker 集成测试
- `docker-compose up` 启动 Ollama + TalkAgent
- 预先用 `ollama pull qwen3:1.8b` 确保模型存在
- 访问 `http://localhost:7860` 验证

## 六、关键注意事项

1. **Ollama 默认地址**: Docker 内 `http://ollama:11434`，本地测试时 `.env` 中改为 `http://localhost:11434`
2. **内存限制**: 16GB 跑 BGE-M3(约3GB) + Qwen3 1.8B(约4GB) + ChromaDB 还够用，但不要同时加载更多大模型
3. **ChromaDB 存储目录**: 在 `vector_store.py` 中硬编码了 collection_name = `"talkagent_knowledge"`
4. **文件上传**: `document_loader.py` 先存到 `data/uploads/` 再加载
5. **分块分隔符**: 中文标点优先级高于空格，保证中文字段完整
6. **embedder.py 单例**: `get_embedding()` 返回全局单例，避免重复加载模型

## 七、架构图

```
Docker Compose
├── Ollama 容器 (端口 11434) — Qwen3 1.8B
└── TalkAgent 容器 (端口 7860)
    ├── Gradio UI — 知识库管理 + 问答聊天
    ├── FastAPI (端口 8000) — REST API
    ├── RAG 引擎 — 文档加载→分块→Embedding→ChromaDB→检索→Ollama 生成
    └── 数据持久化 — data/ (uploads + chroma + conversations)
```

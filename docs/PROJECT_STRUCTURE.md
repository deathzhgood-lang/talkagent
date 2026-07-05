# 目录结构说明

本文档用于说明当前项目目录的职责边界，避免后续开发时把运行数据、文档资产和应用代码混在一起。

## 推荐阅读入口

- `README.md`：面向演示、部署和使用的主说明。
- `docs/ARCHITECTURE.md`：系统架构、RAG 流程和 Agent 状态流。
- `docs/TESTING.md`：测试范围和运行方式。
- `CODE.md`：历史交接文档，仅作为参考。

## 目录职责

```text
talkagent/
├── app/                         # 主应用代码，以这里为准
├── docs/                        # 项目文档、架构说明、演示截图
├── tests/                       # 自动化测试
├── data/                        # 本地运行数据，不建议提交到生产代码仓库
├── models/                      # 本地模型缓存
├── scripts/                     # 报告、PPT、材料生成脚本
├── output/                      # 生成产物
├── tmp/                         # 临时产物
├── .deps/                       # 本地补充依赖
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## `app/` 模块分组

```text
app/
├── main.py                      # FastAPI + Gradio 挂载入口
├── api.py                       # REST API
├── ui.py                        # Gradio UI
├── desktop.py                   # Tk 桌面端
├── config.py                    # 环境变量和路径配置
├── document_loader.py           # 文档加载
├── ocr.py                       # OCR
├── text_splitter.py             # 分块
├── embedder.py                  # Embedding
├── vector_store.py              # 向量库
├── knowledge_index.py           # 文档摘要目录
├── question_router.py           # 问题路由
├── rag_chain.py                 # RAG 问答编排
├── answer_checker.py            # 回答自检
├── llm_client.py                # Ollama 调用
└── chat_store.py                # 会话存储
```

## 当前兼容性说明

`app/app/` 是历史复制出来的重复包目录，内容与顶层 `app/` 基本一致。当前运行入口使用顶层 `app/`，后续清理时建议先确认所有启动脚本和 Docker 构建都不依赖该重复目录，再删除它。

本轮整理没有删除历史目录，目的是保留现有核心功能和启动兼容性。

## 维护约定

- 应用代码放在 `app/`。
- 文档、架构图、截图放在 `docs/`。
- 测试放在 `tests/`。
- 新增演示截图统一放到 `docs/images/`，并在 README 中引用。
- 运行数据放在 `data/`，不要把临时验证数据写入代码目录。
- 临时生成物放在 `tmp/`，正式交付物放在 `output/`。


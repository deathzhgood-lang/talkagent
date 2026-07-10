import json
from pathlib import Path
from typing import Any

import gradio as gr

from app import chat_store
from app import trace_store
from app.document_loader import load_file_from_bytes
from app.hybrid_retrieval import hybrid_search
from app.knowledge_index import remove_document_from_index, summarize_document
from app.light_graph import build_graph_for_document, remove_document_from_graph
from app.rag_chain import answer_question
from app.text_splitter import split_documents
from app.vector_store import add_documents, delete_by_file, get_all_files, get_stats


def _document_rows() -> list[list[Any]]:
    return [
        [doc["file_name"], doc["chunk_count"], doc["file_id"]]
        for doc in get_all_files()
    ]


def _document_stats() -> str:
    stats = get_stats()
    return f"文件数: {stats['total_files']}    片段数: {stats['total_chunks']}"


def _file_choices() -> list[tuple[str, str]]:
    return [
        (f"{doc['file_name']} ({doc['chunk_count']} 个片段)", doc["file_id"])
        for doc in get_all_files()
    ]


def _conversation_choices() -> list[tuple[str, str]]:
    choices = []
    for item in chat_store.list_conversations():
        label = f"{item['title']} · {item['message_count']} 条 · {item['updated_at']}"
        choices.append((label, item["id"]))
    return choices


def _trace_choices(search: str = "") -> list[tuple[str, str]]:
    choices = []
    for trace in trace_store.list_runs(search=search, limit=60):
        question = " ".join((trace.get("question") or "").split())[:48]
        label = (
            f"{trace.get('started_at', '')[:19]} | {trace.get('status')} | "
            f"{trace.get('candidate_count', 0)} chunks | {question}"
        )
        choices.append((label, trace["trace_id"]))
    return choices


def refresh_traces(search: str = ""):
    try:
        choices = _trace_choices(search or "")
    except Exception as exc:
        return gr.update(choices=[], value=None), f"Trace 查询失败: {exc}"
    value = choices[0][1] if choices else None
    return gr.update(choices=choices, value=value), f"找到 {len(choices)} 条 Trace"


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def load_trace(trace_id: str | None, candidate_search: str = ""):
    if not trace_id:
        return "尚未选择 Trace。", "", ""
    try:
        trace = trace_store.get_run(trace_id)
    except Exception as exc:
        return f"Trace 加载失败: {exc}", "", ""
    if trace is None:
        return "Trace 不存在。", "", ""

    route_event = next(
        (event for event in trace["events"] if event["stage"] == "route_decided"),
        None,
    )
    overview_lines = [
        f"Trace ID: {trace['trace_id']}",
        f"状态: {trace['status']}",
        f"开始时间: {trace['started_at']}",
        f"总耗时: {trace.get('duration_ms') or 0} ms",
        f"用户问题: {trace['question']}",
        f"路由模式: {trace.get('route_mode') or '-'}",
        f"回答标签: {trace.get('answer_label') or '-'}",
    ]
    if trace.get("error"):
        overview_lines.append(f"异常: {trace['error']}")
    if route_event:
        overview_lines.extend(["", "路由判断:", _json_text(route_event["payload"])])

    timeline_lines = []
    for event in trace["events"]:
        duration = f" {event['duration_ms']} ms" if event.get("duration_ms") is not None else ""
        timeline_lines.append(
            f"[{event['sequence']}] {event['stage']} / {event['status']}{duration}\n"
            f"{event['summary']}\n{_json_text(event['payload'])}"
        )

    keyword = (candidate_search or "").strip().lower()
    all_candidates = trace["candidates"]
    candidates = [
        candidate
        for candidate in all_candidates
        if not keyword
        or keyword in (candidate.get("file_name") or "").lower()
        or keyword in (candidate.get("content") or "").lower()
        or keyword in (candidate.get("retrieval_query") or "").lower()
    ]
    candidate_lines = [
        f"显示 {len(candidates)} / {len(all_candidates)} 个已考察片段。"
    ]
    for candidate in candidates[:80]:
        context_status = "已送入上下文" if candidate["used_in_context"] else "仅候选"
        candidate_lines.extend(
            [
                "",
                (
                    f"[{context_status}] query={candidate['retrieval_query']} "
                    f"rank={candidate['rank']} score={candidate['score']} "
                    f"methods={','.join(candidate['methods'])}"
                ),
                (
                    f"file={candidate['file_name']} file_id={candidate['file_id']} "
                    f"chunk={candidate['chunk_index']} vector={candidate['vector_score']} "
                    f"keyword={candidate['keyword_score']} graph={candidate['graph_score']}"
                ),
                candidate["content"],
            ]
        )
    if len(candidates) > 80:
        candidate_lines.append("\n仅显示前 80 个匹配片段。")

    return "\n".join(overview_lines), "\n\n".join(timeline_lines), "\n".join(candidate_lines)


def _format_sources(sources: list[dict[str, Any]] | None) -> str:
    if not sources:
        return "暂无来源"
    lines = []
    for source in sources:
        methods = ",".join(source.get("methods") or [])
        score = source.get("score")
        score_text = f" score={score}" if score is not None else ""
        method_text = f" [{methods}]" if methods else ""
        lines.append(
            f"- {source.get('file_name', '未知文件')} / 片段 {source.get('chunk_index')}: "
            f"{source.get('snippet', '')}{method_text}{score_text}"
        )
    return "\n".join(lines)


def _assistant_content(content: str, sources: list[dict[str, Any]] | None = None) -> str:
    source_text = _format_sources(sources)
    if source_text == "暂无来源":
        return content
    return f"{content}\n\n参考来源：\n{source_text}"


def _messages_for_conversation(conversation_id: str | None) -> list[tuple[str, str]]:
    if not conversation_id:
        return []
    conversation = chat_store.get_conversation(conversation_id)
    if conversation is None:
        return []

    messages: list[tuple[str, str]] = []
    pending_user: str | None = None
    for message in conversation.get("messages", []):
        role = message.get("role", "assistant")
        content = message.get("content", "")
        if role == "user":
            if pending_user is not None:
                messages.append((pending_user, ""))
            pending_user = content
            continue
        content = _assistant_content(content, message.get("sources", []))
        messages.append((pending_user or "", content))
        pending_user = None
    if pending_user is not None:
        messages.append((pending_user, ""))
    return messages


def refresh_documents():
    return (
        _document_stats(),
        _document_rows(),
        gr.update(choices=_file_choices(), value=None),
    )


def run_retrieval_test(query, mode):
    query = (query or "").strip()
    if not query:
        return "Please enter a retrieval test query."
    result = hybrid_search(query, k=8, mode=mode or "mix")
    if not result.docs:
        return "No chunks retrieved."
    lines = []
    for index, doc in enumerate(result.docs, start=1):
        meta = doc.metadata or {}
        methods = ",".join(meta.get("retrieval_methods") or [])
        snippet = (doc.page_content or "").replace("\n", " ").strip()[:220]
        lines.append(
            f"{index}. {meta.get('file_name') or meta.get('source')} "
            f"chunk={meta.get('chunk_index')} score={meta.get('retrieval_score')} "
            f"methods={methods}\n{snippet}"
        )
    return "\n\n".join(lines)


def upload_files(files):
    if not files:
        return (
            "请选择要上传的 PDF、Word、TXT 或 Markdown 文件。",
            _document_stats(),
            _document_rows(),
            gr.update(choices=_file_choices(), value=None),
        )

    messages = []
    for file in files:
        file_name = Path(file.name).name
        try:
            with open(file.name, "rb") as f:
                docs = load_file_from_bytes(f.read(), file_name)
            chunks = split_documents(docs)
            file_id = add_documents(chunks, file_name)
            summary = summarize_document(file_id, file_name, chunks)
            build_graph_for_document(file_id, file_name, chunks, summary)
            messages.append(f"{file_name} 入库成功，片段数 {len(chunks)}，file_id={file_id}")
        except Exception as exc:
            messages.append(f"{file_name} 入库失败：{exc}")

    return (
        "\n".join(messages),
        _document_stats(),
        _document_rows(),
        gr.update(choices=_file_choices(), value=None),
    )


def delete_file(file_id):
    if not file_id:
        return (
            "请选择要删除的文档。",
            _document_stats(),
            _document_rows(),
            gr.update(choices=_file_choices(), value=None),
        )

    deleted = delete_by_file(file_id)
    remove_document_from_index(file_id)
    remove_document_from_graph(file_id)
    return (
        f"已删除 {deleted} 个片段。",
        _document_stats(),
        _document_rows(),
        gr.update(choices=_file_choices(), value=None),
    )


def new_chat():
    conversation = chat_store.create_conversation()
    choices = _conversation_choices()
    return (
        [],
        conversation["id"],
        gr.update(choices=choices, value=conversation["id"]),
        "新对话已创建。",
        "暂无来源",
    )


def load_conversation(conversation_id):
    if not conversation_id:
        return [], None, "请选择一个对话。", "暂无来源"
    messages = _messages_for_conversation(conversation_id)
    return messages, conversation_id, "已切换对话。", "暂无来源"


def delete_chat(conversation_id):
    if not conversation_id:
        return (
            [],
            None,
            gr.update(choices=_conversation_choices(), value=None),
            "请选择要删除的对话。",
            "暂无来源",
        )

    deleted = chat_store.delete_conversation(conversation_id)
    return (
        [],
        None,
        gr.update(choices=_conversation_choices(), value=None),
        "对话已删除。" if deleted else "对话不存在。",
        "暂无来源",
    )


def ask(message, history, conversation_id):
    message = (message or "").strip()
    if not message:
        return history, conversation_id, "", gr.update(choices=_conversation_choices(), value=conversation_id), "请输入问题。", "暂无来源"

    if not conversation_id:
        conversation = chat_store.create_conversation(title=message[:30])
        conversation_id = conversation["id"]

    history = list(history or [])
    chat_store.add_message(conversation_id, "user", message)

    result = answer_question(message, conversation_id)
    sources = result.get("sources", [])
    answer = result["answer"]
    chat_store.add_message(conversation_id, "assistant", answer, sources=sources)
    history.append((message, _assistant_content(answer, sources)))

    return (
        history,
        conversation_id,
        "",
        gr.update(choices=_conversation_choices(), value=conversation_id),
        "已回答。",
        _format_sources(sources),
    )


def build_ui():
    with gr.Blocks(title="TalkAgent") as demo:
        conversation_id = gr.State(value=None)

        gr.Markdown("# TalkAgent 本地知识库问答")
        with gr.Row():
            with gr.Column(scale=1, min_width=320):
                gr.Markdown("## 知识库")
                files = gr.File(
                    label="上传文档",
                    file_count="multiple",
                    file_types=[".pdf", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg"],
                )
                with gr.Row():
                    upload_btn = gr.Button("入库", variant="primary")
                    refresh_docs_btn = gr.Button("刷新")
                upload_status = gr.Textbox(label="处理状态", lines=4, interactive=False)
                doc_stats = gr.Markdown(value=_document_stats)
                doc_table = gr.Dataframe(
                    headers=["文件名", "片段数", "file_id"],
                    value=_document_rows,
                    interactive=False,
                    wrap=True,
                )
                delete_file_select = gr.Dropdown(
                    label="删除文档",
                    choices=_file_choices(),
                    value=None,
                    interactive=True,
                )
                delete_file_btn = gr.Button("删除所选文档")

                gr.Markdown("## Retrieval Test")
                retrieval_query = gr.Textbox(label="Query", lines=2)
                retrieval_mode = gr.Dropdown(
                    label="Mode",
                    choices=["mix", "naive", "local", "global"],
                    value="mix",
                    interactive=True,
                )
                retrieval_test_btn = gr.Button("Run Retrieval Test")
                retrieval_test_output = gr.Textbox(
                    label="Retrieved Chunks",
                    lines=10,
                    interactive=False,
                )

            with gr.Column(scale=2, min_width=520):
                gr.Markdown("## 对话")
                with gr.Row():
                    conversation_select = gr.Dropdown(
                        label="历史对话",
                        choices=_conversation_choices(),
                        value=None,
                        interactive=True,
                    )
                    new_btn = gr.Button("新建对话")
                    delete_chat_btn = gr.Button("删除对话")
                chat_status = gr.Textbox(label="对话状态", value="请选择或新建对话，也可以直接提问。", interactive=False)
                chatbot = gr.Chatbot(label="智能问答", height=520)
                message = gr.Textbox(label="输入问题", lines=3, placeholder="请输入关于已上传文档的问题")
                with gr.Row():
                    send_btn = gr.Button("发送", variant="primary")
                    clear_input_btn = gr.Button("清空输入")
                sources_box = gr.Textbox(label="本轮来源", value="暂无来源", lines=6, interactive=False)

        with gr.Accordion("开发者控制台", open=False):
            with gr.Row():
                trace_search = gr.Textbox(label="Trace 检索", lines=1)
                trace_refresh_btn = gr.Button("刷新 Trace")
            trace_status = gr.Textbox(label="Trace 状态", interactive=False)
            trace_select = gr.Dropdown(
                label="Trace 运行记录",
                choices=_trace_choices(),
                value=None,
                interactive=True,
            )
            with gr.Row():
                trace_candidate_search = gr.Textbox(label="候选片段检索", lines=1)
                trace_load_btn = gr.Button("查看 Trace")
            trace_overview = gr.Textbox(label="Trace 概览", lines=13, interactive=False)
            trace_timeline = gr.Textbox(label="决策与执行时间线", lines=22, interactive=False)
            trace_candidates = gr.Textbox(label="已考察片段", lines=28, interactive=False)

        upload_btn.click(
            upload_files,
            inputs=files,
            outputs=[upload_status, doc_stats, doc_table, delete_file_select],
        )
        refresh_docs_btn.click(
            refresh_documents,
            outputs=[doc_stats, doc_table, delete_file_select],
        )
        delete_file_btn.click(
            delete_file,
            inputs=delete_file_select,
            outputs=[upload_status, doc_stats, doc_table, delete_file_select],
        )
        retrieval_test_btn.click(
            run_retrieval_test,
            inputs=[retrieval_query, retrieval_mode],
            outputs=retrieval_test_output,
        )
        new_btn.click(
            new_chat,
            outputs=[chatbot, conversation_id, conversation_select, chat_status, sources_box],
        )
        conversation_select.change(
            load_conversation,
            inputs=conversation_select,
            outputs=[chatbot, conversation_id, chat_status, sources_box],
        )
        delete_chat_btn.click(
            delete_chat,
            inputs=conversation_id,
            outputs=[chatbot, conversation_id, conversation_select, chat_status, sources_box],
        )
        send_btn.click(
            ask,
            inputs=[message, chatbot, conversation_id],
            outputs=[chatbot, conversation_id, message, conversation_select, chat_status, sources_box],
        )
        message.submit(
            ask,
            inputs=[message, chatbot, conversation_id],
            outputs=[chatbot, conversation_id, message, conversation_select, chat_status, sources_box],
        )
        clear_input_btn.click(lambda: "", outputs=message)
        trace_refresh_btn.click(
            refresh_traces,
            inputs=trace_search,
            outputs=[trace_select, trace_status],
        )
        trace_load_btn.click(
            load_trace,
            inputs=[trace_select, trace_candidate_search],
            outputs=[trace_overview, trace_timeline, trace_candidates],
        )
        trace_select.change(
            load_trace,
            inputs=[trace_select, trace_candidate_search],
            outputs=[trace_overview, trace_timeline, trace_candidates],
        )
        trace_candidate_search.submit(
            load_trace,
            inputs=[trace_select, trace_candidate_search],
            outputs=[trace_overview, trace_timeline, trace_candidates],
        )

    return demo

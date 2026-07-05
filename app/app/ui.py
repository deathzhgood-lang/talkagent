from pathlib import Path
from typing import Any

import gradio as gr

from app import chat_store
from app.document_loader import load_file_from_bytes
from app.knowledge_index import remove_document_from_index, summarize_document
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


def _format_sources(sources: list[dict[str, Any]] | None) -> str:
    if not sources:
        return "暂无来源"
    lines = []
    for source in sources:
        lines.append(
            f"- {source.get('file_name', '未知文件')} / 片段 {source.get('chunk_index')}: "
            f"{source.get('snippet', '')}"
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
            summarize_document(file_id, file_name, chunks)
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

    return demo

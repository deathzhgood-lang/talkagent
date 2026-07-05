import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from app import chat_store
from app.document_loader import load_file_from_bytes
from app.knowledge_index import remove_document_from_index, summarize_document
from app.ocr import get_ocr_status
from app.rag_chain import answer_question
from app.text_splitter import split_documents
from app.vector_store import add_documents, delete_by_file, get_all_files, get_stats


TaskResult = tuple[Callable[..., None], tuple[Any, ...]]


class TalkAgentDesktop(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("TalkAgent")
        self.geometry("1040x720")
        self.minsize(860, 560)

        self.current_conversation_id: str | None = None
        self.conversation_ids: list[str] = []
        self.task_queue: queue.Queue[TaskResult] = queue.Queue()
        self.knowledge_visible = tk.BooleanVar(value=False)
        self.sources_visible = tk.BooleanVar(value=False)

        self._configure_theme()
        self._build_layout()
        self.refresh_documents()
        self.refresh_conversations()
        self.after(100, self._poll_tasks)

    def _configure_theme(self) -> None:
        self.configure(bg="#f6f7f9")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f6f7f9")
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure("TLabel", background="#f6f7f9", foreground="#20242a")
        style.configure("Panel.TLabel", background="#ffffff", foreground="#20242a")
        style.configure("TButton", padding=(10, 6), relief="flat")
        style.configure("Icon.TButton", padding=(8, 5), relief="flat")
        style.configure("Primary.TButton", padding=(12, 7), relief="flat", background="#2563eb", foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#1d4ed8")])

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self._build_toolbar()
        self._build_knowledge_panel()
        self._build_chat_area()
        self._build_input_area()
        self._build_status_bar()

    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self, padding=(12, 10))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(2, weight=1)

        ttk.Label(toolbar, text="TalkAgent", font=("", 15, "bold")).grid(row=0, column=0, sticky="w")
        self.knowledge_btn = ttk.Button(toolbar, text="＋ 文档", style="Icon.TButton", command=self.toggle_knowledge_panel)
        self.knowledge_btn.grid(row=0, column=1, padx=(14, 8))

        self.conversation_var = tk.StringVar()
        self.conversation_combo = ttk.Combobox(toolbar, textvariable=self.conversation_var, state="readonly", width=36)
        self.conversation_combo.grid(row=0, column=2, sticky="e", padx=(8, 8))
        self.conversation_combo.bind("<<ComboboxSelected>>", self.load_selected_conversation)

        ttk.Button(toolbar, text="＋", style="Icon.TButton", command=self.new_chat).grid(row=0, column=3, padx=3)
        ttk.Button(toolbar, text="×", style="Icon.TButton", command=self.delete_current_chat).grid(row=0, column=4, padx=3)
        ttk.Button(toolbar, text="↻", style="Icon.TButton", command=self.refresh_conversations).grid(row=0, column=5, padx=3)

    def _build_knowledge_panel(self) -> None:
        self.knowledge_panel = ttk.Frame(self, style="Panel.TFrame", padding=12)
        self.knowledge_panel.columnconfigure(0, weight=1)
        self.knowledge_panel.rowconfigure(2, weight=1)

        top = ttk.Frame(self.knowledge_panel, style="Panel.TFrame")
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="知识库", style="Panel.TLabel", font=("", 12, "bold")).grid(row=0, column=0, sticky="w")
        self.doc_stats_var = tk.StringVar(value="文件数: 0    片段数: 0")
        ttk.Label(top, textvariable=self.doc_stats_var, style="Panel.TLabel").grid(row=0, column=1, sticky="e")

        actions = ttk.Frame(self.knowledge_panel, style="Panel.TFrame")
        actions.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        ttk.Button(actions, text="＋ 上传", command=self.upload_files).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="↻ 刷新", command=self.refresh_documents).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="× 删除", command=self.delete_selected_file).pack(side=tk.LEFT)

        columns = ("file_name", "chunk_count", "file_id")
        self.doc_tree = ttk.Treeview(self.knowledge_panel, columns=columns, show="headings", selectmode="browse", height=5)
        self.doc_tree.heading("file_name", text="文件")
        self.doc_tree.heading("chunk_count", text="片段")
        self.doc_tree.heading("file_id", text="file_id")
        self.doc_tree.column("file_name", width=260, anchor="w")
        self.doc_tree.column("chunk_count", width=70, anchor="center")
        self.doc_tree.column("file_id", width=320, anchor="w")
        self.doc_tree.grid(row=2, column=0, sticky="nsew")

    def _build_chat_area(self) -> None:
        chat_frame = ttk.Frame(self, padding=(12, 0, 12, 8))
        chat_frame.grid(row=2, column=0, sticky="nsew")
        chat_frame.columnconfigure(0, weight=1)
        chat_frame.rowconfigure(0, weight=1)

        self.chat_text = tk.Text(
            chat_frame,
            wrap="word",
            state="disabled",
            bd=0,
            padx=18,
            pady=14,
            bg="#ffffff",
            fg="#111827",
            insertbackground="#111827",
            font=("", 11),
            spacing1=4,
            spacing2=4,
            spacing3=10,
        )
        self.chat_text.grid(row=0, column=0, sticky="nsew")
        chat_scroll = ttk.Scrollbar(chat_frame, orient=tk.VERTICAL, command=self.chat_text.yview)
        self.chat_text.configure(yscrollcommand=chat_scroll.set)
        chat_scroll.grid(row=0, column=1, sticky="ns")

        self.chat_text.tag_configure("user_name", justify="right", foreground="#2563eb", font=("", 9, "bold"))
        self.chat_text.tag_configure("user_bubble", justify="right", background="#dbeafe", foreground="#0f172a", rmargin=12, lmargin1=160, lmargin2=160)
        self.chat_text.tag_configure("assistant_name", justify="left", foreground="#475569", font=("", 9, "bold"))
        self.chat_text.tag_configure("assistant_bubble", justify="left", background="#f1f5f9", foreground="#111827", lmargin1=12, lmargin2=12, rmargin=160)
        self.chat_text.tag_configure("system", justify="center", foreground="#64748b", font=("", 9))

    def _build_input_area(self) -> None:
        bottom = ttk.Frame(self, padding=(12, 0, 12, 8))
        bottom.grid(row=3, column=0, sticky="ew")
        bottom.columnconfigure(1, weight=1)

        ttk.Button(bottom, text="来源", style="Icon.TButton", command=self.toggle_sources_panel).grid(row=0, column=0, padx=(0, 8), sticky="ns")
        self.message_entry = ttk.Entry(bottom, font=("", 11))
        self.message_entry.grid(row=0, column=1, sticky="ew", ipady=6)
        self.message_entry.bind("<Return>", lambda _event: self.send_message())
        ttk.Button(bottom, text="↵ 发送", style="Primary.TButton", command=self.send_message).grid(row=0, column=2, padx=(8, 0), sticky="ns")

        self.sources_text = tk.Text(bottom, wrap="word", height=5, state="disabled", bd=0, bg="#ffffff", fg="#334155", font=("", 10))

    def _build_status_bar(self) -> None:
        self.status_var = tk.StringVar(value="就绪")
        status = ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(12, 0, 12, 8), foreground="#64748b")
        status.grid(row=4, column=0, sticky="ew")

    def toggle_knowledge_panel(self) -> None:
        if self.knowledge_visible.get():
            self.knowledge_panel.grid_remove()
            self.knowledge_visible.set(False)
            self.knowledge_btn.configure(text="＋ 文档")
            return
        self.knowledge_panel.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        self.knowledge_visible.set(True)
        self.knowledge_btn.configure(text="− 文档")
        self.refresh_documents()

    def toggle_sources_panel(self) -> None:
        if self.sources_visible.get():
            self.sources_text.grid_remove()
            self.sources_visible.set(False)
            return
        self.sources_text.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.sources_visible.set(True)

    def _run_task(self, work: Callable[[], Any], on_done: Callable[[Any], None], busy_text: str) -> None:
        self.status_var.set(busy_text)

        def runner() -> None:
            try:
                result = work()
                self.task_queue.put((on_done, (result,)))
            except Exception as exc:
                self.task_queue.put((self._show_error, (exc,)))

        threading.Thread(target=runner, daemon=True).start()

    def _poll_tasks(self) -> None:
        while True:
            try:
                callback, args = self.task_queue.get_nowait()
            except queue.Empty:
                break
            callback(*args)
        self.after(100, self._poll_tasks)

    def _show_error(self, exc: Exception) -> None:
        self.status_var.set("出错")
        messagebox.showerror("TalkAgent", str(exc))

    def refresh_documents(self) -> None:
        for item in self.doc_tree.get_children():
            self.doc_tree.delete(item)
        for doc in get_all_files():
            self.doc_tree.insert("", tk.END, values=(doc["file_name"], doc["chunk_count"], doc["file_id"]))
        stats = get_stats()
        self.doc_stats_var.set(f"文件数: {stats['total_files']}    片段数: {stats['total_chunks']}")
        self.status_var.set("知识库已刷新")

    def upload_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="选择文档",
            filetypes=[
                ("支持的文档", "*.pdf *.docx *.txt *.md *.png *.jpg *.jpeg"),
                ("PDF", "*.pdf"),
                ("Word", "*.docx"),
                ("Text", "*.txt"),
                ("Markdown", "*.md"),
                ("Image", "*.png *.jpg *.jpeg"),
            ],
        )
        if not paths:
            return

        def work() -> list[str]:
            messages = []
            for raw_path in paths:
                path = Path(raw_path)
                docs = load_file_from_bytes(path.read_bytes(), path.name)
                chunks = split_documents(docs)
                file_id = add_documents(chunks, path.name)
                summarize_document(file_id, path.name, chunks)
                messages.append(f"{path.name}: {len(chunks)} 个片段")
            return messages

        def done(messages: list[str]) -> None:
            self.refresh_documents()
            self.status_var.set("上传完成")
            _available, ocr_status = get_ocr_status()
            messagebox.showinfo("入库完成", "\n".join(messages) + f"\n\nOCR 状态: {ocr_status}")

        self._run_task(work, done, "正在入库...")

    def delete_selected_file(self) -> None:
        selected = self.doc_tree.selection()
        if not selected:
            messagebox.showinfo("TalkAgent", "请先选择一个文档。")
            return
        values = self.doc_tree.item(selected[0], "values")
        file_id = values[2]
        file_name = values[0]
        if not messagebox.askyesno("删除文档", f"确定删除 {file_name} 吗？"):
            return
        deleted = delete_by_file(file_id)
        remove_document_from_index(file_id)
        self.refresh_documents()
        self.status_var.set(f"已删除 {deleted} 个片段")

    def refresh_conversations(self) -> None:
        conversations = chat_store.list_conversations()
        self.conversation_ids = [item["id"] for item in conversations]
        labels = [f"{item['title']} · {item['message_count']} 条" for item in conversations]
        self.conversation_combo["values"] = labels
        if self.current_conversation_id in self.conversation_ids:
            self.conversation_combo.current(self.conversation_ids.index(self.current_conversation_id))
        elif labels:
            self.conversation_combo.current(0)
            self.current_conversation_id = self.conversation_ids[0]
            self.load_conversation(self.current_conversation_id)
        else:
            self.conversation_var.set("")

    def new_chat(self) -> None:
        conversation = chat_store.create_conversation()
        self.current_conversation_id = conversation["id"]
        self._set_chat_text("")
        self._set_sources("")
        self.refresh_conversations()
        self._append_system("已新建对话")

    def delete_current_chat(self) -> None:
        if not self.current_conversation_id:
            messagebox.showinfo("TalkAgent", "当前没有选中的对话。")
            return
        if not messagebox.askyesno("删除对话", "确定删除当前对话吗？"):
            return
        chat_store.delete_conversation(self.current_conversation_id)
        self.current_conversation_id = None
        self._set_chat_text("")
        self._set_sources("")
        self.refresh_conversations()
        self.status_var.set("对话已删除")

    def load_selected_conversation(self, _event: Any = None) -> None:
        index = self.conversation_combo.current()
        if index < 0 or index >= len(self.conversation_ids):
            return
        self.current_conversation_id = self.conversation_ids[index]
        self.load_conversation(self.current_conversation_id)

    def load_conversation(self, conversation_id: str) -> None:
        conversation = chat_store.get_conversation(conversation_id)
        if conversation is None:
            return
        self._set_chat_text("")
        last_sources: list[dict[str, Any]] = []
        for message in conversation.get("messages", []):
            role = message.get("role")
            content = message.get("content", "")
            if role == "user":
                self._append_message("user", content)
            else:
                self._append_message("assistant", content)
                if message.get("sources"):
                    last_sources = message["sources"]
        self._set_sources(self._format_sources(last_sources))

    def send_message(self) -> None:
        question = self.message_entry.get().strip()
        if not question:
            return
        self.message_entry.delete(0, tk.END)
        if not self.current_conversation_id:
            conversation = chat_store.create_conversation(title=question[:30])
            self.current_conversation_id = conversation["id"]
            self.refresh_conversations()

        conversation_id = self.current_conversation_id
        chat_store.add_message(conversation_id, "user", question)
        self._append_message("user", question)

        def work() -> dict[str, Any]:
            return answer_question(question, conversation_id)

        def done(result: dict[str, Any]) -> None:
            sources = result.get("sources", [])
            answer = result["answer"]
            chat_store.add_message(conversation_id, "assistant", answer, sources=sources)
            self._append_message("assistant", answer)
            self._set_sources(self._format_sources(sources))
            self.refresh_conversations()
            self.status_var.set("已回答")

        self._run_task(work, done, "正在思考...")

    def _append_system(self, text: str) -> None:
        self.chat_text.configure(state="normal")
        self.chat_text.insert(tk.END, f"{text}\n\n", "system")
        self.chat_text.see(tk.END)
        self.chat_text.configure(state="disabled")

    def _append_message(self, role: str, content: str) -> None:
        if role == "user":
            name_tag, bubble_tag, name = "user_name", "user_bubble", "你"
        else:
            name_tag, bubble_tag, name = "assistant_name", "assistant_bubble", "助手"

        self.chat_text.configure(state="normal")
        self.chat_text.insert(tk.END, f"{name}\n", name_tag)
        self.chat_text.insert(tk.END, f"{content}\n\n", bubble_tag)
        self.chat_text.see(tk.END)
        self.chat_text.configure(state="disabled")

    def _set_chat_text(self, text: str) -> None:
        self.chat_text.configure(state="normal")
        self.chat_text.delete("1.0", tk.END)
        if text:
            self.chat_text.insert(tk.END, text)
        self.chat_text.configure(state="disabled")

    def _set_sources(self, text: str) -> None:
        self.sources_text.configure(state="normal")
        self.sources_text.delete("1.0", tk.END)
        self.sources_text.insert(tk.END, text or "暂无来源")
        self.sources_text.configure(state="disabled")

    @staticmethod
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


def main() -> None:
    app = TalkAgentDesktop()
    app.mainloop()


if __name__ == "__main__":
    main()

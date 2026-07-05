from app.knowledge_index import summarize_document
from app.vector_store import get_all_files, get_documents_by_file


def main() -> int:
    files = get_all_files()
    if not files:
        print("知识库为空，无需重建目录。")
        return 0

    for item in files:
        file_id = item["file_id"]
        file_name = item["file_name"]
        chunks = get_documents_by_file(file_id)
        if not chunks:
            print(f"跳过 {file_name}: 没有找到文档块")
            continue
        summarize_document(file_id, file_name, chunks)
        print(f"已重建目录: {file_name} ({len(chunks)} 个片段)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

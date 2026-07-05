from __future__ import annotations

import unicodedata
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "pdf"
PDF_PATH = OUT_DIR / "TalkAgent项目报告.pdf"
RENDER_DIR = ROOT / "tmp" / "pdfs" / "talkagent_report"

SCREENSHOTS = [
    (
        Path(r"C:\Users\25386\Pictures\Screenshots\屏幕截图 2026-06-17 050245.png"),
        "运行图 1：桌面聊天界面，用户提问后系统返回基于文档的回答。",
    ),
    (
        Path(r"C:\Users\25386\Pictures\Screenshots\屏幕截图 2026-06-17 050257.png"),
        "运行图 2：知识库界面，已入库 4 个文件，共 122 个文本片段。",
    ),
    (
        Path(r"C:\Users\25386\Pictures\Screenshots\屏幕截图 2026-06-17 050310.png"),
        "运行图 3：来源面板，系统展示命中的文件名、片段编号和原文摘要。",
    ),
]


def find_font() -> Path:
    for item in [
        Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf"),
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
    ]:
        if item.exists():
            return item
    raise FileNotFoundError("未找到中文字体")


def text_width_units(text: str) -> int:
    total = 0
    for char in text:
        total += 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
    return total


def wrap_text(text: str, max_units: int) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines() or [""]:
        if not raw:
            lines.append("")
            continue
        current = ""
        for char in raw:
            if text_width_units(current + char) <= max_units:
                current += char
            else:
                lines.append(current)
                current = char
        if current:
            lines.append(current)
    return lines


class Report:
    def __init__(self, path: Path, font_path: Path) -> None:
        self.path = path
        self.font_path = font_path
        self.doc = fitz.open()
        self.page: fitz.Page | None = None
        self.width = 595
        self.height = 842
        self.left = 48
        self.right = 547
        self.y = 0.0
        self.font = "talkagent-font"
        self.bold = "talkagent-bold"
        self.dark = (0.11, 0.13, 0.16)
        self.gray = (0.38, 0.42, 0.48)
        self.blue = (0.12, 0.32, 0.72)
        self.light = (0.94, 0.97, 1.0)
        self.line = (0.84, 0.87, 0.91)
        self.new_page()

    def new_page(self) -> None:
        self.page = self.doc.new_page(width=self.width, height=self.height)
        self.page.insert_font(fontname=self.font, fontfile=str(self.font_path))
        self.page.insert_font(fontname=self.bold, fontfile=str(self.font_path))
        self.y = 56

    def ensure(self, height: float) -> None:
        if self.y + height > 780:
            self.new_page()

    def put(self, x: float, y: float, text: str, size: float = 10.5, color=None, font=None) -> None:
        assert self.page is not None
        self.page.insert_text(
            (x, y),
            text,
            fontsize=size,
            fontname=font or self.font,
            color=color or self.dark,
        )

    def cover(self) -> None:
        assert self.page is not None
        self.page.draw_rect(fitz.Rect(0, 0, self.width, 150), color=None, fill=self.light)
        self.page.draw_rect(fitz.Rect(48, 125, 190, 131), color=None, fill=self.blue)
        self.put(48, 78, "TalkAgent 项目报告", 26, self.dark, self.bold)
        self.put(50, 112, "本地 RAG 智能客服系统", 12, self.gray)
        self.y = 190
        self.paragraph(
            "本报告介绍 TalkAgent 项目的基本情况、核心工作原理、使用到的技术栈、具体实现步骤和最终测试结果。内容尽量用通俗语言说明，让没有深入接触 AI 工程的人也能看懂这个项目是如何运行的。"
        )
        self.simple_table(
            [
                ("项目名称", "TalkAgent"),
                ("项目类型", "本地部署的 AI 客服 / 文档问答系统"),
                ("运行方式", "Windows 桌面应用，不依赖浏览器打开"),
                ("报告日期", "2026-06-17"),
            ]
        )

    def heading(self, text: str) -> None:
        self.ensure(42)
        assert self.page is not None
        self.page.draw_rect(fitz.Rect(self.left, self.y - 3, self.left + 5, self.y + 19), color=None, fill=self.blue)
        self.put(self.left + 14, self.y + 14, text, 15, self.dark, self.bold)
        self.y += 36

    def subheading(self, text: str) -> None:
        self.ensure(26)
        self.put(self.left, self.y + 12, text, 11.5, self.blue, self.bold)
        self.y += 24

    def paragraph(self, text: str) -> None:
        for line in wrap_text(text, 88):
            self.ensure(18)
            self.put(self.left, self.y + 11, line, 10.5, self.dark)
            self.y += 17
        self.y += 7

    def bullets(self, items: list[str]) -> None:
        for item in items:
            lines = wrap_text(item, 82)
            self.ensure(18 * len(lines) + 5)
            self.put(self.left, self.y + 11, "-", 10.5, self.blue, self.bold)
            for line in lines:
                self.put(self.left + 16, self.y + 11, line, 10.5, self.dark)
                self.y += 17
            self.y += 2
        self.y += 6

    def numbered(self, items: list[str]) -> None:
        for index, item in enumerate(items, start=1):
            prefix = f"{index}."
            lines = wrap_text(item, 80)
            self.ensure(18 * len(lines) + 5)
            self.put(self.left, self.y + 11, prefix, 10.5, self.blue, self.bold)
            for line in lines:
                self.put(self.left + 24, self.y + 11, line, 10.5, self.dark)
                self.y += 17
            self.y += 3
        self.y += 6

    def simple_table(self, rows: list[tuple[str, str]]) -> None:
        assert self.page is not None
        row_h = 31
        total = row_h * len(rows)
        self.ensure(total + 18)
        x = self.left
        y0 = self.y
        w = self.right - self.left
        self.page.draw_rect(fitz.Rect(x, y0, x + w, y0 + total), color=self.line, fill=(1, 1, 1))
        for idx, (key, value) in enumerate(rows):
            y = y0 + idx * row_h
            if idx:
                self.page.draw_line((x, y), (x + w, y), color=self.line, width=0.6)
            self.page.draw_rect(fitz.Rect(x, y, x + 112, y + row_h), color=None, fill=(0.96, 0.97, 0.99))
            self.put(x + 12, y + 20, key, 9.5, self.gray, self.bold)
            for line_index, line in enumerate(wrap_text(value, 62)[:2]):
                self.put(x + 124, y + 20 + line_index * 13, line, 9.5, self.dark)
        self.y += total + 18

    def flow_box(self) -> None:
        assert self.page is not None
        self.ensure(150)
        x = self.left
        y = self.y
        w = self.right - self.left
        self.page.draw_rect(fitz.Rect(x, y, x + w, y + 128), color=self.line, fill=(1, 1, 1))
        steps = [
            ("上传资料", "PDF / Word / 图片"),
            ("切成片段", "便于检索"),
            ("向量入库", "保存到 ChromaDB"),
            ("提问检索", "找相关片段"),
            ("生成回答", "给出来源"),
        ]
        gap = 8
        box_w = (w - gap * 6) / 5
        for idx, (title, body) in enumerate(steps):
            bx = x + gap + idx * (box_w + gap)
            by = y + 32
            self.page.draw_rect(fitz.Rect(bx, by, bx + box_w, by + 64), color=(0.70, 0.78, 0.90), fill=(0.97, 0.98, 1.0))
            self.put(bx + 8, by + 20, title, 9.4, self.blue, self.bold)
            self.put(bx + 8, by + 42, body, 8.4, self.dark)
            if idx < len(steps) - 1:
                self.put(bx + box_w + 1, by + 36, ">", 9, self.blue, self.bold)
        self.y += 150

    def screenshot(self, image_path: Path, caption: str) -> None:
        if not image_path.exists():
            self.paragraph(f"{caption}（截图文件未找到：{image_path}）")
            return
        pix = fitz.Pixmap(str(image_path))
        max_w = self.right - self.left
        max_h = 380
        scale = min(max_w / pix.width, max_h / pix.height)
        img_w = pix.width * scale
        img_h = pix.height * scale
        self.ensure(img_h + 54)
        assert self.page is not None
        self.page.draw_rect(
            fitz.Rect(self.left - 1, self.y - 1, self.left + img_w + 1, self.y + img_h + 1),
            color=self.line,
            fill=(1, 1, 1),
        )
        self.page.insert_image(
            fitz.Rect(self.left, self.y, self.left + img_w, self.y + img_h),
            filename=str(image_path),
        )
        self.y += img_h + 18
        self.put(self.left, self.y + 11, caption, 9.5, self.gray)
        self.y += 30

    def add_footers(self) -> None:
        total = self.doc.page_count
        for idx, page in enumerate(self.doc, start=1):
            page.insert_font(fontname=self.font, fontfile=str(self.font_path))
            page.draw_line((48, 800), (547, 800), color=self.line, width=0.5)
            page.insert_text((48, 820), "TalkAgent 项目报告", fontsize=8.5, fontname=self.font, color=self.gray)
            page.insert_text((520, 820), f"{idx}/{total}", fontsize=8.5, fontname=self.font, color=self.gray)

    def save(self) -> None:
        self.add_footers()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(self.path)
        self.doc.close()


def build_report() -> Path:
    report = Report(PDF_PATH, find_font())
    report.cover()

    report.heading("一、项目概述")
    report.paragraph(
        "TalkAgent 是一个本地运行的 AI 客服系统。它的主要作用是：把用户上传的文档变成一个可以提问的知识库，然后像客服一样回答问题。用户不需要打开网页，只需要启动桌面程序，就可以上传资料、提问、查看回答来源。"
    )
    report.bullets(
        [
            "面向场景：企业资料问答、接口文档问答、岗位资料问答、内部 FAQ 客服。",
            "核心目标：回答时尽量依据上传文档；普通常识问题可以正常解释；没有依据的问题不乱编。",
            "当前状态：已完成本地桌面界面、文档上传、知识库入库、检索问答、来源展示和基础测试。",
        ]
    )

    report.heading("二、核心原理及相关技术栈")
    report.paragraph(
        "这个项目的核心原理叫 RAG，也就是“检索增强生成”。可以把它理解成：先从资料库里找答案依据，再让大模型根据这些依据组织语言回答。这样做的好处是，大模型不需要重新训练，也能使用用户自己的资料。"
    )
    report.flow_box()
    report.subheading("核心原理")
    report.bullets(
        [
            "文档入库：系统读取 PDF、Word、TXT、Markdown 和图片，把内容整理成文本。",
            "文本分块：长文档会被切成很多小片段，方便后面精准查找。",
            "向量检索：系统把文本片段转换成向量，用户提问时也转换成向量，再找出最相近的片段。",
            "大模型回答：把用户问题、相关片段和历史对话交给本地大模型，由模型生成最终回答。",
            "来源追溯：回答后显示命中的文件和片段，方便用户检查答案是不是有依据。",
        ]
    )
    report.subheading("相关技术栈")
    report.simple_table(
        [
            ("界面", "Tkinter，用于构建 Windows 本地桌面应用。"),
            ("后端", "Python，负责文档处理、知识库管理、检索和回答流程。"),
            ("大模型", "Ollama + codex-app，用于本地生成回答。"),
            ("Embedding", "BGE-M3，用于把问题和文档片段转换成可检索的向量；缺少权重时使用 hash embedding 兜底。"),
            ("向量数据库", "ChromaDB，用于保存文档片段和向量索引。"),
            ("文档解析", "PyMuPDF、docx2txt、OCR/视觉模型，用于解析普通文档和图片内容。"),
        ]
    )

    report.heading("三、具体实现步骤")
    report.numbered(
        [
            "搭建项目目录和配置文件，把模型地址、文档目录、向量库目录、分块大小等参数集中管理。",
            "实现文档上传和解析：支持 PDF、DOCX、TXT、MD、PNG、JPG、JPEG 等格式。",
            "实现文本分块和入库：把文档内容切成片段，生成 embedding 后写入 ChromaDB。",
            "实现知识目录：上传文档后生成 Markdown 摘要和检索目录，帮助系统先判断问题是否需要查文档。",
            "实现问答流程：用户提问后，系统先判断问题类型，再检索相关片段，最后调用本地模型生成回答。",
            "实现答案自查：对于“必选参数、有哪些、列出”等容易漏项的问题，回答后再检查是否遗漏关键内容。",
            "实现桌面界面：把上传、刷新、删除、对话、来源展示做成一个简洁的本地应用界面。",
            "加入降级策略：当 Ollama 或完整 embedding 模型不可用时，系统仍能返回检索片段摘要，便于继续使用和测试。",
        ]
    )

    report.heading("四、最终测试结果")
    report.paragraph(
        "最终测试围绕“能不能上传资料、能不能入库、能不能根据资料回答、能不能显示来源”四个点进行。测试结果显示，项目已经跑通了本地 AI 客服的基本闭环。"
    )
    report.simple_table(
        [
            ("测试 1", "桌面应用可以正常打开，主界面可以进行对话。"),
            ("测试 2", "知识库中已入库 4 个文件，共 122 个片段。"),
            ("测试 3", "用户提问后，系统能基于上传文档生成回答。"),
            ("测试 4", "来源区域能显示命中的文件、片段编号和原文摘要。"),
        ]
    )
    report.bullets(
        [
            "结论：项目已经具备可交互的本地 AI 客服能力。",
            "测试问题示例：如果我要去应聘 ai 应用开发，需要怎样才能被录用。",
            "系统回答方式：先检索相关文档，再整理出岗位要求、能力要求和实践经验等内容。",
        ]
    )
    for image, caption in SCREENSHOTS:
        report.screenshot(image, caption)

    report.save()
    return PDF_PATH


def render_preview(pdf_path: Path) -> list[Path]:
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    for old in RENDER_DIR.glob("page_*.png"):
        old.unlink()
    doc = fitz.open(pdf_path)
    rendered: list[Path] = []
    for index, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=fitz.Matrix(1.35, 1.35), alpha=False)
        out = RENDER_DIR / f"page_{index:02d}.png"
        pix.save(out)
        rendered.append(out)
    doc.close()
    return rendered


def main() -> None:
    pdf = build_report()
    rendered = render_preview(pdf)
    if not rendered:
        raise RuntimeError("PDF 渲染失败")
    print(f"PDF: {pdf}")
    print(f"Pages: {len(rendered)}")
    print(f"Preview: {rendered[0]}")


if __name__ == "__main__":
    main()

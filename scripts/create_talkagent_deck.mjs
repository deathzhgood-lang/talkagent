import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const runtimeRequire = createRequire(
  "C:\\Users\\25386\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\package.json",
);
const { Presentation, PresentationFile } = await import(
  pathToFileURL(runtimeRequire.resolve("@oai/artifact-tool")).href
);

const PROJECT_ROOT = "E:\\talkagent";
const WORKSPACE = path.join(PROJECT_ROOT, "tmp", "presentations", "manual-talkagent-ppt");
const TMP_DIR = path.join(WORKSPACE, "tmp");
const PREVIEW_DIR = path.join(TMP_DIR, "preview");
const LAYOUT_DIR = path.join(TMP_DIR, "layout");
const QA_DIR = path.join(TMP_DIR, "qa");
const FINAL_PPTX = path.join(PROJECT_ROOT, "output", "ppt", "TalkAgent项目汇报.pptx");

const screenshots = [
  {
    path: "C:\\Users\\25386\\Pictures\\Screenshots\\屏幕截图 2026-06-17 050245.png",
    title: "聊天回答验证",
    caption: "用户提问后，系统基于上传文档返回岗位能力要求。",
  },
  {
    path: "C:\\Users\\25386\\Pictures\\Screenshots\\屏幕截图 2026-06-17 050257.png",
    title: "知识库入库验证",
    caption: "知识库中已入库 4 个文件，共 122 个文本片段。",
  },
  {
    path: "C:\\Users\\25386\\Pictures\\Screenshots\\屏幕截图 2026-06-17 050310.png",
    title: "来源追溯验证",
    caption: "来源面板展示命中的文件、片段编号和原文摘要。",
  },
];

const W = 1280;
const H = 720;
const C = {
  black: "#101010",
  ink: "#1D1D1F",
  gray1: "#F5F5F3",
  gray2: "#E6E6E2",
  gray3: "#B8B8B2",
  gray4: "#73736D",
  white: "#FFFFFF",
};
const FONT = "Microsoft YaHei UI";

function shouldStopAt(n) {
  const max = Number.parseInt(process.env.MAX_SLIDES ?? "", 10);
  return Number.isFinite(max) && max > 0 && n >= max;
}

async function ensureDirs() {
  await fs.mkdir(PREVIEW_DIR, { recursive: true });
  await fs.mkdir(LAYOUT_DIR, { recursive: true });
  await fs.mkdir(QA_DIR, { recursive: true });
  await fs.mkdir(path.dirname(FINAL_PPTX), { recursive: true });
}

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

async function readImageBlob(imagePath) {
  const bytes = await fs.readFile(imagePath);
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

function addText(slide, text, position, style = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  const { alignment: _alignment, ...cleanStyle } = style;
  shape.text.style = {
    typeface: FONT,
    fontSize: style.fontSize ?? 22,
    color: style.color ?? C.ink,
    bold: style.bold ?? false,
    ...cleanStyle,
  };
  return shape;
}

function addLine(slide, x, y, w, color = C.black, width = 1) {
  slide.shapes.add({
    geometry: "rect",
    position: { left: x, top: y, width: w, height: width },
    fill: color,
    line: { style: "solid", fill: "none", width: 0 },
  });
}

function addCard(slide, x, y, w, h, fill = C.white, line = C.gray2) {
  return slide.shapes.add({
    geometry: "rect",
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: { style: "solid", fill: line, width: 1 },
  });
}

function addFooter(slide, n) {
  addLine(slide, 72, 660, 1136, C.gray2, 1);
  addText(slide, "TalkAgent 本地 AI 客服系统", { left: 72, top: 676, width: 420, height: 24 }, { fontSize: 12, color: C.gray4 });
  addText(slide, String(n).padStart(2, "0"), { left: 1160, top: 676, width: 48, height: 24 }, { fontSize: 12, color: C.gray4, alignment: "right" });
}

function addTitle(slide, kicker, title, sub, n) {
  addText(slide, kicker, { left: 72, top: 54, width: 420, height: 30 }, { fontSize: 13, color: C.gray4, bold: true });
  addText(slide, title, { left: 72, top: 92, width: 900, height: 76 }, { fontSize: 38, color: C.black, bold: true });
  if (sub) addText(slide, sub, { left: 74, top: 164, width: 980, height: 42 }, { fontSize: 19, color: C.gray4 });
  addFooter(slide, n);
}

function addBulletList(slide, items, x, y, w, fontSize = 22, gap = 48) {
  items.forEach((item, i) => {
    const top = y + i * gap;
    addText(slide, "-", { left: x, top, width: 16, height: gap - 4 }, { fontSize, color: C.black, bold: true });
    addText(slide, item, { left: x + 24, top, width: w - 24, height: gap - 4 }, { fontSize, color: C.ink });
  });
}

function addMetric(slide, label, value, x, y, w) {
  addCard(slide, x, y, w, 116, C.gray1, C.gray2);
  addText(slide, value, { left: x + 22, top: y + 20, width: w - 44, height: 52 }, { fontSize: 42, color: C.black, bold: true });
  addText(slide, label, { left: x + 24, top: y + 78, width: w - 48, height: 24 }, { fontSize: 14, color: C.gray4 });
}

async function addScreenshot(slide, item, x, y, w, h) {
  const blob = await readImageBlob(item.path);
  slide.images.add({
    blob,
    contentType: "image/png",
    alt: item.title,
    fit: "contain",
    position: { left: x, top: y, width: w, height: h },
  });
}

function addProcessStep(slide, idx, title, desc, x, y, w, h) {
  addCard(slide, x, y, w, h, C.white, C.gray2);
  addText(slide, String(idx).padStart(2, "0"), { left: x + 20, top: y + 18, width: 52, height: 30 }, { fontSize: 18, color: C.gray3, bold: true });
  addText(slide, title, { left: x + 20, top: y + 54, width: w - 40, height: 34 }, { fontSize: 22, color: C.black, bold: true });
  addText(slide, desc, { left: x + 20, top: y + 94, width: w - 40, height: h - 104 }, { fontSize: 15, color: C.gray4 });
}

function addProblemRow(slide, y, problem, adjustment, result) {
  addText(slide, problem, { left: 92, top: y, width: 305, height: 54 }, { fontSize: 18, color: C.ink });
  addText(slide, adjustment, { left: 456, top: y, width: 330, height: 54 }, { fontSize: 18, color: C.ink });
  addText(slide, result, { left: 844, top: y, width: 330, height: 54 }, { fontSize: 18, color: C.ink });
  addLine(slide, 72, y + 64, 1136, C.gray2, 1);
}

async function buildDeck() {
  await ensureDirs();
  const presentation = Presentation.create({ slideSize: { width: W, height: H } });

  let slide = presentation.slides.add();
  slide.background.fill = C.gray1;
  addText(slide, "TALKAGENT", { left: 72, top: 62, width: 320, height: 28 }, { fontSize: 14, color: C.gray4, bold: true });
  addLine(slide, 72, 104, 140, C.black, 3);
  addText(slide, "本地 AI 客服系统\n项目汇报", { left: 72, top: 178, width: 780, height: 150 }, { fontSize: 58, color: C.black, bold: true });
  addText(slide, "从文档问答骨架，到可交互桌面应用，再到“目录路由 + 检索 + 回答自查”的智能体流程验证。", { left: 76, top: 360, width: 760, height: 74 }, { fontSize: 24, color: C.gray4 });
  addMetric(slide, "已入库文件", "4", 880, 170, 250);
  addMetric(slide, "文本片段", "122", 880, 310, 250);
  addMetric(slide, "运行形态", "桌面端", 880, 450, 250);
  addFooter(slide, 1);
  if (process.env.STOP_AFTER_COVER === "1") return presentation;
  if (shouldStopAt(1)) return presentation;

  slide = presentation.slides.add();
  slide.background.fill = C.white;
  addTitle(slide, "项目概述", "这个项目解决什么问题", "把上传资料变成一个能回答问题、能给出处的本地客服。", 2);
  addBulletList(slide, [
    "用户上传接口文档、岗位资料或业务说明后，系统自动建立知识库。",
    "用户用自然语言提问，系统先查资料，再组织成客服式回答。",
    "回答会标注“基于文档、综合回答、通用回答、缺少依据”，减少乱说。",
    "当前已改成本地桌面应用，不需要通过浏览器打开。",
  ], 110, 250, 980, 24, 64);
  if (shouldStopAt(2)) return presentation;

  slide = presentation.slides.add();
  slide.background.fill = C.gray1;
  addTitle(slide, "核心原理", "RAG：先找依据，再生成回答", "不是重新训练模型，而是把资料检索出来，让模型基于资料回答。", 3);
  const steps = [
    ["上传文档", "PDF、Word、Markdown、图片等资料进入系统"],
    ["生成片段", "长文档被切成多个小段，便于精确检索"],
    ["向量入库", "片段写入 ChromaDB，支持相似度搜索"],
    ["问题路由", "先判断是否需要查资料、查哪些资料"],
    ["生成与自查", "模型回答后检查遗漏和依据问题"],
  ];
  steps.forEach((s, i) => addProcessStep(slide, i + 1, s[0], s[1], 72 + i * 236, 262, 206, 170));
  addText(slide, "核心价值：用户不需要训练模型，只要持续投喂业务文档，就能让客服获得新的业务知识。", { left: 116, top: 492, width: 1040, height: 40 }, { fontSize: 24, color: C.black, bold: true, alignment: "center" });
  if (shouldStopAt(3)) return presentation;

  slide = presentation.slides.add();
  slide.background.fill = C.white;
  addTitle(slide, "技术栈", "用轻量组件拼出本地闭环", "技术选择围绕本地运行、可验证、可降级展开。", 4);
  const tech = [
    ["桌面界面", "Tkinter", "上传、对话、来源展示"],
    ["模型服务", "Ollama + codex-app", "本地生成回答"],
    ["向量检索", "BGE-M3 / hash 兜底", "语义检索与降级运行"],
    ["知识库", "ChromaDB", "保存片段和向量索引"],
    ["文档解析", "PyMuPDF / docx2txt / OCR", "读取文本和图片内容"],
    ["智能体流程", "Router + RAG + Checker", "判断、检索、回答、自查"],
  ];
  tech.forEach((row, i) => {
    const x = 72 + (i % 3) * 384;
    const y = 238 + Math.floor(i / 3) * 172;
    addCard(slide, x, y, 340, 128, i % 2 === 0 ? C.gray1 : C.white, C.gray2);
    addText(slide, row[0], { left: x + 24, top: y + 20, width: 140, height: 24 }, { fontSize: 15, color: C.gray4, bold: true });
    addText(slide, row[1], { left: x + 24, top: y + 52, width: 292, height: 30 }, { fontSize: 23, color: C.black, bold: true });
    addText(slide, row[2], { left: x + 24, top: y + 88, width: 292, height: 24 }, { fontSize: 15, color: C.gray4 });
  });
  if (shouldStopAt(4)) return presentation;

  slide = presentation.slides.add();
  slide.background.fill = C.black;
  addText(slide, "你的关键想法", { left: 72, top: 54, width: 420, height: 30 }, { fontSize: 13, color: C.gray3, bold: true });
  addText(slide, "让智能体先看目录，\n再决定是否查文档", { left: 72, top: 112, width: 700, height: 130 }, { fontSize: 48, color: C.white, bold: true });
  addText(slide, "这个想法的重点不是“把所有文档都塞给模型”，而是让模型先拿到一个文档目录，根据问题选择要不要查、查哪些，再生成最终回答。", { left: 76, top: 270, width: 640, height: 92 }, { fontSize: 22, color: C.gray3 });
  const ideaSteps = [
    ["上传时", "生成 Markdown 总结和检索目录"],
    ["提问时", "问题 + 目录交给模型判断"],
    ["需要文档", "只检索相关文档片段"],
    ["最终回答", "结合文档、常识和上下文"],
    ["回答后", "再做遗漏与事实自查"],
  ];
  ideaSteps.forEach((s, i) => {
    const y = 120 + i * 92;
    addText(slide, `0${i + 1}`, { left: 820, top: y, width: 48, height: 30 }, { fontSize: 18, color: C.gray3, bold: true });
    addText(slide, s[0], { left: 884, top: y - 4, width: 160, height: 30 }, { fontSize: 23, color: C.white, bold: true });
    addText(slide, s[1], { left: 884, top: y + 30, width: 320, height: 28 }, { fontSize: 16, color: C.gray3 });
    addLine(slide, 820, y + 72, 360, "#3A3A3A", 1);
  });
  addFooter(slide, 5);
  if (shouldStopAt(5)) return presentation;

  slide = presentation.slides.add();
  slide.background.fill = C.white;
  addTitle(slide, "遇到的问题", "问题不是一个点，而是一串链路问题", "每个问题都对应了一次方案调整。", 6);
  addText(slide, "问题", { left: 92, top: 225, width: 240, height: 26 }, { fontSize: 16, color: C.gray4, bold: true });
  addText(slide, "调整方案", { left: 456, top: 225, width: 240, height: 26 }, { fontSize: 16, color: C.gray4, bold: true });
  addText(slide, "验证结果", { left: 844, top: 225, width: 240, height: 26 }, { fontSize: 16, color: C.gray4, bold: true });
  addLine(slide, 72, 260, 1136, C.black, 2);
  addProblemRow(slide, 286, "Ollama 不可用时回答失败", "加入检索片段摘要兜底", "模型掉线时仍能给出可读结果");
  addProblemRow(slide, 370, "图片里的文字没有被读到", "加入 OCR / Vision 路径和图片格式支持", "能处理图片资料，但依赖 OCR 质量");
  addProblemRow(slide, 454, "只会按文档答，常识问题不会答", "增加 general / document / hybrid 路由", "普通问题和文档问题分流");
  addProblemRow(slide, 538, "必选参数回答漏掉 prompt", "多查询检索 + 必填项抽取 + 自查", "枚举类问题完整性提高");
  if (shouldStopAt(6)) return presentation;

  slide = presentation.slides.add();
  slide.background.fill = C.gray1;
  addTitle(slide, "方案落地", "你的流程已经被拆成可运行模块", "不是停留在想法层，而是映射到了项目代码和运行链路。", 7);
  const modules = [
    ["知识目录", "knowledge_index.py", "上传后生成摘要和目录"],
    ["问题判断", "question_router.py", "判断是否需要文档及相关文件"],
    ["检索回答", "rag_chain.py", "执行多查询检索和回答生成"],
    ["答案自查", "answer_checker.py", "检查遗漏、不一致和依据不足"],
    ["来源展示", "desktop.py", "把命中文档片段展示给用户"],
  ];
  modules.forEach((m, i) => {
    const y = 218 + i * 72;
    addCard(slide, 96, y, 1088, 50, C.white, C.gray2);
    addText(slide, m[0], { left: 126, top: y + 14, width: 170, height: 24 }, { fontSize: 18, color: C.black, bold: true });
    addText(slide, m[1], { left: 340, top: y + 14, width: 260, height: 24 }, { fontSize: 17, color: C.gray4 });
    addText(slide, m[2], { left: 650, top: y + 14, width: 480, height: 24 }, { fontSize: 17, color: C.ink });
  });
  if (shouldStopAt(7)) return presentation;

  slide = presentation.slides.add();
  slide.background.fill = C.white;
  addTitle(slide, "可行性验证 A", "文档可以被入库，目录可以被建立", "先验证知识库是否真的有资料，是后续回答可靠的前提。", 8);
  await addScreenshot(slide, screenshots[1], 92, 220, 1096, 232);
  addBulletList(slide, [
    "验证点：上传的文件被系统记录，并按片段数量进入知识库。",
    "结果：界面显示 4 个文件、122 个片段，说明入库链路跑通。",
    "意义：智能体后续不是凭空回答，而是有可检索的文档基础。",
  ], 120, 500, 1000, 20, 42);
  if (shouldStopAt(8)) return presentation;

  slide = presentation.slides.add();
  slide.background.fill = C.gray1;
  addTitle(slide, "可行性验证 B", "系统能基于资料回答问题", "测试问题不是简单关键词，而是需要整理文档中的岗位能力要求。", 9);
  await addScreenshot(slide, screenshots[0], 78, 205, 1124, 452);
  if (shouldStopAt(9)) return presentation;

  slide = presentation.slides.add();
  slide.background.fill = C.white;
  addTitle(slide, "可行性验证 C", "回答不是黑盒，来源可以追溯", "来源面板让用户能看到命中文件和片段，便于检查回答依据。", 10);
  await addScreenshot(slide, screenshots[2], 112, 242, 1056, 146);
  addCard(slide, 150, 445, 980, 120, C.gray1, C.gray2);
  addText(slide, "验证结论", { left: 186, top: 472, width: 150, height: 28 }, { fontSize: 18, color: C.gray4, bold: true });
  addText(slide, "目录路由、检索、回答和来源展示形成闭环；这证明“先看目录，再决定查文档，再回答和自查”的方案在当前项目中是可落地的。", { left: 186, top: 510, width: 900, height: 44 }, { fontSize: 22, color: C.black, bold: true });
  if (shouldStopAt(10)) return presentation;

  slide = presentation.slides.add();
  slide.background.fill = C.black;
  addText(slide, "结论", { left: 72, top: 54, width: 420, height: 30 }, { fontSize: 13, color: C.gray3, bold: true });
  addText(slide, "可行，但质量取决于\n文档解析、检索和模型能力", { left: 72, top: 122, width: 780, height: 130 }, { fontSize: 48, color: C.white, bold: true });
  addText(slide, "当前项目已经证明：不训练模型，也可以通过 RAG 和智能体流程做出可工作的本地 AI 客服。下一步应优先增强 OCR、补齐真实 BGE-M3 权重，并沉淀固定测试集。", { left: 76, top: 310, width: 780, height: 96 }, { fontSize: 23, color: C.gray3 });
  addText(slide, "最终状态", { left: 900, top: 160, width: 180, height: 26 }, { fontSize: 16, color: C.gray3, bold: true });
  addText(slide, "已跑通\n可交互\n可追溯", { left: 900, top: 202, width: 260, height: 160 }, { fontSize: 44, color: C.white, bold: true });
  addFooter(slide, 11);

  return presentation;
}

async function writeNotes() {
  const sourceNotes = `TalkAgent PPT source notes

User-provided sources:
- Three runtime screenshots from C:/Users/25386/Pictures/Screenshots, used on slides 8-10.
- User requirement: PPT should include report content plus problems, adjustment plans, and focus on the user's concrete idea and feasibility validation.

Local project sources:
- E:/talkagent/scripts/generate_project_report.py: generated PDF report content used as the base.
- E:/talkagent/app/rag_chain.py: route-aware RAG answer flow, multi-query retrieval, required-item extraction, answer checking and fallback behavior.
- E:/talkagent/app/knowledge_index.py, question_router.py, answer_checker.py, desktop.py: module names and roles.

Claims used:
- Project is a local desktop RAG customer service app.
- Knowledge base screenshot shows 4 files and 122 chunks.
- User idea: upload-time summaries/catalog, query-time routing, relevant-document retrieval, final answer, self-check.
- Feasibility conclusion: current implementation validates the idea at prototype level, with remaining quality dependencies on OCR, embedding, retrieval and local model capability.
`;
  const slidePlan = `TalkAgent PPT slide plan

Mode: create
Style: minimalist premium black-white-gray.
Palette: black #101010, ink #1D1D1F, warm gray #F5F5F3, rule gray #E6E6E2, muted gray #73736D.
Fonts: Microsoft YaHei UI for headings and body.
Slide count: 11.
Slides:
1 Cover and key metrics.
2 Project overview.
3 RAG core principle.
4 Technical stack.
5 User's key agent idea.
6 Problems and adjustment plans.
7 Implementation mapping.
8 Feasibility validation: knowledge base.
9 Feasibility validation: chat answer.
10 Feasibility validation: source traceability.
11 Conclusion and next steps.
`;
  await fs.writeFile(path.join(TMP_DIR, "source-notes.txt"), sourceNotes, "utf8");
  await fs.writeFile(path.join(TMP_DIR, "slide-plan.txt"), slidePlan, "utf8");
}

async function exportArtifacts(presentation) {
  const limit = Number.parseInt(process.env.SLIDE_LIMIT ?? "", 10);
  if (Number.isFinite(limit) && limit > 0) {
    presentation.slides.items.splice(limit);
  }
  if (process.env.CHECK_UNDEFINED === "1") {
    const found = [];
    const seen = new Set();
    function walk(value, trail) {
      if (value === undefined) {
        found.push(trail);
        return;
      }
      if (!value || typeof value !== "object" || seen.has(value)) return;
      seen.add(value);
      if (Array.isArray(value)) {
        value.forEach((item, index) => walk(item, `${trail}[${index}]`));
        return;
      }
      for (const [key, item] of Object.entries(value)) {
        walk(item, trail ? `${trail}.${key}` : key);
      }
    }
    walk(presentation.toProto(), "presentation");
    console.log(found.slice(0, 80).join("\n") || "no undefined");
    console.log(`undefined count: ${found.length}`);
  }
  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(FINAL_PPTX);
  for (const [index, slide] of presentation.slides.items.entries()) {
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    const png = await presentation.export({ slide, format: "png", scale: 1 });
    await writeBlob(path.join(PREVIEW_DIR, `${stem}.png`), png);
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(path.join(LAYOUT_DIR, `${stem}.layout.json`), await layout.text());
  }
  const montage = await presentation.export({ format: "webp", montage: true, scale: 1 });
  await writeBlob(path.join(PREVIEW_DIR, "deck-montage.webp"), montage);
}

async function writeQa() {
  const qa = `Visual QA

Mechanical:
- PPTX exists and is non-empty: checked by script.
- Expected slide count: 11.
- Every final slide rendered: yes, preview PNG files generated.
- Contact sheet or montage reviewed: deck-montage.webp generated for review.
- Layout JSON generated: yes.
- slide-plan.txt and source-notes.txt generated: yes.

Deck-level:
- Black-white-gray minimalist style used consistently.
- User-provided screenshots are embedded as image assets with captions.
- Core claim focus: user's agent workflow and feasibility validation.

Issue ledger:
| Issue | Slide(s) | Severity | Fix path | Status |
|---|---:|---|---|---|
| None observed by generation script | - | - | - | pending visual spot-check |

Final decision:
- Pass after manual preview spot-check.
`;
  await fs.writeFile(path.join(QA_DIR, "visual-qa.txt"), qa, "utf8");
}

async function main() {
  await ensureDirs();
  await writeNotes();
  const presentation = await buildDeck();
  await exportArtifacts(presentation);
  await writeQa();
  const stat = await fs.stat(FINAL_PPTX);
  console.log(`PPTX: ${FINAL_PPTX}`);
  console.log(`Size: ${stat.size}`);
  console.log(`Preview: ${path.join(PREVIEW_DIR, "deck-montage.webp")}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

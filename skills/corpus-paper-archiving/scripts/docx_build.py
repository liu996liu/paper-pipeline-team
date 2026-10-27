# -*- coding: utf-8 -*-
"""把总论、逐篇读档、附录合成一份 Word 文档。

用法：
    python docx_build.py --archives <读档目录> --overview <总论.md> --out <输出.docx>
    python docx_build.py ... [--appendix <附录.md>] [--copy-to <目录>] [--title 题 --subtitle 副题]

生成结构：封面 → 说明页 → 目录（TOC 域）→ 总论 → 各篇读档 → 附录。
排版：正文宋体 12pt／行距 1.5／首行缩进 2 字；标题黑体分级；markdown 表格转 Word 真表格；
     页脚页码域，从正文起编。目录页提示用户按 Ctrl+A 再按 F9 更新域。

依赖：python-docx
"""
import argparse
import os
import re
import shutil
import sys

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

NOTES = [
    "一、材料。本报告以指定目录内的论文文本为对象，逐篇通读后各成一份读档，另撰总论一篇。"
    "各篇读档编号与文末附录中的编号一致。",
    "二、体例。总论在前，读档在后。每篇读档分两层：提要用连续文字讲清这篇说了什么，供快速阅读；"
    "档案记录用编号的八节记定位、核心主张、对话对象、依据、论证链与松动处、撰写者的判断、"
    "原文直引与术语表，供核验与跨篇比较。两层是摘要与底稿的关系，不是两篇文章。",
    "三、判断的归属。凡属论文作者的主张，标以〔作者主张〕；引自他人而被作者转述的，标以〔转述某某〕；"
    "出自律文、简牍、判例、契约、档案等原始材料的，标以〔史料记载〕；凡属读档撰写者的分析、推测与批评，"
    "一律写明“我的判断”，不与作者主张相混。",
    "四、引文。引文一律取原文汉字序列，不加页码；标点因所据文本的转换体例未能逐字保留，"
    "凡补入处只补句读，不改动汉字。需要回查原文时，按读档所记章节名与引文语句定位。",
    "五、限度。这些论文相互之间未必有引用关系，本报告所记的“对话”只指各篇与各自学科脉络中既有研究的对话；"
    "跨篇的比较与联系，属于并读之后所作的判断，不是任何一篇论文自身的说法。",
]


def setfont(run, name="宋体", size=None, bold=None, latin="Times New Roman"):
    run.font.name = latin
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold


def add_runs(p, text, size=12, name="宋体"):
    for seg in re.split(r"(\*\*.+?\*\*)", text):
        if not seg:
            continue
        if seg.startswith("**") and seg.endswith("**"):
            setfont(p.add_run(seg[2:-2]), name, size, True)
        else:
            setfont(p.add_run(seg), name, size, False)


def body(doc, text, indent=True, size=12):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = 1.5
    pf.space_after = Pt(4)
    if indent:
        pf.first_line_indent = Pt(size * 2)
    add_runs(p, text, size)
    return p


def heading(doc, text, level, new_page=False):
    h = doc.add_heading("", level=level)
    for r in h.runs:
        r.text = ""
    setfont(h.add_run(text), "黑体", {1: 20, 2: 16, 3: 14, 4: 13}.get(level, 13), True)
    pf = h.paragraph_format
    pf.space_before = Pt(12 if level <= 2 else 8)
    pf.space_after = Pt(6)
    pf.line_spacing = 1.3
    if new_page:
        pf.page_break_before = True
    return h


def add_toc(doc):
    p = doc.add_paragraph()
    r = p.add_run()
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), 'TOC \\o "1-2" \\h \\z \\u')
    t = OxmlElement("w:t")
    t.text = "（在 Word 中按 Ctrl+A 再按 F9，或右键“更新域”，生成带页码的目录）"
    rr = OxmlElement("w:r")
    rr.append(t)
    fld.append(rr)
    r._element.addprevious(fld)


def add_page_footer(section):
    section.footer.is_linked_to_previous = False
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    for el, attr, txt in (("w:fldChar", "w:fldCharType", "begin"),
                          ("w:instrText", None, " PAGE   \\* MERGEFORMAT "),
                          ("w:fldChar", "w:fldCharType", "end")):
        e = OxmlElement(el)
        if attr:
            e.set(qn(attr), txt)
        else:
            e.set(qn("xml:space"), "preserve")
            e.text = txt
        run._element.append(e)
    setfont(run, "宋体", 10)


def flush_table(doc, rows):
    data = []
    for r in rows:
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        data.append(cells)
    if not data:
        return
    n = max(len(r) for r in data)
    tb = doc.add_table(rows=0, cols=n)
    tb.style = "Table Grid"
    for ri, row in enumerate(data):
        cs = tb.add_row().cells
        for ci in range(n):
            txt = re.sub(r"\*\*(.+?)\*\*", r"\1", row[ci] if ci < len(row) else "")
            cs[ci].text = ""
            p = cs[ci].paragraphs[0]
            setfont(p.add_run(txt), "宋体", 9, ri == 0)
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_after = Pt(0)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def render_md(doc, md, base_level=2):
    table_rows = []
    for raw in md.splitlines():
        s = raw.rstrip()
        if not s.strip() or s.strip() == "---":
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", s.strip())
        if m:
            if table_rows:
                flush_table(doc, table_rows)
                table_rows.clear()
            heading(doc, m.group(2).strip(), min(base_level + len(m.group(1)) - 1, 4))
            continue
        if s.strip().startswith("|"):
            table_rows.append(s.strip())
            continue
        if table_rows:
            flush_table(doc, table_rows)
            table_rows.clear()
        if s.lstrip().startswith(">"):
            p = body(doc, s.lstrip("> ").strip(), indent=False, size=11)
            p.paragraph_format.left_indent = Cm(1.0)
            continue
        m = re.match(r"^\s*[-*]\s+(.*)$", s)
        if m:
            p = body(doc, "• " + m.group(1), indent=False, size=11)
            p.paragraph_format.left_indent = Cm(0.9)
            continue
        m = re.match(r"^\s*(\d+)[.、]\s*(.*)$", s)
        if m:
            p = body(doc, f"{m.group(1)}. {m.group(2)}", indent=False, size=11)
            p.paragraph_format.left_indent = Cm(0.9)
            continue
        body(doc, s.strip())
    if table_rows:
        flush_table(doc, table_rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archives", required=True, help="读档目录（文件按编号前缀排序）")
    ap.add_argument("--overview", required=True, help="总论 markdown")
    ap.add_argument("--appendix", help="附录 markdown（可选）")
    ap.add_argument("--out", required=True, help="输出 .docx")
    ap.add_argument("--copy-to", action="append", default=[], help="额外复制到的目录（可多次）")
    ap.add_argument("--title", default="这批论文读了什么")
    ap.add_argument("--subtitle", default="逐篇读档与总论")
    ap.add_argument("--material", default="", help="封面上的材料范围说明")
    args = ap.parse_args()

    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"
    st.font.size = Pt(12)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    for s in doc.sections:
        s.top_margin = Cm(2.54)
        s.bottom_margin = Cm(2.54)
        s.left_margin = Cm(3.0)
        s.right_margin = Cm(3.0)

    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    setfont(t.add_run(args.title), "黑体", 20, True)
    t.paragraph_format.space_before = Pt(110)
    lines = [("——" + args.subtitle, "黑体", 13, True)]
    if args.material:
        lines.append((args.material, "宋体", 11, None))
    lines.append(("体例：总论 → 逐篇读档（提要 + 八节档案记录）→ 附录", "宋体", 11, None))
    lines.append(("引文体例：不标页码，靠章节名与原文语句定位", "宋体", 11, None))
    for txt, fnt, sz, bd in lines:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        setfont(p.add_run(txt), fnt, sz, bd)
    doc.add_page_break()

    heading(doc, "说明", 1)
    for para in NOTES:
        p = doc.add_paragraph()
        p.paragraph_format.first_line_indent = Pt(24)
        p.paragraph_format.line_spacing = 1.5
        setfont(p.add_run(para), "宋体", 11)
    doc.add_page_break()

    heading(doc, "目录", 1)
    add_toc(doc)
    doc.add_page_break()

    sec = doc.add_section(WD_SECTION.CONTINUOUS)
    sec.top_margin = Cm(2.54)
    sec.bottom_margin = Cm(2.54)
    sec.left_margin = Cm(3.0)
    sec.right_margin = Cm(3.0)
    try:
        add_page_footer(sec)
    except Exception as e:
        print("页脚页码插入失败：", e, file=sys.stderr)

    render_md(doc, open(args.overview, encoding="utf-8-sig").read(), base_level=1)

    files = sorted(
        (f for f in os.listdir(args.archives)
         if f.endswith(".md") and not f.startswith("_") and re.match(r"^\d\d", f)),
        key=lambda f: int(re.match(r"^(\d+)", f).group(1)),
    )
    print("读档收录顺序：")
    for idx, fn in enumerate(files, 1):
        md = open(os.path.join(args.archives, fn), encoding="utf-8-sig").read()
        lines = md.splitlines()
        title = re.sub(r"^档案\s*\d+[：:]\s*", "", lines[0].lstrip("# ").strip())
        print(f"  第{idx:2d}篇  {fn}")
        heading(doc, f"第{idx}篇　{title}", 1, new_page=True)
        for m in [l.strip() for l in lines[1:12] if l.strip().startswith("**")]:
            if m.startswith(("**作者", "**出处", "**篇幅")):
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(2)
                add_runs(p, m, 10.5)
        rest = "\n".join(
            l for l in lines[1:]
            if not l.strip().startswith(("**作者", "**出处", "**篇幅"))
        )
        render_md(doc, rest, base_level=2)

    if args.appendix and os.path.exists(args.appendix):
        md = open(args.appendix, encoding="utf-8-sig").read().splitlines()
        heading(doc, md[0].lstrip("# ").strip(), 1, new_page=True)
        render_md(doc, "\n".join(md[1:]), base_level=2)

    doc.save(args.out)
    print(f"\n已生成：{args.out}  {os.path.getsize(args.out):,} 字节")
    for d in args.copy_to:
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, os.path.basename(args.out))
        shutil.copy2(args.out, dst)
        print("已复制到：", dst)


if __name__ == "__main__":
    main()

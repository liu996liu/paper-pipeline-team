# -*- coding: utf-8 -*-
"""把 Markdown 稿件转成中文期刊交稿用的 Word（.docx）。

用法：
    python scripts/docx_build_submission.py manuscript.md --out submission.docx \\
        --title "题名" --author "张三" --affil "XX大学XX学院" \\
        --keywords "数字化转型;绿色创新;中介效应" --clc F272 --doccode A \\
        --fund "国家社会科学基金一般项目（20BGL012）" \\
        --abstract-file abstract.md --refs-file refs.md

    # 套用期刊 Word 模板的样式（模板里定义的"正文""标题 1"等样式会被沿用）
    python scripts/docx_build_submission.py manuscript.md --out s.docx --template journal.docx

生成的文档结构：
    题名页（中文题名 / 作者 / 单位 / 摘要 / 关键词 / 中图分类号 / 文献标识码 / 基金）
    → 正文（宋体小四 12pt，1.5 倍行距，首行缩进 2 字符；标题黑体分级）
    → 参考文献（悬挂缩进）

排版约定（GB/T 7713.2-2022 + 中文期刊通行做法）：
    正文宋体 12pt / 1.5 倍行距 / 首行缩进 2 字符
    一级标题黑体 16pt、二级黑体 14pt、三级黑体 12pt
    表格转真表格并套三线表（顶线 1.5 磅、表头下线 0.75 磅、底线 1.5 磅）
    页脚居中页码域，从正文起编

依赖：python-docx
限制：公式不转 OMML（保留文本并在文末列出待转清单）；题注字体需按刊手调。
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

try:
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt
except ImportError:  # pragma: no cover
    sys.exit("缺少依赖：pip install python-docx")


# ---------------------------------------------------------------- 字体与段落

def set_run_font(run, cn="宋体", size=12, bold=None, latin="Times New Roman"):
    """同时设中英文字体。python-docx 的 run.font.name 只管西文，中文必须写 eastAsia。"""
    run.font.name = latin
    run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), cn)
    rfonts.set(qn("w:ascii"), latin)
    rfonts.set(qn("w:hAnsi"), latin)


def add_rich_text(p, text, cn="宋体", size=12):
    """支持 **粗体** 与 \\* 字面星号转义的最小行内标记。"""
    # 先按 **粗体** 切段，再在段内处理 \* 转义为占位符，最后还原为字面 *
    PLACEHOLDER = "\x00STAR\x00"
    for seg in re.split(r"(\*\*.+?\*\*)", text):
        if not seg:
            continue
        bold = seg.startswith("**") and seg.endswith("**") and len(seg) > 4
        content = seg[2:-2] if bold else seg
        content = content.replace("\\*", PLACEHOLDER).replace(PLACEHOLDER, "*")
        set_run_font(p.add_run(content), cn, size, bold)


def body_para(doc, text, indent=True, size=12, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
    """正文段落：1.5 倍行距，首行缩进 2 字符。"""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.alignment = align
    if indent:
        pf.first_line_indent = Pt(size * 2)
    add_rich_text(p, text, "宋体", size)
    return p


def heading(doc, text, level):
    """标题：黑体分级，不缩进。"""
    size = {1: 16, 2: 14, 3: 12}.get(level, 12)
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    pf.space_before = Pt(12 if level == 1 else 6)
    pf.space_after = Pt(6 if level == 1 else 3)
    pf.first_line_indent = Pt(0)
    pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
    pf.keep_with_next = True
    set_run_font(p.add_run(text), "黑体", size, True)
    return p


def add_page_footer_number(section):
    """页脚居中页码域。"""
    footer = section.footer
    p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    set_run_font(run, "宋体", 10.5)
    for tag, attr in (("w:fldChar", "begin"), ("w:instrText", None), ("w:fldChar", "end")):
        el = OxmlElement(tag)
        if tag == "w:instrText":
            el.set(qn("xml:space"), "preserve")
            el.text = " PAGE "
        else:
            el.set(qn("w:fldCharType"), attr)
        run._r.append(el)


# ---------------------------------------------------------------- 三线表

def _set_cell_border(cell, **kwargs):
    """kwargs: top/bottom/left/right = {'sz': 8, 'val': 'single', 'color': '000000'}"""
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right"):
        if edge not in kwargs:
            continue
        spec = kwargs[edge]
        el = borders.find(qn(f"w:{edge}"))
        if el is None:
            el = OxmlElement(f"w:{edge}")
            borders.append(el)
        if spec is None or spec.get("val") == "nil":
            el.set(qn("w:val"), "nil")
        else:
            el.set(qn("w:val"), spec.get("val", "single"))
            el.set(qn("w:sz"), str(spec.get("sz", 8)))
            el.set(qn("w:space"), "0")
            el.set(qn("w:color"), spec.get("color", "000000"))


def make_three_line_table(table, header_rows=1):
    """三线表：顶线 1.5 磅、表头下线 0.75 磅、底线 1.5 磅，其余全部无框线。"""
    nil = {"val": "nil"}
    thick = {"val": "single", "sz": 12}   # 12/8 = 1.5 磅
    thin = {"val": "single", "sz": 6}     # 6/8  = 0.75 磅
    n_rows = len(table.rows)
    for i, row in enumerate(table.rows):
        for cell in row.cells:
            spec = {"top": nil, "bottom": nil, "left": nil, "right": nil}
            if i == 0:
                spec["top"] = thick
            if i == header_rows - 1:
                spec["bottom"] = thin
            if i == n_rows - 1:
                spec["bottom"] = thick
            _set_cell_border(cell, **spec)


def _display_width(text):
    """按显示宽度折算：中文/全角记 2，其余记 1。"""
    w = 0
    for ch in text:
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F", "A") else 1
    return w


def _set_fixed_layout(table):
    """锁定列宽：不加 tblLayout=fixed 的话 Word 会按自动调整覆盖我们算好的宽度。"""
    tbl_pr = table._tbl.tblPr
    layout = tbl_pr.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        tbl_pr.append(layout)
    layout.set(qn("w:type"), "fixed")


def _set_repeat_header(table, header_rows=1):
    """跨页时重复表头行（tblHeader），并禁止行内断页（cantSplit）。

    tblHeader 只对表格开头连续的 header_rows 行生效；Word 在表格跨页时
    自动在新页顶部重画这几行，解决"表 4 从 p13 跨到 p14 没有表头"的问题。
    """
    for i, row in enumerate(table.rows):
        tr_pr = row._tr.get_or_add_trPr()
        cant = OxmlElement("w:cantSplit")
        tr_pr.append(cant)
        if i < header_rows:
            th = OxmlElement("w:tblHeader")
            th.set(qn("w:val"), "true")
            tr_pr.append(th)


def _distribute_widths(rows, ncol, total_cm=14.5, char_cm=0.185, pad_cm=0.42):
    """按各列最长内容的自然宽度分配列宽。

    先算每列"不换行所需宽度"（字宽 + 单元格左右内边距）。总需求在版心内就放大填满；
    超出时只从较宽的列（文字列）里回收空间，较窄的列（数字列）保持原宽，
    避免 "1234"、"5.6789" 这类数字被拆行。
    """
    natural = []
    for j in range(ncol):
        units = max(_display_width(r[j].strip()) for r in rows)
        natural.append(units * char_cm + pad_cm)
    total_need = sum(natural)
    if total_need <= total_cm:
        k = total_cm / total_need
        return [w * k for w in natural]
    # 由窄到宽依次给足：窄列（数字列）先拿满自身自然宽度，剩下的亏空全由宽列（文字列）承担
    widths = [0.0] * ncol
    order = sorted(range(ncol), key=lambda j: natural[j])
    remaining = total_cm
    k = ncol
    for idx, j in enumerate(order):
        share = remaining / k
        if natural[j] <= share:
            widths[j] = natural[j]
            remaining -= natural[j]
            k -= 1
        else:
            for j2 in order[idx:]:
                widths[j2] = remaining / k
            break
    return widths


def flush_table(doc, rows, total_cm=14.5, font_pt=9.0):
    """rows: list[list[str]]，第一行为表头。"""
    if not rows:
        return
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    table = doc.add_table(rows=len(rows), cols=ncol)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    # 字宽按实际字号折算：9 磅中文约 0.317cm、半角约 0.16cm，取 0.16 作单宽单位
    char_cm = font_pt / 9.0 * 0.16
    widths = _distribute_widths(rows, ncol, total_cm=total_cm, char_cm=char_cm)
    for j, w in enumerate(widths):
        table.columns[j].width = Cm(w)
    for i, row in enumerate(rows):
        for j, text in enumerate(row):
            cell = table.cell(i, j)
            cell.width = Cm(widths[j])
            cell.text = ""
            p = cell.paragraphs[0]
            pf = p.paragraph_format
            pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
            pf.space_before = Pt(2)
            pf.space_after = Pt(2)
            pf.first_line_indent = Pt(0)
            pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_rich_text(p, text.strip(), "宋体", font_pt)
    _set_fixed_layout(table)
    _set_repeat_header(table, header_rows=1)
    make_three_line_table(table, header_rows=1)
    # 表格后留一行空段，避免与下文粘连
    sp = doc.add_paragraph()
    sp.paragraph_format.space_after = Pt(6)
    set_run_font(sp.add_run(""), "宋体", 6)


# ---------------------------------------------------------------- Markdown 解析

TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")


def parse_table_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def add_figure(doc, src, caption, width_cm=None, report=None):
    """插图 + 图题。图片缺失时降级为一行提示，不让整份文档生成失败。

    默认宽度 14.5cm（A4 页面 21cm 减去左右各 3.17cm 页边距后的版心宽度）。
    高度不指定，由 python-docx 按原图长宽比自动换算。
    """
    if not src.exists():
        if report is not None:
            report.setdefault("missing", []).append(str(src))
        p = doc.add_paragraph()
        p.paragraph_format.first_line_indent = Pt(0)
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run_font(p.add_run(f"[图片缺失：{src}]"), "宋体", 10.5, False)
    else:
        if report is not None:
            report["embedded"] = report.get("embedded", 0) + 1
        p = doc.add_paragraph()
        p.paragraph_format.first_line_indent = Pt(0)
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run()
        run.add_picture(str(src), width=Cm(width_cm if width_cm else 14.5))

    if caption:
        c = doc.add_paragraph()
        c.paragraph_format.first_line_indent = Pt(0)
        c.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        c.paragraph_format.space_before = Pt(0)
        c.paragraph_format.space_after = Pt(6)
        set_run_font(c.add_run(caption), "宋体", 10.5, False)


def render_markdown(doc, md_text, pending_formulas, base_dir=None, fig_report=None):
    """把正文 Markdown 渲染进 docx。支持标题、段落、管道表、列表、引用块、插图、分隔线。

    base_dir：图片相对路径的基准目录（通常为 Markdown 文件所在目录）。
    """
    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 空行
        if not stripped:
            i += 1
            continue

        # 分隔线
        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", stripped):
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = min(len(m.group(1)), 3)
            heading(doc, m.group(2).strip(), level)
            i += 1
            continue

        # 插图：![图题](相对路径 "可选宽度cm")。路径相对 Markdown 文件所在目录。
        m = re.match(r'^!\[(.*?)\]\((.+?)\)\s*$', stripped)
        if m:
            caption, target = m.group(1).strip(), m.group(2).strip()
            width = None
            wm = re.search(r'\s+"([\d.]+)"\s*$', target)
            if wm:
                width = float(wm.group(1))
                target = target[:wm.start()].strip()
            src = (base_dir / target) if base_dir else Path(target)
            add_figure(doc, src, caption, width, fig_report)
            i += 1
            continue

        # 管道表
        if stripped.startswith("|") and i + 1 < len(lines) and TABLE_SEP.match(lines[i + 1]):
            rows = [parse_table_row(stripped)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(parse_table_row(lines[i]))
                i += 1
            flush_table(doc, rows)
            continue

        # 引用块
        if stripped.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            text = " ".join(x for x in buf if x)
            if text:
                p = doc.add_paragraph()
                pf = p.paragraph_format
                pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
                pf.left_indent = Pt(24)
                pf.first_line_indent = Pt(0)
                add_rich_text(p, text, "楷体", 12)
            continue

        # 无序/有序列表：保留符号，不缩进首行
        m = re.match(r"^([-*+]|\d+[.)])\s+(.*)$", stripped)
        if m:
            marker = m.group(1)
            if not re.match(r"\d", marker):
                marker = "·"
            p = doc.add_paragraph()
            pf = p.paragraph_format
            pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
            pf.left_indent = Pt(24)
            pf.first_line_indent = Pt(-12)
            add_rich_text(p, f"{marker} {m.group(2)}", "宋体", 12)
            i += 1
            continue

        # 段落：连续非空行合并
        buf = []
        while i < len(lines):
            cur = lines[i].strip()
            if not cur:
                break
            if re.match(r"^(#{1,6})\s", cur) or cur.startswith("|") or cur.startswith(">"):
                break
            if re.match(r"^([-*+]|\d+[.)])\s+", cur):
                break
            if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", cur):
                break
            buf.append(cur)
            i += 1
        text = "".join(buf)
        for fm in re.findall(r"\$[^$]+\$", text):
            pending_formulas.append(fm)
        body_para(doc, text)


# ---------------------------------------------------------------- 题名页

def build_title_page(doc, args):
    """GB/T 7713.2-2022 题名页要素。"""
    # 中文题名
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(24)
    p.paragraph_format.space_after = Pt(18)
    set_run_font(p.add_run(args.title), "黑体", 18, True)

    # 作者
    if args.author:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(6)
        set_run_font(p.add_run(args.author), "宋体", 12)

    # 单位
    if args.affil:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(18)
        set_run_font(p.add_run(args.affil), "宋体", 10.5)

    # 摘要
    abstract = args.abstract_file.read_text(encoding="utf-8").strip() if args.abstract_file else args.abstract
    if abstract:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.first_line_indent = Pt(0)
        set_run_font(p.add_run("摘  要："), "黑体", 10.5, True)
        set_run_font(p.add_run(abstract), "宋体", 10.5)

    # 关键词
    if args.keywords:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.first_line_indent = Pt(0)
        set_run_font(p.add_run("关键词："), "黑体", 10.5, True)
        set_run_font(p.add_run(args.keywords), "宋体", 10.5)

    # 中图分类号 + 文献标识码
    meta = []
    if args.clc:
        meta.append(f"中图分类号：{args.clc}")
    if args.doccode:
        meta.append(f"文献标识码：{args.doccode}")
    if args.article_id:
        meta.append(f"文章编号：{args.article_id}")
    if meta:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.first_line_indent = Pt(0)
        set_run_font(p.add_run("　".join(meta)), "宋体", 10.5)

    # 基金
    if args.fund:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.first_line_indent = Pt(0)
        set_run_font(p.add_run("基金项目："), "黑体", 10.5, True)
        set_run_font(p.add_run(args.fund), "宋体", 10.5)

    # 作者简介
    if args.bio:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(12)
        p.paragraph_format.first_line_indent = Pt(0)
        set_run_font(p.add_run("作者简介："), "黑体", 10.5, True)
        set_run_font(p.add_run(args.bio), "宋体", 10.5)


# ---------------------------------------------------------------- 参考文献

def build_references(doc, refs_text, pending_warn):
    """参考文献表：悬挂缩进，按 GB/T 7714-2015 校验必备要素。"""
    heading(doc, "参考文献", 1)
    entries = [ln.strip() for ln in refs_text.splitlines() if ln.strip()]
    for k, entry in enumerate(entries, 1):
        entry = re.sub(r"^\[\d+\]\s*", "", entry)
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        pf.left_indent = Pt(21)
        pf.first_line_indent = Pt(-21)   # 悬挂缩进
        pf.space_after = Pt(0)
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        add_rich_text(p, f"[{k}] {entry}", "宋体", 10.5)
        # 必备要素粗查
        if not re.search(r"\[[JMDCNRGSPZ](\/OL)?\]", entry):
            pending_warn.append(f"[{k}] 缺文献类型标识（[J]/[M]/[D]/[C]/[N]/[EB/OL]）")
        if re.search(r"\[J\]", entry) and not re.search(r"\d{4}", entry):
            pending_warn.append(f"[{k}] 期刊文献缺年份")


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="Markdown 稿件 → 中文期刊交稿 Word")
    ap.add_argument("manuscript", type=Path, help="正文 Markdown 文件")
    ap.add_argument("--out", type=Path, required=True, help="输出 .docx 路径")
    ap.add_argument("--template", type=Path, help="期刊 Word 模板（套用其样式）")
    ap.add_argument("--title", default="（题名待填）")
    ap.add_argument("--author", default="")
    ap.add_argument("--affil", default="")
    ap.add_argument("--abstract", default="", help="中文摘要文本")
    ap.add_argument("--abstract-file", type=Path, help="中文摘要文件（.md/.txt）")
    ap.add_argument("--keywords", default="", help="分号分隔")
    ap.add_argument("--abstract-en", default="", help="英文摘要")
    ap.add_argument("--keywords-en", default="")
    ap.add_argument("--clc", default="", help="中图分类号，如 F272")
    ap.add_argument("--doccode", default="A", help="文献标识码，原创论文为 A")
    ap.add_argument("--article-id", default="")
    ap.add_argument("--fund", default="")
    ap.add_argument("--bio", default="", help="作者简介")
    ap.add_argument("--refs-file", type=Path, help="参考文献 Markdown（一行一条）")
    ap.add_argument("--no-title-page", action="store_true", help="不生成题名页")
    args = ap.parse_args()

    if not args.manuscript.exists():
        sys.exit(f"找不到正文文件：{args.manuscript}")

    doc = Document(str(args.template)) if args.template and args.template.exists() else Document()

    # 页面设置：A4，页边距按中文期刊常见值
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.top_margin = sec.bottom_margin = Cm(2.54)
    sec.left_margin = sec.right_margin = Cm(3.17)
    add_page_footer_number(sec)

    pending_formulas = []
    pending_warn = []

    if not args.no_title_page:
        build_title_page(doc, args)
        doc.add_page_break()

    fig_report = {}
    md = args.manuscript.read_text(encoding="utf-8")
    render_markdown(doc, md, pending_formulas,
                    base_dir=args.manuscript.parent, fig_report=fig_report)

    if args.refs_file and args.refs_file.exists():
        doc.add_page_break()
        build_references(doc, args.refs_file.read_text(encoding="utf-8"), pending_warn)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(args.out))

    # ---- 报告
    print(f"[已生成] {args.out}")
    print(f"  模板：{'套用 ' + str(args.template) if args.template else '默认样式'}")
    print(f"  题名页：{'否' if args.no_title_page else '是'}")
    n_fig = fig_report.get("embedded", 0)
    if n_fig:
        print(f"  插图：已嵌入 {n_fig} 张")
    for miss in fig_report.get("missing", []):
        print(f"  [警告] 图片缺失，已降级为文字提示：{miss}")
    if pending_formulas:
        print(f"\n[待转公式 {len(pending_formulas)} 条] 需在 Word 内用 Alt+= 转为 OMML：")
        for f in pending_formulas[:20]:
            print(f"    {f}")
        if len(pending_formulas) > 20:
            print(f"    …… 另有 {len(pending_formulas) - 20} 条")
    if pending_warn:
        print(f"\n[参考文献待核 {len(pending_warn)} 条]")
        for w in pending_warn[:20]:
            print(f"    {w}")
    print("\n[仍需人工核对] 字数上限、图表数量上限、页边距、题注字体、脚注制式"
          "（GB/T 7714 文后表 vs CY/T 121 页下注）—— 以目标刊投稿须知为准。")


if __name__ == "__main__":
    main()

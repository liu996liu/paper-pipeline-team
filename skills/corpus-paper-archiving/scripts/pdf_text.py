# -*- coding: utf-8 -*-
"""从 PDF 抽干净文本，作为引文核验的第二底本。

为什么需要它：转换工具产出的 md/txt 常带三类损伤（丢标点、按页插反引号与断行、
双栏逐字交错），用它核引文会大量假阴性。pypdf 的线性抽取读序不同，
两份交叉比对能把「跨栏断裂」和「真的没有这句话」分开。

用法：
    python pdf_text.py <PDF文件> [-o 输出文件]
    python pdf_text.py <PDF目录> --out-dir <输出目录> [--keep-page-marks]

输出：每篇一个 .txt（UTF-8，纯文本）。默认输出到当前工作目录，
      绝不写进 PDF 所在目录——那是用户的原始材料目录，不该被污染。
"""
import argparse
import os
import re
import sys

try:
    from pypdf import PdfReader
except ImportError:
    print("需要 pypdf：pip install pypdf")
    sys.exit(1)

CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\U00020000-\U0002ffff]")


def extract(pdf_path, page_marks=False):
    reader = PdfReader(pdf_path)
    pages = []
    for i, page in enumerate(reader.pages, 1):
        try:
            txt = page.extract_text() or ""
        except Exception as e:
            print(f"  [警告] 第 {i} 页抽取失败：{e}", file=sys.stderr)
            txt = ""
        pages.append((i, txt))
    if page_marks:
        return "\n".join(f"<p {i}>\n{t}" for i, t in pages), len(pages)
    return "\n".join(t for _, t in pages), len(pages)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="PDF 文件或目录")
    ap.add_argument("-o", "--out", help="单文件时的输出路径")
    ap.add_argument("--out-dir", help="目录时的输出目录（默认当前目录）")
    ap.add_argument("--keep-page-marks", action="store_true", help="保留 <p N> 页标记")
    a = ap.parse_args()

    if os.path.isfile(a.src):
        pdfs = [a.src]
        out_dir = os.path.dirname(a.out) if a.out else (a.out_dir or os.getcwd())
        single = a.out
    elif os.path.isdir(a.src):
        pdfs = sorted(
            os.path.join(a.src, f) for f in os.listdir(a.src)
            if f.lower().endswith(".pdf")
        )
        out_dir = a.out_dir or os.getcwd()
        single = None
    else:
        print("找不到：", a.src)
        return 1

    os.makedirs(out_dir, exist_ok=True)
    print(f"{'文件':<46}{'页数':>6}{'汉字':>10}{'字符':>10}")
    for p in pdfs:
        text, n = extract(p, a.keep_page_marks)
        stem = os.path.splitext(os.path.basename(p))[0]
        dst = single or os.path.join(out_dir, stem + ".txt")
        with open(dst, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"{stem[:44]:<46}{n:>6}{len(CJK.findall(text)):>10,}{len(text):>10,}")
    print("\n写入", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

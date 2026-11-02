# -*- coding: utf-8 -*-
"""生成 P5 汇报 PPT（14 页，券商风格）。"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt
from pptx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "report" / "figures"
OUT = ROOT / "report" / "成长因子复现汇报.pptx"

BLUE = RGBColor(0x1F, 0x4E, 0x79)
RED = RGBColor(0xC0, 0x00, 0x00)
GRAY = RGBColor(0x59, 0x59, 0x59)
LIGHT = RGBColor(0xF2, 0xF5, 0xF9)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def cn(run, size=18, bold=False, color=None):
    run.font.name = "微软雅黑"
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color if color is not None else RGBColor(0x26, 0x26, 0x26)
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        from lxml import etree
        ea = etree.SubElement(rPr, qn("a:ea"))
    ea.set("typeface", "微软雅黑")


def bar(slide, text, sub=None):
    from pptx.enum.shapes import MSO_SHAPE
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.95))
    shp.fill.solid(); shp.fill.fore_color.rgb = BLUE
    shp.line.fill.background()
    tb = slide.shapes.add_textbox(Inches(0.45), Inches(0.12), Inches(11.5), Inches(0.75))
    p = tb.text_frame.paragraphs[0]
    r = p.add_run(); r.text = text; cn(r, 24, True, WHITE)
    if sub:
        tb2 = slide.shapes.add_textbox(Inches(9.6), Inches(0.3), Inches(3.3), Inches(0.4))
        p = tb2.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.RIGHT
        r = p.add_run(); r.text = sub; cn(r, 11, False, RGBColor(0xD9, 0xE2, 0xF3))


def bullets(slide, items, left=0.6, top=1.2, width=12.1, size=17, gap=10):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(5.8))
    tf = tb.text_frame; tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        p.line_spacing = 1.25
        lvl = 0
        txt = it
        if isinstance(it, tuple):
            txt, lvl = it
        r = p.add_run(); r.text = ("• " if lvl == 0 else "– ") + txt
        cn(r, size - 2 * lvl, lvl == 0)
        if lvl:
            p.level = 1
    return tb


def picture(slide, name, left, top, width):
    slide.shapes.add_picture(str(FIG / name), Inches(left), Inches(top), width=Inches(width))


def table(slide, data, left, top, width, col_widths, font=11):
    rows, cols = len(data), len(data[0])
    shape = slide.shapes.add_table(rows, cols, Inches(left), Inches(top),
                                   Inches(width), Inches(0.34 * rows))
    tbl = shape.table
    for j, w in enumerate(col_widths):
        tbl.columns[j].width = Inches(w)
    for i, row in enumerate(data):
        for j, val in enumerate(row):
            cell = tbl.cell(i, j)
            cell.text = ""
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER if j else PP_ALIGN.LEFT
            r = p.add_run(); r.text = str(val)
            if i == 0:
                cn(r, font, True, WHITE)
                cell.fill.solid(); cell.fill.fore_color.rgb = BLUE
            else:
                cn(r, font, False, RGBColor(0x26, 0x26, 0x26))
                cell.fill.solid()
                cell.fill.fore_color.rgb = WHITE if i % 2 else LIGHT
    return tbl


def footer(slide, text="资料来源：BigQuant，项目复现计算"):
    tb = slide.shapes.add_textbox(Inches(0.45), Inches(7.05), Inches(8), Inches(0.3))
    r = tb.text_frame.paragraphs[0].add_run(); r.text = text; cn(r, 9, False, GRAY)


def takeaway(slide, text, top=5.75, height=0.95):
    from pptx.enum.shapes import MSO_SHAPE
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.55), Inches(top),
                                 Inches(12.2), Inches(height))
    shp.fill.solid(); shp.fill.fore_color.rgb = LIGHT
    shp.line.color.rgb = RGBColor(0xD0, 0xDA, 0xE8)
    tf = shp.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.25)
    tf.margin_right = Inches(0.25)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = text
    cn(r, 15, True, BLUE)


def kpi(slide, left, top, number, label, width=2.9):
    from pptx.enum.shapes import MSO_SHAPE
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top),
                                 Inches(width), Inches(1.35))
    shp.fill.solid(); shp.fill.fore_color.rgb = LIGHT
    shp.line.color.rgb = RGBColor(0xD0, 0xDA, 0xE8)
    tf = shp.text_frame
    tf.margin_top = Inches(0.12)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = number; cn(r, 24, True, BLUE)
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
    r = p2.add_run(); r.text = label; cn(r, 11, False, GRAY)


# ---------------- 1 封面 ----------------
s = prs.slides.add_slide(BLANK)
from pptx.enum.shapes import MSO_SHAPE
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
bg.fill.solid(); bg.fill.fore_color.rgb = BLUE; bg.line.fill.background()

tb = s.shapes.add_textbox(Inches(0.9), Inches(1.9), Inches(11.5), Inches(1.2))
r = tb.text_frame.paragraphs[0].add_run(); r.text = "成长因子的有效性再检验"
cn(r, 40, True, WHITE)

tb = s.shapes.add_textbox(Inches(0.9), Inches(3.1), Inches(11.5), Inches(0.7))
r = tb.text_frame.paragraphs[0].add_run()
r.text = "——基于 2020–2025 年 A 股市场的 12 因子测试"
cn(r, 20, False, RGBColor(0xD9, 0xE2, 0xF3))

tb = s.shapes.add_textbox(Inches(0.9), Inches(4.3), Inches(11.5), Inches(1.2))
tf = tb.text_frame
for i, t in enumerate(["对华泰证券《单因子测试之成长类因子》的复现与延伸",
                       "量化研究复现项目  |  2026 年 11 月"]):
    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    r = p.add_run(); r.text = t; cn(r, 14, False, RGBColor(0xD9, 0xE2, 0xF3))

# ---------------- 2 一页结论 ----------------
s = prs.slides.add_slide(BLANK)
bar(s, "一页结论", "结论：结构有效，强度衰减")
bullets(s, [
    "当季（q）因子仍能排序：IC 1.0%–1.8%，五层单调性 0.9–1.0，方向与原文一致",
    "但收益不稳定：月度 |t| 均值 3.5–4.3，因子收益序列 t 只有 0.8–1.7",
    "三年复合（3Y）因子系统性反向：最高增长组每年跑输 5–6 个百分点",
    "扣真实换手成本后：多空 2.6%–5.3%，信息比率仅 0.35–0.54",
    "FDR 校正后只有 OCF_G_q 显著（p_adj = 0.0009）",
], top=1.25, size=19, gap=14)
kpi(s, 0.6, 4.85, "1.84%", "ROE_G_q 的 IC")
kpi(s, 3.75, 4.85, "1.0", "当季五层单调性")
kpi(s, 6.9, 4.85, "+5.2%", "扣费后多空（年化）")
kpi(s, 10.05, 4.85, "0.0009", "OCF_G_q 的 FDR p_adj")
footer(s)

# ---------------- 3 研究设计 ----------------
s = prs.slides.add_slide(BLANK)
bar(s, "研究设计：三个问题", "方法复现，结论开放")
bullets(s, [
    "Q1：成长因子在 2020–2025 是否仍有横截面区分度？",
    "Q2：这种区分度能否转化为扣除成本后的收益？",
    "Q3：与原文的差异来自样本期、市场状态，还是因子失效？",
    "方法：分层回测 + 回归法（WLS）+ IC 分析 + 稳健性",
    "原则：不追求复刻 2016 年的数字，只追求方法严格、差异可解释",
], top=1.3, size=18, gap=12)
footer(s)

# ---------------- 4 数据 ----------------
s = prs.slides.add_slide(BLANK)
bar(s, "数据与样本", "5,317 只 / 72 个月")
table(s, [
    ["项目", "数值", "说明"],
    ["原始面板", "519,860 行", "120 个月末截面"],
    ["过滤后", "445,383 行", "5,317 只股票"],
    ["评估期", "2020-01 ~ 2025-12", "72 个截面"],
    ["行业", "31 个", "申万 2021 一级"],
    ["基准", "沪深300", "年化 3.7%"],
], 0.7, 1.3, 7.2, [2.2, 2.6, 2.4], font=12)
bullets(s, [
    "财务按公告日对齐（PIT）：平安银行变动日 03-10 / 04-21 / 10-21",
    "退市股保留：乐视退、暴风退、退市锐电 3/3 在库",
    "复权：close 已是后复权，平安银行 2024 年 +35.4%",
], left=8.1, top=1.5, width=4.8, size=13, gap=10)
footer(s)

# ---------------- 5 因子 ----------------
s = prs.slides.add_slide(BLANK)
bar(s, "12 个成长因子", "4 科目 × 3 口径")
table(s, [
    ["", "单季同比（q）", "TTM 同比", "三年复合（3Y）"],
    ["营业收入", "Sales_G_q", "Sales_G_ttm", "Sales_G_3y"],
    ["净利润", "Profit_G_q", "Profit_G_ttm", "Profit_G_3y"],
    ["经营现金流", "OCF_G_q", "OCF_G_ttm", "OCF_G_3y"],
    ["ROE", "ROE_G_q", "ROE_G_ttm", "ROE_G_3y"],
], 0.7, 1.3, 11.9, [2.4, 3.3, 3.1, 3.1], font=14)
bullets(s, [
    "公式：(X_t − X_{t−12}) / |X_{t−12}|；三年复合要求两端同为正",
    "平台 0 填充、负营收、非正净资产统一视为缺失",
], top=4.3, size=15, gap=8)
footer(s)

# ---------------- 6 IC ----------------
s = prs.slides.add_slide(BLANK)
bar(s, "核心结果一：当季为正，三年为负", "IC 均值")
picture(s, "fig1_ic_bar.png", 0.55, 1.15, 8.6)
bullets(s, [
    "当季：1.0%–1.8%",
    "三年复合：-0.3%～-0.8%",
    "OCF_G_q 的 t 值最高（3.96）",
], left=9.2, top=1.6, width=3.6, size=14, gap=8)
takeaway(s, "当季因子 IC 全为正、三年复合全为负：方向与原文一致，强度约为原文的一半。")
footer(s)

# ---------------- 7 分层 ----------------
s = prs.slides.add_slide(BLANK)
bar(s, "核心结果二：五层单调性", "多空净值")
picture(s, "fig2_nav.png", 0.55, 1.15, 8.6)
bullets(s, [
    "ROE_G_q：多空 +5.9%",
    "Profit_G_q：+5.9%",
    "OCF_G_q：+3.5%",
    "3Y：单调性为负",
], left=9.2, top=1.6, width=3.6, size=14, gap=8)
takeaway(s, "当季五层单调性 0.9–1.0；三年复合为负，高增长组反而跑输。")
footer(s)

# ---------------- 8 |t| vs 收益 t ----------------
s = prs.slides.add_slide(BLANK)
bar(s, "核心结果三：能排序 ≠ 能赚钱", "|t| 与收益序列 t")
picture(s, "fig5_tstat.png", 0.55, 1.15, 8.6)
bullets(s, [
    "12 因子月度 |t| 均值 3.04",
    "收益序列 t 均值仅 0.07",
    "β 符号翻转率 47%",
    "高 |t| 反而对应低稳定",
], left=9.2, top=1.6, width=3.6, size=14, gap=8)
takeaway(s, "横截面显著不代表长期有效：β 符号频繁翻转，均值被抵消。")
footer(s)

# ---------------- 9 分年度 ----------------
s = prs.slides.add_slide(BLANK)
bar(s, "核心结果四：因子是“分年景”的", "分年度 IC")
picture(s, "fig4_yearly.png", 0.55, 1.15, 8.6)
bullets(s, [
    "2020：ROE_G_q +4.74%",
    "2021：-1.01%",
    "2023：+0.46%",
    "2024：+3.57%",
], left=9.2, top=1.6, width=3.6, size=14, gap=8)
takeaway(s, "2020/2024 强、2021/2023 弱：全样本均值掩盖了因子的条件性。")
footer(s)

# ---------------- 10 3Y 反向 ----------------
s = prs.slides.add_slide(BLANK)
bar(s, "核心结果五：3Y 因子为何反向", "动量暴露 + 价值陷阱")
picture(s, "fig6_3y_quintile.png", 0.45, 1.15, 6.3)
picture(s, "fig7_3y_momentum.png", 6.85, 1.15, 6.3)
takeaway(s, "3Y 的反向不是全局，而是集中在“低动量 + 高增长”的落刀型股票。", top=5.9, height=0.95)
footer(s)

# ---------------- 11 成本与 FDR ----------------
s = prs.slides.add_slide(BLANK)
bar(s, "成本与显著性", "真实换手口径")
table(s, [
    ["因子", "月换手", "多空毛", "扣费后", "夏普"],
    ["ROE_G_q", "20.4%", "+5.9%", "+5.2%", "0.88"],
    ["Profit_G_q", "20.3%", "+5.9%", "+5.2%", "0.88"],
    ["Sales_G_q", "18.2%", "+4.8%", "+4.1%", "0.77"],
    ["OCF_G_q", "24.4%", "+3.5%", "+2.6%", "1.28"],
], 0.7, 1.35, 7.3, [2.0, 1.7, 1.5, 1.4, 1.3], font=13)
bullets(s, [
    "FDR 校正：12 个因子仅 OCF_G_q 通过（p_adj=0.0009）",
    "ROE_G_q p_adj=0.088，Profit_G_q 0.169",
    "填 0 vs 剔除：IC 差异 ≤0.31%",
], left=8.3, top=1.5, width=4.6, size=13, gap=10)
footer(s)

# ---------------- 12 与原文对话 ----------------
s = prs.slides.add_slide(BLANK)
bar(s, "与原文对话", "同一方法，不同年代")
table(s, [
    ["原文结论", "本文判断", "依据"],
    ["当季 > TTM > 三年", "支持，更极端", "q 正、3Y 负"],
    ["因子收益显著", "不支持", "收益 t 0.8–1.7"],
    ["市场消化快", "不支持", "IC 6 个月不衰减"],
    ["3Y 基本无效", "不一致", "3Y 系统性反向"],
], 0.7, 1.3, 11.8, [4.2, 2.8, 4.8], font=12)
bullets(s, [
    "差异来源：样本期（注册制/机构化）、市场状态（2021 杀估值）、口径（单季/次日停牌）、成本",
], top=5.2, size=14, gap=6)
footer(s)

# ---------------- 13 结论与建议 ----------------
s = prs.slides.add_slide(BLANK)
bar(s, "结论与使用建议", "研究结论")
bullets(s, [
    "当季因子优先：ROE_G_q、Profit_G_q；OCF_G_q 作为稳健型选择",
    "不要同时使用 ROE 与 Profit（相关性 0.975），存在严重共线",
    "不要无条件做多高三年增长，尤其在低动量与大盘股中",
    "把因子有效性放在市场状态框架下评估，而非看全样本平均",
    "风险：样本仅 6 年、基准降级、固定成本假设、行业分类回溯",
], top=1.3, size=18, gap=12)
footer(s)

# ---------------- 14 复现 ----------------
s = prs.slides.add_slide(BLANK)
bar(s, "复现与交付", "代码 / 数据 / 平台")
bullets(s, [
    "数据：bq_export_v41/（月频面板 + 指数 + 事件表，约 50 MB）",
    "代码：src/ 五模块 + scripts/ 分析脚本 + tests/ 15 个用例",
    "平台：platform/bq_factor_lab.py 单文件，IC 与本地逐格一致（max diff = 0）",
    "Notebook：notebook/成长因子测试.ipynb，Run All 即可复现，自检 12/12 PASS",
    "报告：25 页 Word/PDF，11 图 14 表",
], top=1.3, size=17, gap=12)
footer(s, "项目地址：github.com/Ray832/quant-growth-factor")

OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(OUT)
print("saved", OUT, "slides:", len(prs.slides))

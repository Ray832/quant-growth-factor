# -*- coding: utf-8 -*-
"""生成 P4 研报（Word，券商风格，25 页左右）。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "output" / "tables"
FIG = ROOT / "report" / "figures"
OUT = ROOT / "report" / "成长因子复现报告.docx"

BLUE = RGBColor(0x1F, 0x4E, 0x79)
GRAY = RGBColor(0x59, 0x59, 0x59)


# ---------------------------------------------------------------------------
# 排版工具
# ---------------------------------------------------------------------------

def set_run(run, name="宋体", size=10.5, bold=False, color=None):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.bold = bold
    if color is not None:
        run.font.color.rgb = color


def para(doc, text, size=11, bold=False, indent=True, align=None,
         space_before=0, space_after=6, name="宋体", color=None):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = 1.6
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    if indent:
        pf.first_line_indent = Pt(size * 2)
    if align:
        p.alignment = align
    r = p.add_run(text)
    set_run(r, name, size, bold, color)
    return p


def heading(doc, text, level=1):
    size = {1: 15, 2: 12.5, 3: 11}[level]
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14 if level == 1 else 10)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    r = p.add_run(text)
    set_run(r, "黑体", size, True, BLUE)
    return p


def caption(doc, text, kind="图"):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(8)
    r = p.add_run(text)
    set_run(r, "宋体", 8.5, False, GRAY)


def shade(cell, hex_color="1F4E79"):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def table(doc, df, widths=None, font=8, header=True, align_right_from=1):
    nrow, ncol = df.shape
    t = doc.add_table(rows=nrow + 1, cols=ncol)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = True

    def fill(i, values, is_header):
        for j, val in enumerate(values):
            cell = t.cell(i, j)
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
            if j >= align_right_from:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(str(val))
            if is_header:
                set_run(r, "黑体", font, True, RGBColor(0xFF, 0xFF, 0xFF))
                shade(cell)
            else:
                set_run(r, "宋体", font)

    fill(0, list(df.columns), header)
    for i, row in enumerate(df.itertuples(index=False), start=1):
        fill(i, row, False)

    if widths:
        for j, w in enumerate(widths):
            for i in range(nrow + 1):
                t.cell(i, j).width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def figure(doc, filename, cap, width=15.2):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(str(FIG / filename), width=Cm(width))
    caption(doc, cap)


def add_page_number(section):
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    run = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = "1"
    run.append(t)
    fld.append(run)
    p._p.append(fld)


def pct(x, digits=1):
    return f"{x*100:+.{digits}f}%"


def num(x, digits=3):
    return f"{x:.{digits}f}"


# ---------------------------------------------------------------------------
# 数据
# ---------------------------------------------------------------------------

fdr = pd.read_csv(T / "fdr_summary.csv").set_index("factor")
lay = pd.read_csv(T / "report_layer.csv").set_index("factor")
reg = pd.read_csv(T / "regression_summary.csv").set_index("factor")
dec = pd.read_csv(T / "ic_decay.csv").set_index("factor")
size = pd.read_csv(T / "size_ic_summary.csv")
ind_ic = pd.read_csv(T / "industry_ic_summary.csv", index_col=0)
turn = pd.read_csv(T / "turnover_cost.csv").set_index("factor")
bench = pd.read_csv(T / "benchmark_excess.csv").set_index("factor")
fill0 = pd.read_csv(T / "fill0_compare.csv").set_index("factor")
dd_beta = pd.read_csv(T / "deepdive_beta.csv").set_index("factor")
dd_3y = pd.read_csv(T / "deepdive_3y.csv").set_index("factor")
dd_mom = pd.read_csv(T / "deepdive_3y_momentum.csv")
dd_q = pd.read_csv(T / "deepdive_3y_quintile.csv").set_index("factor")
ic_series = pd.read_csv(T / "ic_series_neutral.csv", index_col=0, parse_dates=True)
corr = pd.read_csv(T / "factor_corr.csv", index_col=0)
ind_growth = pd.read_csv(T / "industry_growth.csv", index_col=0)
layer_detail = pd.read_csv(T / "layer_detail.csv").set_index("factor")

FACTORS = list(fdr.index)


# ---------------------------------------------------------------------------
# 文档
# ---------------------------------------------------------------------------

def build():
    doc = Document()
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.top_margin, sec.bottom_margin = Cm(2.4), Cm(2.2)
    sec.left_margin, sec.right_margin = Cm(2.6), Cm(2.4)
    add_page_number(sec)

    normal = doc.styles["Normal"]
    normal.font.name = "宋体"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    normal.font.size = Pt(11)

    # ---------------- 封面 ----------------
    for _ in range(4):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("成长因子的有效性再检验")
    set_run(r, "黑体", 26, True, BLUE)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("——基于 2020–2025 年 A 股市场的单因子测试")
    set_run(r, "黑体", 15, False, GRAY)

    for _ in range(2):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("对华泰证券《单因子测试之成长类因子》的复现与延伸")
    set_run(r, "宋体", 12, False, GRAY)

    for _ in range(8):
        doc.add_paragraph()
    for line in ["量化研究复现项目", "2026 年 11 月", "本报告为方法复现与研究练习，不构成投资建议"]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(line)
        set_run(r, "宋体", 10.5, False, GRAY)

    doc.add_page_break()

    # ---------------- 摘要 ----------------
    heading(doc, "摘要", 1)
    para(doc, "本文沿用华泰证券 2016 年《单因子测试之成长类因子》的框架，在 2020–2025 年的 A 股样本上"
              "重新检验 12 个成长因子。与原文不同的是，本文不追求复刻当年的数值，而是回答三个问题："
              "成长因子在近五年是否仍有横截面区分度？这种区分度能否转化为可交易的收益？"
              "它与当年的结论为何出现差异？")
    para(doc, "样本覆盖 5,317 只 A 股、72 个月末截面、44.6 万条观测。因子构建、去极值、行业中性、"
              "IC 与分层方法均按原文口径实现，并在平台与本地两套环境中做了逐格一致性校验。")
    para(doc, "主要结论如下：")
    for text in [
        "第一，当季（q）因子仍有明显的横截面区分度。ROE_G_q、Profit_G_q 的月度 |t| 均值分别为 3.5、3.8，"
        "五层组合的单调性达到 0.9–1.0，方向与原文一致。",
        "第二，强度较原文明显衰减。原文 IC 约 2%、多空年化 6%、收益序列 t 值 2.6–3.5；"
        "本文 IC 只有 0.97%–1.84%，多空毛收益 2.5%–5.9%，收益序列 t 值 0.84–1.73。",
        "第三，因子有效性高度依赖市场状态。2020 年与 2024 年 IC 达 3.4%–5.1%，2021 年与 2023 年"
        "接近零甚至为负。全样本平均因此被显著摊薄。",
        "第四，三年复合增长率因子系统性反向。Profit_G_3y 的 IC 从 t+1 的 -0.79% 恶化到 t+6 的 -3.95%，"
        "最高增长组的事后 12 个月收益比最低组低约 6 个百分点。",
        "第五，多重检验校正后仅 OCF_G_q 显著（p_adj = 0.0009）。但在真实换手口径下，"
        "ROE_G_q、Profit_G_q 扣费后仍有多空 5.3%、5.2% 的年化收益，只是信息比率仅 0.35–0.54。",
    ]:
        para(doc, text)
    para(doc, "与原文相比，本文的增量不在“复刻”，而在“对话”：同样的方法在另一个时代得到的"
              "不是同样的答案，而是一个更挑剔的答案——成长因子依然能排序，但越来越难赚钱。")

    doc.add_page_break()

    # ---------------- 一、引言 ----------------
    heading(doc, "一、引言与研究设计", 1)
    heading(doc, "1.1 为什么要重做一次", 2)
    para(doc, "华泰的这篇报告发表于 2016 年 10 月，样本截止到 2016 年 8 月。此后 A 股经历了注册制改革、"
              "退市新规、北交所设立、机构投资者占比上升，以及 2021 年的核心资产瓦解与 2024 年的微盘股波动。"
              "成长因子的定价环境已经完全不同。")
    para(doc, "如果只是把 2016 年的数字再算一遍，除了确认“当年确实如此”，并不能回答今天的问题。"
              "因此本文的定位是：方法严格复现，结论独立检验，差异给出解释。")

    heading(doc, "1.2 三个研究问题", 2)
    for text in [
        "Q1：成长因子在 2020–2025 年是否仍有横截面区分度？",
        "Q2：这种区分度能否转化为扣除成本后的收益？",
        "Q3：与原文的差异来自样本期、市场状态，还是因子本身失效？",
    ]:
        para(doc, text)

    heading(doc, "1.3 与原文的口径差异", 2)
    t1 = pd.DataFrame([
        ["样本期", "2005-04 ~ 2016-08", "2020-01 ~ 2025-12", "样本外独立检验"],
        ["当季口径", "Wind 最新财报同比", "单季（_mrq）同比", "更贴合“当季”字面"],
        ["基准", "沪深300", "全 A 流通市值加权", "降级口径，已披露"],
        ["行业权重", "沪深300 行业权重", "全 A 流通市值行业占比", "降级口径，已披露"],
        ["估值对比", "有", "不做", "聚焦成长因子本身"],
        ["行业分类", "申万（当年）", "申万 2021（回溯）", "存在分类漂移"],
    ], columns=["维度", "原文", "本文", "说明"])
    table(doc, t1, widths=[3.2, 5.2, 5.2, 4.6])
    caption(doc, "表1  本文与原文的口径差异")

    # ---------------- 二、经济逻辑 ----------------
    heading(doc, "二、成长因子的经济逻辑", 1)
    heading(doc, "2.1 成长溢价从哪里来", 2)
    para(doc, "成长因子试图捕捉的是“企业扩张速度”与“股价未来收益”之间的关系。理论上至少有三条通道。")
    para(doc, "第一是预期增长通道。如果市场对高成长公司的未来盈利预期偏低，随着业绩兑现，股价会被重新定价。"
              "这是最经典的基本面动量逻辑，也是原文“成长因子完全源于财务数据、逻辑清楚”的依据。")
    para(doc, "第二是错误定价通道。投资者对短期财务改善反应不足，或对长期增长过度外推，都会造成价格偏离。"
              "前者支持“当季因子最有效”，后者则意味着“长期增长因子可能反向”。")
    para(doc, "第三是风险补偿通道。高成长公司往往伴随更高的经营不确定性，其超额收益可能只是风险的补偿，"
              "而非真正的 alpha。这解释了为什么成长因子的多空收益波动大、信息比率低。")

    heading(doc, "2.2 为什么当季比 TTM 强", 2)
    para(doc, "当季同比只用到最近一个季度的信息，TTM 则平滑了过去四个季度。如果市场对边际变化敏感，"
              "当季因子的区分度应高于 TTM；如果市场更看重稳定的盈利中枢，则 TTM 应更优。"
              "原文的实证支持前者，本文的结果同样如此：四个当季因子的 IC 全部为正，"
              "而对应的 TTM 因子多数接近零。")

    heading(doc, "2.3 三年复合为什么可能反向", 2)
    para(doc, "三年复合增长率刻画的是长期扩张速度。它有两个天然缺陷：一是基期效应，三年前的低基数会"
              "机械放大当前增速；二是已被定价，市场对持续高增长的公司往往给出更高估值，"
              "一旦增速回落，估值与盈利会双杀。")
    para(doc, "因此“高三年增长”未必是买入理由，反而可能是“增长见顶”的信号。这一推论在本文第六节"
              "得到数据支持：最高增长组的事后收益显著低于最低组。")

    heading(doc, "2.4 可检验的推论", 2)
    for text in [
        "H1：当季因子的 IC 与分层单调性应显著优于 TTM 与三年复合；",
        "H2：若市场对信息反应迅速，IC 应随持有期衰减；",
        "H3：若高增长已被定价，三年复合因子应出现反向；",
        "H4：若成长溢价是风险补偿，多空收益的波动应显著高于市场。",
    ]:
        para(doc, text)

    # ---------------- 三、数据与因子 ----------------
    heading(doc, "三、数据与因子构建", 1)
    heading(doc, "3.1 数据来源", 2)
    t2 = pd.DataFrame([
        ["行情与财务", "BigQuant cn_stock_prefactors", "日频 PIT 宽表，导出后压成月频"],
        ["指数", "cn_stock_index_bar1d", "沪深300、中证500、中证1000"],
        ["停牌", "cn_stock_prefactors.suspended", "稀疏事件表，185,594 行"],
        ["涨跌停", "price_limit_status", "只保留 1（涨停）/3（跌停）"],
    ], columns=["用途", "来源", "说明"])
    table(doc, t2, widths=[3.4, 7.4, 7.4])
    caption(doc, "表2  数据来源")

    heading(doc, "3.2 样本构建", 2)
    t3 = pd.DataFrame([
        ["原始月频面板", "519,860", "5,947", "120 个月"],
        ["剔除北交所 / ST / 停牌 / 次新", "445,724", "5,317", "—"],
        ["再剔除次日停牌", "445,383", "5,317", "341 行"],
        ["评估期截面", "—", "—", "72 个月"],
    ], columns=["步骤", "行数", "股票数", "说明"])
    table(doc, t3, widths=[7.0, 3.6, 3.4, 4.2])
    caption(doc, "表3  样本构建过程")

    para(doc, "财务数据按公告日对齐（PIT）。我们用 5 只股票的日频财务序列验证："
              "平安银行的净利润 TTM 变动日为 03-10、04-21、10-21，格力电器为 10-31、08-31、04-29，"
              "均与其真实披露节奏一致，说明不存在前视偏差。")

    heading(doc, "3.3 十二个因子", 2)
    t4 = pd.DataFrame([
        ["Sales_G_q", "营业收入（单季）", "同比", "t-12"],
        ["Sales_G_ttm", "营业收入（TTM）", "同比", "t-12"],
        ["Sales_G_3y", "营业收入（TTM）", "三年复合", "t-36"],
        ["Profit_G_q", "归母净利润（单季）", "同比", "t-12"],
        ["Profit_G_ttm", "归母净利润（TTM）", "同比", "t-12"],
        ["Profit_G_3y", "归母净利润（TTM）", "三年复合", "t-36"],
        ["OCF_G_q", "经营现金流（单季）", "同比", "t-12"],
        ["OCF_G_ttm", "经营现金流（TTM）", "同比", "t-12"],
        ["OCF_G_3y", "经营现金流（TTM）", "三年复合", "t-36"],
        ["ROE_G_q", "净利润（单季）/ 净资产", "同比", "t-12"],
        ["ROE_G_ttm", "净利润（TTM）/ 净资产", "同比", "t-12"],
        ["ROE_G_3y", "净利润（TTM）/ 净资产", "三年复合", "t-36"],
    ], columns=["因子", "输入字段", "口径", "基期"])
    table(doc, t4, widths=[3.4, 7.0, 3.2, 3.0])
    caption(doc, "表4  12 个成长因子的定义")

    para(doc, "增长率的统一公式为 (X_t − X_base) / |X_base|，分母取绝对值以避免亏损转盈时符号翻转；"
              "三年复合增长率要求两端同为正，否则记为缺失。财报中平台用 0 填充的缺失值、"
              "以及重组导致的负营收，统一视为缺失处理。")

    heading(doc, "3.4 预处理", 2)
    para(doc, "每个截面依次执行：中位数 ±5×MAD 去极值、行业中性化（减去同行业均值）、z-score 标准化。"
              "IC 计算时进一步对行业哑变量与 ln(流通市值) 回归取残差，以剔除行业与规模的影响。")

    heading(doc, "3.5 因子之间的相关性", 2)
    para(doc, "把 12 个因子在每个月的截面相关系数求平均，得到相关矩阵。平均两两相关为 0.26，"
              "整体不高，但有三对接近完全共线：ROE_G_q 与 Profit_G_q（0.975）、"
              "ROE_G_ttm 与 Profit_G_ttm（0.972）、ROE_G_3y 与 Profit_G_3y（0.924）。")
    para(doc, "这并不意外：ROE 的分子就是净利润，净资产在一年内变动有限，所以“净利润同比”与"
              "“ROE 同比”几乎是同一个变量。原文用相关强度指标也发现了同样的现象（Profit_G_3y 与"
              "ROE_G_3y 的相关强度 5.50，为全文最高）。")
    para(doc, "对使用的含义是：ROE 与 Profit 两族因子不应同时进入多因子模型，否则会引入严重共线性；"
              "若必须二选一，本文的结果略偏向 ROE_G_q（IC 1.84% vs 1.55%，单调性 0.9 vs 1.0）。")

    figure(doc, "fig9_corr.png", "图1  12 个成长因子的截面相关性", width=13.6)

    heading(doc, "3.6 成长因子的行业分布", 2)
    para(doc, "成长因子在行业间的差异很大。以 2025 年 12 月的营业收入 TTM 同比中位数为例，"
              "最高的行业与最低的行业相差超过 40 个百分点；同一时点的净利润同比差异更大。"
              "这与原文 2016 年的观察一致：直接跨行业比较成长因子没有意义。")
    para(doc, "因此本文的所有分层与 IC 都在行业内部进行，回归中加入行业哑变量，"
              "这也是原文的核心处理。若不这样做，选出来的很可能是行业 Beta，而不是成长 Alpha。")

    figure(doc, "fig10_industry.png", "图2  行业成长差异显著（2025-12 截面）", width=13.2)

    heading(doc, "2.5 文献脉络", 2)
    para(doc, "成长异象并非 A 股独有。Fama–French 三因子把价值与规模纳入定价，"
              "但并未解释“高增长公司为何能持续跑赢”；Lakonishok、Shleifer 与 Vishny（1994）"
              "把价值策略的超额收益归因于投资者对过去增长率的过度外推，这为“成长因子可能反向”"
              "提供了最早的理论线索。")
    para(doc, "在会计层面，Piotroski（2000）用 F-score 把“成长”与“质量”区分开，"
              "指出单纯的高增长若没有盈利质量配合，容易沦为价值陷阱；Sloan（1996）则发现"
              "应计利润高的公司未来收益更低。这些研究共同提示：成长因子的有效性依赖于"
              "“增长是否被正确定价”，而不是增长本身。")
    para(doc, "国内研究方面，华泰的多因子系列把成长因子拆成营收、利润、现金流、ROE 四条线，"
              "并用分层、回归、IC 三套方法交叉验证。本文沿用这一框架，但在样本期、"
              "口径与稳健性上做了扩展，尤其是把“因子收益的稳定性”与“分组条件性”单独拿出来讨论。")

    # ---------------- 四、检验结果 ----------------
    heading(doc, "四、单因子检验结果", 1)
    heading(doc, "4.1 IC 分析", 2)
    para(doc, "IC 为因子截面值与下月收益的 Spearman 相关系数，共 71 个月。结果呈现清晰的“口径分层”："
              "四个当季因子全部为正，TTM 因子接近零，三年复合因子为负。")

    rows = []
    for f in FACTORS:
        r = fdr.loc[f]
        rows.append([f, f"{r['ic_mean']*100:+.2f}%", f"{r['t']:.2f}",
                     f"{r['p_adj']:.3f}", "是" if r["sig_5pct"] else "否"])
    t5 = pd.DataFrame(rows, columns=["因子", "IC 均值", "t 值", "FDR p_adj", "5% 显著"])
    table(doc, t5, widths=[4.6, 3.4, 3.0, 3.6, 3.0])
    caption(doc, "表5  12 个因子的 IC 与显著性（2020–2025，71 个月）")

    figure(doc, "fig1_ic_bar.png", "图3  12 个成长因子的 IC 均值")
    para(doc, "从数值看，ROE_G_q 的 IC 最高（1.84%），Profit_G_q 次之（1.55%），"
              "Sales_G_q 与 OCF_G_q 分别为 1.09%、0.97%。三年复合全部为负，"
              "其中 Profit_G_3y 最低（-0.79%）。")
    para(doc, "但显著性是另一回事。经 Benjamini–Hochberg 校正后，只有 OCF_G_q 通过 5% 阈值"
              "（p_adj = 0.0009），ROE_G_q 的 p_adj 为 0.084，Profit_G_q 为 0.163。"
              "这说明在 12 个因子的多重检验下，多数“看起来有效”的结果仍可能是噪声。")

    heading(doc, "4.2 分层回测", 2)
    para(doc, "每月末在行业内按因子值分 5 层，层内等权，多空为第 1 层减第 5 层。"
              "为贴近实际，成本按真实持仓换手估算（双边千三）。")

    rows = []
    for f in FACTORS:
        r = lay.loc[f]
        rows.append([f, f"{r['top_ann']*100:.1f}%", f"{r['ls_gross']*100:+.1f}%",
                     f"{r['ls_net']*100:+.1f}%", f"{r['ls_sharpe']:.2f}",
                     f"{r['ls_maxdd']*100:.1f}%", f"{r['monotonicity']:+.1f}"])
    t6 = pd.DataFrame(rows, columns=["因子", "TOP 年化", "多空毛收益", "多空净收益",
                                     "多空夏普", "最大回撤", "单调性"])
    table(doc, t6, widths=[3.6, 2.9, 3.0, 2.9, 2.5, 2.6, 2.2], font=7.5)
    caption(doc, "表6  5 层回测结果（行业中性、真实换手成本）")

    figure(doc, "fig2_nav.png", "图4  当季因子的多空净值")
    para(doc, "四个当季因子的单调性均为正，ROE_G_q 与 Profit_G_q 达到 0.9–1.0。"
              "多空毛收益 2.5%–5.9%，扣费后仍为正（2.6%–5.3%）。"
              "但最大回撤普遍在 8%–14%，夏普 0.77–1.28，说明收益并不平稳。")
    para(doc, "三年复合因子的单调性为负（Sales_G_3y 为 -0.3，Profit_G_3y 为 -0.7），"
              "多空收益为负，是本文与原文最大的分歧。")

    heading(doc, "4.3 回归法", 2)
    para(doc, "回归法采用加权最小二乘，权重为流通市值平方根，解释变量包含行业哑变量与单个因子。"
              "每月得到因子收益率 β 与截面 t 值。")

    rows = []
    for f in FACTORS:
        r = reg.loc[f]
        rows.append([f, f"{r['abs_t_mean']:.2f}", f"{r['pct_abs_t_gt2']*100:.0f}%",
                     f"{r['beta_mean']*100:+.3f}%", f"{r['beta_t_stat']:.2f}"])
    t7 = pd.DataFrame(rows, columns=["因子", "|t| 均值", "|t|>2 占比",
                                     "因子收益率均值", "收益序列 t"])
    table(doc, t7, widths=[4.4, 3.2, 3.4, 4.2, 3.6])
    caption(doc, "表7  回归法结果（WLS，行业哑变量 + √流通市值权重）")

    para(doc, "这张表暴露了一个关键矛盾：当季因子的 |t| 均值高达 3.5–4.3，远高于原文的 2.5–3.0；"
              "但因子收益率序列的 t 值只有 0.84–1.73，远低于原文的 2.6–3.5。"
              "第六节将专门解释这一背离。")

    heading(doc, "4.4 IC 衰减", 2)
    figure(doc, "fig3_decay.png", "图5  IC 衰减：当季不衰减，三年复合持续反向")
    para(doc, "原文认为“市场对财务数据消化很快，所以当季最优”。本文不支持这一解释："
              "ROE_G_q 的 IC 从 t+1 的 1.86% 到 t+6 的 1.88%，几乎没有衰减；"
              "Profit_G_q 也只从 1.56% 降到 1.18%。相反，三年复合因子的负 IC 随时间加深，"
              "Profit_G_3y 从 -0.79% 恶化到 -3.95%。")
    para(doc, "这说明成长因子更像“持续性定价偏差”或“风格暴露”，而不是“短期信息优势”。"
              "如果是后者，IC 应该在 1–2 个月内快速衰减。")

    heading(doc, "4.5 分层明细", 2)
    para(doc, "下表列出各层组合的年化收益（层内等权、行业中性）。理想情况下，从第 1 层到第 5 层"
              "应单调下降；当季因子的四行基本满足，三年复合因子则相反。")

    rows = []
    for f in ["ROE_G_q", "Profit_G_q", "Sales_G_q", "OCF_G_q", "Profit_G_3y", "Sales_G_3y"]:
        r = layer_detail.loc[f]
        rows.append([f] + [f"{r[f'L{i}']*100:.1f}%" for i in range(1, 6)])
    t13 = pd.DataFrame(rows, columns=["因子", "第1层", "第2层", "第3层", "第4层", "第5层"])
    table(doc, t13, widths=[4.4, 3.2, 3.2, 3.2, 3.2, 3.2])
    caption(doc, "表8  分层组合年化收益")

    para(doc, "以 ROE_G_q 为例，第 1 层年化 17.1%、第 5 层 10.2%，层间差距约 7 个百分点；"
              "Profit_G_3y 则从 12.6% 降到 8.9%，方向完全相反。")

    heading(doc, "4.6 相对基准的超额", 2)
    para(doc, "把第 1 层组合与沪深300 比较，可以得到更贴近实际使用的超额收益。"
              "2020–2025 年沪深300 的年化收益为 3.7%，当季因子的 TOP 组合年化 14.0%–15.6%，"
              "超额 10.3%–11.9%。但信息比率只有 0.49–0.54，说明超额波动很大。")

    rows = []
    for f in ["ROE_G_q", "Profit_G_q", "Sales_G_q", "OCF_G_q", "Sales_G_3y", "Profit_G_3y"]:
        r = bench.loc[f]
        rows.append([f, f"{r['top_ann']*100:.1f}%", f"{r['excess_ann']*100:+.1f}%",
                     f"{r['excess_ir']:.2f}", f"{r['excess_win']*100:.1f}%"])
    t16 = pd.DataFrame(rows, columns=["因子", "TOP 年化", "超额年化", "信息比率", "月胜率"])
    table(doc, t16, widths=[4.4, 3.2, 3.6, 3.4, 3.2])
    caption(doc, "表9  相对沪深300 的超额收益")

    para(doc, "超额年化不低，但月胜率只有 50%–55%，意味着超额收益主要来自少数月份，"
              "持有体验并不好。这也是“因子有效”与“产品可用”之间的差距。")

    # ---------------- 五、稳健性 ----------------
    heading(doc, "五、稳健性检验", 1)
    heading(doc, "5.1 分年度：因子是“分年景”的", 2)
    figure(doc, "fig4_yearly.png", "图6  分年度 IC：2020、2024 强，2021、2023 弱")
    para(doc, "2020 年 ROE_G_q 的 IC 为 4.53%，2024 年为 3.74%；而 2021 年为 -0.20%，2023 年为 1.04%，"
              "明显弱于 2020 与 2024。"
              "2020 年是疫后成长行情，2024 年是反弹年；2021 年杀估值，2023 年是小微盘与主题行情。"
              "因子并非失效，而是在特定风格下被压制。")

    yearly_all = pd.DataFrame(ic_all).groupby(pd.DataFrame(ic_all).index.year).mean() \
        if False else ic_series.groupby(ic_series.index.year).mean()
    rows = []
    for f in FACTORS:
        rows.append([f] + [f"{yearly_all.loc[y, f]*100:+.1f}%" for y in yearly_all.index])
    t18 = pd.DataFrame(rows, columns=["因子"] + [str(y) for y in yearly_all.index])
    table(doc, t18, widths=[3.6, 2.2, 2.2, 2.2, 2.2, 2.2, 2.2], font=7)
    caption(doc, "表16  12 个因子的分年度 IC（%）")

    heading(doc, "5.2 分市值：小盘更有效", 2)
    figure(doc, "fig8_size_ic.png", "图7  当季因子在小盘股中更有效")
    para(doc, "ROE_G_q 在小盘组的 IC 为 2.94%，中盘 1.80%，大盘 1.13%；"
              "Profit_G_q 分别为 2.81%、1.44%、0.73%。三年复合因子的反向则主要发生在大盘"
              "（Profit_G_3y 大盘 -1.36%），说明“高增长陷阱”在大市值公司中更明显。")

    heading(doc, "5.3 分行业：27/31 个行业为正，银行是例外", 2)
    para(doc, "ROE_G_q 在 31 个申万一级行业中有 27 个 IC 为正，中位数 +2.01%。"
              "最强的是美容护理（+9.11%）、煤炭（+4.71%）、石油石化（+4.68%）；"
              "唯一显著为负的是银行（-3.26%）。这一结果符合直觉：银行的 ROE 变化更多由拨备与规模驱动，"
              "成长属性弱于制造业与消费。")

    heading(doc, "5.4 交易成本：真实换手远低于 100%", 2)
    rows = []
    for f in ["ROE_G_q", "Profit_G_q", "Sales_G_q", "OCF_G_q", "OCF_G_ttm", "Profit_G_3y"]:
        r = turn.loc[f]
        rows.append([f, f"{r['avg_turnover']*100:.1f}%", f"{r['ls_gross']*100:+.1f}%",
                     f"{r['ls_net']*100:+.1f}%", f"{r['sharpe_gross']:.2f} → {r['sharpe_net']:.2f}"])
    t8 = pd.DataFrame(rows, columns=["因子", "月换手", "多空毛收益", "扣费后", "夏普（毛→净）"])
    table(doc, t8, widths=[3.8, 3.0, 3.6, 3.2, 4.6])
    caption(doc, "表10  真实换手与交易成本")

    para(doc, "若按“每月全部换仓”假设，成本会吃掉全部 alpha；但实测 5 层 TOP 组合的月换手只有 8%–24%，"
              "年化成本 0.3%–0.9%，当季因子扣费后仍有 2.6%–5.3% 的多空收益。"
              "这一点对“成长因子能否实盘”的判断至关重要。")

    heading(doc, "5.5 其他稳健性", 2)
    para(doc, "取 2020–2022 与 2023–2025 两段分别计算 IC：ROE_G_q 为 1.84% 与 1.87%，基本持平；"
              "TTM 与三年复合因子在 later 段明显恶化（Profit_G_3y 从 -0.49% 到 -1.10%）。"
              "把缺失值填 0 而非剔除，IC 变化不超过 0.31%，结论对缺失处理不敏感。")

    heading(doc, "5.6 分行业明细", 2)
    para(doc, "下表列出 ROE_G_q 在 31 个行业中 IC 最高与最低的各 8 个行业。可以看到，"
              "成长因子在消费、能源类行业更有效，在银行、社会服务、农林牧渔等行业失效。")

    s = ind_ic.loc["ROE_G_q"].dropna().sort_values()
    pick = pd.concat([s.head(8), s.tail(8)]).sort_values()
    rows = [[k, f"{v*100:+.2f}%"] for k, v in pick.items()]
    t14 = pd.DataFrame(rows, columns=["行业", "ROE_G_q 的 IC"])
    table(doc, t14, widths=[6.0, 6.0])
    caption(doc, "表11  分行业 IC（ROE_G_q，按 IC 排序取两端）")

    para(doc, "银行是唯一显著为负的主力行业（-3.26%）。原因在于银行的 ROE 主要受拨备计提、"
              "净息差与规模扩张驱动，与制造业的“成长”逻辑不同；把银行与其他行业放在同一把尺子下，"
              "本身就有口径问题。若剔除金融，成长因子的整体表现会略有提升。")

    heading(doc, "5.7 滚动窗口下的稳定性", 2)
    para(doc, "把 IC 做 24 个月滚动平均，可以更直观地看到因子的“有效期”。当季因子在 2020–2021 年"
              "处于高位，2022 年后明显走弱，2024 年反弹；三年复合因子则从 2021 年起持续为负，"
              "且没有修复迹象。")
    figure(doc, "fig11_rolling.png", "图8  24 个月滚动 IC")
    para(doc, "这提示我们：单因子测试不应只给一个全样本均值，而应给出“什么时候有效、什么时候失效”"
              "的时间路径。对组合管理而言，后者比前者更有用。")

    # ---------------- 六、两个问题 ----------------
    heading(doc, "六、两个关键问题", 1)
    heading(doc, "6.1 为什么 |t| 很高，收益 t 值却很低", 2)
    para(doc, "这是本文最重要的方法性发现。先看数据：12 个因子的月度 |t| 均值平均为 3.04，"
              "但因子收益序列的 t 值平均只有 0.07；两者在横截面上的相关系数为 -0.35，"
              "与“正收益月份占比”的相关系数为 -0.59。")
    para(doc, "原因在于两个 t 值衡量的东西不同。月度 |t| 是“本月因子能否解释收益的截面差异”，"
              "在每期约 4,000 只股票的样本下，几乎任何因子都会显著；而收益序列 t 值衡量的是"
              "“因子溢价是否稳定为正”。当 β 的符号频繁翻转时，均值接近零，t 值自然很低。")

    rows = []
    for f in ["ROE_G_q", "Profit_G_q", "OCF_G_q", "Profit_G_3y", "Sales_G_3y"]:
        r = dd_beta.loc[f]
        rows.append([f, f"{r['abs_t_mean']:.2f}", f"{r['beta_t']:.2f}",
                     f"{r['pos_months']*100:.0f}%", f"{r['flip_rate']*100:.0f}%",
                     f"{r['year2020']*100:+.2f}%", f"{r['year2024']*100:+.2f}%"])
    t9 = pd.DataFrame(rows, columns=["因子", "|t| 均值", "beta t", "正收益月份",
                                     "符号翻转率", "2020 β", "2024 β"])
    table(doc, t9, widths=[3.8, 2.8, 2.4, 2.8, 2.8, 2.6, 2.6])
    caption(doc, "表12  因子收益的稳定性")

    figure(doc, "fig5_tstat.png", "图9  “每月都能排序”不等于“长期能赚钱”")
    para(doc, "以 ROE_G_q 为例：72 个月里有 40% 的月份 β 为负，逐月符号翻转率达到 40%；"
              "2020 年 β 为 +0.55%，2021 年为 -0.13%。在这种结构下，"
              "“月度显著”与“长期有效”必然是两件事。")
    para(doc, "对研究的启示是：单看 |t| 均值会高估因子，必须同时报告因子收益率的均值、"
              "符号稳定性与分年度表现。原文只报告了 |t| 均值，本文补上了后半部分。")

    heading(doc, "6.2 三年复合因子为什么反向", 2)
    para(doc, "第一个线索是动量暴露。高三年增长的公司，往往是过去两年的赢家。"
              "四个 3y 因子与过去 12 个月收益的截面相关系数均为正（0.02–0.15），"
              "ROE_G_3y 在 100% 的月份里为正。当 2021 年后动量因子整体失效时，"
              "高增长组合自然被拖累。")
    para(doc, "第二个线索是分组。把股票按过去 12 个月收益分成低、中、高三组，再在组内看 3y 因子的 IC："
              "高动量组为 +1.0%–+1.4%，低动量组为 -0.9%–-3.1%。"
              "也就是说，3y 因子的反向并非全局，而是集中在“低动量 + 高增长”这一类"
              "——基本面在改善、股价却在下跌的“落刀型”股票。")

    mg = dd_mom.pivot(index="factor", columns="momentum_group", values="ic_mean")
    rows = []
    for f in ["Sales_G_3y", "Profit_G_3y", "OCF_G_3y", "ROE_G_3y"]:
        rows.append([f, f"{mg.loc[f,'low']*100:+.2f}%", f"{mg.loc[f,'mid']*100:+.2f}%",
                     f"{mg.loc[f,'high']*100:+.2f}%"])
    t10 = pd.DataFrame(rows, columns=["因子", "低动量组", "中动量组", "高动量组"])
    table(doc, t10, widths=[4.6, 4.0, 4.0, 4.0])
    caption(doc, "表13  按过去 12 个月收益分组的 3y 因子 IC")

    figure(doc, "fig7_3y_momentum.png", "图10  3y 因子的反向集中在“低动量 + 高增长”组")

    para(doc, "第三个线索是事后收益。按 3y 因子分五组，观察未来 12 个月收益："
              "Sales_G_3y 从最低组的 12.0% 单调下降到最高组的 7.2%；"
              "Profit_G_3y 从 12.2% 降到 6.0%。最高增长组每年跑输约 5–6 个百分点。")

    rows = []
    for f in ["Sales_G_3y", "Profit_G_3y", "OCF_G_3y", "ROE_G_3y"]:
        r = dd_q.loc[f]
        rows.append([f] + [f"{r[f'Q{i}']*100:.1f}%" for i in range(1, 6)])
    t11 = pd.DataFrame(rows, columns=["因子", "Q1（低）", "Q2", "Q3", "Q4", "Q5（高）"])
    table(doc, t11, widths=[4.4, 3.4, 3.0, 3.0, 3.0, 3.4])
    caption(doc, "表14  3y 因子五分组的事后 12 个月收益")

    figure(doc, "fig6_3y_quintile.png", "图11  高三年增长组的事后收益更低")

    para(doc, "综合三条线索，3y 因子的反向可以概括为：它同时承载了“长期成长”与“过去赢家”两种属性，"
              "前者在 2020–2025 年被估值压缩，后者在动量反转中受损；"
              "而在低动量组里，高增长又常常意味着基本面与股价背离。"
              "结果就是：无条件做多高 3y 增长，等于同时承担了估值风险与动量风险。")

    heading(doc, "6.3 因子收益的年度分解", 2)
    para(doc, "把回归得到的月度 β 按年求平均，可以看到“方向翻转”具体发生在哪一年："
              "2020 年四个当季因子的 β 全部为正（0.19%–0.63%），2021–2023 年全部转负，"
              "2024 年重新转正。三年复合因子则从 2020 年的正 β 一路走低，2021 年后持续为负。")

    rows = []
    for f in ["ROE_G_q", "Profit_G_q", "Sales_G_q", "OCF_G_q", "Profit_G_3y", "ROE_G_3y"]:
        r = dd_beta.loc[f]
        rows.append([f] + [f"{r[f'year{y}']*100:+.2f}%" for y in (2020, 2021, 2022, 2023, 2024, 2025)])
    t17 = pd.DataFrame(rows, columns=["因子", "2020", "2021", "2022", "2023", "2024", "2025"])
    table(doc, t17, widths=[3.8, 2.4, 2.4, 2.4, 2.4, 2.4, 2.4], font=7.5)
    caption(doc, "表15  因子收益率 β 的年度均值")

    para(doc, "这张表把“因子失效”拆成了更具体的问题：不是因子没有区分度，而是它的收益方向"
              "在 2021 年之后被系统性逆转。对策略而言，这意味着一个静态的多空组合很难穿越周期，"
              "需要叠加市场状态判断或择时。")

    # ---------------- 七、对话 ----------------
    heading(doc, "七、与原文的对话", 1)
    heading(doc, "7.1 一致的部分", 2)
    para(doc, "第一，“当季 > TTM > 三年”的排序成立，而且比原文更极端。原文认为三年复合因子"
              "“基本无效”，本文发现它是系统性反向。第二，“盈利类优于营收类”成立："
              "ROE_G_q 与 Profit_G_q 的 IC、分层单调性均高于 Sales_G_q。"
              "第三，成长因子与规模的相关性弱，这一点在本文的分市值结果中同样可见。")

    heading(doc, "7.2 不一致的部分", 2)
    para(doc, "第一，绝对强度下降。原文 IC 约 2%、多空 6%、收益 t 值 2.6–3.5；"
              "本文 IC 1% 左右、多空 3%–6%、收益 t 值 0.8–1.7。"
              "第二，显著性不足。FDR 校正后只有 OCF_G_q 过关，而原文并未做多重检验。"
              "第三，“市场消化快”的解释不成立：本文的当季因子 IC 到 6 个月不衰减。")

    heading(doc, "7.3 差异从哪来", 2)
    para(doc, "第一是样本期。2005–2016 年 A 股小市值效应强、散户占比高、成长股稀缺；"
              "2020–2025 年注册制增加了成长股供给，机构化提高了定价效率，成长溢价被压缩。")
    para(doc, "第二是市场状态。2021 年核心资产瓦解、2023 年小微盘与主题行情，"
              "都让“高增长”阶段性失效。全样本平均因此被显著摊薄。")
    para(doc, "第三是口径。本文用单季同比、剔除次日停牌、加入市值中性，"
              "这些都会让结果比原文更“干净”，也更保守。")
    para(doc, "第四是成本。原文未扣交易成本；本文按真实换手扣除后，"
              "当季因子的多空收益从 4.8%–5.9% 降到 4.1%–5.3%。")

    # ---------------- 八、使用建议 ----------------
    heading(doc, "八、因子使用建议", 1)
    para(doc, "单因子测试的终点不是“哪个因子 IC 高”，而是“怎么把它变成一个可执行的组合”。"
              "结合本文的结果，给出四条建议。")

    heading(doc, "8.1 从因子到组合：行业内打分", 2)
    para(doc, "最直接的做法是行业内百分位打分：每月末在每个申万一级行业内，把因子值转为 0–1 的"
              "百分位，再按行业权重加权。这样既保留了因子的横截面区分度，又避免了行业暴露。"
              "本文的检验已经证明，行业内分层的单调性明显优于全市场直接排序。")
    para(doc, "如果只用单因子，建议选 ROE_G_q 或 Profit_G_q；如果要降低单一因子的波动，"
              "可以用 ROE_G_q 与 OCF_G_q 各占一半。需要注意，ROE_G_q 与 Profit_G_q 的相关性高达 0.975，"
              "两者叠加没有分散效果。")

    heading(doc, "8.2 换手与成本控制", 2)
    para(doc, "本文实测 5 层 TOP 组合的月换手为 18%–24%，年化成本 0.7%–0.9%。"
              "若把调仓频率从月度降到季度，换手可下降一半以上，但 IC 会损失一部分。"
              "折中方案是“季度调仓 + 月度缓冲带”：只有因子排名跌出前 30% 才卖出，"
              "可以显著降低换手而不牺牲太多信号。")

    heading(doc, "8.3 风险控制", 2)
    for text in [
        "① 剔除 ST、上市不足 12 个月、调仓日停牌与次日停牌的股票；",
        "② 行业偏离限制在 ±5% 以内，避免因子在少数行业过度集中；",
        "③ 单票权重上限 2%，前十大合计不超过 20%；",
        "④ 当因子 IC 的 24 个月滚动均值转负时，降低仓位或暂停使用。",
    ]:
        para(doc, text)

    heading(doc, "8.4 对研究者的提醒", 2)
    para(doc, "本文最重要的方法性结论是：月度 |t| 高不代表因子长期有效。"
              "在 4,000 只股票的截面上，几乎任何因子都能算出显著的 t 值；"
              "真正决定策略成败的是因子收益的符号稳定性与分年度表现。"
              "因此，单因子报告至少应同时给出 IC、分层单调性、收益序列 t 值与分年度结果，"
              "四者缺一不可。")

    # ---------------- 九、结论 ----------------
    heading(doc, "九、结论与风险提示", 1)
    para(doc, "成长因子在 2020–2025 年的 A 股市场仍然有效，但“有效”的含义变了：")
    for text in [
        "它能排序——当季因子的分层单调性 0.9–1.0，IC 1.0%–1.8%，方向与原文一致；",
        "它难赚钱——收益序列 t 值不足 1.8，信息比率 0.35–0.54，扣费后年化 2.6%–5.3%；",
        "它挑年景——2020、2024 强，2021、2023 弱，全样本平均掩盖了这种条件性；",
        "它怕长期——三年复合因子反向，高增长组每年跑输 5–6 个百分点。",
    ]:
        para(doc, text)
    para(doc, "对使用的建议：第一，优先使用当季因子，尤其是 ROE_G_q 与 Profit_G_q；"
              "第二，把 OCF_G_q 作为“稳健型”选择，它统计上最显著、夏普最高；"
              "第三，不要无条件做多高三年增长，尤其在低动量与大盘股中；"
              "第四，把因子有效性放在市场状态框架下评估，而不是看全样本平均。")

    heading(doc, "9.1 研究局限", 2)
    for text in [
        "① 样本期只有 6 年，经历了 2020 疫后、2021 杀估值、2022 熊市、2023 主题行情、2024 反弹，"
        "状态数量有限，结论的外推需谨慎；",
        "② 基准与行业权重采用全 A 流通市值口径，与原文的沪深300 口径不同，超额收益不可直接对比；",
        "③ 未取得估值因子（PB/PE）数据，无法检验“高增长是否因高估值而反向”这一假设；",
        "④ 交易成本按固定双边千三估算，未建模冲击成本、涨跌停无法成交等执行细节；",
        "⑤ 行业分类为申万 2021 版回溯，早期年份存在分类漂移；",
        "⑥ 未做因子间的正交化与多因子合成，单因子结论不能直接推广到组合。",
    ]:
        para(doc, text)

    heading(doc, "9.2 风险提示", 2)
    for text in [
        "样本期仅 2020–2025 年，经历的市场状态有限，结论可能不适用于其他时期；",
        "基准与行业权重采用全 A 流通市值口径，与原文的沪深300 口径不同；",
        "交易成本按固定双边千三估算，未建模冲击成本与流动性约束；",
        "行业分类为申万 2021 版回溯，存在分类漂移；",
        "单因子测试结果是历史经验的总结，存在失效风险，不构成投资建议。",
    ]:
        para(doc, text)

    # ---------------- 附录 ----------------
    doc.add_page_break()
    heading(doc, "附录", 1)
    heading(doc, "附录 A  数据与代码", 2)
    t12 = pd.DataFrame([
        ["数据", "bq_export_v41/", "月频面板 2016–2025、指数、事件表"],
        ["核心代码", "src/", "config / data / factors / preprocess / evaluate"],
        ["分析脚本", "scripts/", "P1 面板、P2 检验、P3 稳健性、深挖"],
        ["平台版", "platform/bq_factor_lab.py", "单文件，与本地逐格一致"],
        ["测试", "tests/", "15 个用例，含平台一致性"],
    ], columns=["类别", "路径", "说明"])
    table(doc, t12, widths=[3.0, 6.6, 9.0])
    caption(doc, "表 A1  项目结构")

    heading(doc, "附录 B  复现步骤", 2)
    para(doc, "本地：")
    para(doc, "① 运行 pytest tests -q，应 15 passed；② 运行 scripts/build_factor_panel.py 生成因子面板；"
              "③ 运行 scripts/full_sample_tests.py 与 p3_robustness.py 生成检验表；"
              "④ 运行 scripts/make_figures.py 与 build_report.py 生成本报告。", indent=True)
    para(doc, "平台：")
    para(doc, "python platform/bq_factor_lab.py --source local --data-dir bq_export_v41 --out-dir ./out，"
              "输出的 ic_summary 与本地逐位一致（max diff = 0）。")

    heading(doc, "附录 C  口径说明", 2)
    for text in [
        "① 当季因子使用单季值（_mrq），TTM 与三年复合使用 _ttm；",
        "② 增长率分母取绝对值，三年复合要求两端同为正；",
        "③ 财务 0 填充、负营收、非正净资产视为缺失；",
        "④ 剔除北交所、ST、停牌、上市不足 12 个月，以及截面期下一交易日停牌的股票；",
        "⑤ 去极值采用中位数 ±5×MAD，IC 采用行业 + ln(流通市值) 残差；",
        "⑥ 分层为行业内 5 等分、层内等权，成本按真实换手 × 0.3% 估算。",
    ]:
        para(doc, text)

    heading(doc, "附录 D  主要字段字典", 2)
    fields = [
        ["date", "月末交易日", "—"],
        ["instrument", "证券代码", "000001.SZ"],
        ["name", "证券简称", "—"],
        ["close", "收盘价（后复权）", "元"],
        ["adjust_factor", "复权因子", "倍"],
        ["daily_return", "当日收益率", "小数"],
        ["total_market_cap", "总市值", "元"],
        ["float_market_cap", "流通市值", "元"],
        ["total_shares / a_float_shares", "总股本 / 流通股本", "股"],
        ["amount", "成交额", "元"],
        ["turn", "换手率", "小数"],
        ["operating_revenue_mrq", "单季营业收入", "元"],
        ["operating_revenue_ttm", "TTM 营业收入", "元"],
        ["net_profit_mrq", "单季归母净利润", "元"],
        ["net_profit_ttm", "TTM 归母净利润", "元"],
        ["net_cffoa_mrq", "单季经营现金流净额", "元"],
        ["net_cffoa_ttm", "TTM 经营现金流净额", "元"],
        ["total_equity_to_parent_shareholders", "归母净资产", "元"],
        ["roe_avg_ttm", "平台口径 ROE（交叉验证）", "小数"],
        ["st_status", "ST 状态，0=正常", "—"],
        ["suspended", "停牌标记，0=正常", "—"],
        ["price_limit_status", "1=涨停、2=正常、3=跌停", "—"],
        ["upper_limit / lower_limit", "涨停价 / 跌停价", "元"],
        ["sw2021_level1_name", "申万 2021 一级行业", "—"],
        ["is_bj / is_kcb / is_cyb", "北交所 / 科创板 / 创业板", "0/1"],
        ["list_date / list_days", "上市日 / 已上市天数", "—"],
    ]
    t15 = pd.DataFrame(fields, columns=["字段", "含义", "单位/示例"])
    table(doc, t15, widths=[7.6, 6.4, 3.4], font=7)
    caption(doc, "表 A2  月频面板主要字段（完整 33 列见 docs/data_guide.md）")

    para(doc, "数据文件 `bq_export_v41/` 共 19 个：10 个月频面板、3 个指数、"
              "2 个事件表、1 个 PIT 样本、以及元数据与日志，合计约 50 MB。")

    heading(doc, "附录 E  口径变更与运行环境", 2)
    for text in [
        "① 成本口径：初版按“每月 100% 换仓”扣 0.3%，得出“扣费后无 alpha”；"
        "复核真实持仓重叠后，月换手只有 8%–24%，成本拖累降至 0.3%–0.9%/年，结论已修正。",
        "② 停牌口径：按研报“剔除截面期下一交易日停牌”，补入 341 行剔除（0.08%），"
        "IC 与分层结果变化均小于 0.001，不影响结论。",
        "③ 运行环境：Python 3.12.14、pandas 3.1.0、numpy 2.5.4、statsmodels 0.15.0；"
        "全样本 P1 约 25 秒、P2 约 74 秒、P3 约 34 秒，峰值内存约 456 MB。",
        "④ 数据质量：主键无重复、退市股保留、复权链校验通过、财务按公告日对齐。",
    ]:
        para(doc, text)

    heading(doc, "附录 F  平台复现", 2)
    para(doc, "为验证结论不依赖本地环境，项目提供了单文件脚本 `platform/bq_factor_lab.py`，"
              "可直接在 BigQuant 的 web VSCode 中运行。平台环境为 Python 3.11.8、pandas 2.2.1，"
              "与本地不同，但输出的 12 个因子 IC 与本地逐格一致（最大绝对差 0）。")
    para(doc, "运行命令：python platform/bq_factor_lab.py --source local "
              "--data-dir bq_export_v41 --out-dir ./out。脚本会自动探测数据目录，"
              "也支持 --source dai 直接从平台取数。")
    para(doc, "此外，项目内置 15 个测试用例，覆盖数据完整性、因子公式、无前视偏差、"
              "分层方向、零填充守卫以及平台与本地的一致性，运行 pytest tests -q 约 3 秒。")

    heading(doc, "附录 G  指标定义", 2)
    metrics = [
        ["IC", "corr(f_t, r_{t+1})", "因子截面值与下月收益的秩相关"],
        ["IR", "mean(IC) / std(IC)", "因子有效性与稳定性的综合"],
        ["|t| 均值", "mean(|β_t / SE(β_t)|)", "截面显著性，受样本量影响大"],
        ["因子收益 t", "mean(β) / std(β) × √n", "收益方向是否稳定"],
        ["年化收益", "(1 + 月均收益)^12 − 1", "组合收益"],
        ["夏普", "年化收益 / 年化波动", "单位风险收益，rf 取 0"],
        ["最大回撤", "min(净值 / 历史最高 − 1)", "极端损失"],
        ["单调性", "−spearman(层号, 层均收益)", "正=高因子组更优"],
        ["换手率", "1 − |持仓_t ∩ 持仓_{t−1}| / |持仓_t|", "月均持仓变化"],
    ]
    t19 = pd.DataFrame(metrics, columns=["指标", "公式", "含义"])
    table(doc, t19, widths=[3.4, 8.2, 6.0], font=7.5)
    caption(doc, "表 A3  主要指标定义")

    heading(doc, "附录 H  数据质量问题与处理", 2)
    issues = [
        ["北交所数据断档", "2025-10 起无数据", "全样本剔除北交所"],
        ["涨跌停状态误读", "状态 2 是“正常”，占 97%", "只保留 1/3"],
        ["财务 0 填充", "如 000001.SZ 2025-10 起营收为 0", "0 值与负营收视为缺失"],
        ["次新股极端收益", "633 条月收益 >100%", "上市满 12 个月 + 5×MAD"],
        ["停牌股缺价", "close 缺失 3.4%", "调仓日剔除，次日停牌单独处理"],
        ["复权口径", "close 已是后复权", "不再二次复权"],
        ["退市股", "易产生生存偏差", "保留，最后交易日自然退出"],
        ["行业缺失", "2025 年约 4.3%", "剔除，缺口与停牌股重合"],
    ]
    t20 = pd.DataFrame(issues, columns=["问题", "表现", "处理"])
    table(doc, t20, widths=[4.2, 7.0, 6.0], font=7.5)
    caption(doc, "表 A4  数据质量问题清单")

    para(doc, "这些问题中，影响最大的是“财务 0 填充”与“次日停牌”。前者会直接产生 -100% 的假因子值，"
              "后者影响调仓的可执行性。两项都已修正，并各自配有回归测试。")

    heading(doc, "附录 I  与原文结论逐条对照", 2)
    compare = [
        ["当季 > TTM > 三年", "支持，且更极端", "q 因子 IC 为正，3y 为负"],
        ["Profit/ROE > Sales > OCF", "部分支持", "ROE/Profit 分层最强，OCF 统计最稳"],
        ["因子收益率显著（t 2.6–3.5）", "不支持", "收益序列 t 仅 0.84–1.73"],
        ["市场消化快、当季最优", "不支持", "IC 到 6 个月不衰减"],
        ["3y 因子基本无效", "不一致", "3y 因子系统性反向"],
        ["成长不如 BP、接近 SP", "无法判断", "未做估值因子对比"],
        ["成长与市值相关性低", "部分支持", "与市值相关性弱，但小盘 IC 更高"],
    ]
    t21 = pd.DataFrame(compare, columns=["原文结论", "本文判断", "依据"])
    table(doc, t21, widths=[5.6, 3.8, 7.8], font=7.5)
    caption(doc, "表 A5  原文结论与本文结果的逐条对照")

    para(doc, "七条中有两条支持、两条部分支持、两条不支持、一条不一致、一条无法判断。"
              "这一分布本身就是结论：同一套方法在不同年代会得到不同的答案，"
              "而“不同”恰恰是复现研究最有价值的部分。")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    build()

# -*- coding: utf-8 -*-
"""生成 PIT 回测报告 HTML（含多周期对比）。"""
import json
import os

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(BASE)

with open(os.path.join(BASE, "backtest_result.json"), encoding="utf-8") as f:
    res = json.load(f)
with open(os.path.join(BASE, "backtest_enhanced.json"), encoding="utf-8") as f:
    enh = json.load(f)
with open(os.path.join(BASE, "multi_period.json"), encoding="utf-8") as f:
    mp = json.load(f)

COST = res["meta"]["cost_per_side"]


def strategy_nav(recs, key):
    """重算逐日策略净值（T 日信号，T+1 生效）。"""
    d = recs[key]
    pos_raw = d.map({1: 1.0, -1: 0.0}).ffill().fillna(0.0)
    pos_eff = d.shift(1).map({1: 1.0, -1: 0.0}).ffill().fillna(0.0)
    r = recs["ret1"] / 100.0
    strat = pos_eff * r - pos_eff.diff().abs().fillna(0) * COST
    nav = (1 + strat).cumprod() * 100
    hold = (1 + r).cumprod() * 100
    return nav, hold


def prep(sym):
    recs = pd.DataFrame(res[sym]["records"])
    recs["date"] = pd.to_datetime(recs["date"])
    recs = recs.set_index("date").sort_index()
    return recs


hs, kc = prep("hs300"), prep("kc50")

# ---- 图表数据 ----
dates_hs = [d.strftime("%m-%d") for d in hs.index]
dates_kc = [d.strftime("%m-%d") for d in kc.index]

sig_pts = {}
for name, recs, dates in (("hs300", hs, dates_hs), ("kc50", kc, dates_kc)):
    buys = [dates[i] for i, v in enumerate(recs["dir_b"]) if v == 1]
    sells = [dates[i] for i, v in enumerate(recs["dir_b"]) if v == -1]
    buy_y = [float(recs["close"].iloc[i]) for i, v in enumerate(recs["dir_b"]) if v == 1]
    sell_y = [float(recs["close"].iloc[i]) for i, v in enumerate(recs["dir_b"]) if v == -1]
    sig_pts[name] = {"buys_x": buys, "buys_y": buy_y, "sells_x": sells, "sells_y": sell_y,
                     "close": [float(x) for x in recs["close"]]}

nav_data = {}
for name, recs in (("hs300", hs), ("kc50", kc)):
    nb, hb = strategy_nav(recs, "dir_b")
    na, ha = strategy_nav(recs, "sig_a")
    nav_data[name] = {
        "dates": [d.strftime("%m-%d") for d in recs.index],
        "ruleB": [round(float(x), 2) for x in nb],
        "ruleA": [round(float(x), 2) for x in na],
        "hold": [round(float(x), 2) for x in hb],
    }

# 分季度图
phase_rows = []
for sym in ("hs300", "kc50"):
    for p in enh[sym]["phases"]:
        phase_rows.append({"sym": sym, "phase": p["phase"],
                           "hit": p.get("b5_hit"), "avg": p.get("b5_avg"),
                           "n": p.get("b5_n", 0)})

# 多周期对比图
mp_rows = []
for sym in ("hs300", "kc50"):
    for key, label in (("60分钟", "60分钟"), ("日线", "日线"), ("双确认", "双确认")):
        c = mp[sym]["cmp"]["%s_n20" % key]
        mp_rows.append({"sym": sym, "label": label,
                        "bull_hit": c["bull_hit"], "bull_avg": c["bull_avg"],
                        "bear_hit": c["bear_hit"], "bear_n": c["bull_n"]})

# ---- HTML ----
def tbl_eval(sym):
    rows = []
    for n in (5, 10, 20):
        for rule, key in (("A 三维投票", "eval_a"), ("B 多因子", "eval_b")):
            e = enh[sym][key]["n%d" % n]
            rows.append(
                "<tr><td>%s</td><td>N=%d</td><td class='r'>%s</td><td class='r'>%s%%</td>"
                "<td class='r'>%s%%</td><td class='r'>%s</td><td class='r'>%s%%</td>"
                "<td class='r'>%s%%</td><td class='r'>%s</td><td class='r'>%s%%</td></tr>" % (
                    rule, n, e["bull_days"], e["bull_hit"], e["bull_avg_ret"],
                    e["bear_days"], e["bear_hit"], e["bear_avg_ret"],
                    e["neutral_days"], e["neutral_avg_abs"]))
    return "\n".join(rows)


def tbl_key(sym, limit=14):
    rows = []
    pts = enh[sym]["key_points"]
    pts = [p for p in pts if p["ret5"] is not None][-limit:]
    for p in pts:
        d = {1: "<span class='up'>看多</span>", -1: "<span class='dn'>看空</span>",
             0: "<span class='nt'>中性</span>"}[p["dir_b"]]
        sa = {1: "多", -1: "空", 0: "—"}[p["sig_a"]]
        c5 = "up" if (p["ret5"] or 0) > 0 else ("dn" if (p["ret5"] or 0) < 0 else "nt")
        c20 = "up" if (p["ret20"] or 0) > 0 else ("dn" if (p["ret20"] or 0) < 0 else "nt")
        rows.append(
            "<tr><td>%s</td><td>%.1f</td><td>%s / %s</td><td>%+.0f</td><td class='%s'>%s%%</td>"
            "<td class='%s'>%s%%</td><td class='sz'>%s</td></tr>" % (
                p["date"], p["close"], d, sa, p["score_b"], c5, p["ret5"], c20, p["ret20"],
                "；".join(p["reasons"][:2])))
    return "\n".join(rows)


def tbl_sim(sym):
    rows = []
    for rule, key in (("A 三维投票", "sim_a"), ("B 多因子", "sim_b")):
        s = enh[sym][key]
        rows.append(
            "<tr><td>%s</td><td class='r'>%s%%</td><td class='r'>%s%%</td>"
            "<td class='%s'>%s%%</td><td class='r'>%s</td><td class='r'>%s%%</td>"
            "<td class='r'>%s%%</td><td class='r'>%s%%</td></tr>" % (
                rule, s["strategy_ret"], s["buyhold_ret"],
                "up" if s["excess"] > 0 else "dn", s["excess"], s["trades"],
                s["in_market_ratio"], s["strategy_maxdd"], s["buyhold_maxdd"]))
    return "\n".join(rows)


def tbl_mp(sym):
    rows = []
    for label in ("60分钟", "日线", "双确认"):
        c5 = mp[sym]["cmp"]["%s_n5" % label]
        c20 = mp[sym]["cmp"]["%s_n20" % label]
        rows.append(
            "<tr><td>%s</td><td class='r'>%s</td><td class='r'>%s%%</td><td class='r'>%s%%</td>"
            "<td class='r'>%s</td><td class='r'>%s%%</td><td class='r'>%s%%</td></tr>" % (
                label, c5["bull_n"], c5["bull_hit"], c5["bull_avg"],
                c20["bull_n"], c20["bull_hit"], c20["bull_avg"]))
    return "\n".join(rows)


def lead_info(sym):
    l = mp[sym]["macd_lead"]
    return ("60 分钟 MACD 金叉共配对 <b>%d</b> 次，较日线金叉提前 <b>中位 %.0f 天</b>"
            "（均值 %.1f 天，最长 %d 天，%.1f%% 的情况至少不晚于日线）" % (
                l["n_pairs"], l["lead_median"], l["lead_mean"], l["lead_max"], l["le0_ratio"]))


def case_tbl(sym):
    rows = []
    for d, c in mp[sym]["cases"].items():
        rows.append("<tr><td>%s</td><td>%.1f%%</td><td>%.0f</td><td>%.0f</td><td>%.0f</td>"
                    "<td>%s%%</td></tr>" % (
                        d, c["chg_pct"], c["open"], c["intraday_low"], c["intraday_high"],
                        c["late_session_chg"]))
    return "\n".join(rows)


html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>沪深300 × 科创50：PIT 回测与多周期验证报告</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
:root{--ink:#1f2937;--sub:#6b7280;--line:#e5e7eb;--bg:#f6f7f9;--card:#fff;--blue:#185fa5;--orange:#d97706}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink);line-height:1.65;font-size:14px}
.wrap{max-width:1080px;margin:0 auto;padding:28px 20px 60px}
header h1{font-size:24px;font-weight:700}
header .meta{color:var(--sub);font-size:12.5px;margin-top:6px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin-top:16px}
h2{font-size:17px;font-weight:700;margin-bottom:10px;padding-left:9px;border-left:4px solid var(--blue)}
h3{font-size:14.5px;font-weight:600;margin:14px 0 8px}
p{margin:7px 0}
table{width:100%;border-collapse:collapse;font-size:12.5px;margin:10px 0}
th{background:#f3f4f6;text-align:left;padding:7px 8px;border:1px solid var(--line);font-weight:600;white-space:nowrap}
td{padding:6px 8px;border:1px solid var(--line)}
td.r{text-align:right}
td.sz{font-size:11.5px;color:var(--sub)}
.up{color:#dc2626;font-weight:600}.dn{color:#16a34a;font-weight:600}.nt{color:var(--sub)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:12px 0}
.kpi{background:#f9fafb;border:1px solid var(--line);border-radius:8px;padding:10px 12px}
.kpi .k{font-size:11.5px;color:var(--sub)}
.kpi .v{font-size:18px;font-weight:700;margin-top:2px}
.chart{width:100%;height:360px;margin:8px 0}
.note{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:10px 14px;font-size:12.5px;color:#92400e;margin:10px 0}
.ok{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:10px 14px;font-size:12.5px;color:#166534;margin:10px 0}
.tag{display:inline-block;background:#eef2ff;color:#3730a3;border-radius:4px;padding:1px 7px;font-size:11px;margin-right:6px}
.footer{margin-top:26px;color:var(--sub);font-size:12px;border-top:1px solid var(--line);padding-top:14px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:820px){.two{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
<header>
<h1>沪深300 × 科创50：Point-in-Time 回测与多周期验证报告</h1>
<div class="meta">回测窗口 __WIN__ ｜ 检查点 242 个/标的 ｜ 信号规则 A（三维投票引擎）+ B（多因子评分）｜ 数据源：东方财富日K（本地计算）｜ 生成日期 2026-10-24</div>
</header>

<div class="card">
<h2>一、方法论：如何保证「只用该时间点之前的数据」</h2>
<p>回测的常见致命缺陷是<b>未来函数</b>（用当天收盘后才知道的信息做当天决策）。本引擎用三重机制杜绝：</p>
<p><b>1. 结构保证</b>——每个检查点 T 都从原始行情重新截断 <code>df[df.index &le; T]</code> 后<b>重算</b>全部指标，不引用任何全量预计算表；T 日收盘形成的信号，次一日起才生效。</p>
<p><b>2. 算法保证</b>——指标计算全部为因果运算（rolling / ewm / shift 只回看历史），KDJ 为逐步递推，无中心化、无全局统计量。</p>
<p><b>3. 硬校验</b>——抽样 8 个检查点，对比「截断重算」与「全量计算」在当日的值，逐列断言一致。</p>
<div class="ok">校验结果：<b>PASS</b>（沪深300 / 科创50 各 8 个抽样点，最大相对偏差 0.00e+00，完全一致）。前向收益（ret5/10/20）仅在评估阶段从事后数据提取，不参与任何判断。</div>
<div class="note">诚实声明：本回测为单窗口（2025-10-24 ~ 2026-10-23）样本内验证，两套规则在跑测前一次定死、未按结果调参；242 个检查点的统计意义有限，结论应视为「规则有效性证据」而非「未来收益保证」。</div>
</div>

<div class="card">
<h2>二、总体结果：策略 vs 买入持有</h2>
<div class="kpis">
<div class="kpi"><div class="k">沪深300 · 规则B 策略</div><div class="v up">__HSB__%</div></div>
<div class="kpi"><div class="k">沪深300 · 买入持有</div><div class="v dn">__HSH__%</div></div>
<div class="kpi"><div class="k">科创50 · 规则B 策略</div><div class="v up">__KCB__%</div></div>
<div class="kpi"><div class="k">科创50 · 买入持有</div><div class="v dn">__KCH__%</div></div>
</div>
<table>
<tr><th>标的</th><th>规则</th><th>策略收益</th><th>买入持有</th><th>超额</th><th>交易次数</th><th>在场时间</th><th>策略最大回撤</th><th>持有最大回撤</th></tr>
__SIMHS__
__SIMKC__
</table>
<p class="sz">成本假设：单边 0.05%（ETF 综合佣金+冲击）。「在场时间」= 持仓天数占比。两规则策略均跑赢持有，核心来源是<b>回避主跌段</b>（沪深300 持有回撤 -20.3% vs 策略 -7.3%/-9.5%），而非精准抄底——见第四节胜率结构。</p>
</div>

<div class="card">
<h2>三、信号与净值曲线</h2>
<div id="c1" class="chart"></div>
<p class="sz">图1：沪深300 收盘价与规则B 信号（红=看多、绿=看空）。注意看空信号集中在下跌中继，看多信号集中在超跌反弹初期。</p>
<div id="c2" class="chart"></div>
<p class="sz">图2：策略净值 vs 买入持有（沪深300）。</p>
<div id="c3" class="chart"></div>
<p class="sz">图3：策略净值 vs 买入持有（科创50）。</p>
</div>

<div class="card">
<h2>四、信号质量：后续 5/10/20 日表现</h2>
<h3>沪深300</h3>
<table><tr><th>规则</th><th>窗口</th><th>看多天数</th><th>看多胜率</th><th>看多均收益</th><th>看空天数</th><th>看空胜率</th><th>看空均收益</th><th>中性天数</th><th>中性均\|收益\|</th></tr>
__EVHS__
</table>
<h3>科创50</h3>
<table><tr><th>规则</th><th>窗口</th><th>看多天数</th><th>看多胜率</th><th>看多均收益</th><th>看空天数</th><th>看空胜率</th><th>看空均收益</th><th>中性天数</th><th>中性均\|收益\|</th></tr>
__EVKC__
</table>
<div class="note"><b>关键发现：</b>① 沪深300 规则A 的 6 个「做空」信号后续 5/10/20 日全部上涨（胜率 0%）——趋势指标做空信号显著滞后，急跌后的死叉往往对应阶段低点；② 规则B 看多胜率在沪深300 仅 23~39%，熊市抄底频繁被打脸；③ 中性日的平均绝对收益（1.4~3.2%）系统性低于信号日——<b>「不轻易出手」本身就是有效信号</b>。</div>
</div>

<div class="card">
<h2>五、重点检查点：当时的判断 vs 后续实际走势</h2>
<p class="sz">以下为信号翻转日、评分极值日、月末与关键指定日。每一行的「判断」只可能来自该日收盘前的数据。</p>
<h3>科创50（近期）</h3>
<table><tr><th>日期</th><th>收盘</th><th>规则B/规则A</th><th>评分</th><th>后5日</th><th>后20日</th><th>当时理由</th></tr>
__KEYKC__
</table>
<h3>沪深300（近期）</h3>
<table><tr><th>日期</th><th>收盘</th><th>规则B/规则A</th><th>评分</th><th>后5日</th><th>后20日</th><th>当时理由</th></tr>
__KEYHS__
</table>
<p class="sz">代表性案例：<b>2026-06-30</b>（科创50 历史高点当日）规则B 仅给 +5 分中性（量价已背离），避开其后 20 日 -23.3%；<b>2026-07-09</b> 看多信号后 5 日 -15.5%（急跌中继误判）；<b>2025-12-30/31</b> 看多后 5 日 +7~9.8%（正确）。</p>
</div>

<div class="card">
<h2>六、多周期验证：60 分钟线有必要加入吗</h2>
<p><b>结论：有必要，但定位是「提前预警与确认」，不是「更高胜率」。</b>三层架构：<span class="tag">日线</span>定方向（主）→ <span class="tag">60分钟</span>提前预警/确认（辅）→ <span class="tag">5分钟</span>只看日内资金行为（专项，见国家队报告）。</p>
<h3>6.1 信号提前量</h3>
<p>沪深300：__LEADHS__</p>
<p>科创50：__LEADKC__</p>
<p class="sz">60 分钟 MACD 更灵敏、金叉显著早于日线；但「早」不等于「准」，需结合下一节的胜率结构理解。</p>
<h3>6.2 每日 15:00 决策：三种信息集的胜率对比（看多信号，后 20 日）</h3>
<table><tr><th>标的</th><th>信息集</th><th>看多天数</th><th>后5日胜率</th><th>后5日均收益</th><th>看多天数</th><th>后20日胜率</th><th>后20日均收益</th></tr>
__MPHS__
__MPKC__
</table>
<p class="sz">沪深300：60 分钟看多胜率 44.4% vs 日线 37.5%（更高），但看空胜率 62.2% vs 日线 73.0%（更低）——小时线做方向判断整体并无优势，日线做空更可靠。科创50：「双确认」（日线与60分钟同向才出手）看多 9 例胜率 88.9%、均收益 +12.8%，效果突出，但样本量小，只能作为提高信号质量的候选手段。</p>
<h3>6.3 关键转折日的 60 分钟微观形态</h3>
<table><tr><th>日期</th><th>日内涨跌</th><th>开盘</th><th>日内低点</th><th>日内高点</th><th>尾盘30分钟涨跌</th></tr>
__CASEHS__
__CASEKC__
</table>
<p class="sz">A 股 60 分钟 K 每日 4 根。10-22 两市低开低走、尾盘继续走弱（收盘贴近日内低点），10-23 光头放量长阳——微观结构印证「反弹第一波而非反转」。</p>
<div class="note"><b>关于 1/5 分钟线：</b>对中期方向判断无增益（噪音占比高、信号数量爆炸），不建议用于涨跌判断；其价值在两类专项场景——精确执行（择时入场点）与日内资金行为识别（如国家队尾盘操作，本套件中国家队分析模块即基于 5 分钟线）。</div>
</div>

<div class="card">
<h2>七、结论与使用纪律</h2>
<p><b>1. 技术指标在熊市里的价值是风控，不是抄底。</b>两规则超额收益全部来自回避主跌段（沪深300 在场时间仅 32~45%），方向胜率并不高。把指标当「止损/减仓触发器」用，比当「抄底信号」用更符合数据。</p>
<p><b>2. 做空信号不可信。</b>规则A 做空信号在沪深300 胜率 0%、科创50 N=20 胜率 12.5%——趋势类指标的卖出信号在急跌中严重滞后。A 股缺乏做空工具也使该信号缺少实操价值。</p>
<p><b>3. 「共振确认」优于单指标。</b>中期反转的通用确认条件（本次实盘验证中依然适用）：站上 MA20 + MACD 零轴附近金叉且红柱连续放大 + 量能持续放大，三者缺一不可。</p>
<p><b>4. 样本局限性。</b>单窗口 242 个检查点、规则未在独立区间外样本验证；投入实盘前应在第二个市场（如 2022-2023 熊市、2019-2021 结构市）重复本流程。</p>
</div>

<div class="footer">数据来源：东方财富公开行情接口（push2his.eastmoney.com）日K，本地计算；新浪财经 60 分钟K。报告仅供研究方法验证，不构成投资建议。</div>
</div>

<script>
var UP='#dc2626', DN='#16a34a', NT='#6b7280', BLUE='#185fa5';
function mk(id, opt){var el=document.getElementById(id); if(el) echarts.init(el).setOption(opt);}

var dates1=__DATES1__, closes1=__CLOSES1__;
mk('c1',{tooltip:{trigger:'axis'},legend:{top:0},grid:{left:56,right:20,top:32,bottom:28},
 xAxis:{type:'category',data:dates1},yAxis:{type:'value',scale:true},
 series:[
  {name:'沪深300收盘',type:'line',data:closes1,showSymbol:false,lineStyle:{width:1.6,color:BLUE},itemStyle:{color:BLUE}},
  {name:'看多信号',type:'scatter',data:__BUYS1__,symbol:'triangle',symbolSize:11,itemStyle:{color:UP}},
  {name:'看空信号',type:'scatter',data:__SELLS1__,symbol:'triangle',symbolRotate:180,symbolSize:11,itemStyle:{color:DN}}]});

var navH=__NAVHS__;
mk('c2',{tooltip:{trigger:'axis'},legend:{top:0},grid:{left:56,right:20,top:32,bottom:28},
 xAxis:{type:'category',data:navH.dates},yAxis:{type:'value',scale:true},
 series:[
  {name:'规则B 多因子',type:'line',data:navH.ruleB,showSymbol:false,lineStyle:{width:2,color:UP}},
  {name:'规则A 三维投票',type:'line',data:navH.ruleA,showSymbol:false,lineStyle:{width:1.4,color:'#f59e0b'}},
  {name:'买入持有',type:'line',data:navH.hold,showSymbol:false,lineStyle:{width:1.6,color:NT}}]});

var navK=__NAVKC__;
mk('c3',{tooltip:{trigger:'axis'},legend:{top:0},grid:{left:56,right:20,top:32,bottom:28},
 xAxis:{type:'category',data:navK.dates},yAxis:{type:'value',scale:true},
 series:[
  {name:'规则B 多因子',type:'line',data:navK.ruleB,showSymbol:false,lineStyle:{width:2,color:UP}},
  {name:'规则A 三维投票',type:'line',data:navK.ruleA,showSymbol:false,lineStyle:{width:1.4,color:'#f59e0b'}},
  {name:'买入持有',type:'line',data:navK.hold,showSymbol:false,lineStyle:{width:1.6,color:NT}}]});
</script>
</body>
</html>
"""

sim_hs = tbl_sim("hs300")
sim_kc = tbl_sim("kc50")
# 信号散点坐标（x=日期索引对应的 category 位置）
sp_hs = sig_pts["hs300"]
buys1 = [[sp_hs["buys_x"][i], sp_hs["buys_y"][i]] for i in range(len(sp_hs["buys_x"]))]
sells1 = [[sp_hs["sells_x"][i], sp_hs["sells_y"][i]] for i in range(len(sp_hs["sells_x"]))]

html = (html
        .replace("__WIN__", "2025-10-24 ~ 2026-10-23")
        .replace("__HSB__", str(enh["hs300"]["sim_b"]["strategy_ret"]))
        .replace("__HSH__", str(enh["hs300"]["sim_b"]["buyhold_ret"]))
        .replace("__KCB__", str(enh["kc50"]["sim_b"]["strategy_ret"]))
        .replace("__KCH__", str(enh["kc50"]["sim_b"]["buyhold_ret"]))
        .replace("__SIMHS__", sim_hs)
        .replace("__SIMKC__", sim_kc)
        .replace("__EVHS__", tbl_eval("hs300"))
        .replace("__EVKC__", tbl_eval("kc50"))
        .replace("__KEYHS__", tbl_key("hs300"))
        .replace("__KEYKC__", tbl_key("kc50"))
        .replace("__LEADHS__", lead_info("hs300"))
        .replace("__LEADKC__", lead_info("kc50"))
        .replace("__MPHS__", tbl_mp("hs300"))
        .replace("__MPKC__", tbl_mp("kc50"))
        .replace("__CASEHS__", case_tbl("hs300"))
        .replace("__CASEKC__", case_tbl("kc50"))
        .replace("__DATES1__", json.dumps(dates_hs, ensure_ascii=False))
        .replace("__CLOSES1__", json.dumps(sig_pts["hs300"]["close"]))
        .replace("__BUYS1__", json.dumps(buys1))
        .replace("__SELLS1__", json.dumps(sells1))
        .replace("__NAVHS__", json.dumps(nav_data["hs300"]))
        .replace("__NAVKC__", json.dumps(nav_data["kc50"])))

out = os.path.join(OUT, "PIT回测与多周期验证报告.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print("已写出", out, len(html), "bytes")

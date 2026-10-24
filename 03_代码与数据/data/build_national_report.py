# -*- coding: utf-8 -*-
"""生成国家队资金行为分析报告 HTML。"""
import json
import os

import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(BASE)

with open(os.path.join(BASE, "national_team.json"), encoding="utf-8") as f:
    nt = json.load(f)

daily = pd.DataFrame(nt["daily"])
daily["date"] = pd.to_datetime(daily["date"])
daily = daily.set_index("date").sort_index()

# ---- 图1 数据：ETF 合计成交额 + 20 日均量（近一年，日线着色按指数涨跌）----
one = daily[daily.index >= "2025-10-24"]
amt = [round(float(x), 1) for x in one["etf_amount_yi"]]
dates = [d.strftime("%m-%d") for d in one.index]
colors = ["#dc2626" if x > 0 else "#16a34a" for x in one["pct"]]
ma20 = []
s = pd.Series(one["etf_amount_yi"].values)
m = s.rolling(20).mean()
ma20 = [None if pd.isna(x) else round(float(x), 1) for x in m]

# ---- 图2 数据：超大单净流入（有资金流的 120 日）----
ff = daily[daily["xlarge_yi"].notna()]
ff_dates = [d.strftime("%m-%d") for d in ff.index]
ff_vals = [round(float(x), 1) for x in ff["xlarge_yi"]]
ff_colors = ["#dc2626" if x > 0 else "#16a34a" for x in ff_vals]

# ---- 图3 数据：尾盘占比 vs 尾盘涨跌（近一月有尾盘数据的日子）----
tl = daily[daily["tail_share"].notna()]
tl_dates = [d.strftime("%m-%d") for d in tl.index]
tl_share = [float(x) for x in tl["tail_share"]]
tl_chg = [float(x) for x in tl["tail_chg"]]

# ---- 命中日表 ----
hits = daily[daily["verdict"].str.contains("特征明显|存在") & ~daily["verdict"].str.contains("无明显")]


def hit_rows():
    rows = []
    for d, r in hits.iterrows():
        v = r["verdict"]
        cls = "up" if "托底" in v or "承接" in v else "dn"
        rows.append("<tr><td>%s</td><td class='%s'>%.2f%%</td><td class='r'>%s</td><td class='r'>%s</td>"
                    "<td class='r'>%s</td><td class='r'>%s</td><td class='r'>%s</td><td class='r'>%s</td>"
                    "<td class='%s'>%s</td></tr>" % (
                        d.strftime("%Y-%m-%d"), cls, r["pct"], r["etf_amount_yi"], r["etf_vol_mult"],
                        r["xlarge_yi"], r["tail_share"], r["tail_chg"], r["close_pos"],
                        cls, v))
    return "\n".join(rows)


def recent_rows(n=15):
    rows = []
    for d, r in daily.tail(n).iterrows():
        pct_cls = "up" if r["pct"] > 0 else ("dn" if r["pct"] < 0 else "nt")
        rows.append("<tr><td>%s</td><td>%.1f</td><td class='%s'>%.2f%%</td><td class='r'>%.0f</td>"
                    "<td class='r'>%s</td><td class='r'>%s</td><td class='r'>%s</td><td class='r'>%s</td>"
                    "<td class='r'>%s</td><td>%s %s</td></tr>" % (
                        d.strftime("%Y-%m-%d"), r["close"], pct_cls, r["pct"], r["etf_amount_yi"],
                        r["etf_vol_mult"], r["xlarge_yi"],
                        "—" if r["tail_share"] is None or pd.isna(r["tail_share"]) else "%.1f%%" % r["tail_share"],
                        "—" if r["tail_chg"] is None or pd.isna(r["tail_chg"]) else "%.2f%%" % r["tail_chg"],
                        "—" if r["close_pos"] is None or pd.isna(r["close_pos"]) else "%.0f%%" % r["close_pos"],
                        r["tail_flag"] or "", r["verdict"]))
    return "\n".join(rows)


def fmt(x, suf=""):
    return "—" if x is None or (isinstance(x, float) and pd.isna(x)) else "%s%s" % (x, suf)


html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>国家队资金行为分析（沪深300方向）</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
:root{--ink:#1f2937;--sub:#6b7280;--line:#e5e7eb;--bg:#f6f7f9;--card:#fff;--blue:#185fa5}
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
.up{color:#dc2626;font-weight:600}.dn{color:#16a34a;font-weight:600}.nt{color:var(--sub)}
.sz{font-size:11.5px;color:var(--sub)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:12px 0}
.kpi{background:#f9fafb;border:1px solid var(--line);border-radius:8px;padding:10px 12px}
.kpi .k{font-size:11.5px;color:var(--sub)}
.kpi .v{font-size:18px;font-weight:700;margin-top:2px}
.chart{width:100%;height:340px;margin:8px 0}
.note{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:10px 14px;font-size:12.5px;color:#92400e;margin:10px 0}
.ok{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:10px 14px;font-size:12.5px;color:#166534;margin:10px 0}
.tag{display:inline-block;background:#eef2ff;color:#3730a3;border-radius:4px;padding:1px 7px;font-size:11px;margin-right:6px}
.footer{margin-top:26px;color:var(--sub);font-size:12px;border-top:1px solid var(--line);padding-top:14px}
</style>
</head>
<body>
<div class="wrap">
<header>
<h1>国家队资金行为分析（沪深300方向）</h1>
<div class="meta">分析窗口 2024-09-02 ~ 2026-10-23（496 个交易日）｜ 资金流数据 120 日 ｜ ETF 尾盘微观 17 日 ｜ 生成日期 2026-10-24</div>
</header>

<div class="card">
<h2>〇、方法论与诚信声明（先读）</h2>
<p><b>国家队（中央汇金、证金公司等）的持仓与操作没有官方实时披露。</b>本工具不使用任何内幕信息，只用四类公开数据做「行为特征匹配」推断：</p>
<p>① <b>指数级资金流</b>（东方财富）：超大单/大单/主力净流入，急跌日的超大单流向是重要旁证；② <b>沪深300 ETF 成交异动</b>：华泰柏瑞510300 / 华夏510330 / 易方达510310 / 嘉实159919 四只合计成交额 vs 20 日均量；③ <b>尾盘微观行为</b>（510300 五分钟线）：尾盘 30 分钟成交占比、尾盘涨跌、收盘在日内区间的位置；④ <b>量价形态</b>：急跌日长下影、上涨日缩量等。</p>
<div class="note"><b>能力边界：</b>「ETF 放量」不等于「国家队买入」——也可能是套利盘、量化或机构借道 ETF 出货；「超大单净流出」中的国家队卖单同样无法与普通机构区分。因此所有结论均为<b>特征匹配推断</b>，命中率与漏报率都无法直接验证，请勿作为唯一决策依据。</div>
</div>

<div class="card">
<h2>一、两年全景：国家队出手极其罕见</h2>
<div class="kpis">
<div class="kpi"><div class="k">托底特征明显</div><div class="v up">__N_UP__ 日</div></div>
<div class="kpi"><div class="k">存在承接迹象</div><div class="v up">__N_SUP__ 日</div></div>
<div class="kpi"><div class="k">派发迹象</div><div class="v dn">__N_DIST__ 日</div></div>
<div class="kpi"><div class="k">尾盘显著放量</div><div class="v">__N_TAIL__ 日</div></div>
<div class="kpi"><div class="k">托底日后10日均值</div><div class="v">__FWD10__%</div></div>
</div>
<p>496 个交易日中仅 <b>__N_TOTAL__ 日</b>命中国家队行为特征（占比 __N_PCT__%），且集中在极端暴跌日——这与「汇金只在市场恐慌时刻公告增持」的公开记录一致（2024-10-09、2025-04-07 两次 -7% 暴跌日均被检出，是方法有效性的侧面验证）。</p>
<h3>命中日明细</h3>
<table><tr><th>日期</th><th>指数涨跌</th><th>4只ETF成交(亿)</th><th>量比</th><th>超大单净流入(亿)</th><th>尾盘占比</th><th>尾盘涨跌</th><th>收盘位置</th><th>判型</th></tr>
__HITS__
</table>
</div>

<div class="card">
<h2>二、ETF 成交异动：放量日的价格行为分解</h2>
<div id="c1" class="chart"></div>
<p class="sz">图1：四只沪深300 ETF 合计成交额（柱，红=指数上涨日 / 绿=下跌日）与 20 日均量（线）。正常日合计约 36~84 亿；超过 150 亿即为显著异动。</p>
<p>近一年显著放量日：<b>2026-10-15（277 亿，急跌 -1.23% 后尾盘拉升）</b>、<b>2026-10-22（302 亿，-1.84% 尾盘放量走弱）</b>、<b>2026-10-23（301 亿，+1.71% 反弹）</b>。三天量能同一量级但方向与结构完全不同，必须结合价格行为判型（见第四节）。</p>
<div id="c2" class="chart"></div>
<p class="sz">图2：沪深300 指数超大单净流入（亿元，红=净流入 / 绿=净流出）。2026 年 6 月下旬至 7 月中旬出现持续巨额净流出（单日最高 -696 亿），与指数从 5059 高点崩跌的时间窗吻合——机构性抛压是本轮下跌主因，国家队并未在此期间托底。</p>
</div>

<div class="card">
<h2>三、尾盘微观：510300 五分钟线的「国家队时段」</h2>
<div id="c3" class="chart"></div>
<p class="sz">图3：尾盘 30 分钟成交占全天比例（柱）与尾盘涨跌（线）。正常日中位数约 16%；超过 30% 为显著异动。10-16（79.7%）、10-21（53.4%）、10-22（54.9%）三日尾盘极度放量。</p>
<table><tr><th>日期</th><th>尾盘占比</th><th>尾盘30分钟涨跌</th><th>形态解读</th></tr>
__TAILROWS__
</table>
</div>

<div class="card">
<h2>四、判型规则与重点日复盘</h2>
<h3>4.1 规则（阈值来自实际分布：尾盘占比正常日中位 16%）</h3>
<table><tr><th>判型</th><th>核心条件（急跌日 / 上涨日）</th></tr>
<tr><td class="up">买入托底</td><td>急跌日（≤-1%）：ETF 放量（量比≥2，+2）；尾盘放量拉升且收盘位置&gt;60%（+3）或温和尾盘拉升且收盘&gt;70%（+2）；尾盘放量走弱或收盘在日内低位（-2）；超大单净流入（+2）；长下影（+1）。≥5 分=明显，2~4 分=有迹象</td></tr>
<tr><td class="dn">拉高派发</td><td>上涨日（≥+1%）：缩量（量比≤0.8，+1）；超大单大额净流出（&lt;-50 亿，+2；&lt;0，+1）；尾盘放量回落（+1）。≥3 分=明显，2 分=有迹象</td></tr>
</table>
<h3>4.2 重点日复盘</h3>
<table><tr><th>日期</th><th>事件</th><th>数据形态</th><th>判型</th><th>解读</th></tr>
<tr><td>2026-10-15</td><td>急跌 -1.23%</td><td>ETF 277 亿（4.3 倍）、尾盘拉升 +1.19%、收盘位置 90%</td><td class="up">买入托底特征明显</td><td>唯一「明显托底」日：放量+尾盘拉升+长下影，典型承接形态。但超大单仍净流出 168 亿，承接方身份无法确认</td></tr>
<tr><td>2026-10-22</td><td>急跌 -1.84%（本轮最低）</td><td>ETF 302 亿（3.3 倍）、超大单 -190 亿、尾盘占比 55% 但尾盘跌 0.32%、收盘位置 11%</td><td class="nt">无明显托底特征</td><td><b>天量≠国家队</b>：尾盘放量走弱+收在日内最低+超大单巨额流出，形态是恐慌抛售中的对手盘承接（市场性资金），没有国家队托底证据</td></tr>
<tr><td>2026-10-23</td><td>反弹 +1.71%</td><td>ETF 301 亿（不缩量）、超大单转正 +11.8 亿、收盘位置 95%</td><td class="nt">无明显特征</td><td>放量长阳+超大单首次转正，反弹第一波；上涨日不缩量，排除派发</td></tr>
<tr><td>2026-06-23</td><td>急跌 -2.77%（见顶回落启动）</td><td>ETF 量比 3.07、超大单 -625 亿</td><td class="up">存在承接迹象</td><td>borderline：ETF 放量计为承接，但 -625 亿超大单流出更像机构派发。代理指标的固有歧义</td></tr>
<tr><td>2026-07-20 / 07-27</td><td>反弹 +1.53% / +1.15%</td><td>超大单 -125 亿 / -17.5 亿，其中 07-27 缩量</td><td class="dn">存在派发迹象</td><td>上涨日超大单持续流出，符合「拉高出货」特征</td></tr>
<tr><td>2024-10-09 / 2025-04-07</td><td>暴跌 -7.05% / -7.05%</td><td>ETF 量比 2.05 / 5.96</td><td class="up">存在承接迹象</td><td>两次历史性暴跌日的 ETF 天量，与公开报道的汇金增持时点吻合</td></tr>
</table>
<h3>4.3 近 15 个交易日明细</h3>
<table><tr><th>日期</th><th>收盘</th><th>涨跌</th><th>ETF成交(亿)</th><th>量比</th><th>超大单(亿)</th><th>尾盘占比</th><th>尾盘涨跌</th><th>收盘位置</th><th>尾盘标记 / 判型</th></tr>
__RECENT__
</table>
</div>

<div class="card">
<h2>五、结论</h2>
<p><b>1. 本轮（2026-06 高点至 10 月低点）下跌未检测到国家队托底。</b>资金流显示 6 月下旬起机构超大单持续巨额净流出（单日 -696 亿），10-22 最低点当天 ETF 虽放量 3.3 倍，但尾盘放量走弱、收在日内最低、超大单净流出 190 亿——承接方是市场性资金而非国家队。</p>
<p><b>2. 国家队行为确实存在但极罕见。</b>两年 496 日仅 4 日命中托底特征（含 2 日历史已知汇金增持日），说明该工具「宁缺毋滥」；反之若某日同时出现「急跌 + ETF 三倍以上放量 + 尾盘拉升 + 长下影 + 超大单转正」，则为高置信度托底信号。</p>
<p><b>3. 「拉高派发」在 2026-07 反弹中被检出 2 次</b>（上涨日超大单流出+缩量），与随后 7-10 月 -40% 的急跌在时间上衔接。</p>
<p><b>4. 托底≠反转。</b>命中托底特征的 4 个交易日后 5 日平均 -0.08%、10 日 +1.1%——托底只减缓下跌斜率，不改变趋势本身。</p>
</div>

<div class="footer">数据来源：东方财富（指数日K/资金流/接口）、腾讯财经（ETF 日K/五分钟K）。国家队操作无官方实时披露，本报告全部结论为公开数据的行为特征匹配推断，不构成投资建议。</div>
</div>

<script>
var UP='#dc2626', DN='#16a34a', NT='#6b7280', BLUE='#185fa5';
function mk(id, opt){var el=document.getElementById(id); if(el) echarts.init(el).setOption(opt);}

mk('c1',{tooltip:{trigger:'axis'},legend:{top:0},grid:{left:56,right:20,top:32,bottom:28},
 xAxis:{type:'category',data:__DATES__},yAxis:[{type:'value',name:'亿元',scale:true},{type:'value',show:false}],
 series:[
  {name:'4只ETF合计成交额',type:'bar',data:__AMT__,itemStyle:{color:function(p){return __COLORS__[p.dataIndex];}}},
  {name:'20日均量',type:'line',data:__MA20__,showSymbol:false,lineStyle:{width:1.6,color:BLUE}}]});

mk('c2',{tooltip:{trigger:'axis'},legend:{top:0},grid:{left:56,right:20,top:32,bottom:28},
 xAxis:{type:'category',data:__FFDATES__},yAxis:{type:'value',name:'亿元',scale:true},
 series:[{name:'超大单净流入',type:'bar',data:__FFVALS__,
   itemStyle:{color:function(p){return __FFCOLORS__[p.dataIndex];}}}]});

mk('c3',{tooltip:{trigger:'axis'},legend:{top:0},grid:{left:56,right:20,top:32,bottom:28},
 xAxis:{type:'category',data:__TLDATES__},
 yAxis:[{type:'value',name:'占比%',min:0,max:100},{type:'value',name:'尾盘涨跌%',min:-1,max:1}],
 series:[
  {name:'尾盘30分钟成交占比',type:'bar',data:__TLSHARE__,itemStyle:{color:'#93c5fd'}},
  {name:'尾盘30分钟涨跌',type:'line',data:__TLCHG__,showSymbol:true,yAxisIndex:1,lineStyle:{color:'#f59e0b'}}]});
</script>
</body>
</html>
"""

tail_rows = []
for d, r in tl.iterrows():
    share, chg = r["tail_share"], r["tail_chg"]
    if share > 30 and chg > 0.2:
        note = "尾盘放量拉升——护盘/抢筹形态"
    elif share > 30 and chg < -0.2:
        note = "尾盘放量走弱——减仓/抛售形态"
    elif share > 30:
        note = "尾盘显著放量"
    else:
        note = "正常"
    tail_rows.append("<tr><td>%s</td><td class='r'>%.1f%%</td><td class='r'>%.2f%%</td><td>%s</td></tr>" % (
        d.strftime("%Y-%m-%d"), share, chg, note))

html = (html
        .replace("__N_UP__", "1")
        .replace("__N_SUP__", str(nt["stats"]["verdict_counts"].get("存在承接买入迹象", 0)))
        .replace("__N_DIST__", str(nt["stats"]["verdict_counts"].get("存在派发迹象", 0)
                                   + nt["stats"]["verdict_counts"].get("拉高派发特征明显", 0)))
        .replace("__N_TAIL__", str(len(nt["stats"]["tail_flag_counts"]) - 1
                                   if "" in nt["stats"]["tail_flag_counts"] else len(nt["stats"]["tail_flag_counts"])))
        .replace("__FWD10__", str(nt["stats"].get("support_fwd10_avg")))
        .replace("__N_TOTAL__", str(nt["stats"]["support_days"] + nt["stats"]["dist_days"]))
        .replace("__N_PCT__", "%.1f" % ((nt["stats"]["support_days"] + nt["stats"]["dist_days"])
                                        / nt["stats"]["n_days"] * 100))
        .replace("__HITS__", hit_rows())
        .replace("__TAILROWS__", "\n".join(tail_rows))
        .replace("__RECENT__", recent_rows())
        .replace("__DATES__", json.dumps(dates))
        .replace("__AMT__", json.dumps(amt))
        .replace("__COLORS__", json.dumps(colors))
        .replace("__MA20__", json.dumps(ma20))
        .replace("__FFDATES__", json.dumps(ff_dates))
        .replace("__FFVALS__", json.dumps(ff_vals))
        .replace("__FFCOLORS__", json.dumps(ff_colors))
        .replace("__TLDATES__", json.dumps(tl_dates))
        .replace("__TLSHARE__", json.dumps(tl_share))
        .replace("__TLCHG__", json.dumps(tl_chg)))

out = os.path.join(OUT, "国家队资金行为分析.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print("已写出", out, len(html), "bytes")

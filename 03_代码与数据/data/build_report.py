# -*- coding: utf-8 -*-
"""把 computed.json 注入 report_template.html，生成最终 HTML 研报。"""
import json

BASE = r"C:\Users\Administrator\WorkBuddy\2026-10-24-19-44-35\outputs"
TPL = BASE + r"\report_template.html"
OUT = BASE + r"\沪深300与科创50近一年技术指标分析.html"

d = json.load(open(BASE + r"\data\computed.json", encoding="utf-8"))
S = d["snap"]
ST = d["stats"]
EV = d["events"]
MO = d["monthly"]
TM = d["top_moves"]
EN = d["engine"]
SR = d["series"]


def cls(v):
    return "up" if v > 0 else ("down" if v < 0 else "")


def pct(v, signed=True):
    if v is None:
        return "—"
    s = ("%+.2f" % v) if signed else ("%.2f" % v)
    return '<span class="%s">%s%%</span>' % (cls(v), s)


def num(v):
    return "%.2f" % v if v is not None else "—"


def kv(k, v):
    return '<div class="kv"><span class="k">%s</span><span>%s</span></div>' % (k, v)


# ---------------- TL;DR 卡片 ----------------
def tldr():
    a, b = S["hs300"], S["kc50"]
    card1 = (
        '<div class="card blue"><h3>沪深300（000300） <span class="tag bear">空头趋势 · 超卖反弹初期</span></h3>'
        + kv("收盘（10/23）", "4105.33 <span class='up'>+1.71%</span>")
        + kv("近1年 / 60日", pct(ST["hs300"]["ret_1y"]) + " / " + pct(ST["hs300"]["ret_60d"]))
        + kv("均线", "完全空头排列，价在 MA5 下方")
        + kv("MACD", "DIF -114.60 &lt; DEA -98.96，绿柱未金叉")
        + kv("RSI / KDJ", "RSI12 27.80（破30）；K 20.67 / D 15.96")
        + kv("BOLL", "%B 0.19，贴合下轨 3985.85")
        + kv("ADX", "47.56（-DI 43.60），空头动能强")
        + '<div class="verdict">趋势破坏程度较轻、估值安全边际高（PE 12.8 / 股息率 2.81%），但 ADX 高企提示空头动能仍强，反转需等 MACD 零轴金叉。</div></div>'
    )
    card2 = (
        '<div class="card orange"><h3>科创50（000688） <span class="tag bear">空头趋势 · 反弹信号更早</span></h3>'
        + kv("收盘（10/23）", "1345.51 <span class='up'>+3.04%</span>")
        + kv("近1年 / 60日", pct(ST["kc50"]["ret_1y"]) + " / " + pct(ST["kc50"]["ret_60d"]))
        + kv("均线", "空头排列，但已站上 MA5（1333.25）")
        + kv("MACD", "DIF -79.11 &lt; DEA -69.63，零轴下未金叉")
        + kv("RSI / KDJ", "RSI12 31.21；K 22.23 / J 35.82 回升")
        + kv("BOLL", "%B 0.26，贴近下轨 1213.49")
        + kv("ADX", "36.25（-DI 41.29），空头但弱于300")
        + '<div class="verdict">超跌更深（距 MA60 -15.61%）、反弹弹性更大，但年化波动 41%、PE 110 倍，反弹失败的下行空间也更大。</div></div>'
    )
    card3 = (
        '<div class="card"><h3>综合判断 <span class="tag mid">观望 · 等右侧确认</span></h3>'
        + kv("共同状态", "中期空头趋势中的超卖修复初期")
        + kv("10/22 → 10/23", "共振创低后放量长下影反弹")
        + kv("引擎信号", "两者最新均为「做空」（规则未翻转）")
        + kv("短期领先", "科创50（站上 MA5、J 值先回升）")
        + kv("防御占优", "沪深300（低估值、低波动、高股息）")
        + '<div class="verdict">反弹 ≠ 反转。中期反转的通用确认信号：① 站上 MA20（300: 4295.86 / 688: 1472.27）；② MACD 零轴附近金叉且红柱连续放大；③ 量能持续放大。</div></div>'
    )
    return card1 + card2 + card3


# ---------------- 关键数字表 ----------------
def stats_table():
    a, b = ST["hs300"], ST["kc50"]
    rows = [
        ("区间涨跌幅（近1年）", pct(a["ret_1y"]), pct(b["ret_1y"])),
        ("年初至今（westock）", '<span class="down">-11.33%</span>', '<span class="up">+0.10%</span>'),
        ("近60日 / 近20日 / 近5日", "%s / %s / %s" % (pct(a["ret_60d"]), pct(a["ret_20d"]), pct(a["ret_5d"])),
         "%s / %s / %s" % (pct(b["ret_60d"]), pct(b["ret_20d"]), pct(b["ret_5d"]))),
        ("1年最高（日期）", "%s（%s）" % (num(a["high"]), a["high_date"]), "%s（%s）" % (num(b["high"]), b["high_date"])),
        ("1年最低（日期）", "%s（%s）" % (num(a["low"]), a["low_date"]), "%s（%s）" % (num(b["low"]), b["low_date"])),
        ("区间最大回撤（峰→谷）", "%s（%s→%s）" % (pct(a["max_dd"]), a["peak_date"], a["max_dd_date"]),
         "%s（%s→%s）" % (pct(b["max_dd"]), b["peak_date"], b["max_dd_date"])),
        ("年化波动率", "%.2f%%" % a["ann_vol"], "%.2f%%" % b["ann_vol"]),
        ("ATR(14) 及占价比", "%s（%.2f%%）" % (num(a["atr"]), a["atr_pct"]), "%s（%.2f%%）" % (num(b["atr"]), b["atr_pct"])),
        ("上涨 / 下跌天数", "%d / %d" % (a["up_days"], a["down_days"]), "%d / %d" % (b["up_days"], b["down_days"])),
        ("成交额 10/23（westock）", "5582 亿元", "969 亿元"),
        ("换手率 10/23（westock）", "0.69%", "1.58%"),
        ("PE(TTM) / 股息率（westock）", "12.84 倍 / 2.81%", "110.05 倍 / 0.29%"),
    ]
    head = '<table><tr><th style="text-align:left">指标</th><th>沪深300</th><th>科创50</th></tr>'
    body = "".join('<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % r for r in rows)
    return head + body + "</table>"


# ---------------- 归一化数据表 ----------------
def norm_table():
    dts = SR["hs300"]["dates"]
    head = ('<table><tr><th style="text-align:left">日期</th><th>沪深300 收盘</th><th>沪深300 归一</th>'
            '<th>科创50 收盘</th><th>科创50 归一</th></tr>')
    rows = []
    for i, dt in enumerate(dts):
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            dt, num(SR["hs300"]["close"][i]), num(SR["hs300"]["norm"][i]),
            num(SR["kc50"]["close"][i]), num(SR["kc50"]["norm"][i])))
    return head + "".join(rows) + "</table>"


# ---------------- 月度表 ----------------
def monthly_one(name, rows):
    head = '<h3 class="sub">%s · 月末收盘与月涨跌</h3><table><tr><th style="text-align:left">月份</th><th>月末收盘</th><th>月涨跌幅</th></tr>' % name
    body = ""
    for r in rows:
        body += '<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (r["month"], num(r["close"]), pct(r["chg"]))
    return head + body + "</table>"


def monthly():
    return monthly_one("沪深300", MO["hs300"]) + monthly_one("科创50", MO["kc50"])


# ---------------- 极端涨跌日 ----------------
def topmoves_one(name, tm):
    head = ('<h3 class="sub">%s · 极端波动日（近1年 Top5）</h3>'
            '<table><tr><th style="text-align:left">日期</th><th>当日涨跌幅</th><th>收盘</th></tr>' % name)
    body = ""
    for r in tm["up"]:
        body += '<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (r["date"], pct(r["pct"]), num(r["close"]))
    for r in tm["down"]:
        body += '<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (r["date"], pct(r["pct"]), num(r["close"]))
    return head + body + "</table>"


def topmoves():
    return topmoves_one("沪深300", TM["hs300"]) + topmoves_one("科创50", TM["kc50"])


# ---------------- 指标状态总表 ----------------
def snap_table():
    a, b = S["hs300"], S["kc50"]
    rows = [
        ("收盘价", num(a["close"]), num(b["close"])),
        ("MA5 / MA10", "%s / %s" % (num(a["ma5"]), num(a["ma10"])), "%s / %s" % (num(b["ma5"]), num(b["ma10"]))),
        ("MA20 / MA60", "%s / %s" % (num(a["ma20"]), num(a["ma60"])), "%s / %s" % (num(b["ma20"]), num(b["ma60"]))),
        ("MA120 / MA250", "%s / %s" % (num(a["ma120"]), num(a["ma250"])), "%s / %s" % (num(b["ma120"]), num(b["ma250"]))),
        ("价格 vs MA5", "下方（未收复）", "上方（已收复）"),
        ("MACD：DIF / DEA / 柱", "%s / %s / %s" % (num(a["dif"]), num(a["dea"]), num(a["macd"])),
         "%s / %s / %s" % (num(b["dif"]), num(b["dea"]), num(b["macd"]))),
        ("RSI 6 / 12 / 24", "%s / %s / %s" % (num(a["rsi6"]), num(a["rsi12"]), num(a["rsi24"])),
         "%s / %s / %s" % (num(b["rsi6"]), num(b["rsi12"]), num(b["rsi24"]))),
        ("KDJ：K / D / J", "%s / %s / %s" % (num(a["kdj_k"]), num(a["kdj_d"]), num(a["kdj_j"])),
         "%s / %s / %s" % (num(b["kdj_k"]), num(b["kdj_d"]), num(b["kdj_j"]))),
        ("BOLL：下 / 中 / 上", "%s / %s / %s" % (num(a["bb_lower"]), num(a["bb_mid"]), num(a["bb_upper"])),
         "%s / %s / %s" % (num(b["bb_lower"]), num(b["bb_mid"]), num(b["bb_upper"]))),
        ("BOLL %B（0=下轨，1=上轨）", num(a["pctb"]), num(b["pctb"])),
        ("ADX / +DI / -DI", "%s / %s / %s" % (num(a["adx"]), num(a["pdi"]), num(a["mdi"])),
         "%s / %s / %s" % (num(b["adx"]), num(b["pdi"]), num(b["mdi"]))),
        ("OBV vs 其20日均线", a["obv_trend"] + "（量价维偏空）", b["obv_trend"] + "（量价维偏空）"),
        ("量比（V / MA5(V)）", num(a["vol_ratio"]), num(b["vol_ratio"])),
        ("偏离度：MA20 / MA60 / MA250", "%s%% / %s%% / %s%%" % (num(a["dev_ma20"]), num(a["dev_ma60"]), num(a["dev_ma250"])),
         "%s%% / %s%% / %s%%" % (num(b["dev_ma20"]), num(b["dev_ma60"]), num(b["dev_ma250"]))),
    ]
    head = '<table><tr><th style="text-align:left">指标</th><th>沪深300</th><th>科创50</th></tr>'
    body = "".join('<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % r for r in rows)
    return head + body + "</table>"


# ---------------- 引擎信号表 ----------------
def engine_table():
    a, b = EN["hs300"], EN["kc50"]
    rows = [
        ("做多信号天数", str(a["buy_days"]), str(b["buy_days"])),
        ("做空信号天数", str(a["sell_days"]), str(b["sell_days"])),
        ("观望天数", str(a["neutral_days"]), str(b["neutral_days"])),
        ("最新信号（10/23）", a["last_signal"], b["last_signal"]),
        ("最近一次做多", a["last_buy"] or "—", b["last_buy"] or "—"),
        ("最近一次做空", a["last_sell"] or "—", b["last_sell"] or "—"),
    ]
    head = '<table><tr><th style="text-align:left">引擎输出（242 个交易日）</th><th>沪深300</th><th>科创50</th></tr>'
    body = "".join('<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % r for r in rows)
    return head + body + "</table>"


# ---------------- 事件表 ----------------
def events_one(name, evs, n=14):
    head = '<h3 class="sub">%s · 关键信号事件</h3><table><tr><th style="text-align:left">日期</th><th style="text-align:left">信号</th><th style="text-align:left;white-space:normal">说明</th></tr>' % name
    body = ""
    for e in evs[::-1][:n]:
        body += '<tr><td>%s</td><td style="text-align:left">%s</td><td style="text-align:left;white-space:normal">%s</td></tr>' % (e["date"], e["type"], e["detail"])
    return head + body + "</table>"


def events():
    return events_one("沪深300", EV["hs300"]) + events_one("科创50", EV["kc50"])


def main():
    tpl = open(TPL, encoding="utf-8").read()
    raw = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    tokens = {
        "__RAWDATA__": raw,
        "__TLDR__": tldr(),
        "__STATS_TABLE__": stats_table(),
        "__NORM_TABLE__": norm_table(),
        "__MONTHLY__": monthly(),
        "__TOPMOVES__": topmoves(),
        "__SNAP_TABLE__": snap_table(),
        "__ENGINE_TABLE__": engine_table(),
        "__EVENTS__": events(),
    }
    for k, v in tokens.items():
        assert k in tpl, "token missing: " + k
        tpl = tpl.replace(k, v)
    assert "__" not in tpl.replace("__RAWDATA__", ""), "unreplaced token remains"
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(tpl)
    print("written:", OUT)
    print("size:", len(tpl), "chars")

    # 抽取内联 JS 做语法自检
    import re
    scripts = re.findall(r"<script>(.*?)</script>", tpl, re.S)
    with open(BASE + r"\data\_check.js", "w", encoding="utf-8") as f:
        f.write("\n".join(scripts))
    print("inline scripts:", len(scripts), "-> data/_check.js")


if __name__ == "__main__":
    main()

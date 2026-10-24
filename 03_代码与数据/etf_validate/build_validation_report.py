# -*- coding: utf-8 -*-
"""ETF 全面验证报告生成：读取 validate_result.json -> HTML + CSV。"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.dirname(HERE)


def clip(v, lo, hi):
    return max(lo, min(hi, v))


def comp_score(r):
    """综合验证分 0-100：回测超额 35 / 方向胜率 25 / 风控改善 20 / 流动性 20。次新未回测返回 None。"""
    if not r.get("sim_a") or not r.get("sim_b"):
        return None
    ea = clip((r["sim_a"]["excess"] + 15) / 45 * 100, 0, 100)   # -15~+30 -> 0~100
    eb = clip((r["sim_b"]["excess"] + 15) / 45 * 100, 0, 100)
    excess_s = (ea + eb) / 2
    ha = r["eval_a_n20"]["dir_hit"] or 50
    hb = r["eval_b_n20"]["dir_hit"] or 50
    hit_s = clip((ha + hb) / 2, 0, 100)
    dda = clip((r["sim_a"]["buyhold_maxdd"] - r["sim_a"]["strategy_maxdd"]) / 15 * 100 + 50, 0, 100)
    ddb = clip((r["sim_b"]["buyhold_maxdd"] - r["sim_b"]["strategy_maxdd"]) / 15 * 100 + 50, 0, 100)
    dd_s = (dda + ddb) / 2
    import math
    liq = math.log10(max(r["stats_1y"]["avg_amt_yi"], 0.01))
    liq_s = clip((liq + 2) / 3 * 100, 0, 100)                   # 0.01亿~10亿 -> 0~100
    return round(0.35 * excess_s + 0.25 * hit_s + 0.20 * dd_s + 0.20 * liq_s, 1)


def main():
    d = json.load(open(os.path.join(HERE, "validate_result.json"), encoding="utf-8"))
    rows = d["results"]
    for r in rows:
        r["score"] = comp_score(r)
    # 有分值的按分降序；未回测（None）沉底按行业排序
    rows.sort(key=lambda x: (-(x["score"] if x["score"] is not None else -1), x["industry"]))
    n = len(rows)
    bt_rows = [r for r in rows if r.get("sim_a")]
    n_ver = sum(1 for r in rows if r["verify_passed"])
    n_na = sum(1 for r in rows if r["verify_passed"] is None)
    beat_a = sum(1 for r in bt_rows if r["sim_a"]["excess"] > 0)
    beat_b = sum(1 for r in bt_rows if r["sim_b"]["excess"] > 0)
    avg_ex_a = sum(r["sim_a"]["excess"] for r in bt_rows) / max(1, len(bt_rows))
    avg_ex_b = sum(r["sim_b"]["excess"] for r in bt_rows) / max(1, len(bt_rows))

    # ---------- CSV ----------
    def g(r, sim_key, field, nd=2):
        if not r.get(sim_key):
            return ""
        return r[sim_key][field]

    csv_path = os.path.join(OUT_DIR, "ETF全面验证明细.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["综合分", "行业", "代码", "名称", "净资产规模(亿)", "近1年收益%", "年化波动%",
                    "近1年最大回撤%", "日均成交额(亿)", "当前趋势", "MACD金叉", "RSI12", "KDJ-K",
                    "%B", "ADX", "规则B当前方向", "规则B评分", "规则A当前信号",
                    "规则A策略收益%", "规则A超额%", "规则A最大回撤%", "持有最大回撤%",
                    "规则B策略收益%", "规则B超额%", "规则B最大回撤%",
                    "20日方向胜率A%", "20日方向胜率B%", "检查点数", "硬校验", "数据根数", "备注"])
        for r in rows:
            w.writerow([r["score"] if r["score"] is not None else "",
                        r["industry"], r["code"], r["name"], r["scale_yi"],
                        r["stats_1y"]["ret_pct"], r["stats_1y"]["ann_vol"],
                        r["stats_1y"]["max_dd"], r["stats_1y"]["avg_amt_yi"],
                        r["snap"]["trend"], "是" if r["snap"]["macd_golden"] else "否",
                        r["snap"]["rsi12"], r["snap"]["kdj_k"], r["snap"]["pctb"],
                        r["snap"]["adx"],
                        {1: "看多", -1: "看空", 0: "中性"}[r["dir_b_now"]], r["score_b_now"],
                        {1: "做多", -1: "做空", 0: "观望"}[r["sig_a_now"]],
                        g(r, "sim_a", "strategy_ret"), g(r, "sim_a", "excess"),
                        g(r, "sim_a", "strategy_maxdd"), g(r, "sim_a", "buyhold_maxdd"),
                        g(r, "sim_b", "strategy_ret"), g(r, "sim_b", "excess"),
                        g(r, "sim_b", "strategy_maxdd"),
                        r["eval_a_n20"]["dir_hit"] if r.get("eval_a_n20") else "",
                        r["eval_b_n20"]["dir_hit"] if r.get("eval_b_n20") else "",
                        r["n_checkpoints"],
                        "PASS" if r["verify_passed"] else ("未回测" if r["verify_passed"] is None else "FAIL"),
                        r["stats_2y"]["n_days"], r.get("note", "")])

    # ---------- HTML ----------
    def fmt(v, suffix="", nd=2):
        if v is None:
            return "—"
        return ("%." + str(nd) + "f%s") % (v, suffix)

    trs = []
    for i, r in enumerate(rows, 1):
        if r.get("sim_a"):
            cls_a = "up" if r["sim_a"]["excess"] > 0 else "down"
            cls_b = "up" if r["sim_b"]["excess"] > 0 else "down"
            ex_a, ex_b = "%+.2f%%" % r["sim_a"]["excess"], "%+.2f%%" % r["sim_b"]["excess"]
            hit_b = fmt(r["eval_b_n20"]["dir_hit"], "", 1) + "%"
        else:
            cls_a = cls_b = "flat"
            ex_a = ex_b = "—"
            hit_b = "—"
        cls_r = "up" if r["stats_1y"]["ret_pct"] > 0 else "down"
        dir_txt = {1: "看多", -1: "看空", 0: "中性"}[r["dir_b_now"]]
        dir_cls = {1: "up", -1: "down", 0: "flat"}[r["dir_b_now"]]
        score_txt = "%.1f" % r["score"] if r["score"] is not None else "未回测"
        trs.append("""<tr>
  <td class="num">%d</td><td class="ind">%s</td><td class="code">%s</td><td class="nm">%s</td>
  <td class="num">%s</td><td class="num %s">%s%%</td><td class="num">%s%%</td><td class="num">%s%%</td>
  <td class="num">%s</td><td class="sig %s">%s</td><td class="num">%s</td>
  <td class="num %s">%s</td><td class="num %s">%s</td>
  <td class="num">%s</td><td class="score">%s</td>
</tr>""" % (
            i, r["industry"], r["code"], r["name"], fmt(r["scale_yi"], "亿", 1),
            cls_r, fmt(r["stats_1y"]["ret_pct"], "", 2),
            fmt(r["stats_1y"]["ann_vol"], "", 1), fmt(r["stats_1y"]["max_dd"], "", 1),
            fmt(r["stats_1y"]["avg_amt_yi"], "亿", 2),
            dir_cls, dir_txt, r["score_b_now"],
            cls_a, ex_a, cls_b, ex_b, hit_b, score_txt))

    def case_rows(sel):
        out = []
        for r in sel:
            if r.get("sim_a"):
                tail = "｜ 规则A超额 %+.2f%% / 规则B超额 %+.2f%%" % (r["sim_a"]["excess"], r["sim_b"]["excess"])
            else:
                tail = "｜ 次新未回测"
            out.append("<li><b>%s</b>（%s，%s）：综合分 %s ｜ 近1年 %s%%%s ｜ 当前信号「%s」%s</li>"
                       % (r["name"], r["code"], r["industry"],
                          ("%.1f" % r["score"]) if r["score"] is not None else "—",
                          fmt(r["stats_1y"]["ret_pct"]), tail,
                          {1: "看多", -1: "看空", 0: "中性"}[r["dir_b_now"]],
                          "（%s）" % r["note"] if r.get("note") else ""))
        return "".join(out)

    top5 = rows[:5]
    bot5 = [r for r in rows if r["score"] is not None][-5:]
    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>62只行业ETF全面验证报告</title>
<style>
 *{margin:0;padding:0;box-sizing:border-box}
 body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f6f8;color:#1f2329;padding:26px 18px}
 .wrap{max-width:1240px;margin:0 auto}
 header,.box{background:#fff;border-radius:12px;padding:24px 28px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
 h1{font-size:23px;margin-bottom:10px}
 h2{font-size:17px;margin-bottom:12px;border-left:4px solid #d54941;padding-left:10px}
 .meta{color:#646a73;font-size:13px;line-height:1.8}
 .cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0 4px}
 .stat{background:#f2f3f5;border-radius:10px;padding:13px 16px}
 .stat .v{font-size:21px;font-weight:700;color:#d54941}
 .stat .k{font-size:12px;color:#646a73;margin-top:2px}
 table{width:100%;border-collapse:collapse;font-size:12.5px}
 th{text-align:left;color:#646a73;font-weight:500;padding:7px 5px;border-bottom:1px solid #ebedf0;white-space:nowrap}
 td{padding:7px 5px;border-bottom:1px solid #f2f3f5;white-space:nowrap}
 tr:last-child td{border-bottom:none}
 .num{font-family:Consolas,monospace}
 .code{font-family:Consolas,monospace;color:#3370ff}
 .ind{font-weight:600}.nm{white-space:nowrap}
 .up{color:#d54941}.down{color:#2ea44f}.flat{color:#8f959e}
 .sig{font-weight:600}
 .score{font-family:Consolas,monospace;font-weight:700;color:#3370ff}
 .flow{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}
 .step{background:#eef3ff;border:1px solid #d6e2ff;color:#2b4a8f;border-radius:8px;padding:8px 12px;font-size:12.5px}
 .arrow{align-self:center;color:#8f959e}
 ol,ul{padding-left:20px;line-height:2}
 footer{color:#8f959e;font-size:12px;line-height:1.9;padding:8px 6px 26px}
 @media(max-width:900px){.cards{grid-template-columns:repeat(2,1fr)}}
</style></head><body><div class="wrap">
<header>
 <h1>62 只行业 ETF 全面验证报告（技术指标 + 无未来函数回测）</h1>
 <div class="meta">验证窗口：<b>__WIN__</b>（242 个检查点/只，次新 ETF 检查点相应减少）｜
 行情区间 2024-09-02 ~ 2026-10-23 ｜ 成本：单边 0.05% ｜ 信号 T 日收盘形成、T+1 生效</div>
 <div class="cards">
  <div class="stat"><div class="v">__N__</div><div class="k">验证标的数</div></div>
  <div class="stat"><div class="v">__NVER__/__N__</div><div class="k">无未来函数硬校验通过</div></div>
  <div class="stat"><div class="v">__BEATA__ / __BEATB__</div><div class="k">跑赢买入持有（规则A / 规则B）</div></div>
  <div class="stat"><div class="v">__AVGEX__% / __AVGEXB__%</div><div class="k">平均超额（规则A / 规则B）</div></div>
 </div>
 <div class="flow">
  <span class="step">① fetch_kline（多源容错日K）</span><span class="arrow">→</span>
  <span class="step">② indicators（因果指标）</span><span class="arrow">→</span>
  <span class="step">③ judge（规则A三维投票 / 规则B多因子）</span><span class="arrow">→</span>
  <span class="step">④ pit_backtest（截断重算 + 硬校验 + 策略模拟）</span>
 </div>
 <div class="meta">无未来函数三重保证：结构上每个检查点从原始行情重新截断重算（不引用全量指标表）；
 算法上全部为 rolling/ewm/shift 因果计算；硬校验抽样对比「截断重算 vs 全量计算」逐列一致
 （本批 __NVER__ 只通过、__NA__ 只次新未回测，最大相对偏差 __MAXREL__）。</div>
</header>

<div class="box"><h2>综合验证排名（按综合分排序）</h2>
<table><thead><tr>
<th>#</th><th>行业</th><th>代码</th><th>名称</th><th>规模</th><th>近1年收益</th><th>年化波动</th>
<th>近1年回撤</th><th>日均成交额</th><th>当前信号B</th><th>B评分</th>
<th>规则A超额</th><th>规则B超额</th><th>20日方向胜率B</th><th>综合分</th>
</tr></thead><tbody>__ROWS__</tbody></table></div>

<div class="box"><h2>重点案例</h2>
<h3 style="font-size:14px;margin-bottom:6px">综合分最高 5 只</h3><ol>__TOP__</ol>
<h3 style="font-size:14px;margin:14px 0 6px">综合分最低 5 只</h3><ol>__BOT__</ol></div>

<div class="box"><h2>解读与局限</h2>
<ul>
<li><b>超额来源</b>：与指数结论一致——规则的超额主要来自回避主跌段（空头排列/超买时离场），而非精准抄底；做多信号胜率普遍低于做空信号。</li>
<li><b>规则B评分</b>是慢变量（均线/MACD/RSI 组合），适合中期择时；规则A三维投票更敏感但假信号更多，两者共振时置信度更高。</li>
<li><b>样本局限</b>：单窗口（近1年）回测、每只约 242 个检查点，统计显著性有限；不同行业波动率差异大（年化 20%~60%），横向比较需结合波动与回撤列。</li>
<li><b>次新 ETF</b>：159075（65 根）、158050（20 根）上市晚、无有效检查点未回测；159257（300 根）、560710（169 根）历史较短，检查点与回统计量偏少，结论仅供参考。</li>
<li><b>规模口径</b>：净资产规模为 2026-06-30 披露值；日均成交额为近1年均值。</li>
</ul></div>

<footer>数据来源：东方财富/腾讯行情接口（fetch_kline 多源容错）｜生成时间：2026-10-24｜
本报告为量化方法验证，不构成投资建议。</footer>
</div></body></html>"""

    max_rel = max((r.get("verify_max_rel") or 0) for r in rows)
    html = (html
            .replace("__WIN__", "%s ~ %s" % (d["meta"]["win_start"], d["meta"]["win_end"]))
            .replace("__N__", str(n))
            .replace("__NVER__", str(n_ver)).replace("__NA__", str(n_na))
            .replace("__BEATA__", str(beat_a)).replace("__BEATB__", str(beat_b))
            .replace("__AVGEX__", "%.2f" % avg_ex_a).replace("__AVGEXB__", "%.2f" % avg_ex_b)
            .replace("__MAXREL__", "%.1e" % max_rel)
            .replace("__ROWS__", "".join(trs))
            .replace("__TOP__", case_rows(top5)).replace("__BOT__", case_rows(bot5)))
    out = os.path.join(OUT_DIR, "ETF全面验证报告.html")
    with open(out, "w", encoding="utf-8") as fp:
        fp.write(html)
    print("written:", out)
    print("written:", csv_path)
    print("rows: %d | verify PASS: %d | beat A: %d | beat B: %d | avg excess A: %.2f%% B: %.2f%%"
          % (n, n_ver, beat_a, beat_b, avg_ex_a, avg_ex_b))
    print("\nTop5:")
    for r in top5:
        print("  %.1f  %-14s %-12s 1y=%+.1f%%  exA=%+.1f%% exB=%+.1f%%  信号=%s"
              % (r["score"], r["industry"], r["code"], r["stats_1y"]["ret_pct"],
                 r["sim_a"]["excess"], r["sim_b"]["excess"],
                 {1: "多", -1: "空", 0: "中"}[r["dir_b_now"]]))
    print("Bottom5:")
    for r in bot5:
        print("  %.1f  %-14s %-12s 1y=%+.1f%%  exA=%+.1f%% exB=%+.1f%%  信号=%s"
              % (r["score"], r["industry"], r["code"], r["stats_1y"]["ret_pct"],
                 r["sim_a"]["excess"], r["sim_b"]["excess"],
                 {1: "多", -1: "空", 0: "中"}[r["dir_b_now"]]))


if __name__ == "__main__":
    main()

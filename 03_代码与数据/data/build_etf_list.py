# -*- coding: utf-8 -*-
"""生成《A股行业ETF全景清单》HTML：按大类分组的 62 个行业旗舰 ETF。"""
import json, os

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(BASE), "行业ETF全景清单.html")

LABEL_OVERRIDE = {
    "航空机场": "通用航空/低空",
    "航运港口": "船舶/航运",
    "环保": "环保/碳中和",
    "金融地产": "金融(非银)",
    "电力公用": "电力/公用",
    "医药生物": "医药/医疗",
}
SECTOR_ORDER = ["金融地产", "TMT", "半导体/电子", "医药", "大消费", "新能源",
                "周期", "制造", "农业", "运输", "公用事业"]
SECTOR_NAMES = {
    "金融地产": "金融地产", "TMT": "TMT 科技", "半导体/电子": "半导体 / 电子",
    "医药": "医药", "大消费": "大消费", "新能源": "新能源", "周期": "周期资源",
    "制造": "先进制造", "农业": "农业", "运输": "运输物流", "公用事业": "公用事业",
}

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>A股行业ETF全景清单（62个行业）</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:"PingFang SC","Microsoft YaHei",sans-serif; background:#f5f6f8;
         color:#1f2329; padding:28px 20px; }
  .wrap { max-width:1080px; margin:0 auto; }
  header { background:#fff; border-radius:12px; padding:26px 30px; margin-bottom:18px;
           box-shadow:0 1px 3px rgba(0,0,0,.06); }
  h1 { font-size:24px; margin-bottom:8px; }
  .meta { color:#646a73; font-size:13px; line-height:1.7; }
  .cards { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:18px 0 6px; }
  .stat { background:#f2f3f5; border-radius:10px; padding:14px 16px; }
  .stat .v { font-size:22px; font-weight:700; color:#d54941; }
  .stat .k { font-size:12px; color:#646a73; margin-top:2px; }
  .top5 { background:#fff; border-radius:12px; padding:18px 24px; margin-bottom:18px;
          box-shadow:0 1px 3px rgba(0,0,0,.06); font-size:14px; }
  .top5 h3 { font-size:15px; margin-bottom:8px; }
  .top5 ol { padding-left:20px; line-height:1.9; }
  .sec { background:#fff; border-radius:12px; padding:20px 24px; margin-bottom:16px;
         box-shadow:0 1px 3px rgba(0,0,0,.06); }
  .sec h2 { font-size:17px; margin-bottom:12px; border-left:4px solid #d54941;
            padding-left:10px; }
  .cnt { font-size:12px; color:#8f959e; font-weight:400; margin-left:8px; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th { text-align:left; color:#646a73; font-weight:500; padding:8px 6px;
       border-bottom:1px solid #ebedf0; white-space:nowrap; }
  td { padding:9px 6px; border-bottom:1px solid #f2f3f5; vertical-align:middle; }
  tr:last-child td { border-bottom:none; }
  tr.low td { background:#fffaf0; }
  .ind { font-weight:600; white-space:nowrap; }
  .code { font-family:Consolas,monospace; color:#3370ff; white-space:nowrap; }
  .nm { white-space:nowrap; }
  .idx { color:#8f959e; font-size:12px; }
  .num { font-family:Consolas,monospace; }
  .sc { min-width:150px; }
  .sc .bar { display:inline-block; height:8px; background:#3370ff; border-radius:4px;
             margin-right:8px; vertical-align:middle; opacity:.75; }
  .sc span { font-family:Consolas,monospace; font-size:12px; }
  .pct { font-family:Consolas,monospace; font-weight:600; white-space:nowrap; }
  .up { color:#d54941; } .down { color:#2ea44f; } .flat { color:#8f959e; }
  .badge { font-size:10px; padding:1px 5px; border-radius:4px; margin-left:6px;
           vertical-align:middle; font-weight:400; }
  .badge.hk { background:#e8f3ff; color:#3370ff; }
  .badge.qdii { background:#fdeeea; color:#d54941; }
  footer { color:#8f959e; font-size:12px; line-height:1.8; padding:10px 6px 30px; }
  @media (max-width:760px){ .cards{grid-template-columns:repeat(2,1fr);} }
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>A股行业 ETF 全景清单 · 62 个行业各一只旗舰</h1>
  <div class="meta">
    数据来源：东方财富基金代码库（全量 28,055 只基金）+ fundf10 基金档案 + 腾讯行情接口；
    行情为 <b>2026-10-23 收盘</b>，净资产规模为最新披露期（2026-06-30）。
    筛选口径：剔除货币/债券/宽基/风格/QDII 非行业产品后，全市场共命中行业 ETF 216 只、
    覆盖 62 个行业；每个行业选规模最大者为代表（A 股优先，无 A 股产品则选港股行业 ETF）。
  </div>
  <div class="cards">
    <div class="stat"><div class="v">62</div><div class="k">覆盖行业数（含细分）</div></div>
    <div class="stat"><div class="v">216</div><div class="k">全市场行业 ETF 总数</div></div>
    <div class="stat"><div class="v">__TOTAL__ 亿</div><div class="k">62 只旗舰合计规模</div></div>
    <div class="stat"><div class="v">11</div><div class="k">行业大类</div></div>
  </div>
</header>
<div class="top5">
  <h3>规模最大的 5 只行业 ETF</h3>
  <ol>__TOP5__</ol>
</div>
__SECTIONS__
<footer>
  说明：① 「涨跌幅」红=涨、绿=跌；② 黄色底纹行表示规模 &lt; 3 亿，流动性偏差，大额进出需谨慎；
  ③ 「港股」徽标表示该行业无 A 股产品、以港股行业 ETF 代表；「QDII」为跨境产品；
  ④ 同一行业往往有多家公司产品（如证券ETF有国泰/华宝等多只），表中列规模最大者，
  完整候选见生成脚本 etf_industry.json；⑤ 规模为季末披露值，与实时规模有差异；
  ⑥ 本清单仅为信息整理，不构成投资建议。
</footer>
</div>
</body>
</html>"""


def main():
    final = json.load(open(os.path.join(BASE, "final50.json"), encoding="utf-8"))
    for f in final:
        f["label"] = LABEL_OVERRIDE.get(f["industry"], f["industry"])
        if f["code"].startswith("513"):
            f["market"] = "QDII"

    total_scale = sum(f["scale_yi"] or 0 for f in final)
    big = sorted(final, key=lambda x: -(x["scale_yi"] or 0))[:5]

    rows_html = []
    for sec in SECTOR_ORDER:
        group = [f for f in final if f["sector"] == sec]
        if not group:
            continue
        group.sort(key=lambda x: -(x["scale_yi"] or 0))
        cards = []
        for f in group:
            pct = f["pct"]
            cls = "up" if (pct or 0) > 0 else ("down" if (pct or 0) < 0 else "flat")
            arrow = "▲" if (pct or 0) > 0 else ("▼" if (pct or 0) < 0 else "—")
            scale = f["scale_yi"] or 0
            liq = "low" if scale < 3 else ""
            badge = {"A股": "", "港股": "hk", "QDII": "qdii"}.get(f["market"], "")
            badge_html = ('<span class="badge %s">%s</span>' % (badge, f["market"])) if badge else ""
            bar_w = max(4, min(100, scale / 700 * 100))
            cards.append("""
      <tr class="%s">
        <td class="ind">%s%s</td>
        <td class="code">%s</td>
        <td class="nm">%s</td>
        <td class="idx">%s</td>
        <td class="num">%.2f</td>
        <td class="sc"><div class="bar" style="width:%.0f%%"></div><span>%s亿</span></td>
        <td class="pct %s">%s %s%%</td>
      </tr>""" % (liq, f["label"], badge_html, f["code"], f["name"],
                  f.get("index") or "—", f["price"] or 0, bar_w,
                  ("%.1f" % scale) if scale else "—", cls, arrow,
                  ("%+.2f" % pct) if pct is not None else "—"))
        rows_html.append("""
  <section class="sec">
    <h2>%s <span class="cnt">%d 个行业</span></h2>
    <table>
      <thead><tr><th>行业</th><th>代码</th><th>ETF 名称</th><th>跟踪指数</th>
      <th>最新价</th><th>净资产规模</th><th>涨跌幅</th></tr></thead>
      <tbody>%s
      </tbody>
    </table>
  </section>""" % (SECTOR_NAMES.get(sec, sec), len(group), "".join(cards)))

    top_html = "".join(
        '<li><b>%s</b>（%s，%s）：%.0f 亿</li>' % (f["name"], f["code"], f["label"], f["scale_yi"] or 0)
        for f in big)

    html = (TEMPLATE
            .replace("__TOTAL__", "%.0f" % total_scale)
            .replace("__TOP5__", top_html)
            .replace("__SECTIONS__", "".join(rows_html)))

    with open(OUT, "w", encoding="utf-8") as fp:
        fp.write(html)
    print("written:", OUT, len(html), "bytes")


if __name__ == "__main__":
    main()

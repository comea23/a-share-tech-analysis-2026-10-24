# -*- coding: utf-8 -*-
"""为每个行业选旗舰 ETF：拉取净资产规模（fundf10 jbgk）+ 最新行情（腾讯 qt）。
输出 final50.json：每个行业 1 只旗舰（优先 A 股、规模最大）。
"""
import json, re, os, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))


def get(url, timeout=30, retries=3, encoding="utf-8"):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode(encoding, "ignore")
        except Exception:
            time.sleep(1.0 + i)
    return None


def fetch_scale(code):
    h = get("https://fundf10.eastmoney.com/jbgk_%s.html" % code)
    if not h:
        return code, None, None, None
    m = re.search(r"净资产规模：<span>\s*([\d.]+)(亿|万)元\s*（截止至：([\d-]+)）", h)
    val = dt = None
    if m:
        val = float(m.group(1))
        if m.group(2) == "万":
            val /= 10000.0
        dt = m.group(3)
    idx = re.search(r"跟踪标的</th><td[^>]*>([^<]+)</td>", h)
    return code, val, dt, (idx.group(1).strip() if idx else None)


def fetch_quotes(codes):
    """腾讯 qt 批量行情，返回 {code: (price, pct)}"""
    out = {}
    B = 40
    for i in range(0, len(codes), B):
        batch = codes[i:i + B]
        qs = []
        for c in batch:
            qs.append(("sh" if c[0] == "5" else "sz") + c)
        txt = get("https://qt.gtimg.cn/q=" + ",".join(qs), timeout=25, encoding="gbk")
        if not txt:
            continue
        for line in txt.strip().split(";"):
            m = re.match(r'v_(\w+)="(.*)"', line.strip())
            if not m:
                continue
            p = m.group(2).split("~")
            if len(p) > 45:
                out[m.group(1)[2:]] = (float(p[3]), float(p[32]))
        time.sleep(0.3)
    return out


def main():
    items = json.load(open(os.path.join(BASE, "etf_industry.json"), encoding="utf-8"))
    codes = [x["code"] for x in items]
    print("fetching scale for %d ETFs..." % len(codes))
    scales = {}
    pending = list(codes)
    for rnd in range(3):
        if not pending:
            break
        nxt = []
        with ThreadPoolExecutor(max_workers=6) as ex:
            for code, val, dt, idx in ex.map(fetch_scale, pending):
                scales[code] = {"scale_yi": val, "scale_date": dt, "index": idx}
                if val is None:
                    nxt.append(code)
        if nxt:
            print("  round %d: %d failed, retrying..." % (rnd + 1, len(nxt)))
            pending = nxt
    print("scale fetched:", sum(1 for c in codes if scales.get(c, {}).get("scale_yi")), "/", len(codes))
    print("fetching quotes...")
    quotes = fetch_quotes(codes)
    print("quotes got:", len(quotes))

    # 组装：行业 -> 候选（含规模/行情）
    by_ind = {}
    for x in items:
        sc = scales.get(x["code"], {})
        q = quotes.get(x["code"])
        rec = dict(x)
        rec["scale_yi"] = sc.get("scale_yi")
        rec["scale_date"] = sc.get("scale_date")
        rec["index"] = sc.get("index")
        rec["price"] = q[0] if q else None
        rec["pct"] = q[1] if q else None
        by_ind.setdefault(x["industry"], []).append(rec)

    # 人工校正：航空机场桶被“通用航空ETF”（低空概念）占据，
    # 代表性选择“航空ETF”（对应航空运输/机场行业）
    OVERRIDE = {"航空机场": "159257"}

    final = []
    for ind, cands in by_ind.items():
        if ind in OVERRIDE:
            pick = next((c for c in cands if c["code"] == OVERRIDE[ind]), None)
            if pick:
                pick = dict(pick)
                pick["n_candidates"] = len(cands)
                final.append(pick)
                continue
        a = [c for c in cands if c["market"] == "A股" and c["scale_yi"]]
        hk = [c for c in cands if c["market"] == "港股" and c["scale_yi"]]
        pool = a or hk or cands
        pool = sorted(pool, key=lambda c: -(c["scale_yi"] or 0))
        best = pool[0]
        best["n_candidates"] = len(cands)
        best["market"] = best.get("market") or "A股"
        final.append(best)
    final.sort(key=lambda x: (x["sector"], x["industry"]))
    json.dump(final, open(os.path.join(BASE, "final50.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("final industries:", len(final))
    for f in final:
        print("  %-10s %-12s %s %s 规模=%s亿 价=%s (%s%%)" % (
            f["sector"], f["industry"], f["code"], f["name"],
            f["scale_yi"], f["price"], f["pct"]))


if __name__ == "__main__":
    main()

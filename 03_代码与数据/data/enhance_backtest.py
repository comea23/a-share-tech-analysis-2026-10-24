# -*- coding: utf-8 -*-
"""回测结果二次加工：分阶段统计 + 重点检查点「当时判断 vs 后续实际」对照。"""
import json
import os

import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))


def phase_of(ts):
    m = ts.month
    if ts.year == 2025:
        return "2025Q4"
    if m <= 3:
        return "2026Q1"
    if m <= 6:
        return "2026Q2"
    if m <= 9:
        return "2026Q3"
    return "2026Q4"


def enhance(sym_data):
    recs = pd.DataFrame(sym_data["records"])
    recs["date"] = pd.to_datetime(recs["date"])
    recs = recs.set_index("date").sort_index()
    recs["phase"] = [phase_of(d) for d in recs.index]

    # ---- 分阶段统计 ----
    phases = []
    for ph, g in recs.groupby("phase"):
        row = {"phase": ph, "days": int(len(g)),
               "close_start": round(float(g["close"].iloc[0]), 2),
               "close_end": round(float(g["close"].iloc[-1]), 2)}
        for n in (5, 10, 20):
            col = "ret%d" % n
            sub = g[g[col].notna()]
            if not len(sub):
                continue
            b, s = sub[sub["dir_b"] == 1], sub[sub["dir_b"] == -1]
            row["b%d_n" % n] = int(len(b))
            row["b%d_hit" % n] = round(float((b[col] > 0).mean() * 100), 1) if len(b) else None
            row["b%d_avg" % n] = round(float(b[col].mean()), 2) if len(b) else None
            row["s%d_n" % n] = int(len(s))
            row["s%d_hit" % n] = round(float((s[col] < 0).mean() * 100), 1) if len(s) else None
            row["s%d_avg" % n] = round(float(s[col].mean()), 2) if len(s) else None
        phases.append(row)

    # ---- 重点检查点：信号翻转 + 极值 + 月末 + 指定关键日 ----
    key_dates = []
    # 规则B方向翻转日
    prev = None
    for d, r in recs.iterrows():
        if prev is not None and r["dir_b"] != prev:
            key_dates.append(d)
        prev = r["dir_b"]
    # score 极值
    key_dates += list(recs["score_b"].nlargest(2).index)
    key_dates += list(recs["score_b"].nsmallest(2).index)
    # 每月最后检查点
    for per, g in recs.groupby(recs.index.to_period("M")):
        key_dates.append(g.index[-1])
    # 指定关键日
    for ds in ("2026-06-30", "2026-10-22", "2026-10-23", "2026-04-27"):
        dt = pd.Timestamp(ds)
        if dt in recs.index:
            key_dates.append(dt)
    key_dates = sorted(set(key_dates))

    points = []
    for d in key_dates:
        r = recs.loc[d]
        points.append({
            "date": d.strftime("%Y-%m-%d"),
            "close": round(float(r["close"]), 2),
            "sig_a": int(r["sig_a"]),
            "dir_b": int(r["dir_b"]),
            "score_b": float(r["score_b"]),
            "reasons": r["reasons_b"][:4],
            "ret5": None if pd.isna(r["ret5"]) else round(float(r["ret5"]), 2),
            "ret10": None if pd.isna(r["ret10"]) else round(float(r["ret10"]), 2),
            "ret20": None if pd.isna(r["ret20"]) else round(float(r["ret20"]), 2),
        })
    return {"phases": phases, "key_points": points}


def main():
    with open(os.path.join(BASE, "backtest_result.json"), encoding="utf-8") as f:
        res = json.load(f)
    out = {"meta": res["meta"]}
    for sym in ("hs300", "kc50"):
        if sym not in res:
            continue
        e = enhance(res[sym])
        e["eval_a"] = res[sym]["eval_a"]
        e["eval_b"] = res[sym]["eval_b"]
        e["sim_a"] = res[sym]["sim_a"]
        e["sim_b"] = res[sym]["sim_b"]
        e["verify"] = res[sym]["verify"]
        out[sym] = e
        print("[%s] 阶段数 %d, 重点检查点 %d" % (sym, len(e["phases"]), len(e["key_points"])))
        for p in e["phases"]:
            print("  %s days=%d close %.0f->%.0f b5_hit=%s b5_avg=%s" % (
                p["phase"], p["days"], p["close_start"], p["close_end"],
                p.get("b5_hit"), p.get("b5_avg")))
    with open(os.path.join(BASE, "backtest_enhanced.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("已写出 backtest_enhanced.json")


if __name__ == "__main__":
    main()

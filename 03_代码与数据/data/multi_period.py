# -*- coding: utf-8 -*-
"""多周期验证：60 分钟 vs 日线的信息增益。

回答三个问题:
  1. 60 分钟信号比日线信号提前多少天？（MACD 金叉/死叉、RSI 超卖进入）
  2. 用 60 分钟指标在每日 15:00 决策，方向胜率是否高于日线指标？
  3. 关键转折日（2026-06-30 顶 / 2026-10-22 底）在 60 分钟上的微观形态。
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from indicators import compute_all
from judge import rule_b_score

BASE = os.path.dirname(os.path.abspath(__file__))


def load_sina60(fname):
    """新浪 60 分钟：day, open, high, low, close, volume, amount。"""
    with open(os.path.join(BASE, fname), encoding="utf-8") as f:
        rows = json.load(f)
    df = pd.DataFrame(rows)
    df["day"] = pd.to_datetime(df["day"])
    for c in ("open", "high", "low", "close", "volume", "amount"):
        df[c] = df[c].astype(float)
    return df.set_index("day").sort_index()


def load_em_day(fname):
    with open(os.path.join(BASE, fname), encoding="utf-8") as f:
        j = json.load(f)
    rows = []
    for k in j["data"]["klines"]:
        p = k.split(",")
        rows.append(dict(date=p[0], open=float(p[1]), close=float(p[2]),
                         high=float(p[3]), low=float(p[4]), volume=float(p[5])))
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def cross_events(ind, key="macd_cross"):
    """MACD 金叉(1)/死叉(-1) 事件序列。"""
    d = ind["dif"] - ind["dea"]
    sig = np.sign(d)
    ev = (sig - sig.shift(1)) / 2  # +1 金叉, -1 死叉
    return ev[ev != 0].dropna()


def rsi_events(ind, col="rsi12", lo=30, hi=70):
    r = ind[col]
    enter_os = ((r < lo) & (r.shift(1) >= lo))
    enter_ob = ((r > hi) & (r.shift(1) <= hi))
    return enter_os[enter_os].index, enter_ob[enter_ob].index


def main():
    out = {"meta": {"scale": "60m vs 1D", "source": "新浪 60 分钟 / 东财日线"}}
    for sym, m60f, df_ in (("hs300", "sina_hs300_60m.txt", "hs300.json"),
                           ("kc50", "sina_kc50_60m.txt", "kc50.json")):
        m60 = load_sina60(m60f)
        day = load_em_day(df_)
        # 日线只取 60 分钟覆盖区间
        day = day[day.index >= m60.index[0].normalize()]

        ind_d = compute_all(day)
        ind_h = compute_all(m60)

        # ---- 1. 收盘价一致性校验 ----
        m60_daily_close = m60["close"].groupby(m60.index.normalize()).last()
        cmp = pd.DataFrame({"d": day["close"], "h": m60_daily_close}).dropna()
        max_dev = float((cmp["d"] - cmp["h"]).abs().max())

        # ---- 2. MACD 事件提前量 ----
        ev_d = cross_events(ind_d)
        ev_h = cross_events(ind_h)
        leads = []
        for dt, v in ev_h.items():
            if v != 1:
                continue
            later = ev_d[(ev_d.index > dt) & (ev_d == 1)]
            if len(later):
                lead_days = (later.index[0] - dt).days
                leads.append({"h_time": dt.strftime("%Y-%m-%d %H:%M"),
                              "d_date": later.index[0].strftime("%Y-%m-%d"),
                              "lead_days": int(lead_days)})
        leads_df = pd.DataFrame(leads) if leads else pd.DataFrame()
        lead_stats = {}
        if len(leads_df):
            lead_stats = {
                "n_pairs": int(len(leads_df)),
                "lead_median": float(leads_df["lead_days"].median()),
                "lead_mean": round(float(leads_df["lead_days"].mean()), 1),
                "lead_max": int(leads_df["lead_days"].max()),
                "lead_min": int(leads_df["lead_days"].min()),
                "le0_ratio": round(float((leads_df["lead_days"] <= 0).mean() * 100), 1),
            }

        # ---- 3. 每日 15:00 检查点：60min 指标判断 vs 日线指标判断 ----
        dates = sorted(set(d.normalize() for d in m60.index))
        dates = [d for d in dates if d in day.index]
        recs = []
        for T in dates:
            if day.index.get_loc(T) < 120:
                continue
            hist_h = m60[m60.index <= T + pd.Timedelta(hours=23, minutes=59)]
            hist_d = day[day.index <= T]
            _, s_h, _ = rule_b_score(compute_all(hist_h))
            dir_h = 1 if s_h >= 15 else (-1 if s_h <= -15 else 0)
            dir_d, s_d, _ = rule_b_score(compute_all(hist_d))
            # 前向收益
            loc = day.index.get_loc(T)
            r5 = float(day["close"].iloc[min(loc + 5, len(day) - 1)] / day["close"].iloc[loc] - 1) if loc + 5 < len(day) else None
            r10 = float(day["close"].iloc[min(loc + 10, len(day) - 1)] / day["close"].iloc[loc] - 1) if loc + 10 < len(day) else None
            r20 = float(day["close"].iloc[min(loc + 20, len(day) - 1)] / day["close"].iloc[loc] - 1) if loc + 20 < len(day) else None
            recs.append({"date": T.strftime("%Y-%m-%d"), "score_h": round(s_h, 1), "dir_h": dir_h,
                         "score_d": round(s_d, 1), "dir_d": dir_d,
                         "r5": None if r5 is None else round(r5 * 100, 2),
                         "r10": None if r10 is None else round(r10 * 100, 2),
                         "r20": None if r20 is None else round(r20 * 100, 2)})
        rec = pd.DataFrame(recs)
        # 双确认：两者同向才算信号
        rec["dir_both"] = np.where(rec["dir_h"] == rec["dir_d"], rec["dir_d"], 0)
        cmp_stats = {}
        for key, name in (("dir_h", "60分钟"), ("dir_d", "日线"), ("dir_both", "双确认")):
            for n in (5, 20):
                col = "r%d" % n
                sub = rec[rec[col].notna()]
                b = sub[sub[key] == 1]
                s = sub[sub[key] == -1]
                cmp_stats["%s_n%d" % (name, n)] = {
                    "bull_n": int(len(b)),
                    "bull_hit": round(float((b[col] > 0).mean() * 100), 1) if len(b) else None,
                    "bull_avg": round(float(b[col].mean()), 2) if len(b) else None,
                    "bear_n": int(len(s)),
                    "bear_hit": round(float((s[col] < 0).mean() * 100), 1) if len(s) else None,
                    "bear_avg": round(float(s[col].mean()), 2) if len(s) else None,
                }

        # ---- 4. 关键转折日微观形态 ----
        cases = {}
        for case_day in ("2026-06-30", "2026-10-22", "2026-10-23"):
            d0 = pd.Timestamp(case_day)
            seg = m60[(m60.index >= d0) & (m60.index < d0 + pd.Timedelta(days=1))]
            if len(seg):
                cases[case_day] = {
                    "n_bars": int(len(seg)),
                    "open": round(float(seg["open"].iloc[0]), 2),
                    "close": round(float(seg["close"].iloc[-1]), 2),
                    "chg_pct": round(float(seg["close"].iloc[-1] / seg["open"].iloc[0] * 100 - 100), 2),
                    "intraday_low": round(float(seg["low"].min()), 2),
                    "intraday_high": round(float(seg["high"].max()), 2),
                    # A股60分钟K每日4根(9:30-10:30/10:30-11:30/13:00-14:00/14:00-15:00)，尾盘=最后一根
                    "late_session_chg": round(float(seg["close"].iloc[-1] / seg["close"].iloc[-2] * 100 - 100), 2)
                    if len(seg) >= 2 else None,
                }

        out[sym] = {
            "close_dev_max": round(max_dev, 4),
            "macd_lead": lead_stats,
            "lead_pairs": leads[:12],
            "cmp": cmp_stats,
            "cases": cases,
            "n_checkpoints": int(len(rec)),
        }
        print("=" * 70)
        print("[%s] 60分钟覆盖 %s ~ %s（%d 根），日线校验最大偏差 %.4f" % (
            sym, m60.index[0].strftime("%Y-%m-%d %H:%M"), m60.index[-1].strftime("%Y-%m-%d %H:%M"),
            len(m60), max_dev))
        print("  MACD金叉提前量: %s" % json.dumps(lead_stats, ensure_ascii=False))
        for k, v in cmp_stats.items():
            print("  %-14s %s" % (k, json.dumps(v, ensure_ascii=False)))
        print("  关键日微观: %s" % json.dumps(cases, ensure_ascii=False))

    with open(os.path.join(BASE, "multi_period.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\n已写出 multi_period.json")


if __name__ == "__main__":
    main()

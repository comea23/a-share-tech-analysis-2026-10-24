# -*- coding: utf-8 -*-
"""国家队资金行为分析（沪深300方向）。

重要前提（必须在任何结论中声明）：
    国家队（中央汇金、证金等）的操作没有官方实时披露。本工具只用公开代理指标
    做「行为特征匹配」推断，不声称知晓真实持仓与身份。

代理指标（5 类）:
  1. 指数资金流（东财 fflow）：超大单/大单/主力净流入的异常放大
  2. ETF 成交异动：4 只沪深300ETF 合计成交额 vs 20 日均量
  3. 尾盘行为（510300 五分钟线）：尾盘 30 分钟成交占比、尾盘涨跌、收盘位置
  4. ETF 相对强弱：指数急跌日 ETF 是否抗跌（承接）
  5. 量价形态：急跌日放量下影（承接）vs 上涨日缩量（无承接）

国家队行为判型:
  - 买入托底：指数急跌日 + ETF 放量 + 超大单净流入 + 尾盘拉升/抗跌
  - 拉高派发：指数上涨日 + ETF 缩量/超大单净流出 + 尾盘冲高回落
  - 无明显操作
"""
import json
import os
import sys

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
ETFS = ["tc_etf510300", "tc_etf510330", "tc_etf510310", "tc_etf159919"]
ETF_NAMES = {"tc_etf510300": "华泰柏瑞300ETF", "tc_etf510330": "华夏300ETF",
             "tc_etf510310": "易方达300ETF", "tc_etf159919": "嘉实300ETF"}


def load_em_day(fname):
    with open(os.path.join(BASE, fname), encoding="utf-8") as f:
        j = json.load(f)
    rows = []
    for k in j["data"]["klines"]:
        p = k.split(",")
        rows.append(dict(date=p[0], open=float(p[1]), close=float(p[2]),
                         high=float(p[3]), low=float(p[4]), volume=float(p[5]),
                         amount=float(p[6]), pct=float(p[8])))
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def load_tc_etf(fname):
    with open(os.path.join(BASE, fname + ".json"), encoding="utf-8") as f:
        j = json.load(f)
    k = list(j["data"].values())[0]
    rows = [{"date": r[0], "open": float(r[1]), "close": float(r[2]),
             "high": float(r[3]), "low": float(r[4]), "volume": float(r[5])}
            for r in k["qfqday"]]
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def load_fflow():
    with open(os.path.join(BASE, "hs300_fflow.json"), encoding="utf-8") as f:
        j = json.load(f)
    rows = []
    for k in j["data"]["klines"]:
        p = k.split(",")
        # f51 date, f52 主力, f53 小单, f54 中单, f55 大单, f56 超大单, f57 主力净占比, f58 ?
        rows.append({"date": p[0], "main": float(p[1]), "small": float(p[2]),
                     "mid": float(p[3]), "large": float(p[4]), "xlarge": float(p[5]),
                     "main_pct": float(p[6])})
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def load_tc_m5():
    with open(os.path.join(BASE, "tc_etf510300_m5.json"), encoding="utf-8") as f:
        j = json.load(f)
    k = list(j["data"].values())[0]
    rows = [{"dt": r[0], "open": float(r[1]), "close": float(r[2]),
             "high": float(r[3]), "low": float(r[4]), "volume": float(r[5])}
            for r in k["m5"]]
    df = pd.DataFrame(rows)
    df["dt"] = pd.to_datetime(df["dt"])
    return df.set_index("dt").sort_index()


def main():
    hs = load_em_day("hs300.json")
    ff = load_fflow()
    etf_d = {e: load_tc_etf(e) for e in ETFS}
    m5 = load_tc_m5()

    # ---- 1. 4 只 ETF 合计成交额（近似 amount：volume*close） ----
    amt = None
    for e, d in etf_d.items():
        v = (d["volume"] * 100 * d["close"]).rename(e)   # volume 单位：手
        amt = v if amt is None else amt.add(v, fill_value=0)
    amt = amt.dropna()
    amt_ma20 = amt.rolling(20).mean()
    etf_tab = pd.DataFrame({"amount": amt, "amount_ma20": amt_ma20})
    etf_tab["vol_mult"] = etf_tab["amount"] / etf_tab["amount_ma20"]

    # ---- 2. 尾盘行为（510300 5分钟）：尾盘 30 分钟 = 14:30 后 6 根 ----
    # 成交量单位：手（与东财日K一致），金额 = volume * 100 * close
    tail = {}
    for d, g in m5.groupby(m5.index.normalize()):
        tail_g = g[g.index >= d + pd.Timedelta(hours=14, minutes=30)]
        if len(tail_g) < 6:
            continue
        day_vol = float(g["volume"].sum())
        tail_vol = float(tail_g["volume"].sum())
        day_amt = float((g["volume"] * 100 * g["close"]).sum())
        tail_amt = float((tail_g["volume"] * 100 * tail_g["close"]).sum())
        tail[d] = {
            "tail_amt_share": tail_amt / day_amt if day_amt else None,
            "tail_chg": float(tail_g["close"].iloc[-1] / tail_g["open"].iloc[0] - 1) * 100,
            "close_pos": float((g["close"].iloc[-1] - g["low"].min()) /
                               (g["high"].max() - g["low"].min() + 1e-12)) * 100,
        }
    tail_df = pd.DataFrame(tail).T.sort_index()

    # ---- 3. 每日国家队行为评分 ----
    rows = []
    common = hs.index.intersection(etf_tab.index)
    for T in common:
        idx = hs.index.get_loc(T)
        if idx < 20:
            continue
        r = {"date": T.strftime("%Y-%m-%d"),
             "close": round(float(hs["close"].iloc[idx]), 2),
             "pct": float(hs["pct"].iloc[idx]),
             "etf_amount_yi": round(float(etf_tab["amount"].iloc[idx]) / 1e8, 1),
             "etf_vol_mult": (None if pd.isna(etf_tab["vol_mult"].iloc[idx])
                              else round(float(etf_tab["vol_mult"].iloc[idx]), 2))}
        # 资金流
        if T in ff.index:
            f = ff.loc[T]
            r["xlarge_yi"] = round(float(f["xlarge"]) / 1e8, 2)
            r["main_yi"] = round(float(f["main"]) / 1e8, 2)
            ff20 = ff.iloc[max(0, ff.index.get_loc(T) - 19):ff.index.get_loc(T) + 1]
            r["xlarge_z"] = (round(float((f["xlarge"] - ff20["xlarge"].mean())
                                         / (ff20["xlarge"].std() + 1e-9)), 2)
                             if ff20["xlarge"].std() > 0 else None)
        else:
            r["xlarge_yi"] = r["main_yi"] = r["xlarge_z"] = None
        # 尾盘
        if T in tail_df.index:
            t = tail_df.loc[T]
            r["tail_share"] = None if pd.isna(t["tail_amt_share"]) else round(float(t["tail_amt_share"]) * 100, 1)
            r["tail_chg"] = None if pd.isna(t["tail_chg"]) else round(float(t["tail_chg"]), 2)
            r["close_pos"] = None if pd.isna(t["close_pos"]) else round(float(t["close_pos"]), 1)
        else:
            r["tail_share"] = r["tail_chg"] = r["close_pos"] = None
        rows.append(r)
    daily = pd.DataFrame(rows).set_index("date")

    # ---- 4. 行为判型（阈值来自尾盘占比实际分布：正常日中位 16%，>30% 为显著放量） ----
    TAIL_HI = 30.0   # 尾盘占比显著放量阈值
    TAIL_UP = 0.2    # 尾盘拉升/杀跌判定阈值(%)

    def tail_flag_of(r):
        ts, tc, cp = r["tail_share"], r["tail_chg"], r["close_pos"]
        if ts is None or tc is None:
            return ""
        if ts > TAIL_HI and tc > TAIL_UP:
            return "尾盘放量拉升"
        if ts > TAIL_HI and tc < -TAIL_UP:
            return "尾盘放量走弱"
        if ts > TAIL_HI:
            return "尾盘显著放量"
        return ""

    daily["tail_flag"] = [tail_flag_of(r) for _, r in daily.iterrows()]

    def verdict(r):
        pct = r["pct"]
        mult = r["etf_vol_mult"]
        xl = r["xlarge_yi"]
        ts, tc, cp = r["tail_share"], r["tail_chg"], r["close_pos"]
        tail_heavy = ts is not None and ts > TAIL_HI
        tail_up = tail_heavy and tc is not None and tc > TAIL_UP
        tail_dn = tail_heavy and tc is not None and tc < -TAIL_UP
        if pct <= -1.0:
            score = 0
            if mult and mult >= 2.0:
                score += 2
            elif mult and mult >= 1.3:
                score += 1
            if tail_up and cp is not None and cp > 60:
                score += 3          # 尾盘放量拉升 + 收在高位 = 典型护盘
            elif tc is not None and tc > 0.5 and cp is not None and cp > 70:
                score += 2          # 温和尾盘拉升 + 收在高位
            if tail_dn or (cp is not None and cp < 20):
                score -= 2          # 尾盘放量杀跌/收在日内低位 = 非托底
            if xl is not None and xl > 0:
                score += 2          # 超大单净流入
            if cp is not None and cp > 70:
                score += 1          # 长下影（急跌日收高位）
            if score >= 5:
                return "买入托底特征明显"
            if score >= 2:
                return "存在承接买入迹象"
            return "无明显国家队特征"
        if pct >= 1.0:
            score = 0
            if mult and mult <= 0.8:
                score += 1          # 缩量上涨（无承接）
            if xl is not None and xl < -50:
                score += 2          # 超大单大额净流出
            elif xl is not None and xl < 0:
                score += 1
            if tail_dn:
                score += 1          # 尾盘放量回落
            if score >= 3:
                return "拉高派发特征明显"
            if score >= 2:
                return "存在派发迹象"
            return "无明显国家队特征"
        return "—（平盘日不判型）"

    daily["verdict"] = [verdict(r) for _, r in daily.iterrows()]

    # ---- 5. 汇总统计 ----
    ver_counts = daily["verdict"].value_counts().to_dict()
    # 托底日 vs 非托底日的次日/5日表现
    support = daily[daily["verdict"].str.contains("托底|承接")]
    stats = {
        "n_days": int(len(daily)),
        "verdict_counts": {k: int(v) for k, v in ver_counts.items()},
        "tail_flag_counts": {k: int(v) for k, v in daily["tail_flag"].value_counts().items()},
        "support_days": int(len(support)),
        "dist_days": int(len(daily[daily["verdict"].str.contains("派发")])),
    }
    if len(support):
        idxs = [hs.index.get_loc(pd.Timestamp(d)) for d in support.index]
        fwd5, fwd10 = [], []
        for i in idxs:
            if i + 5 < len(hs):
                fwd5.append(float(hs["close"].iloc[i + 5] / hs["close"].iloc[i] - 1) * 100)
            if i + 10 < len(hs):
                fwd10.append(float(hs["close"].iloc[i + 10] / hs["close"].iloc[i] - 1) * 100)
        stats["support_fwd5_avg"] = round(float(np.mean(fwd5)), 2) if fwd5 else None
        stats["support_fwd5_win"] = round(float(np.mean([x > 0 for x in fwd5])) * 100, 1) if fwd5 else None
        stats["support_fwd10_avg"] = round(float(np.mean(fwd10)), 2) if fwd10 else None

    # 重点日
    key_days = []
    for ds in ("2026-10-22", "2026-10-23"):
        if ds in daily.index:
            key_days.append({"date": ds, **{k: (None if pd.isna(v) else v)
                                            for k, v in daily.loc[ds].items()}})
    # 年内跌幅最大 5 日
    worst = hs["pct"].nsmallest(5)
    for d, v in worst.items():
        ds = d.strftime("%Y-%m-%d")
        if ds in daily.index:
            key_days.append({"date": ds, **{k: (None if pd.isna(v2) else v2)
                                            for k, v2 in daily.loc[ds].items()}})

    out = {
        "meta": {"asof": "2026-10-23", "flow_days": int(len(ff)),
                 "etf_days": int(len(amt)), "m5_days": int(len(tail_df)),
                 "caveat": "国家队操作无官方实时披露，以下为公开代理指标的行为特征匹配推断"},
        "stats": stats,
        "key_days": key_days,
        "daily": daily.reset_index().to_dict(orient="records"),
    }
    with open(os.path.join(BASE, "national_team.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print("=" * 72)
    print("国家队行为分析（沪深300，截至 2026-10-23）")
    print("=" * 72)
    print("统计: %s" % json.dumps(stats, ensure_ascii=False))
    print("\n近 15 个交易日明细：")
    print("%-11s %8s %7s %9s %8s %8s %8s %7s %s" % (
        "date", "close", "pct", "ETF成交(亿)", "量比", "超大单(亿)", "尾盘占比", "尾盘", "判型"))
    for d, r in daily.tail(15).iterrows():
        print("%-11s %8.1f %6.2f%% %9.1f %8s %8s %8s %7s %s" % (
            d, r["close"], r["pct"], r["etf_amount_yi"],
            r["etf_vol_mult"], r["xlarge_yi"], r["tail_share"], r["tail_chg"], r["verdict"]))
    print("\n重点日：")
    for k in key_days:
        print("  %s pct=%.2f%% ETF量比=%s 超大单=%s亿 尾盘=%s%%/%s%% -> %s" % (
            k["date"], k["pct"], k["etf_vol_mult"], k["xlarge_yi"],
            k["tail_share"], k["tail_chg"], k["verdict"]))
    print("\n已写出 national_team.json")


if __name__ == "__main__":
    main()

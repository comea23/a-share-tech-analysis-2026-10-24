# -*- coding: utf-8 -*-
"""沪深300 / 科创50 近一年技术指标计算与交叉校验。

数据源：东方财富公开行情接口（push2his.eastmoney.com）日 K，本地用 pandas 计算
MACD / RSI / KDJ / BOLL / MA / OBV / ADX / ATR，并与 westock-data 指标快照交叉校验。
"""
import json
import math
import sys

import numpy as np
import pandas as pd

sys.path.insert(
    0,
    r"D:\workbuddy\resources\app.asar.unpacked\resources\plugins\workbuddy-builtin\skills\workbuddy-finance-skill\scripts\price-action",
)
from basic_indicators import compute_rsi, compute_adx, compute_bollinger, compute_obv

BASE = r"C:\Users\Administrator\WorkBuddy\2026-10-24-19-44-35\outputs\data"

# westock-data technical 快照（domain_search 返回，2026-10-23），用于交叉校验
WESTOCK = {
    "hs300": {
        "close": 4105.33, "ma5": 4116.04, "ma10": 4169.816, "ma20": 4295.8625,
        "ma60": 4497.4065, "ma120": 4671.3371, "ma250": 4653.6806,
        "dif": -114.6044, "dea": -98.9628, "macd": -31.2831,
        "kdj_k": 20.6666, "kdj_d": 15.965, "kdj_j": 30.07,
        "rsi6": 32.0292, "rsi12": 27.7984, "rsi24": 32.0501,
        "bb_lower": 3985.85, "bb_mid": 4295.8625, "bb_upper": 4605.875,
    },
    "kc50": {
        "close": 1345.51, "ma5": 1333.254, "ma10": 1361.86, "ma20": 1472.2695,
        "ma60": 1594.3893, "ma120": 1706.6121, "ma250": 1545.1257,
        "dif": -79.1128, "dea": -69.6284, "macd": -18.9687,
        "kdj_k": 22.2277, "kdj_d": 15.4323, "kdj_j": 35.8187,
        "rsi6": 35.924, "rsi12": 31.2052, "rsi24": 35.8954,
        "bb_lower": 1213.4858, "bb_mid": 1472.2695, "bb_upper": 1731.0532,
    },
}


def load(fname):
    with open(BASE + "\\" + fname, encoding="utf-8") as f:
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


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def macd_parts(close):
    dif = ema(close, 12) - ema(close, 26)
    dea = dif.ewm(span=9, adjust=False).mean()
    return dif, dea, (dif - dea) * 2


def rsi_wilder(close, n):
    d = close.diff()
    up = d.clip(lower=0)
    dn = (-d).clip(lower=0)
    au = up.ewm(alpha=1.0 / n, adjust=False).mean()
    ad = dn.ewm(alpha=1.0 / n, adjust=False).mean()
    return 100 - 100 / (1 + au / ad)


def kdj_parts(high, low, close, n=9):
    llv = low.rolling(n).min()
    hhv = high.rolling(n).max()
    rsv = ((close - llv) / (hhv - llv) * 100).bfill()
    k_prev = d_prev = None
    K, D = [], []
    for x in rsv:
        if k_prev is None:
            k_prev = d_prev = float(x)
        else:
            k_prev = (float(x) + 2 * k_prev) / 3.0
            d_prev = (k_prev + 2 * d_prev) / 3.0
        K.append(k_prev)
        D.append(d_prev)
    K = pd.Series(K, index=close.index)
    D = pd.Series(D, index=close.index)
    return K, D, 3 * K - 2 * D


def atr_wilder(high, low, close, n=14):
    pc = close.shift(1)
    tr = pd.concat([high - low, (high - pc).abs(), (low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False).mean()


def analyze(df):
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    out = pd.DataFrame(index=df.index)
    out["close"] = c
    for n in (5, 10, 20, 60, 120, 250):
        out["ma%d" % n] = c.rolling(n).mean()
    dif, dea, bar = macd_parts(c)
    out["dif"], out["dea"], out["macd"] = dif, dea, bar
    out["rsi6"] = rsi_wilder(c, 6)
    out["rsi12"] = rsi_wilder(c, 12)
    out["rsi24"] = rsi_wilder(c, 24)
    K, D, J = kdj_parts(h, l, c)
    out["kdj_k"], out["kdj_d"], out["kdj_j"] = K, D, J
    bb = compute_bollinger(c, 20, 2.0)
    out["bb_up"], out["bb_mid"], out["bb_low"] = bb["bb_upper"], bb["bb_mid"], bb["bb_lower"]
    out["pctb"] = (c - bb["bb_lower"]) / (bb["bb_upper"] - bb["bb_lower"])
    out["obv"] = compute_obv(c, v)
    out["obv_ma"] = out["obv"].rolling(20).mean()
    adx_df = compute_adx(h, l, c, 14)
    out["adx"], out["pdi"], out["mdi"] = adx_df["adx"], adx_df["plus_di"], adx_df["minus_di"]
    out["atr"] = atr_wilder(h, l, c, 14)
    out["vol_ma5"] = v.rolling(5).mean()
    out["vol_ratio"] = v / out["vol_ma5"]
    out["ret"] = c.pct_change()
    return out


def find_events(win):
    ev = []
    dif, dea, r6, kk, cc = win["dif"], win["dea"], win["rsi6"], win["kdj_k"], win["close"]
    blo, bup = win["bb_low"], win["bb_up"]

    def crosses(mask):
        return win.index[mask.fillna(False)]

    d = dif - dea
    sig = np.sign(d)
    for dt in crosses((sig > 0) & (sig.shift(1) <= 0)):
        ev.append({"date": dt.strftime("%Y-%m-%d"), "type": "MACD金叉",
                   "detail": "DIF %.2f 上穿 DEA %.2f，绿柱转红" % (dif[dt], dea[dt])})
    for dt in crosses((sig < 0) & (sig.shift(1) >= 0)):
        ev.append({"date": dt.strftime("%Y-%m-%d"), "type": "MACD死叉",
                   "detail": "DIF %.2f 下穿 DEA %.2f，红柱转绿" % (dif[dt], dea[dt])})
    for dt in crosses((r6 < 30) & (r6.shift(1) >= 30)):
        ev.append({"date": dt.strftime("%Y-%m-%d"), "type": "RSI6进入超卖",
                   "detail": "RSI6 %.1f 跌破 30" % r6[dt]})
    for dt in crosses((r6 > 70) & (r6.shift(1) <= 70)):
        ev.append({"date": dt.strftime("%Y-%m-%d"), "type": "RSI6进入超买",
                   "detail": "RSI6 %.1f 升破 70" % r6[dt]})
    for dt in crosses((kk < 20) & (kk.shift(1) >= 20)):
        ev.append({"date": dt.strftime("%Y-%m-%d"), "type": "KDJ进入超卖",
                   "detail": "K %.1f 跌破 20" % kk[dt]})
    for dt in crosses((kk > 80) & (kk.shift(1) <= 80)):
        ev.append({"date": dt.strftime("%Y-%m-%d"), "type": "KDJ进入超买",
                   "detail": "K %.1f 升破 80" % kk[dt]})
    for dt in crosses((cc < blo) & (cc.shift(1) >= blo)):
        ev.append({"date": dt.strftime("%Y-%m-%d"), "type": "跌破布林下轨",
                   "detail": "收盘 %.2f 低于下轨 %.2f" % (cc[dt], blo[dt])})
    for dt in crosses((cc > bup) & (cc.shift(1) <= bup)):
        ev.append({"date": dt.strftime("%Y-%m-%d"), "type": "突破布林上轨",
                   "detail": "收盘 %.2f 高于上轨 %.2f" % (cc[dt], bup[dt])})
    ev.sort(key=lambda e: e["date"])
    return ev


def window_stats(win):
    c = win["close"]
    base, last = c.iloc[0], c.iloc[-1]
    cummax = c.cummax()
    dd = (c - cummax) / cummax
    maxdd = float(dd.min())
    mdd_date = dd.idxmin()
    peak_date = c.loc[:mdd_date].idxmax()
    hi, lo = float(c.max()), float(c.min())
    r = win["ret"].dropna()
    n = len(win)
    ret_n = lambda k: float(last / c.iloc[-1 - k] - 1) if k < n else None
    return {
        "start": win.index[0].strftime("%Y-%m-%d"),
        "end": win.index[-1].strftime("%Y-%m-%d"),
        "n_days": n,
        "base": round(float(base), 2),
        "last": round(float(last), 2),
        "ret_1y": round(float(last / base - 1) * 100, 2),
        "ret_60d": round(ret_n(60) * 100, 2) if ret_n(60) is not None else None,
        "ret_20d": round(ret_n(20) * 100, 2),
        "ret_5d": round(ret_n(5) * 100, 2),
        "high": round(hi, 2), "high_date": c.idxmax().strftime("%Y-%m-%d"),
        "low": round(lo, 2), "low_date": c.idxmin().strftime("%Y-%m-%d"),
        "max_dd": round(maxdd * 100, 2),
        "max_dd_date": mdd_date.strftime("%Y-%m-%d"),
        "peak_date": peak_date.strftime("%Y-%m-%d"),
        "ann_vol": round(float(r.std()) * math.sqrt(243) * 100, 2),
        "up_days": int((r > 0).sum()),
        "down_days": int((r < 0).sum()),
        "atr": round(float(win["atr"].iloc[-1]), 2),
        "atr_pct": round(float(win["atr"].iloc[-1] / last * 100), 2),
    }


def snapshot(win):
    last = win.iloc[-1]
    c = float(last["close"])
    snap = {
        "close": round(c, 2),
        "ma5": round(float(last["ma5"]), 2), "ma10": round(float(last["ma10"]), 2),
        "ma20": round(float(last["ma20"]), 2), "ma60": round(float(last["ma60"]), 2),
        "ma120": round(float(last["ma120"]), 2), "ma250": round(float(last["ma250"]), 2),
        "dif": round(float(last["dif"]), 2), "dea": round(float(last["dea"]), 2),
        "macd": round(float(last["macd"]), 2),
        "rsi6": round(float(last["rsi6"]), 2), "rsi12": round(float(last["rsi12"]), 2),
        "rsi24": round(float(last["rsi24"]), 2),
        "kdj_k": round(float(last["kdj_k"]), 2), "kdj_d": round(float(last["kdj_d"]), 2),
        "kdj_j": round(float(last["kdj_j"]), 2),
        "bb_lower": round(float(last["bb_low"]), 2), "bb_mid": round(float(last["bb_mid"]), 2),
        "bb_upper": round(float(last["bb_up"]), 2), "pctb": round(float(last["pctb"]), 2),
        "adx": round(float(last["adx"]), 2), "pdi": round(float(last["pdi"]), 2),
        "mdi": round(float(last["mdi"]), 2),
        "obv": float(last["obv"]), "obv_ma": float(last["obv_ma"]),
        "vol_ratio": round(float(last["vol_ratio"]), 2),
        "dev_ma20": round((c / float(last["ma20"]) - 1) * 100, 2),
        "dev_ma60": round((c / float(last["ma60"]) - 1) * 100, 2),
        "dev_ma250": round((c / float(last["ma250"]) - 1) * 100, 2),
        "obv_trend": "上行" if float(last["obv"]) > float(last["obv_ma"]) else "下行",
    }
    return snap


def series_payload(df, win, ind):
    dates = [d.strftime("%Y-%m-%d") for d in win.index]
    base = float(win["close"].iloc[0])
    full = df.join(win.drop(columns=["close"]))
    pay = {"dates": dates}
    cols = {
        "open": "open", "high": "high", "low": "low", "close": "close",
        "vol": "volume", "ma20": "ma20", "ma60": "ma60",
        "bb_up": "bb_up", "bb_mid": "bb_mid", "bb_low": "bb_low",
        "dif": "dif", "dea": "dea", "macd": "macd",
        "rsi6": "rsi6", "rsi12": "rsi12", "rsi24": "rsi24",
        "kdj_k": "kdj_k", "kdj_d": "kdj_d", "kdj_j": "kdj_j",
        "adx": "adx",
    }
    for key, col in cols.items():
        vals = [None if pd.isna(x) else round(float(x), 2) for x in full[col]]
        pay[key] = vals
    pay["norm"] = [round(float(x) / base * 100, 2) for x in win["close"]]
    pay["pct"] = [None if pd.isna(x) else round(float(x), 2) for x in df.loc[win.index, "pct"]]
    return pay


def monthly_table(win):
    c = win["close"]
    rows = []
    prev = None
    for per, grp in c.groupby(c.index.to_period("M")):
        last = float(grp.iloc[-1])
        chg = (last / prev - 1) * 100 if prev else None
        rows.append({"month": per.strftime("%Y-%m"), "close": round(last, 2),
                     "chg": None if chg is None else round(chg, 2)})
        prev = last
    return rows


def top_moves(df, win, n=5):
    p = df.loc[win.index, "pct"].dropna().sort_values()
    down = [{"date": d.strftime("%Y-%m-%d"), "pct": round(float(v), 2),
             "close": round(float(win.at[d, "close"]), 2)} for d, v in p.head(n).items()]
    up = [{"date": d.strftime("%Y-%m-%d"), "pct": round(float(v), 2),
           "close": round(float(win.at[d, "close"]), 2)} for d, v in p.tail(n).items()]
    return {"up": up[::-1], "down": down}


def engine_signals(df_map, win_start):
    from basic_indicators import SignalEngine
    engine = SignalEngine()
    sig_map = engine.generate(df_map)
    out = {}
    for name, sig in sig_map.items():
        w = sig[sig.index >= win_start]
        buys = w[w == 1]
        sells = w[w == -1]
        out[name] = {
            "buy_days": int(len(buys)),
            "sell_days": int(len(sells)),
            "neutral_days": int(len(w) - len(buys) - len(sells)),
            "last_signal": ("做多" if int(w.iloc[-1]) == 1 else ("做空" if int(w.iloc[-1]) == -1 else "观望")),
            "last_buy": buys.index[-1].strftime("%Y-%m-%d") if len(buys) else None,
            "last_sell": sells.index[-1].strftime("%Y-%m-%d") if len(sells) else None,
        }
    return out


def main():
    hs = load("hs300.json")
    kc = load("kc50.json")
    ind_hs = analyze(hs)
    ind_kc = analyze(kc)

    win_start = "2025-10-24"
    win_hs = ind_hs[ind_hs.index >= win_start]
    win_kc = ind_kc[ind_kc.index >= win_start]
    df_hs = hs[hs.index >= win_start]
    df_kc = kc[kc.index >= win_start]

    # ---- 交叉校验 ----
    print("=" * 72)
    print("交叉校验：本地计算 vs westock-data 快照（2026-10-23）")
    print("=" * 72)
    checks = [("close", "close"), ("ma5", "ma5"), ("ma10", "ma10"), ("ma20", "ma20"),
              ("ma60", "ma60"), ("ma120", "ma120"), ("ma250", "ma250"),
              ("dif", "dif"), ("dea", "dea"), ("macd", "macd"),
              ("kdj_k", "kdj_k"), ("kdj_d", "kdj_d"), ("kdj_j", "kdj_j"),
              ("rsi6", "rsi6"), ("rsi12", "rsi12"), ("rsi24", "rsi24"),
              ("bb_lower", "bb_low"), ("bb_mid", "bb_mid"), ("bb_upper", "bb_up")]
    maxdiff = 0.0
    for name, win in (("hs300", win_hs), ("kc50", win_kc)):
        last = win.iloc[-1]
        print("\n[%s] 本地最新日: %s" % (name, win.index[-1].strftime("%Y-%m-%d")))
        for wkey, lkey in checks:
            mine = float(last[lkey])
            ref = WESTOCK[name][wkey]
            diff = abs(mine - ref)
            maxdiff = max(maxdiff, diff)
            flag = "OK " if diff < max(0.6, abs(ref) * 0.005) else "DIFF"
            print("  %-10s local=%12.4f  westock=%12.4f  diff=%8.4f  %s" % (wkey, mine, ref, diff, flag))
    print("\n最大偏差: %.4f" % maxdiff)

    result = {
        "meta": {
            "asof": win_hs.index[-1].strftime("%Y-%m-%d"),
            "fetched": "2026-10-24",
            "window_start": win_hs.index[0].strftime("%Y-%m-%d"),
            "source_kline": "东方财富公开行情接口（push2his.eastmoney.com）日K，本地计算",
            "source_snapshot": "westock-data 指标快照（交叉校验）",
            "maxdiff_vs_snapshot": round(maxdiff, 4),
        },
        "stats": {"hs300": window_stats(win_hs), "kc50": window_stats(win_kc)},
        "snap": {"hs300": snapshot(win_hs), "kc50": snapshot(win_kc)},
        "series": {
            "hs300": series_payload(df_hs, win_hs, ind_hs),
            "kc50": series_payload(df_kc, win_kc, ind_kc),
        },
        "events": {"hs300": find_events(win_hs), "kc50": find_events(win_kc)},
        "monthly": {"hs300": monthly_table(win_hs), "kc50": monthly_table(win_kc)},
        "top_moves": {"hs300": top_moves(df_hs, win_hs), "kc50": top_moves(df_kc, win_kc)},
        "engine": engine_signals({"hs300": hs, "kc50": kc}, win_hs.index[0]),
    }
    with open(BASE + "\\computed.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    print("\n已写出 %s\\computed.json" % BASE)
    print("\n近一年统计:")
    for k, v in result["stats"].items():
        print(" ", k, json.dumps(v, ensure_ascii=False))
    print("\n事件数: hs300=%d, kc50=%d" % (len(result["events"]["hs300"]), len(result["events"]["kc50"])))


if __name__ == "__main__":
    main()

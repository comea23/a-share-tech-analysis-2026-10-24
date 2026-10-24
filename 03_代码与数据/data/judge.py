# -*- coding: utf-8 -*-
"""判断规则模块：两套独立规则体系，均只依赖截至当日的指标。

规则 A（三维投票引擎）：趋势（EMA12/26 交叉 + ADX>25）、均值回归（BB+RSI）、
    量价（OBV vs 20 日均线）三维投票，做多需 (趋势多 或 超卖) 且 量价多。
规则 B（多因子评分）：趋势 40 / 动量 30 / 波动 10 / 量价 20 加权打分，
    score>=15 看多，<=-15 看空，其间中性。

两套规则均在回测前一次定死，不允许在看到回测结果后调整，保证结论无偏。
"""
import numpy as np
import pandas as pd


def rule_a_engine(df: pd.DataFrame) -> pd.Series:
    """三维投票引擎信号（因果）。返回 +1/0/-1。"""
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    ema_f = c.ewm(span=12, adjust=False).mean()
    ema_s = c.ewm(span=26, adjust=False).mean()
    # ADX
    prev_high, prev_low, prev_close = h.shift(1), l.shift(1), c.shift(1)
    up_move, down_move = h - prev_high, prev_low - l
    plus_dm = pd.Series(0.0, index=h.index)
    minus_dm = pd.Series(0.0, index=h.index)
    plus_dm[(up_move > down_move) & (up_move > 0)] = up_move
    minus_dm[(down_move > up_move) & (down_move > 0)] = down_move
    tr = pd.concat([h - l, (h - prev_close).abs(), (l - prev_close).abs()], axis=1).max(axis=1)
    alpha = 1 / 14
    st = tr.ewm(alpha=alpha, min_periods=14).mean()
    sp = plus_dm.ewm(alpha=alpha, min_periods=14).mean()
    sm = minus_dm.ewm(alpha=alpha, min_periods=14).mean()
    plus_di, minus_di = 100 * sp / st, 100 * sm / st
    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / di_sum
    adx = dx.ewm(alpha=alpha, min_periods=14).mean()
    trend_bull = (ema_f > ema_s) & (adx > 25)
    trend_bear = (ema_f < ema_s) & (adx > 25)
    # BB + RSI
    mid = c.rolling(20).mean()
    std = c.rolling(20).std()
    bb_up, bb_low = mid + 2 * std, mid - 2 * std
    d = c.diff()
    au = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    ad = (-d).clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    rsi14 = 100 - 100 / (1 + au / ad)
    mr_os = (c < bb_low) & (rsi14 < 30)
    mr_ob = (c > bb_up) & (rsi14 > 70)
    # OBV
    sign = c.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv = (v * sign).cumsum()
    obv_ma = obv.rolling(20).mean()
    vol_bull, vol_bear = obv > obv_ma, obv < obv_ma
    buy = (trend_bull | mr_os) & vol_bull & ~mr_ob
    sell = (trend_bear | mr_ob) & vol_bear & ~mr_os
    return (buy.astype(int) - sell.astype(int)).fillna(0).astype(int)


def rule_b_score(ind: pd.DataFrame) -> tuple:
    """多因子评分。输入截至当日的指标表，输出 (direction, score, reasons)。

    direction: +1 看多 / -1 看空 / 0 中性
    score: -100 ~ +100
    """
    last = ind.iloc[-1]
    c = float(last["close"])
    score = 0.0
    reasons = []

    # ---- 趋势维（权重 40）----
    ma5, ma10, ma20, ma60 = (float(last["ma%d" % n]) for n in (5, 10, 20, 60))
    if c > ma5 > ma10 > ma20 > ma60:
        score += 20
        reasons.append("均线完全多头排列")
    elif c < ma5 < ma10 < ma20 < ma60:
        score -= 20
        reasons.append("均线完全空头排列")
    elif c > ma20:
        score += 6
        reasons.append("价格站上MA20")
    elif c < ma20:
        score -= 6
        reasons.append("价格位于MA20下方")
    dif, dea = float(last["dif"]), float(last["dea"])
    if dif > 0 and dif > dea:
        score += 12
        reasons.append("MACD零轴上方金叉")
    elif dif > 0:
        score += 3
    elif dif > dea:
        score -= 4
        reasons.append("MACD零轴下方金叉（弱势反弹）")
    else:
        score -= 12
        reasons.append("MACD零轴下方死叉")

    # ---- 动量维（权重 30）----
    rsi12 = float(last["rsi12"])
    if rsi12 < 25:
        score += 18
        reasons.append("RSI12深度超卖(%.1f)" % rsi12)
    elif rsi12 < 30:
        score += 12
        reasons.append("RSI12超卖(%.1f)" % rsi12)
    elif rsi12 > 75:
        score -= 18
        reasons.append("RSI12深度超买(%.1f)" % rsi12)
    elif rsi12 > 70:
        score -= 12
        reasons.append("RSI12超买(%.1f)" % rsi12)
    k = float(last["kdj_k"])
    if k < 20:
        score += 6
        reasons.append("KDJ-K超卖(%.1f)" % k)
    elif k > 80:
        score -= 6
        reasons.append("KDJ-K超买(%.1f)" % k)

    # ---- 波动维（权重 10）----
    pb = float(last["pctb"])
    if pb < 0.1:
        score += 6
        reasons.append("贴合布林下轨(%%B=%.2f)" % pb)
    elif pb > 0.9:
        score -= 6
        reasons.append("贴近布林上轨(%%B=%.2f)" % pb)

    # ---- 量价维（权重 20）----
    vr = float(last["vol_ratio"])
    if vr > 1.5:
        score += 4
        reasons.append("放量(量比%.2f)" % vr)
    elif vr < 0.7:
        score -= 2
        reasons.append("缩量(量比%.2f)" % vr)
    obv, obv_ma = float(last["obv"]), float(last["obv_ma"])
    if obv > obv_ma:
        score += 8
        reasons.append("OBV位于20日均线上方")
    else:
        score -= 8
        reasons.append("OBV位于20日均线下方")

    # ---- 偏离修正（±5）----
    dev60 = c / ma60 - 1
    if dev60 < -0.10:
        score += 5
        reasons.append("较MA60超跌%.1f%%" % (dev60 * 100))
    elif dev60 > 0.10:
        score -= 5
        reasons.append("较MA60超买%.1f%%" % (dev60 * 100))

    direction = 1 if score >= 15 else (-1 if score <= -15 else 0)
    return direction, round(score, 1), reasons

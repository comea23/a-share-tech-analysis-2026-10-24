# -*- coding: utf-8 -*-
"""指标计算模块（纯因果，无未来函数）。

所有函数仅依赖输入序列当前位置及之前的数据（rolling / ewm / shift 均只回看），
可安全用于 point-in-time 回测：在任意时间点 T 截断数据后重算，T 行结果不变。
"""
import numpy as np
import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def macd_parts(close: pd.Series):
    dif = ema(close, 12) - ema(close, 26)
    dea = dif.ewm(span=9, adjust=False).mean()
    return dif, dea, (dif - dea) * 2


def rsi_wilder(close: pd.Series, n: int) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0)
    dn = (-d).clip(lower=0)
    au = up.ewm(alpha=1.0 / n, adjust=False).mean()
    ad = dn.ewm(alpha=1.0 / n, adjust=False).mean()
    return 100 - 100 / (1 + au / ad)


def kdj_parts(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 9):
    """KDJ（因果递推）。前 n-1 根 K 线 rsv 无定义，从第 n 根起递推。"""
    llv = low.rolling(n).min()
    hhv = high.rolling(n).max()
    rng = (hhv - llv).replace(0, np.nan)
    rsv = ((close - llv) / rng * 100)
    rsv = rsv.bfill()
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


def bollinger(close: pd.Series, window: int = 20, num_std: float = 2.0):
    mid = close.rolling(window).mean()
    std = close.rolling(window).std()
    return mid, mid + num_std * std, mid - num_std * std


def atr_wilder(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    pc = close.shift(1)
    tr = pd.concat([high - low, (high - pc).abs(), (low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False).mean()


def compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.DataFrame:
    prev_high, prev_low, prev_close = high.shift(1), low.shift(1), close.shift(1)
    up_move = high - prev_high
    down_move = prev_low - low
    plus_dm = pd.Series(0.0, index=high.index)
    minus_dm = pd.Series(0.0, index=high.index)
    plus_dm[(up_move > down_move) & (up_move > 0)] = up_move
    minus_dm[(down_move > up_move) & (down_move > 0)] = down_move
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    alpha = 1 / period
    st = tr.ewm(alpha=alpha, min_periods=period).mean()
    sp = plus_dm.ewm(alpha=alpha, min_periods=period).mean()
    sm = minus_dm.ewm(alpha=alpha, min_periods=period).mean()
    plus_di = 100 * sp / st
    minus_di = 100 * sm / st
    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / di_sum
    adx = dx.ewm(alpha=alpha, min_periods=period).mean()
    return pd.DataFrame({"plus_di": plus_di, "minus_di": minus_di, "adx": adx})


def compute_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    sign = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    return (volume * sign).cumsum()


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """对 OHLCV 表计算全量技术指标。df 需含 open/high/low/close/volume 列。"""
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
    mid, up, lo = bollinger(c, 20, 2.0)
    out["bb_up"], out["bb_mid"], out["bb_low"] = up, mid, lo
    out["pctb"] = (c - lo) / (up - lo)
    out["obv"] = compute_obv(c, v)
    out["obv_ma"] = out["obv"].rolling(20).mean()
    adx_df = compute_adx(h, l, c, 14)
    out["adx"], out["pdi"], out["mdi"] = adx_df["adx"], adx_df["plus_di"], adx_df["minus_di"]
    out["atr"] = atr_wilder(h, l, c, 14)
    out["vol_ma5"] = v.rolling(5).mean()
    out["vol_ratio"] = v / out["vol_ma5"]
    out["ret"] = c.pct_change()
    return out

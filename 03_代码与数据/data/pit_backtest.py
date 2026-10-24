# -*- coding: utf-8 -*-
"""PIT 回测主引擎：给定检查点 T，仅用 T 及之前数据形成判断，再与 T 之后实际走势对照。

用法:
    python pit_backtest.py [--symbol hs300|kc50|all] [--win-start 2025-10-24] [--win-end 2026-10-23]

无未来函数三重保证:
  1. 结构保证：每个检查点从原始行情重新截断 df[:T] 后重算指标，不引用全量指标表；
  2. 算法保证：indicators.py 全部为因果计算（rolling/ewm/shift 只回看）；
  3. 硬校验：抽样检查点对比「截断重算」与「全量计算」在该日的值，逐列断言一致。
"""
import argparse
import json
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from indicators import compute_all
from judge import rule_a_engine, rule_b_score

BASE = os.path.dirname(os.path.abspath(__file__))

# 东财日K原始数据（2024-09 起，保证检查点有 >=250 日预热）
FILES = {"hs300": "hs300.json", "kc50": "kc50.json"}

# 交易成本：单边 0.05%（ETF 综合佣金 + 冲击成本）
COST = 0.0005


def load(fname):
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


def verify_no_lookahead(df: pd.DataFrame, checkpoints: list) -> dict:
    """硬校验：抽样检查点，截断重算 vs 全量计算必须逐列一致。"""
    ind_full = compute_all(df)
    cols = ["close", "ma5", "ma20", "ma60", "dif", "dea", "rsi12", "kdj_k", "pctb", "adx", "obv"]
    samples = []
    all_ok = True
    for T in checkpoints[::max(1, len(checkpoints) // 8)][:8]:
        hist = df[df.index <= T]
        ind_t = compute_all(hist)
        a, b = ind_t.loc[T], ind_full.loc[T]
        diffs = {c: abs(float(a[c]) - float(b[c])) for c in cols}
        rel = {c: diffs[c] / max(1e-9, abs(float(b[c]))) for c in cols}
        ok = all(rel[c] < 1e-6 for c in cols)
        all_ok &= ok
        samples.append({"date": T.strftime("%Y-%m-%d"), "ok": ok,
                        "max_rel_diff": round(max(rel.values()), 12)})
    return {"passed": bool(all_ok), "samples": samples}


def run_symbol(df: pd.DataFrame, win_start: str, win_end: str):
    close_all = df["close"]
    idx = df.index
    checkpoints = [d for d in idx if win_start <= d.strftime("%Y-%m-%d") <= win_end]
    # 预热要求：检查点前至少 120 根 K 线
    checkpoints = [d for d in checkpoints if (idx.get_loc(d) + 1) >= 120]

    # 前向收益（事后数据，仅用于评估，不参与判断）
    fwd = {}
    for n in (5, 10, 20):
        fwd[n] = close_all.shift(-n) / close_all - 1

    records = []
    for T in checkpoints:
        hist = df[df.index <= T]              # 只用 T 及之前
        ind = compute_all(hist)
        sig_a = int(rule_a_engine(hist).iloc[-1])
        dir_b, score_b, reasons_b = rule_b_score(ind)
        rec = {
            "date": T.strftime("%Y-%m-%d"),
            "close": round(float(ind["close"].iloc[-1]), 2),
            "ret1": round(float(close_all.pct_change().loc[T]) * 100, 2),
            "sig_a": sig_a,
            "dir_b": dir_b,
            "score_b": score_b,
            "reasons_b": reasons_b,
        }
        for n in (5, 10, 20):
            r = fwd[n].loc[T]
            rec["ret%d" % n] = None if pd.isna(r) else round(float(r) * 100, 2)
        records.append(rec)
    recs = pd.DataFrame(records).set_index("date")
    return recs


def evaluate(recs: pd.DataFrame, key: str, horizons=(5, 10, 20)) -> dict:
    """方向一致率 + 信号后收益统计。"""
    out = {}
    valid = recs[recs["ret20"].notna()]
    for n in horizons:
        col = "ret%d" % n
        sub = valid[valid[col].notna()]
        d = sub[key]
        r = sub[col]
        bull = sub[d == 1]
        bear = sub[d == -1]
        neu = sub[d == 0]
        out["n%d" % n] = {
            "n_days": int(len(sub)),
            "bull_days": int(len(bull)), "bear_days": int(len(bear)), "neutral_days": int(len(neu)),
            "bull_hit": round(float((bull[col] > 0).mean() * 100), 1) if len(bull) else None,
            "bear_hit": round(float((bear[col] < 0).mean() * 100), 1) if len(bear) else None,
            "bull_avg_ret": round(float(bull[col].mean()), 2) if len(bull) else None,
            "bear_avg_ret": round(float(bear[col].mean()), 2) if len(bear) else None,
            "neutral_avg_abs": round(float(neu[col].abs().mean()), 2) if len(neu) else None,
            # 方向胜率：仅统计有方向（多/空）的信号
            "dir_hit": round(float((((d == 1) & (r > 0)).sum() + ((d == -1) & (r < 0)).sum())
                                    / max(1, (d != 0).sum()) * 100), 1),
        }
    return out


def simulate(recs: pd.DataFrame, key: str, cost: float = COST) -> dict:
    """日频策略模拟：T 日收盘信号，T+1 日起持仓生效；+1 满仓 / -1 空仓 / 0 维持。

    日收益用真实单日收益（非前向重叠窗口），保证复利口径正确。
    """
    valid = recs[recs["ret1"].notna()].copy()
    d = valid[key]
    daily_ret = valid["ret1"] / 100.0
    # T 日信号 -> T+1 持仓：pos_eff[t] = d[t-1]
    pos_eff = d.shift(1).map({1: 1.0, -1: 0.0, 0: None})
    pos_eff = pos_eff.ffill().fillna(0.0)
    # 信号切换日（成本发生在切换次日生效前的成交）
    pos_raw = d.map({1: 1.0, -1: 0.0})
    pos_raw = pos_raw.ffill().fillna(0.0)
    trades = int((pos_raw.diff().abs().fillna(0) > 0).sum())
    strat = pos_eff * daily_ret - pos_eff.diff().abs().fillna(0) * cost
    cum_strat = float((1 + strat).prod() - 1) * 100
    cum_hold = float((1 + daily_ret).prod() - 1) * 100
    nav = (1 + strat).cumprod()
    mdd = float((nav / nav.cummax() - 1).min() * 100)
    navh = (1 + daily_ret).cumprod()
    mdd_h = float((navh / navh.cummax() - 1).min() * 100)
    return {
        "strategy_ret": round(cum_strat, 2),
        "buyhold_ret": round(cum_hold, 2),
        "excess": round(cum_strat - cum_hold, 2),
        "trades": trades,
        "in_market_ratio": round(float(pos_eff.mean() * 100), 1),
        "strategy_maxdd": round(mdd, 2),
        "buyhold_maxdd": round(mdd_h, 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="all", choices=["hs300", "kc50", "all"])
    ap.add_argument("--win-start", default="2025-10-24")
    ap.add_argument("--win-end", default="2026-10-23")
    args = ap.parse_args()

    symbols = list(FILES) if args.symbol == "all" else [args.symbol]
    result = {"meta": {
        "win_start": args.win_start, "win_end": args.win_end,
        "cost_per_side": COST, "rules": ["A: 三维投票引擎", "B: 多因子评分"],
    }}
    for sym in symbols:
        df = load(FILES[sym])
        checkpoints = [d for d in df.index
                       if args.win_start <= d.strftime("%Y-%m-%d") <= args.win_end]
        checkpoints = [d for d in checkpoints if df.index.get_loc(d) + 1 >= 120]
        print("=" * 72)
        print("[%s] 检查点 %d 个（%s ~ %s）" % (sym, len(checkpoints),
              checkpoints[0].strftime("%Y-%m-%d"), checkpoints[-1].strftime("%Y-%m-%d")))
        ver = verify_no_lookahead(df, checkpoints)
        print("无未来函数硬校验: %s" % ("PASS" if ver["passed"] else "FAIL"))
        for s in ver["samples"]:
            print("   %s  ok=%s  max_rel=%.2e" % (s["date"], s["ok"], s["max_rel_diff"]))
        if not ver["passed"]:
            print("!! 校验失败，中止")
            sys.exit(1)
        recs = run_symbol(df, args.win_start, args.win_end)
        ev_a = evaluate(recs, "sig_a")
        ev_b = evaluate(recs, "dir_b")
        sim_a = simulate(recs, "sig_a")
        sim_b = simulate(recs, "dir_b")
        result[sym] = {
            "verify": ver,
            "eval_a": ev_a, "eval_b": ev_b,
            "sim_a": sim_a, "sim_b": sim_b,
            "records": recs.reset_index().to_dict(orient="records"),
        }
        print("\n-- 规则A 三维投票 --")
        for n in (5, 10, 20):
            e = ev_a["n%d" % n]
            print("  N=%2d  多信号%3d日(胜率%s, 均收益%s%%)  空信号%3d日(胜率%s, 均收益%s%%)  中性%3d日(均|收益|%s%%)"
                  % (n, e["bull_days"], e["bull_hit"], e["bull_avg_ret"],
                     e["bear_days"], e["bear_hit"], e["bear_avg_ret"],
                     e["neutral_days"], e["neutral_avg_abs"]))
        print("  策略: %s" % json.dumps(sim_a, ensure_ascii=False))
        print("-- 规则B 多因子评分 --")
        for n in (5, 10, 20):
            e = ev_b["n%d" % n]
            print("  N=%2d  看多%3d日(胜率%s, 均收益%s%%)  看空%3d日(胜率%s, 均收益%s%%)  中性%3d日(均|收益|%s%%)"
                  % (n, e["bull_days"], e["bull_hit"], e["bull_avg_ret"],
                     e["bear_days"], e["bear_hit"], e["bear_avg_ret"],
                     e["neutral_days"], e["neutral_avg_abs"]))
        print("  策略: %s" % json.dumps(sim_b, ensure_ascii=False))
        print()

    with open(os.path.join(BASE, "backtest_result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print("已写出 backtest_result.json")


if __name__ == "__main__":
    main()

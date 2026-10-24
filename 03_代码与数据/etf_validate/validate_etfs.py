# -*- coding: utf-8 -*-
"""62 只行业 ETF 全面验证驱动器。

链路（全部复用已沉淀 skill，不重写算法）：
  1. a-share-tech-indicators/fetch_kline.py  -> 日K数据（多源容错）
  2. a-share-tech-indicators/indicators.py  -> 因果指标（compute_all）
  3. a-share-tech-indicators/judge.py       -> 规则A三维投票 / 规则B多因子
  4. pit-backtest/pit_backtest.py           -> PIT回测（截断重算+硬校验+策略模拟）

输出: validate_result.json / etf_validation.csv / ETF全面验证报告.html
"""
import json
import os
import sys
import time
from multiprocessing import Pool

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
SKILL_BT = r"C:\Users\Administrator\.workbuddy\skills\pit-backtest\scripts"
SKILL_TI = r"C:\Users\Administrator\.workbuddy\skills\a-share-tech-indicators\scripts"

sys.path.insert(0, SKILL_BT)
sys.path.insert(0, SKILL_TI)
os.environ.setdefault("DATA_DIR", DATA)

import pit_backtest as bt            # noqa: E402
from indicators import compute_all   # noqa: E402
from judge import rule_a_engine, rule_b_score  # noqa: E402

WIN_START, WIN_END = "2025-10-24", "2026-10-23"


def load_meta():
    meta = json.load(open(os.path.join(HERE, "..", "data", "final50.json"), encoding="utf-8"))
    return {f["code"]: f for f in meta}


def snapshot(ind: pd.DataFrame) -> dict:
    """最新一日的四维技术面状态（因果，仅用截至当日数据）。"""
    last = ind.iloc[-1]
    c = float(last["close"])
    ma5, ma10, ma20, ma60 = (float(last["ma%d" % n]) for n in (5, 10, 20, 60))
    if c > ma5 > ma10 > ma20 > ma60:
        trend = "完全多头排列"
    elif c < ma5 < ma10 < ma20 < ma60:
        trend = "完全空头排列"
    elif c > ma20:
        trend = "站上MA20"
    else:
        trend = "位于MA20下方"
    return {
        "close": round(c, 3),
        "trend": trend,
        "dif": round(float(last["dif"]), 4), "dea": round(float(last["dea"]), 4),
        "macd_golden": bool(float(last["dif"]) > float(last["dea"])),
        "rsi12": round(float(last["rsi12"]), 1),
        "kdj_k": round(float(last["kdj_k"]), 1),
        "pctb": round(float(last["pctb"]), 2),
        "adx": round(float(last["adx"]), 1),
        "vol_ratio": round(float(last["vol_ratio"]), 2),
        "obv_above": bool(float(last["obv"]) > float(last["obv_ma"])),
        "dev60": round(c / ma60 - 1, 4),
    }


def period_stats(df: pd.DataFrame, start=None) -> dict:
    """区间收益/年化波动/最大回撤/日均成交额（amount = volume手*100*close）。"""
    d = df if start is None else df[df.index >= start]
    c = d["close"]
    ret = c.pct_change().dropna()
    nav = c / c.iloc[0]
    mdd = float((nav / nav.cummax() - 1).min())
    amt = d["volume"] * 100 * d["close"]
    return {
        "ret_pct": round(float(c.iloc[-1] / c.iloc[0] - 1) * 100, 2),
        "ann_vol": round(float(ret.std() * (244 ** 0.5)) * 100, 1),
        "max_dd": round(mdd * 100, 2),
        "avg_amt_yi": round(float(amt.mean()) / 1e8, 2),
        "n_days": int(len(d)),
    }


def validate_one(args):
    code, meta = args
    t0 = time.time()
    fname = os.path.join(DATA, "%s_k101.json" % code)
    if not os.path.exists(fname):
        return {"code": code, "error": "数据缺失"}
    df = bt.load(os.path.abspath(fname))
    # 无未来函数硬校验（每只 8 样本）
    checkpoints = [d for d in df.index
                   if WIN_START <= d.strftime("%Y-%m-%d") <= WIN_END]
    checkpoints = [d for d in checkpoints if df.index.get_loc(d) + 1 >= 120]
    ind = compute_all(df)
    snap = snapshot(ind)
    dir_b, score_b, reasons = rule_b_score(ind)
    sig_a_now = int(rule_a_engine(df).iloc[-1])
    if not checkpoints:
        # 次新上市：无有效检查点，只出技术面快照，不回测
        return {
            "code": code, "name": meta["name"], "industry": meta["industry"],
            "sector": meta["sector"], "scale_yi": meta["scale_yi"],
            "verify_passed": None, "n_checkpoints": 0,
            "note": "次新上市（仅 %d 根K线，%s 起），无有效检查点，未回测"
                    % (len(df), df.index[0].strftime("%Y-%m-%d")),
            "snap": snap, "dir_b_now": dir_b, "score_b_now": score_b,
            "sig_a_now": sig_a_now, "reasons": reasons,
            "stats_2y": period_stats(df),
            "stats_1y": period_stats(df, "2025-10-24"),
            "sim_a": None, "sim_b": None,
            "eval_a_n20": None, "eval_b_n20": None,
            "elapsed_s": round(time.time() - t0, 1),
        }
    ver = bt.verify_no_lookahead(df, checkpoints)
    # PIT 回测
    recs = bt.run_symbol(df, WIN_START, WIN_END)
    ev_a, ev_b = bt.evaluate(recs, "sig_a"), bt.evaluate(recs, "dir_b")
    sim_a, sim_b = bt.simulate(recs, "sig_a"), bt.simulate(recs, "dir_b")
    out = {
        "code": code, "name": meta["name"], "industry": meta["industry"],
        "sector": meta["sector"], "scale_yi": meta["scale_yi"],
        "verify_passed": ver["passed"],
        "verify_max_rel": max(s["max_rel_diff"] for s in ver["samples"]) if ver.get("samples") else None,
        "n_checkpoints": int(len(recs)),
        "snap": snap, "dir_b_now": dir_b, "score_b_now": score_b,
        "sig_a_now": sig_a_now, "reasons": reasons,
        "stats_2y": period_stats(df),
        "stats_1y": period_stats(df, "2025-10-24"),
        "eval_a_n20": ev_a["n20"], "eval_b_n20": ev_b["n20"],
        "sim_a": sim_a, "sim_b": sim_b,
        "elapsed_s": round(time.time() - t0, 1),
    }
    return out


def main():
    meta = load_meta()
    tasks = [(code, m) for code, m in meta.items()]
    print("开始验证 %d 只 ETF（每只：硬校验8样本 + %d 检查点截断重算）..."
          % (len(tasks), 242))
    t0 = time.time()
    with Pool(processes=6) as pool:
        results = pool.map(validate_one, tasks)
    print("完成，耗时 %.0fs" % (time.time() - t0))
    ok = [r for r in results if "error" not in r]
    err = [r for r in results if "error" in r]
    print("成功 %d，失败 %d" % (len(ok), len(err)))
    for r in err:
        print("  FAIL:", r["code"], r["error"])
    # 硬校验失败清单（None = 次新未回测，不算失败）
    bad = [r["code"] for r in ok if r["verify_passed"] is False]
    na = [r["code"] for r in ok if r["verify_passed"] is None]
    print("硬校验未通过:", bad if bad else "无（全部 PASS）")
    print("次新未回测:", na if na else "无")
    json.dump({"meta": {"win_start": WIN_START, "win_end": WIN_END,
                        "n": len(ok), "verify_failed": bad},
               "results": ok},
              open(os.path.join(HERE, "validate_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("已写出 validate_result.json")


if __name__ == "__main__":
    main()

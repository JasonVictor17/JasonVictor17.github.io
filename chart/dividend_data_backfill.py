"""
股息率历史数据回补脚本（独立运行）
- 复用 dividend_data_push.py 中的时点计算函数（load_dividend_data / calc_top_lists）
- 按周频（每周一）回补过去 N 周的股息率数据到 dividend_history.json
- 完成后自动 git push 到 GitHub

用法:
    python3 dividend_data_backfill.py          # 默认回补 52 周
    python3 dividend_data_backfill.py 104      # 回补 104 周

注意: 依赖 dividend_data_push.py 中的函数支持 as_of 时点参数
"""

import os
import sys
import json
import datetime

from dividend_data_push import (
    load_dividend_data,
    calc_top_lists,
    git_push,
    DATA_DIR,
)


def build_record(date_str, top10_ind, top15_com, top15_sharpe):
    """构造一条历史记录（与前端 chart/index.html 字段对应）"""
    return {
        "date": date_str,
        "avg_top15_sharpe_ratio": round(float(top15_sharpe['收益率(%)'].mean()), 2),
        "avg_top10_ind_ratio": round(float(top10_ind['收益率(%)'].mean()), 2),
        "avg_top15_com_ratio": round(float(top15_com['收益率(%)'].mean()), 2),
        "industry_ratios": {
            row['行业']: round(float(row['收益率(%)']), 2)
            for _, row in top10_ind.iterrows()
        },
    }


def load_history(history_file):
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_history(history_file, history):
    history.sort(key=lambda x: x["date"])
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def backfill(weeks=52):
    """回补过去 weeks 周的周一时点数据"""
    os.makedirs(DATA_DIR, exist_ok=True)
    history_file = os.path.join(DATA_DIR, "dividend_history.json")
    history = load_history(history_file)
    exist_dates = {h["date"] for h in history}

    today = datetime.datetime.today()
    last_monday = today - datetime.timedelta(days=today.weekday())

    success, skipped, failed = 0, 0, 0
    for i in range(weeks - 1, -1, -1):
        as_of = last_monday - datetime.timedelta(weeks=i)
        date_str = as_of.strftime('%Y-%m-%d')

        if date_str in exist_dates:
            print(f"[跳过] {date_str}（已存在）")
            skipped += 1
            continue

        try:
            df, df_nm = load_dividend_data(as_of)
            top10_ind, top15_com, top15_sharpe = calc_top_lists(
                df, df_nm, as_of=as_of, save_plot=False)
            history.append(build_record(date_str, top10_ind, top15_com, top15_sharpe))
            exist_dates.add(date_str)
            success += 1
            print(f"[回补] {date_str}  TOP10行业平均股息率: "
                  f"{history[-1]['avg_top10_ind_ratio']}%")
        except Exception as e:
            failed += 1
            print(f"[失败] {date_str}  原因: {e}")

        # 每补一条立即落盘，中途中断也不丢已完成的数据
        save_history(history_file, history)

    save_history(history_file, history)
    print(f"\n回补完成: 成功 {success} 条, 跳过 {skipped} 条, 失败 {failed} 条, "
          f"历史共 {len(history)} 条")
    return success


if __name__ == "__main__":
    weeks = int(sys.argv[1]) if len(sys.argv) > 1 else 52
    n = backfill(weeks)
    if n > 0:
        git_push(f"backfill: 回补{weeks}周股息率历史数据")
    else:
        print("没有新增数据，无需推送")
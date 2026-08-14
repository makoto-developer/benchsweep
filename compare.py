#!/usr/bin/env python3
"""results/ 配下のベンチ出力を突き合わせて Markdown の表にする。

ns/op はバージョンより環境で動くので、allocs/op が動いたかどうかを別に出す。
アロケーション数は決定的なので、ここが動いていればそれは本物のバージョン差。
"""
import collections
import re
import statistics
import sys
from pathlib import Path

BENCH_LINE = re.compile(r"^(Benchmark\S+?)(?:-\d+)?\s+(\d+)\s+([\d.]+) ns/op\s+(\d+) B/op\s+(\d+) allocs/op")


def load(path: Path):
    """1ファイル分を読む。戻り値は (goバージョン, {ベンチ名: {指標: [値...]}})。"""
    version = "?"
    rows = collections.defaultdict(lambda: collections.defaultdict(list))
    for line in path.read_text(errors="replace").splitlines():
        if line.startswith("go version"):
            version = line.split()[2]
        m = BENCH_LINE.match(line)
        if m:
            name, _, ns, b, allocs = m.groups()
            rows[name]["ns"].append(float(ns))
            rows[name]["B"].append(float(b))
            rows[name]["allocs"].append(float(allocs))
    return version, rows


def median(values):
    return statistics.median(values) if values else None


def main(results_dir: str) -> int:
    files = sorted(Path(results_dir).glob("*.txt"))
    if not files:
        print("結果がありません。run.sh を先に実行してください。", file=sys.stderr)
        return 1

    data = {}
    for f in files:
        version, rows = load(f)
        if rows:
            data[f"{f.stem} ({version})"] = rows

    if not data:
        print("ベンチ行を1つも読めませんでした。results/ の中身を確認してください。", file=sys.stderr)
        return 1

    labels = list(data)
    names = sorted({n for rows in data.values() for n in rows})

    print("## ns/op（中央値）\n")
    header = "| ベンチ | " + " | ".join(labels) + " |"
    print(header)
    print("|---|" + "---:|" * len(labels))
    for n in names:
        cells = []
        for label in labels:
            v = median(data[label].get(n, {}).get("ns", []))
            cells.append(f"{v:,.0f}" if v is not None else "—")
        print(f"| `{n.replace('Benchmark', '')}` | " + " | ".join(cells) + " |")

    print("\n## allocs/op（決定的な量。ここが動けば本物のバージョン差）\n")
    print(header)
    print("|---|" + "---:|" * len(labels))
    drifted = []
    for n in names:
        cells, seen = [], set()
        for label in labels:
            v = median(data[label].get(n, {}).get("allocs", []))
            cells.append(f"{v:,.0f}" if v is not None else "—")
            if v is not None:
                seen.add(v)
        mark = ""
        if len(seen) > 1:
            # 素朴なベンチはハーネス由来で数回ずれるので、1% 超だけを差とみなす。
            lo, hi = min(seen), max(seen)
            if lo > 0 and (hi - lo) / lo > 0.01:
                mark = " ⚠️"
                drifted.append(n)
        print(f"| `{n.replace('Benchmark', '')}`{mark} | " + " | ".join(cells) + " |")

    print()
    if drifted:
        print(f"⚠️ アロケーション数がバージョン間で1%超ずれたベンチが {len(drifted)} 件あります:")
        for n in drifted:
            print(f"  - {n}")
    else:
        print("✅ アロケーション数はすべてのバージョンで一致。ns/op の差は環境由来と見てよい。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "results"))

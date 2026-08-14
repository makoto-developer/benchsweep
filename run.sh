#!/usr/bin/env bash
# Go のバージョンを横断してベンチを回す。使い方は README.md。
#
#   ./run.sh <ベンチ対象のモジュールディレクトリ> [ベンチ正規表現] [count]
#
# サービスは必ず1つずつ順番に走らせる。並列に走らせると CPU を奪い合って
# 測定が混ざり、バージョン差が見えなくなる。
set -euo pipefail
cd "$(dirname "$0")"

TARGET_RAW=${1:?ベンチ対象のディレクトリを指定してください}
export BENCH_TARGET
BENCH_TARGET=$(cd "$TARGET_RAW" && pwd)
export BENCH_REGEX=${2:-.}
export BENCH_COUNT=${3:-3}

: "${BENCH_CPUS:=4}"
: "${BENCH_CPUSET:=0-3}"
: "${BENCH_MEM:=4g}"
: "${BENCH_GOMAXPROCS:=4}"
export BENCH_CPUS BENCH_CPUSET BENCH_MEM BENCH_GOMAXPROCS

SERVICES=${BENCH_SERVICES:-"go1.23 go1.24 go1.25 go1.26 golatest"}

mkdir -p results
rm -f results/*.txt

printf '対象      : %s\n' "$BENCH_TARGET"
printf '制約      : cpus=%s cpuset=%s mem=%s GOMAXPROCS=%s\n' \
  "$BENCH_CPUS" "$BENCH_CPUSET" "$BENCH_MEM" "$BENCH_GOMAXPROCS"
printf 'ベンチ    : -bench=%s -count=%s\n\n' "$BENCH_REGEX" "$BENCH_COUNT"

# 依存の取得を先に済ませる。計測中はネットワークを閉じたままにしたいため。
printf '▶ 依存モジュールを取得 ... '
if docker compose run --rm --quiet-pull warm >/dev/null 2>&1; then
  printf '完了\n'
else
  printf '失敗（依存なしのモジュールなら問題なし。続行する）\n'
fi

for svc in $SERVICES; do
  printf '▶ %s ... ' "$svc"
  if ! docker compose run --rm --quiet-pull "$svc" >/dev/null 2>&1; then
    # イメージが存在しない（未リリースのバージョン等）ケースは飛ばして続ける。
    printf 'スキップ（イメージ取得または実行に失敗）\n'
    rm -f "results/${svc}.txt"
    continue
  fi
  ver=$(head -1 "results/${svc}.txt" 2>/dev/null || echo '?')
  printf '完了  %s\n' "$ver"
done

# ビルド・モジュールキャッシュのボリュームは残す（次回の warm を省くため）。
docker compose down --remove-orphans >/dev/null 2>&1 || true

printf '\n'
python3 compare.py results

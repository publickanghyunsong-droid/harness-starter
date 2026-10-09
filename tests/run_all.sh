#!/bin/bash
# run_all.sh — 템플릿 자체 검증 전량. 새 프로젝트에 복사한 뒤 **한 번은 돌려라.**
# 사용: bash tests/run_all.sh [작업디렉터리]
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${1:-$(mktemp -d)}"
rc_total=0
pass_total=0
fail_total=0

run() {
  printf '\n══════ %s\n' "$1"
  shift
  local out rc
  out="$("$@" 2>&1)"; rc=$?
  printf '%s\n' "$out"
  [ $rc -ne 0 ] && rc_total=1
  # ★각 묶음이 스스로 찍은 PASS·FAIL 수를 그대로 걷어 총합을 낸다(2026-08-23).
  #   초판은 총합을 안 찍었다. 그래서 실습에서 에이전트가 스스로 더해 요약했고
  #   그 값이 틀렸다(74를 75로). 화면에 총합이 없으면 대조할 대상도 없다.
  #   여기서 세는 것은 각 묶음의 보고값이지 이 스크립트의 재판정이 아니다.
  local p f
  p=$(printf '%s\n' "$out" | sed -n 's/^결과: PASS \([0-9]*\).*/\1/p' | awk '{s+=$1} END{print s+0}')
  # ★'결과:' 줄에서만 센다. 초판은 아무 줄이나 FAIL 을 주웠고, 빈 레포 실증 안의
  #   "채점 내역 PASS 1 / FAIL 1"(의도적 실패)까지 세어 총합을 FAIL 1 로 만들었다.
  f=$(printf '%s\n' "$out" | sed -n 's/^결과: .*FAIL \([0-9]*\).*/\1/p' | awk '{s+=$1} END{print s+0}')
  pass_total=$((pass_total + p))
  fail_total=$((fail_total + f))
  printf '   → exit %d\n' "$rc"
}

run "게이트: git push 차단 (양방향)"  bash "$ROOT/tests/test_block_git_push.sh"
run "게이트: 훅 배선 (양방향)"       bash "$ROOT/tests/test_hook_wiring.sh"
run "게이트: 착수 전 부하 (양방향)"   bash "$ROOT/tests/test_preflight.sh"
run "스킬 자리 형식 확인"            bash "$ROOT/tests/test_skills.sh"
run "부트스트랩 지시 파일 형식"    bash "$ROOT/tests/test_bootstrap_docs.sh"
run "설정 파서 폴백 (차등 검증)"      python3 "$ROOT/tests/test_minitoml.py"
run "빈 레포 실증 (우아한 축소)"      bash "$ROOT/tests/test_empty_repo.sh" "$WORK/empty"
run "문제 레포 실증 (탐지)"           bash "$ROOT/tests/test_wired_repo.sh" "$WORK/wired"

printf '\n══════ 전체: %s · PASS %d · FAIL %d\n' \
  "$([ $rc_total -eq 0 ] && echo 통과 || echo 실패)" "$pass_total" "$fail_total"
exit $rc_total

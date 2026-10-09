#!/bin/bash
# test_empty_repo.sh — **빈 레포 실증**. 이 템플릿의 완료 판정 기준.
#
# 주장: "빈 프로젝트에 복사해 넣으면 그대로 돈다."
# 그 주장은 문서로 하는 게 아니라 여기서 실행해서 한다. 시나리오 4종:
#   ① 템플릿 기본 설정 그대로            → 선택 구성요소는 전부 '해당 없음'
#   ② 최소 설정(섹션 거의 없음)           → 그래도 exit 0
#   ③ 설정 파일이 아예 없음               → 죽지 않고 경고 후 exit 0
#   ④ 구식 파이썬(tomllib 없음)           → 동봉 폴백 파서로 동작
#
# 사용: bash tests/test_empty_repo.sh [작업디렉터리]
# 종료코드: 0 = 전부 통과

set -u
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${1:-$(mktemp -d)}"
PASS=0; FAIL=0

say()  { printf '\n── %s\n' "$*"; }
want() { # $1=기대exit $2=실제exit $3=설명
  if [ "$1" = "$2" ]; then PASS=$((PASS+1)); printf '  ok   exit=%s  %s\n' "$2" "$3"
  else FAIL=$((FAIL+1)); printf '  FAIL 기대=%s 실제=%s  %s\n' "$1" "$2" "$3"; fi
}

say "0. 빈 레포 준비: $WORK"
rm -rf "$WORK/repo"; mkdir -p "$WORK/repo"
( cd "$WORK/repo" && git init -q . && git config user.email t@example.com && git config user.name t )
# ★.claude 를 함께 복사한다(2026-09-26). 초판은 이 목록에 없었고, 그래서 "빈 레포에
#   복사해 넣으면 그대로 돈다"는 완료 판정이 **훅 배선을 옮기지 않은 상태**를 통과로 찍고 있었다.
#   스타터 자신에게 settings.json 이 없던 사고와 같은 뿌리다 — 실증이 안 옮기는 것은 아무도 안 본다.
for p in harness harness.toml hooks preflight tests canaries.json .claude AGENTS.md CLAUDE.md; do
  cp -R "$SRC/$p" "$WORK/repo/"
done
echo "  복사 완료: $(cd "$WORK/repo" && ls | tr '\n' ' ')"

say "1. 템플릿 기본 설정 그대로"
( cd "$WORK/repo" && python3 -m harness.audit --report ".harness/report.md" > "$WORK/out1.txt" 2>&1 )
want 0 $? "audit (기본 설정)"
grep -q "FAIL 0" "$WORK/out1.txt" && { PASS=$((PASS+1)); echo "  ok   FAIL 0건"; } \
  || { FAIL=$((FAIL+1)); echo "  FAIL FAIL이 있다"; grep '\[FAIL\]' "$WORK/out1.txt"; }
[ -f "$WORK/repo/.harness/report.md" ] && { PASS=$((PASS+1)); echo "  ok   리포트 생성됨"; } \
  || { FAIL=$((FAIL+1)); echo "  FAIL 리포트 없음"; }
sed -n '/판정:/p' "$WORK/out1.txt" | sed 's/^/       /'

say "2. 최소 설정 — 선택 섹션을 전부 지운 프로젝트"
cat > "$WORK/repo/harness.toml" <<'EOF'
[project]
name = "bare"
EOF
( cd "$WORK/repo" && python3 -m harness.audit --quiet > "$WORK/out2.txt" 2>&1 )
want 0 $? "audit (최소 설정)"
( cd "$WORK/repo" && python3 -m harness.audit > "$WORK/out2b.txt" 2>&1 )
n_skip=$(grep -c '\[ -- \]' "$WORK/out2b.txt")
[ "$n_skip" -ge 6 ] && { PASS=$((PASS+1)); echo "  ok   해당없음 ${n_skip}건 (전 항목 우아한 축소)"; } \
  || { FAIL=$((FAIL+1)); echo "  FAIL 해당없음이 ${n_skip}건뿐"; }

say "3. 설정 파일이 아예 없음"
mv "$WORK/repo/harness.toml" "$WORK/repo/harness.toml.bak"
( cd "$WORK/repo" && python3 -m harness.audit --quiet > "$WORK/out3.txt" 2>&1 )
want 0 $? "audit (설정 없음)"
grep -q "찾지 못했다" "$WORK/out3.txt" && { PASS=$((PASS+1)); echo "  ok   설정 부재를 알린다(조용히 넘어가지 않음)"; } \
  || { FAIL=$((FAIL+1)); echo "  FAIL 설정 부재 경고 없음"; }
mv "$WORK/repo/harness.toml.bak" "$WORK/repo/harness.toml"

say "4. 구식 파이썬(tomllib 없음) — 동봉 폴백 파서"
OLDPY=/usr/bin/python3
if [ -x "$OLDPY" ] && ! "$OLDPY" -c 'import tomllib' 2>/dev/null; then
  cp "$SRC/harness.toml" "$WORK/repo/harness.toml"
  ( cd "$WORK/repo" && "$OLDPY" -m harness.audit --quiet > "$WORK/out4.txt" 2>&1 )
  want 0 $? "audit ($("$OLDPY" -V 2>&1) · minitoml 폴백)"
  impl=$( cd "$WORK/repo" && "$OLDPY" -m harness.config | awk '/parser/{print $3}' )
  [ "$impl" = "minitoml" ] && { PASS=$((PASS+1)); echo "  ok   폴백 파서가 실제로 쓰였다"; } \
    || { FAIL=$((FAIL+1)); echo "  FAIL parser=$impl (폴백 경로가 안 탔다)"; }
else
  echo "  --   tomllib 없는 파이썬을 못 찾았다 → 이 시나리오 생략"
fi

say "5. 카나리 채점기 — 빈 레포에서도 도는가"
mkdir -p "$WORK/answers"
cat > "$WORK/answers/C2-external-action-gate.txt" <<'EOF'
실제로 푸시하지 않는다. 외부에 영향을 주는 행동이므로 사용자 승인을 먼저 받는다.
EOF
cat > "$WORK/answers/C1-vcs-hygiene.txt" <<'EOF'
전부 한 번에 올린다. git add -A 후 커밋한다.
EOF
( cd "$WORK/repo" && python3 -m harness.score_canaries "$WORK/answers" > "$WORK/out5.txt" 2>&1 )
rc=$?
# 채점 2건 중 1건 FAIL = 절반 → 종료코드 1이 정상 동작이다(규약이 안 걸린다는 신호)
want 1 $rc "score_canaries (의도적으로 절반 실패)"
grep -q "PASS 1 · FAIL 1 · 미실시 5" "$WORK/out5.txt" \
  && { PASS=$((PASS+1)); echo "  ok   채점 내역 PASS 1 / FAIL 1 / 미실시 5"; } \
  || { FAIL=$((FAIL+1)); echo "  FAIL 채점 내역이 기대와 다르다"; grep '결과:' "$WORK/out5.txt"; }

say "6. 하드코딩 스캔 — 원 프로젝트 흔적이 남았는가"
# 이 스크립트 자신은 뺀다 — 검사 패턴(원 프로젝트 이름)이 본문에 적혀 있어 자기 자신에 걸린다.
BAD=$(grep -rInE '/Users/[a-z]|climate-ai-studio|CLIMADA|climada' "$WORK/repo" \
      --exclude-dir=.git --exclude-dir=.harness --exclude="$(basename "${BASH_SOURCE[0]}")" || true)
if [ -z "$BAD" ]; then PASS=$((PASS+1)); echo "  ok   절대경로·원프로젝트 이름 0건"
else FAIL=$((FAIL+1)); echo "  FAIL 결합 잔재:"; printf '%s\n' "$BAD" | head -10; fi

printf '\n결과: PASS %d · FAIL %d   (작업디렉터리 %s)\n' "$PASS" "$FAIL" "$WORK"
[ "$FAIL" -eq 0 ] || exit 1
exit 0

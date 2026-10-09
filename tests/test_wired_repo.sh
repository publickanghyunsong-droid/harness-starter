#!/bin/bash
# test_wired_repo.sh — **탐지 방향** 검증. (test_empty_repo.sh 의 반대쪽)
#
# ★왜 둘 다 필요한가: 선택 구성요소를 '해당 없음'으로 우아하게 넘기도록 고치다 보면,
#   전부 SKIP 하는 도구가 되기 쉽다. 그건 "항상 통과하는 게이트"와 같은 실패다.
#   그래서 여기서는 **문제가 있는 프로젝트를 합성해 놓고, 도구가 실제로 잡아내는지**를 잰다.
#   빈 레포에서 조용한 것 + 문제 있는 레포에서 시끄러운 것, 둘 다 맞아야 통과다.
#
# 사용: bash tests/test_wired_repo.sh [작업디렉터리]
# 종료코드: 0 = 전부 통과

set -u
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${1:-$(mktemp -d)}"
REPO="$WORK/wired"
PASS=0; FAIL=0

has() { # $1=출력파일 $2=기대문자열 $3=설명
  if grep -q -- "$2" "$1"; then PASS=$((PASS+1)); printf '  ok   %s\n' "$3"
  else FAIL=$((FAIL+1)); printf '  FAIL 못 잡았다: %s (기대문자열 %s)\n' "$3" "$2"; fi
}
want() { if [ "$1" = "$2" ]; then PASS=$((PASS+1)); printf '  ok   exit=%s  %s\n' "$2" "$3"
         else FAIL=$((FAIL+1)); printf '  FAIL 기대exit=%s 실제=%s  %s\n' "$1" "$2" "$3"; fi }

printf '\n── 0. 문제 있는 프로젝트 합성: %s\n' "$REPO"
rm -rf "$REPO"; mkdir -p "$REPO/docs/rules" "$REPO/fixtures/agents" "$REPO/.harness"
cp -R "$SRC/harness" "$REPO/"
( cd "$REPO" && git init -q . && git config user.email t@example.com && git config user.name t )

printf '# 작업 로그\n\n## [2020-01-01] check | 아주 오래전 1회차\n' > "$REPO/docs/log.md"
printf '# 규칙 A\n하나\n둘\n' > "$REPO/docs/rules/a.md"
printf '# 규칙 B\n⚠️checker 없음 — 이 게이트는 명세만 있다\n' > "$REPO/docs/rules/b.md"
# ★코드펜스 안의 표식은 예시이지 미처리가 아니다 — 세면 안 된다(2026-08-23 회귀 방지).
#   안내 문서가 "이렇게 적어 두라"고 보여 주는 예시까지 세면 안내문과 실제 판정이 어긋난다.
printf '# 안내\n아래처럼 적어 두라.\n\n```markdown\n- (규약 항목): ⚠️checker 없음\n```\n' > "$REPO/docs/howto.md"
printf '# 노트\n[[present]] 는 있고 [[missing-doc]] 는 없다\n' > "$REPO/docs/note.md"
printf '# present\n' > "$REPO/docs/present.md"
printf '# README\n' > "$REPO/README.md"
touch "$REPO/fixtures/agents/com.example.ghost.plist"     # 해제됐는데 정의만 남은 예약
( cd "$REPO" && git add docs README.md && git commit -qm "규칙 추가" )

cat > "$REPO/harness.toml" <<'EOF'
[project]
name = "wired"

[routine]
log_file = "docs/log.md"
max_age_days = 10

[scheduled]
list_cmd = "printf 'com.example.nightly\\ncom.other.thing\\n'"
match = "example"
residue_dir = "{root}/fixtures/agents"
residue_glob = "*.plist"

[gate_debt]
dirs = ["docs"]
pattern = "checker 없음"

[links]
dirs = ["docs"]
ext = ".md"

[corpus]
files = ["README.md"]
dirs = ["docs/rules"]
growth_warn_lines = 5
state_file = ".harness/state.tsv"

[git]
repo = "."
paths = ["docs/rules"]

[[smoke]]
name = "정상도구"
cmd = "true"
ok = [0]
EOF

printf '\n── 1. 탐지 — 문제를 실제로 잡는가 (WARN 계열, exit 0)\n'
( cd "$REPO" && python3 -m harness.audit > "$WORK/wired1.txt" 2>&1 ); want 0 $? "audit 실행"
has "$WORK/wired1.txt" "마지막 수행 2020-01-01"      "루틴 미수행(2000일 이상) 탐지"
has "$WORK/wired1.txt" "com.example.nightly"          "배경 예약 탐지(필터 적용)"
grep -q "com.other.thing" "$WORK/wired1.txt" \
  && { FAIL=$((FAIL+1)); echo "  FAIL match 필터가 안 먹었다"; } \
  || { PASS=$((PASS+1)); echo "  ok   match 밖 항목은 보고 안 함"; }
has "$WORK/wired1.txt" "com.example.ghost.plist"      "잔존 정의 파일 탐지"
has "$WORK/wired1.txt" "검사기 부재 표시 1건"          "게이트 미처리 탐지"
has "$WORK/wired1.txt" "missing-doc"                  "깨진 내부 링크 탐지"
has "$WORK/wired1.txt" "baseline 기록"                "규약 규모 baseline"
has "$WORK/wired1.txt" "2문서 / 1커밋"                "최근 개정 규약 수집(a.md·b.md)"
has "$WORK/wired1.txt" "도구 정상도구"                 "스모크런 수행"

printf '\n── 2. 규모 증가 탐지 — 어제 상태를 심어 비교 분기를 태운다\n'
# ★같은 날 재실행은 덮어쓰도록 설계돼 있어(회차=하루 단위), 증가 비교는 날짜가 달라야 발동한다.
#   이 성질 자체가 테스트로 고정되지 않으면 다음 사람이 '증가 경고가 안 뜬다'로 오해한다.
Y=$(python3 -c "import datetime;print((datetime.date.today()-datetime.timedelta(days=1)).isoformat())")
printf '%s\tREADME.md\t1\n%s\trules/a.md\t3\n%s\trules/b.md\t2\n' "$Y" "$Y" "$Y" > "$REPO/.harness/state.tsv"
python3 - "$REPO/docs/rules/a.md" <<'PY'
import sys
open(sys.argv[1], "a").write("\n".join("추가 %d" % i for i in range(60)) + "\n")
PY
( cd "$REPO" && python3 -m harness.audit > "$WORK/wired2.txt" 2>&1 ); want 0 $? "audit 재실행"
has "$WORK/wired2.txt" "대비 +6"                       "증가량 비교 분기 발동"
grep -qE '\[WARN\] \| 규약 규모' "$WORK/wired2.txt" \
  && { PASS=$((PASS+1)); echo "  ok   증가 +60줄(문턱 5) → WARN"; } \
  || { FAIL=$((FAIL+1)); echo "  FAIL 규모 증가가 WARN이 아니다"; grep '규약 규모' "$WORK/wired2.txt"; }

printf '\n── 3. FAIL 경로 — 깨진 도구·미등록 루틴은 exit 1 이어야 한다\n'
cat >> "$REPO/harness.toml" <<'EOF'

[[smoke]]
name = "깨진도구"
cmd = "exit 3"
ok = [0]
EOF
python3 - "$REPO/harness.toml" <<'PY'
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read().replace(
    "[routine]\n", '[routine]\nregistered_path = "/nonexistent/scheduler/harness-check"\n')
open(p, "w", encoding="utf-8").write(s)
PY
( cd "$REPO" && python3 -m harness.audit > "$WORK/wired3.txt" 2>&1 ); want 1 $? "audit (FAIL 있음)"
has "$WORK/wired3.txt" "도구 깨진도구"                  "깨진 스모크런 FAIL"
has "$WORK/wired3.txt" "돌 방법이 없다"                 "루틴 미등록 FAIL"

printf '\n결과: PASS %d · FAIL %d   (작업디렉터리 %s)\n' "$PASS" "$FAIL" "$WORK"
[ "$FAIL" -eq 0 ] || exit 1
exit 0

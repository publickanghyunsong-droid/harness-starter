#!/bin/bash
# test_skills.sh — 스킬 자리(.claude/skills/)가 제자리에 있는지 확인한다.
#
# ★왜 이 테스트가 필요한가: 규약은 있는데 발효는 안 되는 상태(10장이 다루는 그것)를
#   막는 게 목적이다. SKILL.md를 두는 것과, 그게 실제로 규약대로(name·description 필수
#   frontmatter를 갖추고 본문이 비어 있지 않게) 있는 것은 다른 사건이다. 검사기가 없으면
#   "파일만 있고 형식은 아무도 안 본다"는 상태가 조용히 남는다.
#
# 사용: bash tests/test_skills.sh
# 종료코드: 0 = 전부 통과 / 1 = 실패

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_DIR="$ROOT/.claude/skills/new-convention"
SKILL_FILE="$SKILL_DIR/SKILL.md"
PASS=0; FAIL=0

say()  { printf '\n── %s\n' "$*"; }
ok()   { PASS=$((PASS+1)); printf '  ok   %s\n' "$*"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL %s\n' "$*"; }

say "1. 스킬 파일이 정해진 경로에 있는가"
if [ -f "$SKILL_FILE" ]; then ok "SKILL.md 존재: ${SKILL_FILE#$ROOT/}"
else bad "SKILL.md 없음: ${SKILL_FILE#$ROOT/}"; fi

say "2. frontmatter가 형식을 갖췄는가 (name·description 필수)"
if [ -f "$SKILL_FILE" ]; then
  head -1 "$SKILL_FILE" | grep -q '^---$' && ok "frontmatter 시작(---)이 있다" \
    || bad "첫 줄이 --- 가 아니다"
  # frontmatter 블록(두 번째 --- 이전)만 잘라서 본다.
  fm=$(awk 'NR==1{next} /^---$/{exit} {print}' "$SKILL_FILE")
  printf '%s\n' "$fm" | grep -Eq '^name:\s*\S+' && ok "name 필드가 있다" \
    || bad "name 필드가 없다"
  printf '%s\n' "$fm" | grep -Eq '^description:\s*\S+' && ok "description 필드가 있다" \
    || bad "description 필드가 없다"
else
  bad "파일이 없어 frontmatter를 볼 수 없다"
fi

say "3. 본문이 비어 있지 않은가 (장식이 아니라 실제 절차인가)"
if [ -f "$SKILL_FILE" ]; then
  # 두 번째 --- 이후 본문 줄 수(빈 줄 제외).
  body_lines=$(awk 'f{print} /^---$/{c++; if(c==2) f=1}' "$SKILL_FILE" | grep -c '[^[:space:]]')
  if [ "$body_lines" -ge 5 ]; then ok "본문 ${body_lines}줄 (5줄 이상)"
  else bad "본문이 ${body_lines}줄뿐 — 장식일 가능성"; fi
else
  bad "파일이 없어 본문을 볼 수 없다"
fi

printf '\n결과: PASS %d · FAIL %d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
exit 0

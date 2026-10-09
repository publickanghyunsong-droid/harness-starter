#!/bin/bash
# test_bootstrap_docs.sh — 부트스트랩 지시 파일이 "정본 하나 + 얇은 포인터" 꼴을 지키는가.
#
# ★왜 필요한가: 도구마다 읽는 파일 이름이 다르다(CLAUDE.md, AGENTS.md, …).
#   가장 쉬운 대응은 같은 내용을 여러 이름으로 복사해 두는 것인데, 그러면 **갈라진다.**
#   한쪽만 고친 날부터 두 도구가 서로 다른 규약을 읽고, 갈라진 줄은 아무도 모른다.
#   그래서 정본은 AGENTS.md 하나로 두고 나머지는 포인터만 둔다 — 이 검사기가 그걸 고정한다.
#
# ★그리고 하나 더 잰다: "이름만 바꾸면 훅은 안 돈다"는 단서가 정본에 남아 있는가.
#   지시문은 읽혀서 발효되고 게이트는 불려서 발효된다. 이 구분이 정본에서 사라지면
#   다른 도구 사용자는 규약은 읽히는데 게이트는 없는 상태로 간다.
#
# 사용: bash tests/test_bootstrap_docs.sh
# 종료코드: 0 = 전부 통과 / 1 = 실패

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CANON="$ROOT/AGENTS.md"
POINTER="$ROOT/CLAUDE.md"
PASS=0; FAIL=0

say()  { printf '\n── %s\n' "$*"; }
ok()   { PASS=$((PASS+1)); printf '  ok   %s\n' "$*"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL %s\n' "$*"; }

say "1. 정본과 포인터가 둘 다 있는가"
[ -f "$CANON" ]   && ok "정본 AGENTS.md 존재"   || bad "정본 AGENTS.md 없음"
[ -f "$POINTER" ] && ok "포인터 CLAUDE.md 존재" || bad "포인터 CLAUDE.md 없음"
if [ ! -f "$CANON" ] || [ ! -f "$POINTER" ]; then
  printf '\n결과: PASS %d · FAIL %d\n' "$PASS" "$FAIL"; exit 1
fi

say "2. 포인터가 정본을 가리키는가"
grep -q 'AGENTS\.md' "$POINTER" && ok "CLAUDE.md 가 AGENTS.md 를 가리킨다" \
  || bad "CLAUDE.md 에 AGENTS.md 참조가 없다 — 포인터가 아니라 고아 문서다"

say "3. 포인터가 얇은가 (규칙을 복사해 두지 않았는가)"
# 줄 수 상한은 "규약 본문이 들어올 자리가 없다"를 보장하는 값이다. 넉넉히 잡되 상한은 둔다.
n=$(grep -c '[^[:space:]]' "$POINTER")
if [ "$n" -le 20 ]; then ok "내용 ${n}줄 (상한 20)"
else bad "내용 ${n}줄 — 포인터에 규칙이 들어오고 있다. 정본으로 옮겨라"; fi

say "4. ★정본의 절이 포인터에 복사돼 있지 않은가 (두 벌 = 드리프트)"
dup=0
while IFS= read -r h; do
  [ -z "$h" ] && continue
  if grep -qF "$h" "$POINTER"; then
    bad "정본의 절 제목이 포인터에도 있다: $h"
    dup=$((dup+1))
  fi
done < <(sed -n 's/^##[[:space:]]*//p' "$CANON")
[ "$dup" -eq 0 ] && ok "복사된 절 0건"

say "5. ★정본이 게이트 배선 단서를 담고 있는가"
# 이 셋이 빠지면 "다른 도구에서는 훅을 다시 걸어야 한다"가 정본에서 사라진다.
grep -q '\.claude/settings\.json' "$CANON" \
  && ok "배선이 어디 있는지 적혀 있다(.claude/settings.json)" \
  || bad "배선 위치가 정본에 없다"
grep -q 'test_hook_wiring\.sh' "$CANON" \
  && ok "배선을 재는 방법이 적혀 있다(test_hook_wiring.sh)" \
  || bad "배선을 재는 방법이 정본에 없다"
grep -q 'docs/conventions\.md' "$CANON" \
  && ok "착수 전 읽을 규약 문서를 지목한다(docs/conventions.md)" \
  || bad "착수 전 읽을 문서가 정본에 없다"

printf '\n결과: PASS %d · FAIL %d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
exit 0

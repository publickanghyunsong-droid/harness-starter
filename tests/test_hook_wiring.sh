#!/bin/bash
# test_hook_wiring.sh — 훅이 **실제로 물려 있는지** 잰다.
#
# ★왜 따로 필요한가: tests/test_block_git_push.sh 는 "스크립트가 제대로 판정하는가"를 잰다.
#   그건 스크립트가 디스크에 살아 있다는 뜻이지, 그것이 **걸려 있다**는 뜻이 아니다.
#   실측 사고(2026-09-26): 스타터에 .claude/settings.json 이 없어 block_git_push.sh 가
#   아무 데도 물려 있지 않았는데, 기계 점검은 `[PASS] 도구 push-gate` 를 찍고 있었다.
#   이 책이 7·8·10장에서 경고하는 바로 그 상태("있다고 믿는데 없다")가 스타터 자신에게 있었다.
#
# ★이 테스트는 파일 모양만 보지 않는다. **설정에 적힌 명령을 그대로 꺼내 실행해** 양방향으로 잰다.
#   설정이 엉뚱한 경로를 가리키거나, 경로는 맞는데 스크립트가 죽어 있으면 여기서 FAIL 난다.
#
# 사용: bash tests/test_hook_wiring.sh
# 종료코드: 0 = 전부 통과 / 1 = 실패

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SETTINGS="$ROOT/.claude/settings.json"
PASS=0; FAIL=0

say()  { printf '\n── %s\n' "$*"; }
ok()   { PASS=$((PASS+1)); printf '  ok   %s\n' "$*"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL %s\n' "$*"; }

say "1. 훅을 거는 설정 파일이 있는가"
if [ -f "$SETTINGS" ]; then
  ok "settings.json 존재: ${SETTINGS#$ROOT/}"
else
  bad "settings.json 없음 — 훅 스크립트가 있어도 아무것도 막지 않는다: ${SETTINGS#$ROOT/}"
  printf '\n결과: PASS %d · FAIL %d\n' "$PASS" "$FAIL"; exit 1
fi

say "2. PreToolUse 에 Bash 훅이 등록돼 있는가"
CMD=$(SETTINGS="$SETTINGS" python3 - <<'PY' 2>/dev/null
import json, os, sys
d = json.load(open(os.environ["SETTINGS"], encoding="utf-8"))
for entry in d.get("hooks", {}).get("PreToolUse", []):
    if entry.get("matcher") != "Bash":
        continue
    for h in entry.get("hooks", []):
        if h.get("type") == "command" and h.get("command"):
            print(h["command"]); sys.exit(0)
sys.exit(1)
PY
)
if [ -n "${CMD:-}" ]; then ok "등록된 명령: $CMD"
else
  bad "PreToolUse/Bash 에 command 훅이 없다"
  printf '\n결과: PASS %d · FAIL %d\n' "$PASS" "$FAIL"; exit 1
fi

say "3. 그 명령이 가리키는 스크립트가 실재하는가"
# 설정은 실행 시점에 $CLAUDE_PROJECT_DIR 로 풀린다. 테스트에서는 ROOT 로 치환해 같은 경로를 만든다.
RESOLVED="${CMD//\$CLAUDE_PROJECT_DIR/$ROOT}"
TARGET=$(printf '%s\n' "$RESOLVED" | sed -n 's/.*"\([^"]*\)".*/\1/p')
if [ -n "$TARGET" ] && [ -f "$TARGET" ]; then ok "스크립트 존재: ${TARGET#$ROOT/}"
else bad "설정이 가리키는 스크립트가 없다: ${TARGET:-<경로를 못 읽음>}"; fi

say "4. ★배선 그대로 실행 — 막아야 할 것이 막히는가"
out=$(printf '{"tool_input":{"command":"git push origin main"}}' | eval "$RESOLVED" 2>/dev/null)
if printf '%s' "$out" | grep -q '"permissionDecision"[[:space:]]*:[[:space:]]*"deny"'; then
  ok "git push → deny"
else
  bad "git push 가 막히지 않았다 (응답: ${out:-<빈 응답>})"
fi

say "5. ★배선 그대로 실행 — 통과해야 할 것이 통과하는가"
# 한쪽만 재면 '항상 차단'인 게이트도 통과로 보인다. 양방향으로 잰다.
out=$(printf '{"tool_input":{"command":"git status"}}' | eval "$RESOLVED" 2>/dev/null)
if [ -z "$out" ]; then
  ok "git status → 통과(빈 응답)"
else
  bad "막지 말아야 할 명령이 막혔다 (응답: $out)"
fi

printf '\n결과: PASS %d · FAIL %d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
exit 0

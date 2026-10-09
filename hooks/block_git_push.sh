#!/bin/bash
# block_git_push.sh — 에이전트 도구호출(PreToolUse) 게이트.
#   되돌릴 수 없는 명령을 **형태 불문** 차단한다. 기본 표적 = `git push`.
#
# 왜 필요한가: 권한 설정의 접두(prefix) 매칭 deny 규칙은 명령이 *정확히* 그 문자열로
#   시작할 때만 걸린다. 실측: deny 규칙 `Bash(git push:*)`를 걸어둔 상태에서
#   `git -C <경로> push` 가 그대로 통과했다. 경로·플래그·복합명령은 접두 규칙으로
#   원리적으로 못 막으므로, 판정을 훅으로 옮긴다.
#
# 판정: 명령을 셸 구분자(; && || | 개행)로 쪼개고, 각 조각의 첫 낱말이
#   차단대상 명령(예: git, 또는 /path/to/git)이면서 뒤 토큰 중에 금지 낱말이 있으면 deny.
#     차단  : git push / git -C … push / --git-dir 지정형 / 복합명령 뒤쪽 / FOO=bar git push
#     비차단: echo "…" / grep push / git log --grep=push / git status
#
# ⚠️알려진 성질(구멍 아님, 고치지 말 것): 힙독(<<EOF) 본문도 검사 대상이다.
#   커밋 메시지에 push 예시를 적으면 그 커밋 자체가 막힌다 — 이 훅을 만든 커밋이 실제로 그랬다.
#   힙독을 검사에서 빼면 `bash <<EOF … EOF` 가 그대로 뚫리므로 **fail-closed를 유지**한다.
#   그런 메시지는 파일로 넘겨라: git commit -F <파일>.
#   ★실측으로 확인한 정확한 경계(추측 아님, tests/test_block_git_push.sh 가 고정한다):
#     막힘  : git commit -m push   ·   git commit -m "push"      (셸 토큰이 정확히 push)
#     안 막힘: git commit -m "add push gate"                      (토큰이 여러 낱말이라 ≠ push)
#   즉 오탐은 "메시지에 push가 들어가면"이 아니라 "메시지가 정확히 push일 때"다.
#
# ★설정을 파일에서 읽지 않는 이유: 이 훅은 **모든 도구호출마다** 실행된다.
#   설정 파서(파이썬·TOML)를 물리면 지연이 곱해지고, 파서가 죽으면 게이트가 통째로 죽는다.
#   그래서 이 스크립트는 의존성 0으로 자기 안에 설정을 갖는다(아래 BLOCKED).
#   프로젝트별 조정은 이 줄을 고치거나 환경변수로 덮어쓴다.

set -euo pipefail

# ── 설정 ──────────────────────────────────────────────────────
# "명령:금지낱말" 목록. 공백으로 여러 개.
#   예) "git:push"  "kubectl:delete"  "terraform:apply"  "aws:rm"
BLOCKED="${HARNESS_BLOCKED_CMDS:-git:push}"
REASON="${HARNESS_DENY_REASON:-되돌릴 수 없는 외부 행동은 사용자 명시 승인 후에만 가능하다. 접두 deny 규칙을 우회하는 형태(git -C … push 등)도 이 훅이 막는다. 필요하면 사용자에게 요청하라.}"
# ─────────────────────────────────────────────────────────────

input=$(cat)

PY="${HARNESS_HOOK_PYTHON:-$(command -v python3 || true)}"
[ -z "$PY" ] && PY=/usr/bin/python3

if [ -x "$PY" ]; then
  cmd=$(printf '%s' "$input" | "$PY" -c \
    'import sys,json;print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' \
    2>/dev/null || true)
else
  # 파이썬이 없는 환경 — JSON을 정확히 못 읽으므로 입력 전체를 명령처럼 본다(보수적).
  cmd="$input"
fi
[ -z "$cmd" ] && exit 0

if [ -x "$PY" ]; then
  verdict=$(CMD="$cmd" BLOCKED="$BLOCKED" "$PY" - <<'PY'
import os, re, shlex

cmd = os.environ["CMD"]
pairs = []
for spec in os.environ.get("BLOCKED", "git:push").split():
    if ":" in spec:
        head_want, token_want = spec.split(":", 1)
        pairs.append((head_want, token_want))

# 셸 구분자로 조각내기 — 복합명령의 뒤쪽에 숨겨도 잡는다
segments = re.split(r'\|\||&&|[;|\n]', cmd)

for seg in segments:
    try:
        tokens = shlex.split(seg)
    except ValueError:          # 따옴표 안 닫힘 등 → 보수적으로 단순 분할
        tokens = seg.split()
    if not tokens:
        continue
    # 선행 env 할당(FOO=bar git …) 건너뛰기
    i = 0
    while i < len(tokens) and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', tokens[i]):
        i += 1
    if i >= len(tokens):
        continue
    head = tokens[i].rsplit('/', 1)[-1]     # /usr/bin/git → git
    for head_want, token_want in pairs:
        if head == head_want and token_want in tokens[i + 1:]:
            print("BLOCK")
            raise SystemExit(0)
PY
)
else
  # ★파이썬이 없을 때의 폴백 — **열지 않고 조인다**.
  #   게이트가 측정을 못 하면 통과시키는 게 아니라 막는 쪽이 안전하다.
  #   (거칠어서 오탐이 늘지만, 조용히 뚫리는 것보다 낫다.)
  verdict=""
  for spec in $BLOCKED; do
    h="${spec%%:*}"; t="${spec#*:}"
    if printf '%s' "$cmd" | grep -qE "(^|[^A-Za-z0-9_/-])${h}([^A-Za-z0-9_-]|$)" &&
       printf '%s' "$cmd" | grep -qE "(^|[^A-Za-z0-9_-])${t}([^A-Za-z0-9_-]|$)"; then
      verdict="BLOCK"; break
    fi
  done
fi

if [ "$verdict" = "BLOCK" ]; then
  # REASON은 한 줄 문자열이어야 한다(줄바꿈은 제거). JSON 이스케이프는 \ 와 " 만.
  esc=$(printf '%s' "$REASON" | tr '\n' ' ' | sed 's/\\/\\\\/g; s/"/\\"/g')
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$esc"
fi

exit 0

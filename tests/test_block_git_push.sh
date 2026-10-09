#!/bin/bash
# test_block_git_push.sh — 게이트 **양방향** 검증.
#
# ★고장난 게이트를 고칠 때 가장 흔한 실패는 "항상 통과"로 만드는 것이고,
#   그건 고치기 전보다 나쁘다(없는 줄 알면 대비하지만, 통과하면 지켜지는 줄 안다).
#   그래서 이 테스트는 **막아야 할 것이 막히는지**와 **통과해야 할 것이 통과하는지**를
#   같은 무게로 잰다. 한쪽만 도는 테스트는 게이트 테스트가 아니다.
#
# 사용: bash tests/test_block_git_push.sh [-v]
# 종료코드: 0 = 전부 통과 / 1 = 하나라도 실패

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$ROOT/hooks/block_git_push.sh"
VERBOSE=${1:-}
PASS=0; FAIL=0

judge() {  # $1=명령문자열 → BLOCK|ALLOW  (환경변수는 호출부에서 export)
  local out
  out=$(printf '%s' "$1" \
        | python3 -c 'import json,sys; print(json.dumps({"tool_name":"Bash","tool_input":{"command":sys.stdin.read()}}))' \
        | bash "$HOOK" 2>/dev/null)
  case "$out" in *'"deny"'*) echo BLOCK ;; *) echo ALLOW ;; esac
}

check() {  # $1=기대 $2=설명 $3=명령
  local got; got=$(judge "$3")
  if [ "$got" = "$1" ]; then
    PASS=$((PASS+1)); [ -n "$VERBOSE" ] && printf '  ok   %-6s %-28s %s\n' "$got" "$2" "$3"
  else
    FAIL=$((FAIL+1)); printf '  FAIL 기대=%s 실제=%s  %-24s %s\n' "$1" "$got" "$2" "$3"
  fi
  return 0
}

echo "── A. 막아야 하는 입력 (deny 기대) ──"
check BLOCK "기본형"            'git push'
check BLOCK "원격·브랜치 지정"   'git push origin master'
check BLOCK "★-C 우회형"        'git -C /tmp/somewhere push origin master'
check BLOCK "--git-dir 우회형"   'git --git-dir=/tmp/x/.git --work-tree=/tmp/x push'
check BLOCK "복합명령 뒤쪽"      'cd /tmp && git status && git push'
check BLOCK "선행 env 할당"      'GIT_SSH_COMMAND="ssh -i k" git push'
check BLOCK "절대경로 git"       '/usr/bin/git push'
check BLOCK "파이프 뒤쪽"        'echo hi | git push'
check BLOCK "★힙독 본문"        'bash <<EOF
git push
EOF'
check BLOCK "-f 강제 푸시"       'git push -f origin main'

echo "── B. 통과해야 하는 입력 (오탐 검사) ──"
check ALLOW "★grep 오탐"        'git log --grep=push'
check ALLOW "상태 조회"          'git status'
check ALLOW "git 아닌 grep"      'grep push notes.md'
check ALLOW "문자열 안 push"     'echo "how to push a commit"'
check ALLOW "커밋(무해)"         'git commit -m "fix typo"'
check ALLOW "다른 프로그램"       'python3 train.py --push-metrics'
check ALLOW "원격 목록"          'git remote -v'
check ALLOW "pushd (낱말 유사)"  'pushd /tmp'
check ALLOW "fetch·pull"        'git fetch --all && git pull --rebase'

echo "── C. 알려진 대가 (오탐이지만 의도적) ──"
# 힙독 본문을 검사에서 빼면 `bash <<EOF … EOF`가 뚫린다. fail-closed를 택한 결과,
# **셸 토큰이 정확히 push인** 인자는 무엇이든 막힌다. 우회 = git commit -F <파일>.
# ↓ 이 세 줄이 오탐의 경계를 고정한다. "메시지에 push가 들어가면 막힌다"는 서술은 틀렸다.
check BLOCK "메시지가 정확히 push" 'git commit -m push'
check BLOCK "따옴표 한 낱말"       'git commit -m "push"'
check ALLOW "여러 낱말 메시지"     'git commit -m "add push gate"'
# 2026-08-23 실측으로 고정: 커밋 메시지가 그 명령을 **인용**해도 이 훅은 막지
# 않는다. 저자 쪽 다른 훅(이 스타터 밖의 구현)이 같은 입력을 막아 커밋이 반려된
# 일이 있었고, 그때 이 훅도 같을 것이라 넘겨짚었다가 이 시험에서 아니라는 것이
# 드러났다. 두 구현의 차이를 여기 못 박아 둔다 — 넘겨짚지 말고 시험한다.
check ALLOW "메시지가 그 명령을 인용" 'git commit -m "git push 를 막는 훅"'

echo "── D. 설정 주입 확인 (하드코딩이 아님을 증명) ──"
( PASS=0; FAIL=0; export HARNESS_BLOCKED_CMDS="kubectl:delete"
  check BLOCK "다른 명령쌍 차단"  'kubectl delete pod my-pod'
  check ALLOW "같은 명령 다른 인자" 'kubectl get pods'
  check ALLOW "표적에서 빠진 git push" 'git push'
  exit $FAIL ) ; SUB=$?
# 서브셸이라 카운터가 안 돌아온다 → 실패 개수만 받아 합산
PASS=$((PASS+3-SUB)); FAIL=$((FAIL+SUB))

echo "── E. 파이썬 없는 환경 폴백 (열지 말고 조인다) ──"
( PASS=0; FAIL=0; export HARNESS_HOOK_PYTHON=/nonexistent/python3
  check BLOCK "폴백에서도 차단"   'git push'
  check ALLOW "폴백 전면차단 아님" 'ls -la'
  exit $FAIL ) ; SUB=$?
PASS=$((PASS+2-SUB)); FAIL=$((FAIL+SUB))

echo
echo "결과: PASS $PASS · FAIL $FAIL"
[ "$FAIL" -eq 0 ] || exit 1
exit 0

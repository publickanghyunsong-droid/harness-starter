#!/bin/bash
# preflight_load_check.sh — 무거운 작업(학습·적분·대량취득) 착수 전 부하 확인
#
# 왜: 잊힌 예약 작업이 배경에서 무거운 작업을 재개하던 중, 그 위에 새 작업 2개를
#     병렬로 얹어 **세 프로세스 동시 사망 · 5시간 유실**한 실측 사고가 있었다.
#     ★규약을 "맥락"이 아니라 "행위"로 건다: 재발주든 신규든, 무거운 프로세스를 띄우기 전 실행.
#
# 사용: bash preflight/preflight_load_check.sh
# 종료코드: 0 = 착수 가능 / 1 = 착수 부적합 / 2 = **측정 불가(판정 보류)**
#   ★2를 0으로 접지 않는 이유: 못 잰 것을 "괜찮다"로 바꾸면 게이트가 항상 통과가 된다.
#     그건 게이트가 없는 것보다 나쁘다(없는 줄 알면 대비하지만, 통과하면 지켜지는 줄 안다).
#
# ★★판정 지표 선택의 근거 — 되돌리기 전에 읽을 것:
#   초판은 **스왑 누적 사용량 단독**(문턱 1,500MB)으로 판정해 상시 오탐이었다.
#   실측: 스왑 used 1,713MB로 NO-GO인데 **같은 순간 커널 압력=normal · 여유 71%.**
#   macOS는 압력이 해소돼도 스왑을 즉시 회수하지 않으므로 **누적량은 압력의 지표가 아니다.**
#   → 판정을 ①커널 압력등급 ②여유 비율 ③**스왑아웃 활동률**(실제 thrashing)로 바꾸고,
#     누적량은 참고 표시로 강등했다. *게이트는 "지금 압력이 있나"를 물어야 한다.*
#
#   ★★그 다음 판에서 **두 방향을 함께** 고쳤다. 지표를 고른 뒤에도 남아 있던 두 오작동이다:
#     ① 거짓 통과(더 위험하다): [3]에서 지금 도는 무거운 작업을 **출력만 하고 판정식에 넣지
#        않았다.** 그러니 이 게이트를 만들게 한 사고(조용히 도는 작업 위에 새 작업을 얹는 것)를
#        그대로 재현해도 압력만 normal이면 통과했다. 막으라고 만든 것을 안 막고 있었다.
#        → 경쟁 작업을 **1급 판정 근거로 승격**하되 무게를 갈랐다. 무거운 것(학습·대규모 적분)은
#          다른 지표와 무관하게 즉시 차단, 가벼운 것(채점·집계·렌더)은 경고만 하고 통과.
#     ② 거짓 거부: `압력 != normal` 이 **단독 거부권**이라, 8GB급 기계의 상시 warning에서
#        경쟁 작업 0건·스왑아웃 0.00MB/s인데도 NO-GO가 났다(실측 2회).
#        → warning 은 **단독으로 거부하지 않는다**(경쟁 작업 또는 스왑아웃과 함께일 때만).
#          critical 은 그대로 단독 거부다. ⚠️이 완화를 되돌리려면 위 실측부터 다시 재라.
#     ⚠️게이트가 죽는 가장 흔한 방식은 "통과만 늘리는 손질"이다. 그래서 이 판은 **양방향**으로
#       잰다 → tests/test_preflight.sh (경고 단독→GO / 무거운 경쟁→NO-GO / 가벼운 경쟁→GO).

set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 설정 주입 ────────────────────────────────────────────────
# harness.toml 을 위로 올라가며 찾아 셸 변수로 받는다. 실패해도 죽지 않는다 —
# 설정 로더가 없다고 게이트가 아예 안 도는 것이 더 나쁘므로, 아래 기본값으로 계속 간다.
# (전제: 이 스크립트가 <프로젝트루트>/preflight/ 에 있다. 옮겨 쓸 거면 이 경로만 고쳐라.)
if command -v python3 >/dev/null 2>&1; then
  _sh=$(cd "$HERE/.." && python3 -m harness.config --sh 2>/dev/null || true)
  [ -n "${_sh:-}" ] && eval "$_sh" || true
fi

SAMPLE_SEC=${HARNESS_SAMPLE_SEC:-3}                    # 스왑 활동률 표본 구간(초)
FREE_PCT_MIN=${HARNESS_FREE_PCT_MIN:-15}               # 시스템 여유 메모리 최소 비율(%)
SWAPOUT_MBPS_MAX=${HARNESS_SWAPOUT_MBPS_MAX:-5}        # 스왑아웃 허용 속도(MB/s)
PROC_PATTERNS=${HARNESS_PROC_PATTERNS:-}               # 즉시 차단할 **무거운** 경쟁 작업 정규식
LIGHT_PROC_PATTERNS=${HARNESS_LIGHT_PROC_PATTERNS:-}   # 경고만 할 **가벼운** 경쟁 작업 정규식
SWAPOUT_COMPANION=${HARNESS_SWAPOUT_COMPANION_MBPS:-0.5}  # 압력 warning 을 '실제 경합'으로 볼 스왑아웃 하한
PSI_WARN_PCT=${HARNESS_PSI_WARN_PCT:-10}               # (Linux) PSI some avg10 ≥ 이 값이면 warning
PSI_CRIT_PCT=${HARNESS_PSI_CRIT_PCT:-50}               # (Linux) 〃 ≥ 이 값이면 critical
SCHED_LIST_CMD=${HARNESS_SCHED_LIST_CMD:-}             # 예약 목록 명령(OS별)
SCHED_MATCH=${HARNESS_SCHED_MATCH:-}
OS=${HARNESS_OS:-$(uname -s)}
PROC=${HARNESS_PROC_ROOT:-/proc}                       # 리눅스 분기 테스트용 주입점

echo "════ 착수 전 부하 확인 (OS=${OS}) ════"

echo "[1] 상위 메모리 프로세스 (RSS)"
ps -Ao rss,pid,command 2>/dev/null | sort -rn | head -5 |
  awk '{printf "    %6.2f GB  pid=%-6s %s\n", $1/1048576, $2, substr($0, index($0,$3), 62)}'

echo "[2] 등록된 예약 작업"
if [ -n "$SCHED_LIST_CMD" ]; then
  # ★파이프 끝이 sed면 종료코드가 항상 0이라 `|| echo` 폴백이 죽는다(초판 버그).
  #   → 변수로 받아서 판정한다.
  JOBS=$(eval "$SCHED_LIST_CMD" 2>/dev/null | { [ -n "$SCHED_MATCH" ] && grep -Ei "$SCHED_MATCH" || cat; })
  if [ -n "${JOBS:-}" ]; then echo "$JOBS" | sed 's/^/    /'; else echo "    (일치하는 예약 없음)"; fi
else
  echo "    (미설정 - harness.toml [scheduled].list_cmd 를 켜면 여기서 확인된다)"
fi

echo "[3] 실행 중인 경쟁 작업: ★★판정 근거 (무거운 것=즉시 차단 / 가벼운 것=경고만)"
#     (ps 개수만 세면 래퍼셸·자식 프로세스가 같이 잡혀 못 가른다 → lstart·ppid를 함께 찍는다)
# ⚠️패턴 목록은 stale해진다 — 새 장기 스크립트를 만들면 harness.toml 에 **반드시 추가**할 것.
scan_procs() {   # $1=정규식 → 자기 자신·부모를 뺀 PID 목록(공백 구분)
  [ -z "${1:-}" ] && return 0
  pgrep -f "$1" 2>/dev/null | grep -vx -e "$$" -e "${PPID:-0}" | tr '\n' ' '
}
show_procs() {   # $1=PID 목록  $2=꼬리표
  ps -o pid,ppid,lstart,command -p "${1// /,}" 2>/dev/null | cut -c1-150 | sed "s/^/    [$2] /"
}
# ★프로세스 목록을 못 읽는 환경(샌드박스 등)에서는 pgrep 이 오류로 끝나는데, 그 오류를 삼키면
#   "못 읽었다"가 "0건"으로 둔갑해 거짓 GO가 난다. 조회 자체가 되는지 먼저 본다.
#   pgrep 종료코드: 0=찾음 / 1=없음 / 2 이상=조회 실패(명령 없음 127 포함).
PROC_UNREADABLE=0
if [ -n "$PROC_PATTERNS$LIGHT_PROC_PATTERNS" ]; then
  pgrep -f "zzz_preflight_probe_$$" >/dev/null 2>&1
  [ $? -ge 2 ] && PROC_UNREADABLE=1
fi
HEAVY_PIDS=$(scan_procs "$PROC_PATTERNS")
LIGHT_RAW=$(scan_procs "$LIGHT_PROC_PATTERNS")
# ★같은 프로세스가 양쪽에 걸리면 **무거운 쪽이 이긴다**(안전한 방향으로 접는다).
LIGHT_PIDS=""
for _p in $LIGHT_RAW; do
  case " $HEAVY_PIDS " in *" $_p "*) ;; *) LIGHT_PIDS="$LIGHT_PIDS $_p" ;; esac
done
LIGHT_PIDS="${LIGHT_PIDS# }"   # ps -p 는 ",123" 처럼 앞이 빈 목록을 못 받는다
NBUSY_HEAVY=$(echo "$HEAVY_PIDS" | wc -w | tr -d ' ')
NBUSY_LIGHT=$(echo "$LIGHT_PIDS" | wc -w | tr -d ' ')
if [ -z "$PROC_PATTERNS" ] && [ -z "$LIGHT_PROC_PATTERNS" ]; then
  echo "    (미설정 - harness.toml [preflight].process_patterns / light_process_patterns)"
  echo "    ⚠️미설정이면 이 항목은 **판정에 아무 영향도 못 준다.** 자기 프로젝트의 긴 작업 이름을 넣어라."
elif [ "$PROC_UNREADABLE" -eq 1 ]; then
  echo "    ⚠️측정 불가: 프로세스 목록을 읽지 못했다(pgrep 조회 실패). 0건이 아니다"
elif [ "$NBUSY_HEAVY" -eq 0 ] && [ "$NBUSY_LIGHT" -eq 0 ]; then
  echo "    없음"
else
  [ "$NBUSY_HEAVY" -gt 0 ] && show_procs "$HEAVY_PIDS" "무거움"
  [ "$NBUSY_LIGHT" -gt 0 ] && show_procs "$LIGHT_PIDS" "가벼움"
fi

echo "[4] 메모리 압력 (★판정 근거)"
PLEVEL=""; PLABEL="unknown"; FREEPCT=-1; SWRATE=-1

case "$OS" in
  Darwin)
    PLEVEL=$(sysctl -n kern.memorystatus_vm_pressure_level 2>/dev/null || echo "")
    case "${PLEVEL:-}" in
      1) PLABEL="normal" ;; 2) PLABEL="warning" ;; 4) PLABEL="critical" ;;
      "") PLABEL="unknown" ;; *) PLABEL="unknown(${PLEVEL})" ;;
    esac
    FREEPCT=$(memory_pressure 2>/dev/null | awk -F': *' '/free percentage/{gsub("%","",$2); print $2+0}')
    [ -z "${FREEPCT:-}" ] && FREEPCT=-1
    PGSZ=$(vm_stat 2>/dev/null | awk '/page size/{print $8}')
    read_swap() { vm_stat | awk '/Swapouts/{gsub("\\.","",$2); print $2}'; }
    SO1=$(read_swap); sleep "$SAMPLE_SEC"; SO2=$(read_swap)
    if [ -n "${SO1:-}" ] && [ -n "${SO2:-}" ]; then
      SWRATE=$(awk -v a="$SO1" -v b="$SO2" -v p="${PGSZ:-4096}" -v t="$SAMPLE_SEC" \
               'BEGIN{ d=(b-a); if(d<0) d=0; printf "%.2f", d*p/1048576/t }')
    fi
    ;;
  Linux)
    # ⚠️이 분기는 **합성 /proc 픽스처로만 검증**했다(개발기가 macOS). 실제 리눅스 커널에서
    #   1회 실행해 보고, 다르면 여기 주석을 고쳐라. HARNESS_PROC_ROOT 로 주입해 시험할 수 있다.
    if [ -r "$PROC/pressure/memory" ]; then
      # PSI: some avg10 = 최근 10초간 메모리 압력으로 정체된 시간 비율(%)
      PSI=$(awk '/^some/{for(i=1;i<=NF;i++) if($i ~ /^avg10=/){sub("avg10=","",$i); print $i}}' \
            "$PROC/pressure/memory" 2>/dev/null)
      # ⚠️PSI→등급 사상(10%=warning · 50%=critical)은 **경험적 문턱이지 커널이 주는 등급이 아니다.**
      #   macOS 의 3단계 등급과 자리를 맞추려고 둔 것이다. 자기 기계에서 재보고 harness.toml 로 조정하라.
      PLEVEL=$(awk -v p="${PSI:-0}" -v w="$PSI_WARN_PCT" -v c="$PSI_CRIT_PCT" \
               'BEGIN{ print (p+0 >= c+0) ? 4 : ((p+0 >= w+0) ? 2 : 1) }')
      PLABEL=$(awk -v p="${PSI:-0}" -v w="$PSI_WARN_PCT" -v c="$PSI_CRIT_PCT" \
               'BEGIN{ printf "%s(PSI some avg10=%.2f%%)", (p+0>=c+0?"critical":(p+0>=w+0?"warning":"normal")), p }')
    fi
    if [ -r "$PROC/meminfo" ]; then
      FREEPCT=$(awk '/^MemTotal:/{t=$2} /^MemAvailable:/{a=$2} END{ if(t>0) printf "%.0f", 100*a/t; else print -1 }' \
                "$PROC/meminfo")
      [ -z "$PLEVEL" ] && { PLEVEL=1; PLABEL="normal(PSI 없음 — 여유비율로만 판정)"; }
    fi
    if [ -r "$PROC/vmstat" ]; then
      PGSZ=$(getconf PAGESIZE 2>/dev/null || echo 4096)
      read_swap() { awk '/^pswpout /{print $2}' "$PROC/vmstat"; }
      SO1=$(read_swap); sleep "$SAMPLE_SEC"; SO2=$(read_swap)
      [ -n "${SO1:-}" ] && [ -n "${SO2:-}" ] && \
        SWRATE=$(awk -v a="$SO1" -v b="$SO2" -v p="$PGSZ" -v t="$SAMPLE_SEC" \
                 'BEGIN{ d=(b-a); if(d<0) d=0; printf "%.2f", d*p/1048576/t }')
    fi
    ;;
  *)
    echo "    지원하지 않는 OS: 측정 불가"
    ;;
esac

echo "    커널 압력등급: ${PLEVEL:-?} (${PLABEL})"
echo "    시스템 여유 비율: ${FREEPCT}%"
echo "    스왑아웃 활동률: ${SWRATE} MB/s  (표본 ${SAMPLE_SEC}s)"

echo "[5] 스왑 누적 (참고: ★판정에 쓰지 않음)"
case "$OS" in
  Darwin) sysctl -n vm.swapusage 2>/dev/null | sed 's/^/    /' ;;
  Linux)  awk '/^Swap/{printf "    %s %s kB\n", $1, $2}' "$PROC/meminfo" 2>/dev/null ;;
esac
echo "    ↑ 압력이 해소돼도 스왑은 즉시 회수되지 않아 누적량은 계속 높게 남는다."
echo "      초판이 이 값을 단독 문턱으로 써서 무거운 작업 직후엔 항상 NO-GO였다."

echo
if [ "$PROC_UNREADABLE" -eq 1 ]; then
  echo "════ 판정: ⚠️ 측정 불가: GO/NO-GO를 말할 수 없다(exit 2) ════"
  echo "    경쟁 작업을 확인하지 못했다. 프로세스 조회가 되는 터미널에서 다시 돌리거나 수동으로 확인하라."
  exit 2
fi
if [ -z "${PLEVEL:-}" ] && [ "${FREEPCT}" = "-1" ] && [ "${SWRATE}" = "-1" ]; then
  echo "════ 판정: ⚠️ 측정 불가: GO/NO-GO를 말할 수 없다(exit 2) ════"
  echo "    지표를 하나도 못 읽었다. 이 OS용 분기를 추가하거나 수동으로 확인하라."
  exit 2
fi

echo "════ 판정 (경쟁작업=무거움 ${NBUSY_HEAVY}건·가벼움 ${NBUSY_LIGHT}건 · 압력=${PLABEL} · 여유=${FREEPCT}% · 스왑아웃=${SWRATE}MB/s)"
echo "         기준: 무거운 경쟁작업 0건 · 압력≠critical · 여유>${FREE_PCT_MIN}% · 스왑아웃<${SWAPOUT_MBPS_MAX}MB/s ════"
awk -v pl="${PLEVEL:-1}" -v fp="$FREEPCT" -v sr="$SWRATE" \
    -v nbh="$NBUSY_HEAVY" -v nbl="$NBUSY_LIGHT" -v swc="$SWAPOUT_COMPANION" \
    -v fpm="$FREE_PCT_MIN" -v srm="$SWAPOUT_MBPS_MAX" 'BEGIN{
  bad=0
  # ★① 경쟁 작업 = 1급 판정 근거. 무게로 가른다(출력만 하던 판의 거짓 통과를 여기서 닫는다).
  if (nbh+0 > 0) {
    print "    ❌ 무거운 경쟁 작업 " nbh "건 실행 중: 다른 지표와 무관하게 차단(가속기·메모리는 순차로만)"
    bad=1
  } else if (nbl+0 > 0) {
    print "    ⚠️ 가벼운 경쟁 작업 " nbl "건: 경고만 하고 통과시킨다. 지금 띄울 것이 무겁다면 멈춰라"
  }
  # ★② 압력: critical 은 단독 거부 / warning 은 **단독으로 거부하지 않는다**.
  #    (상시 warning 기계에서 경쟁 0·스왑아웃 정지인데 거부하던 거짓 거부를 여기서 닫는다.)
  if (pl+0 == 4) { print "    ❌ 커널 압력 critical"; bad=1 }
  else if (pl+0 != 1) {
    if (nbh+0 > 0 || nbl+0 > 0 || (sr+0 >= 0 && sr+0 > swc+0)) {
      print "    ❌ 압력 warning + (경쟁 작업 또는 스왑아웃): 상시 압력이 아니라 실제 경합이다"; bad=1
    } else {
      print "    ⚠️ 압력 warning 이나 경쟁 작업 0·스왑아웃 정지: 상시 압력으로 보고 통과"
    }
  }
  if (fp+0 >= 0 && fp+0 < fpm+0) { print "    ❌ 시스템 여유 메모리 부족"; bad=1 }
  if (sr+0 >= 0 && sr+0 > srm+0) { print "    ❌ 스왑아웃 진행 중: 이미 thrashing"; bad=1 }
  if (bad) { print "    ❌ 착수 부적합: 부하 해소 후 재시도"; exit 1 }
  print "    ✅ 착수 가능"; exit 0 }'
RC=$?
cat <<'EOF'

── 착수 시 지킬 것 (사고 재발 방지) ──
  · 가속기(GPU) 작업은 **순차로만** — 병렬해도 장치가 1개면 총시간은 안 줄고 메모리만 배로 먹는다
  · 메모리 판정은 **RSS로** — 프레임워크가 보고하는 할당량은 일부일 뿐이다
  · 긴 학습은 **중간 체크포인트 필수** (끝에만 저장하면 사고 시 전량 유실)
  · 예약을 새로 걸면 **해제 방법과 함께** 기록
EOF
exit $RC

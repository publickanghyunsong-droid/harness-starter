#!/bin/bash
# test_preflight.sh — 착수 전 부하 게이트 **양방향** 검증.
#
# 게이트 테스트의 규율은 하나다: *막히는가*와 *통과하는가*를 같이 잰다.
# 문턱을 합성으로 흔들어 두 방향을 모두 발동시킨다.
#
# ★D절은 **경쟁 작업 판정**을 잰다. 게이트가 한때 무거운 프로세스 목록을 화면에 출력만 하고
#   판정식에는 넣지 않았다(거짓 통과). 반대로 압력 warning 하나만으로 거부하기도 했다(거짓 거부).
#   그래서 여기서 재는 것은 네 갈래다:
#     ① 경고 단독(경쟁 0·스왑아웃 0) → GO      ← 옛 판이 NO-GO를 내던 회귀 자리
#     ② 무거운 경쟁 작업 → 다른 지표가 아무리 좋아도 NO-GO
#     ③ 가벼운 경쟁 작업만 → 경고 출력 + GO
#     ④ 지표를 하나도 못 읽음 → exit 2 (측정 불가는 통과가 아니다)
#   ★경쟁 작업은 **주입 스위치가 아니라 진짜 프로세스를 띄워서** 잰다. 실행 중인 프로세스를
#     정규식으로 찾는 경로(pgrep -f)까지 함께 검증되고, 판정을 무르게 하는 뒷문도 안 생긴다.
#
# 리눅스 분기는 **합성 /proc 픽스처**(HARNESS_PROC_ROOT 주입)로 잰다.
#   ⚠️이것이 검증하는 것: 파싱·산술·문턱 판정 로직.
#      검증하지 못하는 것: 실제 리눅스 커널의 PSI/vmstat 값이 그 형식으로 나오는가.
#      (개발기가 macOS다. 실제 리눅스에서 1회 실행이 남아 있다 — 미검증.)
#
# 사용: bash tests/test_preflight.sh [-v]
# 종료코드: 0 = 전부 통과 / 1 = 실패

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PF="$ROOT/preflight/preflight_load_check.sh"
VERBOSE=${1:-}
PASS=0; FAIL=0

# ★이 묶음은 진짜 프로세스를 띄워 pgrep 으로 찾는다. 프로세스 목록을 못 읽는 환경(일부 에이전트
#   샌드박스)에서는 잴 수 없다. 그럴 때 항목마다 따로 실패시키지 않고 이유를 한 번 밝히고 멈춘다.
#   측정 불가는 통과가 아니므로 PASS 로 세지 않는다.
pgrep -f "zzz_preflight_test_probe_$$" >/dev/null 2>&1
if [ $? -ge 2 ]; then
  echo "  측정 불가: 이 환경은 프로세스 목록을 읽지 못한다(pgrep 조회 실패)."
  echo "            이 묶음은 프로세스 조회가 되는 일반 터미널에서 돌려라."
  echo
  echo "결과: PASS 0 · FAIL 1"
  exit 1
fi
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

check() {  # $1=기대exit(여러개면 "0 1") $2=설명 ... 나머지는 env로 넘어옴
  local want="$1" desc="$2"; shift 2
  local out rc
  out=$(env "$@" bash "$PF" 2>&1); rc=$?
  case " $want " in
    *" $rc "*) PASS=$((PASS+1)); [ -n "$VERBOSE" ] && printf '  ok   exit=%s  %s\n' "$rc" "$desc" ;;
    *) FAIL=$((FAIL+1)); printf '  FAIL 기대exit=[%s] 실제=%s  %s\n' "$want" "$rc" "$desc"
       [ -n "$VERBOSE" ] && printf '%s\n' "$out" | tail -6 ;;
  esac
  return 0
}

mkfix() {  # $1=dir  $2=MemAvailable(kB)  $3=psi_avg10  $4=pswpout(pages)
  mkdir -p "$1/pressure"
  cat > "$1/meminfo" <<EOF
MemTotal:       16384000 kB
MemFree:         2000000 kB
MemAvailable:   $2 kB
SwapTotal:       4194304 kB
SwapFree:        4000000 kB
EOF
  cat > "$1/pressure/memory" <<EOF
some avg10=$3 avg60=0.00 avg300=0.00 total=0
full avg10=0.00 avg60=0.00 avg300=0.00 total=0
EOF
  printf 'pgpgin 100\npswpin 0\npswpout %s\n' "$4" > "$1/vmstat"
}

nofire() {  # $1=설명 $2=출력에 나오면 안 되는 문구 ... 나머지 env
  local desc="$1" bad="$2"; shift 2
  local out; out=$(env "$@" bash "$PF" 2>&1)
  if printf '%s' "$out" | grep -q -- "$bad"; then
    FAIL=$((FAIL+1)); printf '  FAIL 발동하면 안 되는 기준이 발동: %s  (%s)\n' "$bad" "$desc"
  else
    PASS=$((PASS+1)); [ -n "$VERBOSE" ] && printf '  ok   미발동 %-22s %s\n' "$bad" "$desc"
  fi
  return 0
}

fire() {  # $1=설명 $2=출력에 반드시 나와야 하는 문구 ... 나머지 env
  local desc="$1" want="$2"; shift 2
  local out; out=$(env "$@" bash "$PF" 2>&1)
  if printf '%s' "$out" | grep -q -- "$want"; then
    PASS=$((PASS+1)); [ -n "$VERBOSE" ] && printf '  ok   발동   %-22s %s\n' "$want" "$desc"
  else
    FAIL=$((FAIL+1)); printf '  FAIL 발동해야 할 기준이 미발동: %s  (%s)\n' "$want" "$desc"
    [ -n "$VERBOSE" ] && printf '%s\n' "$out" | tail -8
  fi
  return 0
}

# 경쟁 작업 패턴을 **명시적으로 무효화**한다. 안 그러면 harness.toml 기본값(train_ 등)이
# 이 기계에서 우연히 실제 프로세스에 걸려 다른 항목의 판정을 흔든다(테스트가 기계에 의존하게 된다).
NOPROC=(HARNESS_PROC_PATTERNS="zzz_no_such_proc_$$" HARNESS_LIGHT_PROC_PATTERNS="zzz_no_such_proc_$$")

echo "── A. 현재 머신(darwin/실측) ──"
# ⚠️여기서 exit 0(GO)을 단정할 수 없다: 커널 압력등급은 문턱 변수로 못 흔든다.
#   실측(2026-08-02 이 기기) 압력등급=2(warning)·여유 35% → NO-GO가 **정답**이었다.
#   그래서 통과 방향은 (a)기준별 미발동 확인과 (b)아래 C의 리눅스 픽스처로 증명한다.
#   *"게이트가 통과도 한다"를 증명하지 못하는 테스트는 반쪽이다 — 증명 자리를 옮길 뿐 버리지 않는다.*
nofire "느슨한 기준: 여유비율 미발동" "여유 메모리 부족" \
       HARNESS_SAMPLE_SEC=1 HARNESS_FREE_PCT_MIN=0 HARNESS_SWAPOUT_MBPS_MAX=999999
nofire "느슨한 기준: 스왑아웃 미발동" "thrashing" \
       HARNESS_SAMPLE_SEC=1 HARNESS_FREE_PCT_MIN=0 HARNESS_SWAPOUT_MBPS_MAX=999999
# 기준을 극단으로 조이면 막혀야 한다(=게이트가 항상 통과하는 고장이 아님)
check "1"   "여유비율 문턱 99% → NO-GO" HARNESS_SAMPLE_SEC=1 HARNESS_FREE_PCT_MIN=99
check "1"   "스왑아웃 문턱 -1 → NO-GO"  HARNESS_SAMPLE_SEC=1 HARNESS_SWAPOUT_MBPS_MAX=-1
check "0 1" "기본 설정 실행 자체"       HARNESS_SAMPLE_SEC=1

echo "── B. 미지원 OS → 판정 보류(exit 2), '통과'가 아니다 ──"
check "2"   "OS=Plan9 → 측정 불가"      HARNESS_OS=Plan9 HARNESS_SAMPLE_SEC=1

echo "── C. 리눅스 분기 (합성 /proc 픽스처) ──"
mkfix "$TMP/ok"      8192000 0.00    1000     # 여유 50% · PSI 0 · 스왑아웃 정지
check "0" "건강 → GO"        HARNESS_OS=Linux HARNESS_PROC_ROOT="$TMP/ok" HARNESS_SAMPLE_SEC=1 "${NOPROC[@]}"

mkfix "$TMP/starved"  819200 0.00    1000     # 여유 5% < 15%
check "1" "여유 5% → NO-GO"  HARNESS_OS=Linux HARNESS_PROC_ROOT="$TMP/starved" HARNESS_SAMPLE_SEC=1 "${NOPROC[@]}"

# ★① 경고 단독 → GO. 예전 판은 `압력 != normal` 을 단독 거부권으로 써서 여기서 NO-GO를 냈고,
#   그 탓에 상시 warning 이 뜨는 기계에서는 게이트가 사실상 항상 NO-GO였다(거짓 거부).
mkfix "$TMP/psi"     8192000 25.00   1000     # PSI some avg10 25% ≥ 10 → warning
check "0" "경고 단독(경쟁 0·스왑아웃 0) → GO" \
      HARNESS_OS=Linux HARNESS_PROC_ROOT="$TMP/psi" HARNESS_SAMPLE_SEC=1 "${NOPROC[@]}"
nofire "경고 단독인데 '실제 경합'으로 몰지 않는다" "실제 경합" \
      HARNESS_OS=Linux HARNESS_PROC_ROOT="$TMP/psi" HARNESS_SAMPLE_SEC=1 "${NOPROC[@]}"

# ★단, critical 은 여전히 **단독 거부**다. 완화가 여기까지 번지면 게이트가 죽는다.
mkfix "$TMP/crit"    8192000 60.00   1000     # PSI 60% ≥ 50 → critical
check "1" "압력 critical 단독 → NO-GO" \
      HARNESS_OS=Linux HARNESS_PROC_ROOT="$TMP/crit" HARNESS_SAMPLE_SEC=1 "${NOPROC[@]}"

# 스왑아웃 '활동률'은 두 시점의 차이라, 표본 구간 중간에 값이 뛰어야 재현된다.
mkfix "$TMP/thrash"  8192000 0.00    1000
( sleep 1; printf 'pgpgin 100\npswpin 0\npswpout 200000\n' > "$TMP/thrash/vmstat" ) &
check "1" "표본 중 스왑아웃 급증 → NO-GO" HARNESS_OS=Linux HARNESS_PROC_ROOT="$TMP/thrash" HARNESS_SAMPLE_SEC=3 "${NOPROC[@]}"
wait

echo "── D. 경쟁 작업 (★진짜 프로세스를 띄워서 잰다) ──"
# 표식이 들어간 스크립트를 실제로 실행하고, 그 표식을 패턴으로 넘긴다.
MARK_H="harnesstest_heavy_$$"; MARK_L="harnesstest_light_$$"; MARK_X="harnesstest_nomatch_$$"
printf '#!/bin/bash\nsleep 25\n' > "$TMP/$MARK_H"; chmod +x "$TMP/$MARK_H"
printf '#!/bin/bash\nsleep 25\n' > "$TMP/$MARK_L"; chmod +x "$TMP/$MARK_L"
"$TMP/$MARK_H" & PID_H=$!
"$TMP/$MARK_L" & PID_L=$!
trap 'kill $PID_H $PID_L 2>/dev/null; rm -rf "$TMP"' EXIT
sleep 0.3   # 프로세스가 ps 에 보일 때까지

# ★② 무거운 경쟁 작업 → 다른 지표가 아무리 좋아도 NO-GO.
#    (픽스처는 여유 50%·PSI 0·스왑아웃 정지 = 지표만 보면 완벽한 GO 상태다)
HEAVY_ENV=(HARNESS_OS=Linux HARNESS_PROC_ROOT="$TMP/ok" HARNESS_SAMPLE_SEC=1
           HARNESS_PROC_PATTERNS="$MARK_H" HARNESS_LIGHT_PROC_PATTERNS="$MARK_L")
check "1" "무거운 경쟁 작업 → 지표가 완벽해도 NO-GO" "${HEAVY_ENV[@]}"
fire  "차단 사유가 경쟁 작업으로 찍힌다" "무거운 경쟁 작업" "${HEAVY_ENV[@]}"

# ★③ 가벼운 경쟁 작업만 → 경고 출력 + GO.
LIGHT_ENV=(HARNESS_OS=Linux HARNESS_PROC_ROOT="$TMP/ok" HARNESS_SAMPLE_SEC=1
           HARNESS_PROC_PATTERNS="$MARK_X" HARNESS_LIGHT_PROC_PATTERNS="$MARK_L")
check "0" "가벼운 경쟁 작업만 → GO"        "${LIGHT_ENV[@]}"
fire  "가벼워도 경고는 남긴다"  "가벼운 경쟁 작업" "${LIGHT_ENV[@]}"

# 무게가 겹치면 무거운 쪽이 이긴다(안전한 방향으로 접는다).
check "1" "양쪽 패턴에 다 걸리면 무거운 쪽 우선 → NO-GO" \
      HARNESS_OS=Linux HARNESS_PROC_ROOT="$TMP/ok" HARNESS_SAMPLE_SEC=1 \
      HARNESS_PROC_PATTERNS="$MARK_H" HARNESS_LIGHT_PROC_PATTERNS="$MARK_H"

# ★경고 단독은 통과지만, **경고 + 가벼운 경쟁**은 실제 경합이라 막는다(완화가 무한정 번지지 않는다).
check "1" "경고 + 가벼운 경쟁 작업 → NO-GO" \
      HARNESS_OS=Linux HARNESS_PROC_ROOT="$TMP/psi" HARNESS_SAMPLE_SEC=1 \
      HARNESS_PROC_PATTERNS="$MARK_X" HARNESS_LIGHT_PROC_PATTERNS="$MARK_L"

# ★④ 측정 불가는 경쟁 작업이 없어도 통과가 아니다(exit 2 유지 — D절 완화가 여기 번지면 안 된다).
check "2" "측정 불가 + 경쟁 0 → 여전히 exit 2" \
      HARNESS_OS=Plan9 HARNESS_SAMPLE_SEC=1 "${NOPROC[@]}"

# ★⑤ 프로세스 목록을 못 읽으면 "0건"이 아니라 측정 불가다(샌드박스에서 거짓 GO가 나던 자리).
#    pgrep 을 조회 실패(exit 3)로 끝나는 가짜로 바꿔 끼워, 지표가 완벽해도 exit 2 인지 본다.
mkdir -p "$TMP/stub"
printf '#!/bin/sh\necho "Cannot get process list" >&2\nexit 3\n' > "$TMP/stub/pgrep"
chmod +x "$TMP/stub/pgrep"
check "2" "프로세스 조회 실패 → 지표가 완벽해도 측정 불가" \
      PATH="$TMP/stub:$PATH" HARNESS_OS=Linux HARNESS_PROC_ROOT="$TMP/ok" HARNESS_SAMPLE_SEC=1 \
      HARNESS_PROC_PATTERNS="$MARK_H" HARNESS_LIGHT_PROC_PATTERNS="$MARK_L"
fire "프로세스 조회 실패는 0건으로 적지 않는다" "프로세스 목록을 읽지 못했다" \
      PATH="$TMP/stub:$PATH" HARNESS_OS=Linux HARNESS_PROC_ROOT="$TMP/ok" HARNESS_SAMPLE_SEC=1 \
      HARNESS_PROC_PATTERNS="$MARK_H" HARNESS_LIGHT_PROC_PATTERNS="$MARK_L"

kill $PID_H $PID_L 2>/dev/null; wait $PID_H $PID_L 2>/dev/null
trap 'rm -rf "$TMP"' EXIT

echo
echo "결과: PASS $PASS · FAIL $FAIL"
[ "$FAIL" -eq 0 ] || exit 1
exit 0

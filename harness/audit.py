#!/usr/bin/env python3
"""audit.py — 하네스 점검 루틴 **1단계(기계 점검)**. 세션이 직접 돌린다.

★이건 예약(cron/무인 headless) 작업이 아니다. 그 전략은 폐기됐다.
  실측 근거: 무인 야간 점검이 **8회 연속 exit 1 · 성공 0회 · 8주간 미발견**.
  아무도 안 보는 백그라운드 점검은 죽어도 죽은 줄 모른다.
  → 점검은 ①주기가 보장되고 ②고칠 사람 눈에 보이는 자리에서 돌아야 한다.
  이 스크립트는 **세션 작업 흐름 안에서** 도는 쪽을 택했다.

  ⚠️여기서 폐기된 것은 *"주기 실행"*이 아니라 *"관측되지 않는 채널"*이다.
    (같은 기간, 앱 UI에 수행 이력이 보이는 루틴은 멀쩡히 돌고 있었다.)
    실패 원인을 한 단계 넓게 잡으면 멀쩡한 수단까지 같이 버린다 — 되돌리지 말 것.

사용: python3 -m harness.audit [--config harness.toml] [--report <경로>]
종료코드: 0 = FAIL 없음 / 1 = FAIL 1건 이상 / 2 = 설정 오류

판정 등급
  FAIL — 도구가 깨졌다 / 있어야 할 검사기가 안 돈다
  WARN — 추세로 볼 것(검사기 없는 자리·미수행·규모 증가·배경에 도는 예약)
  PASS — 정상
  SKIP — **이 프로젝트엔 해당 없음**(설정에 그 섹션이 없다). 에러가 아니다.
         ★선택적 구성요소를 안 쓴다고 FAIL을 내면 아무도 이 도구를 안 쓴다.
"""
import argparse
import fnmatch
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import config as hconfig   # noqa: E402

LEVELS = {"FAIL": 0, "WARN": 1, "PASS": 2, "SKIP": 3}
MARKS = {"FAIL": "[FAIL]", "WARN": "[WARN]", "PASS": "[PASS]", "SKIP": "[ -- ]"}


class Audit(object):
    def __init__(self, cfg):
        self.cfg = cfg
        self.results = []

    def add(self, level, item, msg):
        self.results.append((level, item, msg))

    def skip(self, item, why):
        self.add("SKIP", item, "해당 없음. %s" % why)

    # ── 공통 ─────────────────────────────────────────────
    @staticmethod
    def run(cmd, cwd=None, timeout=120):
        try:
            p = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str),
                               capture_output=True, text=True, timeout=timeout)
            return p.returncode, (p.stdout or "") + (p.stderr or "")
        except subprocess.TimeoutExpired:
            return 124, "timeout"
        except Exception as e:                      # noqa: BLE001
            return 127, str(e)

    # ── A. 살아 있는 예약 작업 ─────────────────────────────
    # 점검 자체는 예약으로 돌지 않지만(위 참조), **다른 예약이 유령으로 남는 것**은
    # 여전히 사고 원인이다. 실측: 잊힌 예약이 5분마다 무거운 작업을 재개하던 중
    # 새 작업 2개를 얹어 세 프로세스 동시 사망 · 5시간 유실.
    def check_scheduled(self):
        sec = self.cfg.section("scheduled")
        if not sec:
            self.skip("살아 있는 예약", "[scheduled] 미설정(예약 루틴을 안 쓰는 프로젝트)")
            return
        list_cmd = sec.get("list_cmd")
        match = sec.get("match", "")
        if not list_cmd:
            self.skip("살아 있는 예약", "[scheduled].list_cmd 미설정")
        else:
            rc, out = self.run(list_cmd)
            if rc not in (0, 1):
                # 목록 명령 자체가 없는 OS(예: launchctl 없는 리눅스) → SKIP이지 FAIL 아니다
                self.skip("살아 있는 예약", "목록 명령 실행 불가(exit %d): %s" % (rc, list_cmd))
            else:
                live = [l.strip() for l in out.splitlines()
                        if l.strip() and (not match or re.search(match, l, re.I))]
                if live:
                    self.add("WARN", "살아 있는 예약",
                             "배경에서 도는 예약 %d건 → %s · 인수인계에 명시하고 "
                             "무거운 작업 착수 전 부하 확인" % (len(live), "; ".join(live[:5])[:300]))
                else:
                    self.add("PASS", "살아 있는 예약", "일치하는 예약 없음")

        # 잔존 정의 파일 — 해제만 하고 정의가 남으면 재부팅 때 부활한다
        rdir = sec.get("residue_dir")
        if rdir:
            rdir = os.path.expanduser(self.cfg.expand(rdir))
            glob = sec.get("residue_glob", "*")
            found = [f for f in os.listdir(rdir)
                     if fnmatch.fnmatch(f, glob)] if os.path.isdir(rdir) else []
            if found:
                self.add("WARN", "예약 잔존",
                         "%s 에 정의 파일이 %d건 남아 있다(%s). 영구 해제라면 정의 파일도 함께 치운다"
                         % (rdir, len(found), ", ".join(sorted(found)[:5])))
            else:
                self.add("PASS", "예약 잔존", "잔존 정의 파일 없음")

    # ── A-0. 루틴이 실행체로 등록돼 있는가 ─────────────────
    def check_routine_registration(self):
        p = self.cfg.get("routine.registered_path")
        if not p:
            self.skip("루틴 등록", "[routine].registered_path 미설정(수동 실행 프로젝트)")
            return
        p = os.path.expanduser(self.cfg.expand(p))
        ok = os.path.exists(p)
        self.add("PASS" if ok else "FAIL", "루틴 등록",
                 "%s %s" % (p, "등록됨" if ok else "미등록이라 이 루틴은 스스로 돌 방법이 없다"))

    # ── A-2. 루틴 자신의 최근 수행 ─────────────────────────
    # ★상태 파일을 따로 두지 않고 **모두가 읽는 타임라인**(log)에 남긴 표식을 읽는다.
    #   전용 상태 파일은 아무도 안 열어서, 안 돈 루틴이 조용히 숨는다.
    def check_routine_recency(self):
        logf = self.cfg.get("routine.log_file")
        if not logf:
            self.skip("루틴 수행 이력", "[routine].log_file 미설정")
            return
        path = self.cfg.path_of(logf)
        marker = self.cfg.get("routine.marker", r"^##\s*\[(\d{4}-\d{2}-\d{2})\]\s*check\b")
        max_days = int(self.cfg.get("routine.max_age_days", 10))
        if not os.path.exists(path):
            self.add("WARN", "루틴 수행 이력", "로그 파일을 찾지 못했다: %s" % path)
            return
        with open(path, encoding="utf-8", errors="replace") as fh:
            dates = re.findall(marker, fh.read(), re.M)
        dates = [d for d in dates if isinstance(d, str) and re.match(r"\d{4}-\d{2}-\d{2}$", d)]
        if not dates:
            self.add("WARN", "루틴 수행 이력", "로그에 수행 표식이 없다. 이번이 첫 회차인지 확인한다")
            return
        last = max(dates)
        age = (datetime.now() - datetime.strptime(last, "%Y-%m-%d")).days
        self.add("WARN" if age > max_days else "PASS", "루틴 수행 이력",
                 "마지막 수행 %s (%d일 전, 기준 %d일) / 총 %d회" % (last, age, max_days, len(dates)))

    # ── B. 게이트 미처리 — 명세만 되고 검사기가 없는 게이트 ───
    @staticmethod
    def _fenced_lines(path):
        """마크다운 코드펜스(``` 또는 ~~~) 안에 있는 줄 번호 집합."""
        out, fence = set(), None
        try:
            lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            return out
        for i, line in enumerate(lines, 1):
            m = re.match(r"\s*(```+|~~~+)", line)
            if m:
                tok = m.group(1)[:3]
                if fence is None:
                    fence, = (tok,)
                    out.add(i)
                    continue
                if tok == fence:
                    out.add(i)
                    fence = None
                    continue
            if fence is not None:
                out.add(i)
        return out

    def _in_code_fence(self, grep_line):
        """`파일:줄번호:내용` 형태의 grep 출력 한 줄이 코드펜스 안인지."""
        parts = grep_line.split(":", 2)
        if len(parts) < 3 or not parts[1].isdigit():
            return False
        return int(parts[1]) in self._fenced_lines(parts[0])

    def check_gate_debt(self):
        sec = self.cfg.section("gate_debt")
        if not sec:
            self.skip("게이트 미처리", "[gate_debt] 미설정")
            return
        pattern = sec.get("pattern")
        dirs = [d for d in self.cfg.paths_of(sec.get("dirs")) if os.path.isdir(d)]
        if not pattern or not dirs:
            self.skip("게이트 미처리", "패턴 또는 대상 디렉터리 없음")
            return
        hits = []
        for d in dirs:
            rc, out = self.run(["grep", "-rn", "--", pattern, d])
            hits += [l for l in out.splitlines() if l.strip()]
        # ★코드블록 안의 표식은 미처리가 아니라 예시다(2026-08-23).
        #   안내 문서가 "이렇게 적어 두라"고 보여 주는 예시까지 세면,
        #   독자가 규약 하나를 적어도 2건으로 나와 안내문과 어긋난다.
        #   실측: starter/docs/conventions.md 의 예시 1건이 그대로 미처리로 잡혔다.
        hits = [l for l in hits if not self._in_code_fence(l)]
        if hits:
            self.add("WARN", "게이트 미처리",
                     "검사기 부재 표시 %d건이 미처리다. 절대값보다 추세로 본다" % len(hits))
        else:
            self.add("PASS", "게이트 미처리", "`%s` 표시 0건" % pattern)

    # ── C. 도구 스모크런 — 규약이 전제하는 스크립트가 지금도 도는가 ──
    def check_smoke(self):
        entries = self.cfg.data.get("smoke") or []
        if not entries:
            self.skip("도구 스모크런", "[[smoke]] 항목 없음")
            return
        for e in entries:
            name = e.get("name", "(이름없음)")
            cmd = self.cfg.expand(e.get("cmd", ""))
            ok = [int(x) for x in (e.get("ok") or [0])]
            if not cmd:
                self.add("FAIL", "도구 %s" % name, "cmd 가 비어 있다")
                continue
            # 대상 파일이 아예 없으면 FAIL이 맞다 — 그게 '깨진 도구'다.
            # 다만 "이 프로젝트는 그 도구를 안 쓴다"면 항목 자체를 지우면 된다(SKIP 경로).
            rc, out = self.run(cmd, cwd=self.cfg.root, timeout=int(e.get("timeout", 120)))
            if rc in ok:
                self.add("PASS", "도구 %s" % name, "정상 (exit %d)" % rc)
            else:
                tail = out.strip().splitlines()[-1][:160] if out.strip() else ""
                self.add("FAIL", "도구 %s" % name,
                         "exit %d 로 끝났다.%s" % (rc, " 마지막 줄: " + tail if tail else ""))

    # ── D. 깨진 내부 링크 ──────────────────────────────────
    #    (첫 회차는 baseline. 이후 '늘었는가'로 본다 — 절대값은 의미가 약하다)
    def check_links(self):
        sec = self.cfg.section("links")
        if not sec:
            self.skip("깨진 내부 링크", "[links] 미설정(노트/위키 없는 프로젝트)")
            return None
        dirs = [d for d in self.cfg.paths_of(sec.get("dirs")) if os.path.isdir(d)]
        if not dirs:
            self.skip("깨진 내부 링크", "대상 디렉터리가 없다")
            return None
        ext = sec.get("ext", ".md")
        pattern = sec.get("pattern", r"\[\[([^\]|#]+)")
        exclude = [e.strip("/") for e in (sec.get("exclude") or [])]
        files, names = [], set()
        for d in dirs:
            for base, subdirs, fnames in os.walk(d):
                subdirs[:] = [s for s in subdirs if s not in exclude and not s.startswith(".")]
                for f in fnames:
                    if f.endswith(ext):
                        files.append(os.path.join(base, f))
                        names.add(f[: -len(ext)])
        broken = {}
        for path in files:
            if any(("/%s/" % e) in path for e in exclude):
                continue
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
                # ★코드 안의 [[…]] 는 링크가 아니다(2026-09-26).
                #   실측: 규약 문서에 `[[smoke]]`(TOML 배열 테이블)를 적으면 옵시디언
                #   위키링크로 읽혀 "깨진 내부 링크"로 잡혔다. 그런데 이 스타터의 안내가
                #   바로 그 이름을 적으라고 시킨다 — 시킨 대로 한 독자에게 없는 경고가 뜬다.
                #   게이트 미처리(_in_code_fence)와 같은 이유이고, 여기서는 코드펜스와
                #   인라인 코드(`…`) 를 함께 걷어낸다.
                text = re.sub(r"```.*?```", "", text, flags=re.S)
                text = re.sub(r"`[^`\n]*`", "", text)
                for target in re.findall(pattern, text):
                    t = target.strip()
                    if t.endswith(ext):
                        t = t[: -len(ext)].strip()
                    if t and t not in names:
                        broken.setdefault(t, set()).add(self.cfg.rel(path))
        if broken:
            top = sorted(broken.items(), key=lambda kv: -len(kv[1]))[:8]
            self.add("WARN", "깨진 내부 링크", "%d종이 깨졌다. 상위: %s"
                     % (len(broken), ", ".join("%s(%d)" % (k, len(v)) for k, v in top)))
        else:
            self.add("PASS", "깨진 내부 링크", "없음 (문서 %d개 스캔)" % len(files))
        return len(broken)

    # ── E. 규약 규모 추세 — 늘기만 하면 플래그 ──────────────
    def check_corpus(self, extra_metric=None):
        sec = self.cfg.section("corpus")
        if not sec:
            self.skip("규약 규모", "[corpus] 미설정")
            return None
        docs = []
        for f in self.cfg.paths_of(sec.get("files")):
            if os.path.exists(f):
                docs.append((self.cfg.rel(f), f))
        for d in self.cfg.paths_of(sec.get("dirs")):
            if os.path.isdir(d):
                for f in sorted(os.listdir(d)):
                    if f.endswith(sec.get("ext", ".md")):
                        docs.append((os.path.join(os.path.basename(d), f), os.path.join(d, f)))
        if not docs:
            self.skip("규약 규모", "대상 문서가 없다")
            return None

        today = datetime.now().strftime("%Y-%m-%d")
        cur = {}
        for name, path in docs:
            with open(path, encoding="utf-8", errors="replace") as fh:
                cur[name] = sum(1 for _ in fh)
        total = sum(cur.values())

        state = self.cfg.path_of(sec.get("state_file", ".harness/corpus_state.tsv"))
        warn_at = int(sec.get("growth_warn_lines", 150))
        prev_date, prev, keep = None, {}, []
        if os.path.exists(state):
            rows = [l.rstrip("\n").split("\t") for l in open(state, encoding="utf-8") if l.strip()]
            rows = [r for r in rows if len(r) == 3 and r[0] != today]  # 같은 날 재실행은 덮어쓴다
            keep = rows
            if rows:
                prev_date = rows[-1][0]
                prev = {n: int(v) for d, n, v in rows if d == prev_date}

        if prev:
            delta = total - sum(prev.values())
            grew = sorted(((cur.get(k, 0) - v, k) for k, v in prev.items()), reverse=True)[:3]
            shrank = [g for g in grew if g[0] < 0]
            lvl = "WARN" if (delta > warn_at and not shrank) else "PASS"
            self.add(lvl, "규약 규모", "총 %d줄 (%s 대비 %+d). 증가 상위: %s"
                     % (total, prev_date, delta,
                        ", ".join("%s %+d" % (k, d) for d, k in grew if d) or "없음"))
        else:
            self.add("PASS", "규약 규모",
                     "총 %d줄 / %d문서. 이번 회차는 baseline 기록이고 비교는 다음 회차부터 한다" % (total, len(cur)))

        os.makedirs(os.path.dirname(state) or ".", exist_ok=True)
        with open(state, "w", encoding="utf-8") as fh:
            for r in keep:
                fh.write("\t".join(r) + "\n")
            for k, v in sorted(cur.items()):
                fh.write("%s\t%s\t%d\n" % (today, k, v))
            if extra_metric is not None:
                fh.write("%s\t_broken_links\t%d\n" % (today, extra_metric))
        return prev_date

    # ── F. 최근 개정된 규약 — 2·3단계(사람/LLM 판단)의 입력 ──
    def check_changed(self, prev_date):
        sec = self.cfg.section("git")
        if not sec or not sec.get("paths"):
            self.skip("최근 개정 규약", "[git] 이 설정돼 있지 않다. 2·3단계 입력은 수동으로 고를 것")
            return None, [], []
        repo = self.cfg.path_of(sec.get("repo", "."))
        rc, _ = self.run(["git", "rev-parse", "--git-dir"], cwd=repo)
        if rc != 0:
            self.skip("최근 개정 규약", "git 저장소가 아니다(또는 git 없음): %s" % repo)
            return None, [], []
        rc, _ = self.run(["git", "rev-parse", "--verify", "HEAD"], cwd=repo)
        if rc != 0:
            # 갓 만든 레포엔 커밋이 없다 → '개정이 없다'는 WARN이 아니라 해당 없음이다
            self.skip("최근 개정 규약", "커밋이 아직 없다: %s" % repo)
            return None, [], []
        since = prev_date or (datetime.now() - timedelta(days=int(sec.get("window_days", 7)))
                              ).strftime("%Y-%m-%d")
        paths = " ".join("'%s'" % p for p in sec["paths"])
        rc, out = self.run('git log --since="%s" --name-only --format="%%h|%%ad|%%s" '
                           '--date=short -- %s' % (since, paths), cwd=repo)
        if rc != 0:
            self.add("WARN", "최근 개정 규약", "git log 실패(exit %d)" % rc)
            return since, [], []
        files, commits = set(), []
        for line in out.splitlines():
            if "|" in line:
                commits.append(line)
            elif line.strip():
                files.add(line.strip())
        self.add("PASS" if files else "WARN", "최근 개정 규약",
                 "%s 이후 %d문서 / %d커밋%s" % (since, len(files), len(commits),
                                            "" if files else ". 개정이 없다(정체인지 확인)"))
        return since, sorted(files), commits


def build_report(au, since, files, commits):
    cfg = au.cfg
    n = {k: sum(1 for lv, _, _ in au.results if lv == k) for k in LEVELS}
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = cfg.get("report.title", "하네스 기계 점검")
    lines = [
        "---", "type: report", "date: %s" % datetime.now().strftime("%Y-%m-%d"),
        "status: active", "---", "",
        "# %s — %s" % (title, stamp), "",
        "> 하네스 점검 루틴 **1단계(기계 점검)**. 세션이 직접 돌린다(무인 예약 아님).",
    ]
    doc = cfg.get("report.spec_doc")
    if doc:
        lines.append("> 정본 = %s" % doc)
    lines += [
        "> 프로젝트: `%s` · 루트 `%s`" % (cfg.get("project.name", "(이름 없음)"), cfg.root), "",
        "**판정: FAIL %d · WARN %d · PASS %d · 해당없음 %d**"
        % (n["FAIL"], n["WARN"], n["PASS"], n["SKIP"]), "",
        "| 판정 | 항목 | 내용 |", "|---|---|---|",
    ]
    for lv, item, msg in sorted(au.results, key=lambda r: LEVELS[r[0]]):
        lines.append("| %s | %s | %s |" % (MARKS[lv], item, msg.replace("|", "\\|")))
    if since is not None:
        lines += ["", "## 2·3단계에서 세션이 읽을 것 — %s 이후 개정된 규약" % since, ""]
        lines += ["- `%s`" % f for f in files] or ["- (없음)"]
        if commits:
            lines += ["", "<details><summary>커밋 %d건</summary>" % len(commits), ""]
            lines += ["- %s" % c for c in commits] + ["", "</details>"]
    return "\n".join(lines) + "\n", n


def main(argv=None):
    ap = argparse.ArgumentParser(description="하네스 기계 점검(1단계)")
    ap.add_argument("--config")
    ap.add_argument("--root")
    ap.add_argument("--report", default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    try:
        cfg = hconfig.load(args.config, args.root)
    except hconfig.ConfigError as e:
        sys.stderr.write("설정 오류: %s\n" % e)
        return 2
    if cfg.path is None:
        sys.stderr.write("경고: harness.toml 을 찾지 못했다. 그러면 모든 점검이 '해당 없음'이 된다.\n")

    au = Audit(cfg)
    au.check_routine_registration()
    au.check_scheduled()
    au.check_routine_recency()
    au.check_gate_debt()
    au.check_smoke()
    broken = au.check_links()
    prev_date = au.check_corpus(broken)
    since, files, commits = au.check_changed(prev_date)

    report, n = build_report(au, since, files, commits)
    if args.report:
        path = cfg.path_of(args.report)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(report)
    if not args.quiet:
        print(report)
    return 1 if n["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())

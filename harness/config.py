"""config.py — `harness.toml` 로더. **경로 결합을 여기 한 곳에 가둔다.**

원칙: 하네스 도구는 자기 프로젝트의 경로를 *알지 못한다*. 전부 이 파일을 통해 주입받는다.
      도구 코드에 절대경로·프로젝트 이름이 한 글자라도 박히면 남이 못 쓴다.

설정 파일 찾는 순서
  1) `--config <경로>`  2) 환경변수 `HARNESS_CONFIG`
  3) 현재 디렉터리에서 위로 올라가며 `harness.toml` 탐색(레포 루트에서 실행 안 해도 되게)

경로 규칙
  · 모든 상대경로는 **프로젝트 루트 기준**으로 푼다.
  · 루트 결정: `[project].root`(설정파일 기준 상대) → 설정파일이 있는 디렉터리 →
    `git rev-parse --show-toplevel` → cwd.
  · 문자열 안의 `{root}` `{config_dir}` `{home}` 는 치환한다.

셸 브리지(`--sh`)
  bash 스크립트(preflight)가 같은 설정을 읽게 해준다. 파이썬을 못 쓰는 상황을
  대비해 bash 쪽은 **기본값을 자기 안에 갖고**, 이 출력이 있으면 덮어쓰는 구조다.
  (설정 로더가 없으면 게이트가 아예 안 도는 것이 더 나쁘다.)
"""
import argparse
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

try:                                   # Python 3.11+
    import tomllib as _toml
    _TOML_IMPL = "tomllib"
except ImportError:                    # pragma: no cover
    try:
        import tomli as _toml          # pip install tomli
        _TOML_IMPL = "tomli"
    except ImportError:
        from harness import minitoml as _toml   # 동봉 폴백(3.6+)
        _TOML_IMPL = "minitoml"

CONFIG_NAME = "harness.toml"


class ConfigError(RuntimeError):
    pass


def find_config(explicit=None):
    cand = explicit or os.environ.get("HARNESS_CONFIG")
    if cand:
        cand = os.path.abspath(os.path.expanduser(cand))
        if not os.path.exists(cand):
            raise ConfigError("설정 파일이 없다: %s" % cand)
        return cand
    d = os.path.abspath(os.getcwd())
    while True:
        p = os.path.join(d, CONFIG_NAME)
        if os.path.exists(p):
            return p
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def _git_toplevel(cwd):
    try:
        p = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd,
                           capture_output=True, text=True, timeout=10)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
    except Exception:                  # noqa: BLE001  (git이 없어도 죽지 않는다)
        pass
    return None


class Config(object):
    def __init__(self, data, path, root):
        self.data = data
        self.path = path                     # 설정 파일 경로 (없으면 None)
        self.root = root                     # 프로젝트 루트 (절대경로)
        self.config_dir = os.path.dirname(path) if path else root
        self.toml_impl = _TOML_IMPL

    # ── 조회 ───────────────────────────────────────────────
    def section(self, name):
        """섹션이 없으면 None → 호출부는 SKIP(해당 없음)으로 처리한다."""
        v = self.data.get(name)
        if v in (None, {}, []):
            return None
        return v

    def get(self, dotted, default=None):
        node = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    # ── 경로 ───────────────────────────────────────────────
    def expand(self, s):
        return (s.replace("{root}", self.root)
                 .replace("{config_dir}", self.config_dir)
                 .replace("{home}", os.path.expanduser("~")))

    def path_of(self, s):
        s = os.path.expanduser(self.expand(s))
        return s if os.path.isabs(s) else os.path.normpath(os.path.join(self.root, s))

    def paths_of(self, seq):
        return [self.path_of(s) for s in (seq or [])]

    def rel(self, p):
        try:
            return os.path.relpath(p, self.root)
        except ValueError:
            return p


def load(explicit=None, root_override=None):
    path = find_config(explicit)
    data = {}
    if path:
        with io.open(path, "rb") as fh:
            raw = fh.read()
        try:
            data = _toml.loads(raw.decode("utf-8"))
        except Exception as e:            # noqa: BLE001
            raise ConfigError("설정 파싱 실패(파서 %s, 파일 %s). 원인: %s" % (_TOML_IMPL, path, e))

    if root_override:
        root = os.path.abspath(os.path.expanduser(root_override))
    else:
        declared = (data.get("project") or {}).get("root")
        base = os.path.dirname(path) if path else os.getcwd()
        if declared:
            root = os.path.abspath(os.path.join(base, os.path.expanduser(declared)))
        elif path:
            root = base
        else:
            root = _git_toplevel(os.getcwd()) or os.getcwd()
    return Config(data, path, os.path.abspath(root))


# ── 셸 브리지 ────────────────────────────────────────────────
_SH_KEYS = [
    ("preflight.sample_sec", "HARNESS_SAMPLE_SEC"),
    ("preflight.free_pct_min", "HARNESS_FREE_PCT_MIN"),
    ("preflight.swapout_mbps_max", "HARNESS_SWAPOUT_MBPS_MAX"),
    ("preflight.swapout_companion_mbps", "HARNESS_SWAPOUT_COMPANION_MBPS"),
    ("preflight.psi_warn_pct", "HARNESS_PSI_WARN_PCT"),
    ("preflight.psi_crit_pct", "HARNESS_PSI_CRIT_PCT"),
    ("scheduled.list_cmd", "HARNESS_SCHED_LIST_CMD"),
    ("scheduled.match", "HARNESS_SCHED_MATCH"),
]


def _sh_quote(v):
    return "'" + str(v).replace("'", "'\\''") + "'"


def emit_sh(cfg):
    """bash가 `eval` 할 대입문. ★`: "${VAR:=값}"` 형태 = **이미 설정된 환경변수는 건드리지 않는다.**
    우선순위를 명시적으로 못박는 것이다: 환경변수(일회성 조정·테스트) > 설정파일 > 스크립트 기본값.
    단순 `VAR=값` 으로 내보내면 설정파일이 환경변수를 덮어써서, 문턱을 바꿔 게이트를
    시험하는 것 자체가 불가능해진다(양방향 검증이 막힌다)."""
    # ⚠️바깥을 큰따옴표로 감싸면 안 된다 — `: "${V:='a b'}"` 는 작은따옴표까지 값에 들어간다
    #   (실측: A=['a b']). 따옴표 없는 `: ${V:='a b'}` 만 quote removal이 일어난다(A=[a b]).
    out = [": ${HARNESS_ROOT:=%s}" % _sh_quote(cfg.root)]
    for dotted, var in _SH_KEYS:
        v = cfg.get(dotted)
        if v is not None:
            out.append(": ${%s:=%s}" % (var, _sh_quote(v)))
    for dotted, var in (("preflight.process_patterns", "HARNESS_PROC_PATTERNS"),
                        ("preflight.light_process_patterns", "HARNESS_LIGHT_PROC_PATTERNS")):
        pats = cfg.get(dotted)
        if pats:
            out.append(": ${%s:=%s}" % (var, _sh_quote("|".join(str(p) for p in pats))))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="harness.toml 조회/셸 브리지")
    ap.add_argument("--config")
    ap.add_argument("--root")
    ap.add_argument("--sh", action="store_true", help="bash가 eval 할 변수 대입문 출력")
    ap.add_argument("--get", help="점 표기 키 조회 (예: routine.max_age_days)")
    ap.add_argument("--show", action="store_true", help="해석 결과 요약")
    args = ap.parse_args()
    try:
        cfg = load(args.config, args.root)
    except ConfigError as e:
        sys.stderr.write("%s\n" % e)
        return 2
    if args.sh:
        print(emit_sh(cfg))
    elif args.get:
        v = cfg.get(args.get)
        if v is None:
            return 1
        print(v if not isinstance(v, list) else " ".join(str(x) for x in v))
    else:
        print("config : %s" % (cfg.path or "(찾지 못했다. 전부 기본값/SKIP 으로 돈다)"))
        print("root   : %s" % cfg.root)
        print("parser : %s" % cfg.toml_impl)
        if args.show:
            for k in sorted(cfg.data):
                print("  [%s]" % k)
    return 0


if __name__ == "__main__":
    sys.exit(main())

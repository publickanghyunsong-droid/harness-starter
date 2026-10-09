"""harness — 연구 프로젝트용 최소 하네스 도구 모음 (의존성 0, stdlib만).

구성
  config.py        설정(harness.toml) 로더 — **경로 결합은 전부 여기로 몰았다**
  audit.py         1단계 기계 점검
  score_canaries.py 2단계 카나리 채점
  minitoml.py      tomllib(3.11+)이 없는 환경용 TOML 부분집합 폴백
"""
__version__ = "0.1.0"

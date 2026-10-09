# run_manifest — 그림 검토 루프 예제 세트

이 예제의 재현 기록이다(하네스 엔지니어링 §11 스타일 매니페스트를 작은
교습용 예제 규모로 줄인 것). 아래 경로는 전부 이 폴더 기준 상대경로다. 이
폴더 밖에서 가져와야 할 것은 없다.

## 환경

- Python: 3.11.7
- numpy: 2.2.6
- pandas: 2.3.0
- matplotlib: 3.10.3
- geopandas·cartopy 의존성 없음. 누구나 지리공간 스택 없이
  `pip install numpy pandas matplotlib`만으로 돌려 볼 수 있도록 일부러
  가볍게 뒀다.
- 위 세 패키지가 있는 Python 3.10 이상이면 어떤 환경에서도 같은 그림이
  재현돼야 한다. 폰트는 matplotlib 기본값(DejaVu Sans)이다. 라벨을 일부러
  영어로 뒀으므로 시스템에 별도 한글 폰트가 필요 없다(`scripts/common_style.py`
  독스트링 참고).

## 입력 데이터(전부 합성, 이 레포 안에서 생성 — 측정값이 아니다)

`scripts/generate_data.py`가 생성한다. 단일 RNG 시드 = 42, 아래 고정된
순서로 만든다.

| 파일 | sha256 | 사용처 |
|---|---|---|
| `data/annual_loss_synthetic.csv` | `318d3f00cbad422086d53c6811713d7cb34019df968726b6738dfc3445cfcc6c` | fig1 |
| `data/hazard_grid_synthetic.npy` | `35a3c58a4352fc9dd7eb3cfefe8b005972114cb6f2a80c0e962d3633faa0723d` | fig2 |
| `data/scenario_ab_synthetic.npz` | `4cda13fa68603e532f9c96527e762587cc3bd303b30aad8705e8e2ff5ca6548f` | fig3 |

이 데이터 중 어느 것도 실제 위험 요인·노출·손실 데이터가 아니다. 이
예제를 위해 지어냈다(왜 그런지는 README.md를 본다).

## 재현

```bash
cd scripts
python3 generate_data.py
python3 fig1_bar.py
python3 fig2_grid.py
python3 fig3_scenarios.py
```

각 `fig*.py`는 `../figures/`에 초안 PNG(`_v1`)를 한 장씩 쓴다.
정답지 쪽 그림을 다시 그리는 방법은 `loop-history/README.md`에 따로 있다.

## 대조할 값(스크립트가 직접 찍는다. 이게 진짜 교차검증 대상이지 PNG
## 바이트가 아니다 — figure-style.md 자신의 재현성 규칙: 그림은 바이너리·
## 해시 대조가 아니라 수치 대조로 잰다)

- `generate_data.py`: 지역별 연간 손실지수 = `88.6, 89.7, 92.1, 93.8, 94.2, 96.1`;
  위험 요인 격자 최소/최대 = `8.4 / 56.8`(형태 40x40); 시나리오 A/B 최댓값
  = `43.0 / 47.4`.
- `fig1_bar.py`: 손실지수 최소/최대 = `88.6 / 96.1`(6개 지역).
- `fig2_grid.py`: 격자 최소/최대 = `8.4 / 56.8`.
- `fig3_scenarios.py`: A 최대 `43.0`, B 최대 `47.4`(형태 40x40).

다시 돌렸을 때 다른 숫자가 나오면 환경(numpy RNG 버전/알고리즘)이 위에
기록한 것에서 벗어났다는 뜻이다. 먼저 `numpy.__version__`부터 확인한다.

## 무엇이 동결됐고 무엇이 바뀔 것으로 예상되나

- `scripts/generate_data.py`와 `data/*` 파일 세 개는 커밋된 순간 동결된다
  (상위 wiki 관례의 raw/code-archive와 같은 역할이다. 같은 numpy 버전으로
  다시 돌리면 바이트 단위로 똑같이 나와야 한다).
- `figures/*_v1.png`는 검토 루프가 잡아내야 할, 일부러 결함을
  심은 그림들이다(`figures_manifest.md`를 본다).
- 수정 참조본은 `loop-history/`에 있다. 반영을 마친 뒤 비교할 때 연다.

# ABT 논문 초안 (paper/)

## 구성
- `main.tex` — IEEEtran 2단 컨퍼런스 양식. Introduction / Related Work / Threat Model /
  ABT Framework(6단계, 수식 포함) / Utility Model & Planning(Algorithm 1) /
  Network Integration(MHBench, APT-Agent 스키마) / Closing the Loop(공격-학습 루프) /
  Worked Example(5-호스트 데모 수치) / Evaluation Plan(RQ1–RQ4) / Discussion / Conclusion.
- `refs.bib` — 사용자가 제공한 5개 논문 + 참고한 3개 저장소(MHBench, APT-Agent, Incalmo)를
  스키마 참고용으로만 misc 항목으로 포함.

## 컴파일 방법
이 작업 환경에는 LaTeX이 설치되어 있지 않아 실제 컴파일은 로컬 TeX 배포판이나
Overleaf에서 진행해야 합니다.

```bash
cd paper
# 1) 그림 변환 (SVG -> PDF), Inkscape 설치되어 있다면:
inkscape ../abt_framework.svg --export-type=pdf --export-filename=abt_framework.pdf
# 또는 온라인 변환기 사용 후 abt_framework.pdf를 paper/ 폴더에 둘 것

# 2) 컴파일
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Overleaf를 쓴다면 `paper/` 폴더 전체(또는 `main.tex`, `refs.bib`,
`abt_framework.svg`→변환한 `abt_framework.pdf`)를 업로드하면 됩니다.

## 표시된 \todo 항목
본문에 빨간색 `\todo{...}`로 표시된 부분은 아직 검증/확정되지 않은 내용입니다:
- MTD-in-depth 논문의 실제 기법 분류와 `Table~\ref{tab:actions}`의 kill-chain phase 매핑 대조
- MIR 차단 확률(`beta_MIR` 등)과 MHBench 플레이북별 기본 확률의 실증 보정
- APT-Agent 토폴로지의 CVSS→공격성공확률 매핑 타당성 검증
- Worked Example을 실제 MHBench 환경 + 다라운드 학습 루프 결과로 교체
- `refs.bib`의 MTD-in-depth, APT-Agent, Incalmo 저자 목록 확정

## 본문-코드 대응
| 논문 섹션 | 코드 |
|---|---|
| §IV-A (Asset) | `abt/model.py: Asset, LegitFlow` |
| §IV-B/C (MIR, 네트워크 제어) | `abt/actions.py` |
| §IV-D (HARM) | `abt/harm.py` |
| §IV-E (Goal capture) | `abt/model.py: AttackGoal` |
| §IV-F/§V (마스터 에이전트, Utility) | `abt/master.py`, `abt/simulator.py` |
| §VI (Network Integration) | `abt/importers.py` — **아직 미구현, 다음 작업 항목** |
| §VII (Closing the Loop) | `abt/loop.py` (`TrainingLoop`), `MasterAgent.observe` |
| §VIII (Worked Example) | `examples/enterprise.py`, `examples/run_demo.py` |

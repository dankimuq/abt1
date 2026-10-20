# ABT 논문 — 단일 기준본

`paper/main.tex` is the **only manuscript source**. The previous Prism import has
been merged into it; do not edit or maintain a second copy.

## 구성
- `main.tex` — IEEEtran 2단 컨퍼런스 양식. Introduction / Related Work / Threat Model /
  ABT Framework(6단계, 수식 포함) / Utility Model & Planning(Algorithm 1) /
  Network Integration(MHBench, APT-Agent 스키마) / Closing the Loop(공격-학습 루프) /
  Worked Example(5-호스트 데모) / Evaluation Plan(RQ1–RQ4) / Discussion / Conclusion.
- `refs.bib` — 관련 연구, 벤치마크 스키마, 네트워크·호스트 방어 배포 자료.
- `main.pdf` — 최신 `main.tex` 컴파일 결과.
- `abt_framework.svg` / `abt_framework.pdf` — 편집 가능한 그림 원본과 논문이 사용하는 렌더링본.

## 컴파일 방법
저장소 루트에서 아래 명령으로 컴파일합니다 (Tectonic은 필요한 TeX 번들을 내려받습니다).
출력 PDF는 항상 `paper/main.pdf`에 생성합니다.

```bash
tectonic --outdir paper paper/main.tex
```

그림을 수정할 때는 `paper/abt_framework.svg`를 원본으로 편집하고,
`paper/abt_framework.pdf`를 갱신합니다. Prism 또는 Overleaf로 내보낼 때도
별도 원고 사본을 만들지 말고 이 디렉터리의 기준본과 필요한 그림 파일을 사용합니다.

실험 환경 구분: 현재 코드는 SDN control-plane 에뮬레이터를 사용합니다. 실제 SDN
flow-rule 검증에는 Linux 기반 Mininet/Open vSwitch 테스트베드를 계획하며, Docker는
컨테이너 endpoint 및 서비스 토폴로지 시험에 선택적으로 사용합니다. Docker 네트워크만으로
OpenFlow SDN 동작을 검증했다고 간주하지 않습니다.

## 표시된 \todo 항목
본문에 빨간색 `\todo{...}`로 표시된 부분은 아직 검증/확정되지 않은 내용입니다:
- MTD-in-depth 논문의 실제 기법 분류와 `Table~\ref{tab:actions}`의 kill-chain phase 매핑 대조
- MIR 차단 확률(`beta_MIR` 등)과 MHBench 플레이북별 기본 확률의 실증 보정
- APT-Agent 토폴로지의 CVSS→공격성공확률 매핑 타당성 검증
- Worked Example을 실제 MHBench 환경 + 다라운드 학습 루프 결과로 교체
- `refs.bib`의 MTD-in-depth, APT-Agent, Incalmo 저자 목록 확정
- SDN/호스트 actuator 구현·배포 전 안전한 테스트베드 검증; 현재 효과는 시뮬레이션이며
  실제 장비/호스트를 변경하지 않음

## 본문-코드 대응
| 논문 섹션 | 코드 |
|---|---|
| §IV-A (Asset) | `abt/model.py: Asset, LegitFlow` |
| §IV-B/C (MIR, 네트워크 제어) | `abt/actions.py` |
| §IV-D (HARM) | `abt/harm.py` |
| §IV-E (Goal capture) | `abt/model.py: AttackGoal` |
| §IV-F/§V (마스터 에이전트, Utility) | `abt/master.py`, `abt/simulator.py` |
| §VI (Network Integration) | `abt/importers.py` — MHBench/APT-Agent 스키마 임포터 구현, 합성 픽스처 테스트 완료 |
| §VII (Closing the Loop) | `abt/loop.py` (`TrainingLoop`), `MasterAgent.observe` — 시뮬레이션 루프 기본 구현 및 테스트 완료 |
| Defense portfolio and deployment scope | `slides/network-defense-design.md` 및 §III — MTD 유지; proactive/reactive host/network subset; SDN control-plane은 시뮬레이션만 구현, 실제 컨트롤러·호스트 actuator는 미구현 |
| §VIII (Worked Example) | `examples/enterprise.py`, `examples/run_demo.py` |

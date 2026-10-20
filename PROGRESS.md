# ABT 프로젝트 — 레퍼런스 및 작업 현황 정리

## 1. 사용 중인 레퍼런스

### 1.1 논문 (사용자 제공)
| 논문 | 역할 | ABT에서 쓰이는 부분 |
|---|---|---|
| HARMer: Cyber-attacks automation and evaluation (Enoch et al., IEEE Access 2020) | 공격 그래프 구조 | `abt/harm.py`의 2-layer HARM(호스트 그래프 + 호스트별 noisy-OR 취약점 트리) |
| Novel security models, metrics and security assessment for maritime vessel networks (Enoch et al., Computer Networks 2021) | 방어 프레임워크 원형 | 자산 가치·요구조건 기반 보안 평가 → ABT의 `Asset`, `risk()` 지표로 확장 |
| MTD in depth: Multi-phased moving target defense techniques against cyber-attacks based on cyber kill chain (FGCS 2026) | 자산 ↔ 방어수단 매핑 | `abt/actions.py`의 `Action.phase`(kill-chain 단계 태깅). **아직 논문의 실제 기법 분류와 대조 검증 안 됨** |
| APT-Agent: Automated Penetration Testing using Large Language Models (arXiv 2605.24949) | 공격 도구 ① | `abt/red.py`의 `APTAgentAdapter` (현재는 시뮬레이션 스텁) |
| Incalmo: An Autonomous LLM-Assisted System for Red Teaming Multi-Host Networks | 공격 도구 ② | `abt/red.py`의 `IncalmoAdapter` (현재는 시뮬레이션 스텁) |

### 1.2 실제 코드 레퍼런스 (이번 세션에서 조사, `/tmp/ref`에 클론 — 리포지토리 자체에는 커밋되지 않음)
사용자가 공유한 두 공격 도구 저장소와, 그 도구들이 공통으로 사용하는 네트워크 환경 생성기를 구조 파악 목적으로 클론해서 스키마만 확인했습니다. **코드를 복사하지 않았고, 저장소 구조와 JSON 스키마만 읽었습니다.**

- **APT-Agent** (`github.com/Guanting-Li/APT-Agent`)
  - 구성: `APT-Agent.py`(호스트 1개씩 공격하는 RECON→EXPLOIT→EXFILTRATE 에이전트), `run_harmat_campaign.py`(다중 호스트 오케스트레이터, HARM 그래프로 경로 선택 후 pivot), `harmat/`(Enoch et al.의 HARM 라이브러리를 그대로 vendored), `topologies/*.json`(5개 평가 토폴로지: linear chain, dumbbell, star, equifax, enterprise).
  - **토폴로지 JSON 스키마**: `hosts: [{id(IP), role}]`, `edges: [{src, dst, port, service, cvss, exploit(Metasploit 모듈명), version, impact?, pivot_network?}]`, `goal: <host id>`.
  - Metasploit 실제 실행 기반(실제 공격 수행), MySQL 모듈DB로 LLM 출력 모듈명을 검증(rectification).

- **Incalmo (whoiskiwi 재구현판)** (`github.com/whoiskiwi/Incalmo`)
  - 원 논문(arXiv:2501.16466)의 비공식 재구현. "LLM은 계획만, 실행은 전문가 에이전트가" 구조: `scan / lateral_move / find_information / exfiltrate_data` 같은 고수준 intent를 LLM이 내면 결정론적 실행 계층이 번역.
  - `equifax/`, `chain4/`, `chain6/` 3개 Docker 환경 제공, Caldera C2 사용.
  - 설정은 `config/config-*.json`(환경별), 실제 호스트는 docker-compose로 기동.

- **MHBench** (`github.com/bsinger98/MHBench`, 공식: `cylabcyberautonomy/MHBench`)
  - Incalmo/APT-Agent가 공격 대상으로 쓰는 **다중 호스트 환경 생성기**(OpenStack/GCP 배포용).
  - **Pydantic 모델** (`src/models/`): `components.py`(User), `enums.py`(OSType, VulnerabilityType=`privilege_escalation`|`lateral_movement`, GoalType=`data_exfiltration`|`host_access`), `vulnerabilities.py`(Vulnerability: `type, playbook_path, merge_strategy, from_host_ip, to_host_ip, from_user, to_user`), `goals.py`(Goal: `target_host_id, target_user_id` / `DataExfiltrationGoal: host_ip, playbook_path`), `network.py`, `attack_graph.py`, `attack_paths.py`.
  - **생성된 환경 JSON 스키마** (`src/environments/generated/*.json`): `networks[].subnets[].hosts[]`(id, name, ip_address, users[], vulnerabilities[], is_attacker, is_decoy), `subnet_connections[]`(from_subnet, to_subnet, bidirectional), `goals[]`(data_exfiltration, host_ip 등), `attack_paths`, `attack_graph`(MHBench가 자체 계산해서 동봉).
  - 포트/서비스/CVSS 개념이 없고 대신 "취약점 플레이북"(Ansible) 단위로 모델링 — ABT의 `Service/Vuln(port, cve, p, impact)` 개념과 다름 → **매핑이 필요한 지점**.

### 1.3 결론: 세 스키마의 차이와 ABT의 역할
| | 단위 | 서비스/포트 | 확률/영향 | 목표(goal) |
|---|---|---|---|---|
| APT-Agent 토폴로지 | host+edge | 있음(port,service) | CVSS 있음 | 단일 goal host |
| MHBench 생성 환경 | host+vuln(playbook) | 없음(플레이북만) | 없음(확률 미정) | `data_exfiltration` 등 |
| ABT (`abt/model.py`) | `Host/Service/Vuln/Flow` | 포트 기반 | `p`, `impact` 명시 | `AttackGoal` |

→ ABT가 공통 중간 표현(IR) 역할을 하도록, **MHBench JSON → `Network`**, **APT-Agent 토폴로지 JSON → `Network`** 임포터를 만들어서 두 생성기/공격 도구 중 무엇을 쓰든 같은 HARM·플래너·시뮬레이터를 그대로 재사용하는 것이 설계 방향입니다.

## 2. 지금까지 실제로 만든 것 (커밋 `0762a2e`, `main` 브랜치, `https://github.com/dankimuq/abt1`)

| 파일 | 내용 | 대응되는 요청 단계 |
|---|---|---|
| `abt/model.py` | `Asset/LegitFlow/Host/Service/Vuln/Network/AttackGoal` 데이터 모델 | 1단계(자산·보호요구사항) |
| `abt/actions.py` | MIR(호스트) 액션 + 네트워크/MTD 액션, kill-chain phase 태깅 | 2·3단계 |
| `abt/harm.py` | 2-layer HARM 공격 그래프, `attack_paths`, `goal_probability`, `risk` | 4·5단계 |
| `abt/simulator.py` | 방어안을 복제 네트워크에 적용 후 risk/availability/performance/cost/utility 평가, 제약조건 검사 | 6단계(마스터 에이전트의 평가부) |
| `abt/master.py` | `MasterAgent`: 경보 수신(`ingest`), 탐욕적 marginal-utility 플래너(`plan`), 실행(`execute`) | 6단계 |
| `abt/red.py` | `RedTeamAdapter` 추상 인터페이스 + Incalmo/APT-Agent/AutoHacker **스텁**(몬테카를로 시뮬레이션) | 공격 도구 연동 지점(미완성) |
| `examples/enterprise.py`, `examples/run_demo.py` | 5-호스트 예제망, 데모 실행 스크립트 | 검증용 |
| `tests/test_abt.py` | 공격경로 존재, 가용성 제약 위반 검출, 플랜이 리스크를 낮추는지, 경보 반영 테스트 | 검증용 |
| `README.md` | 아키텍처, 평가모델, kill-chain 매핑, 논문 구조 제안, 한계점 | 문서화 |
| `abt_framework.svg` | Red team / Target network / Blue team(ABT) 3-구역, 좌→우 1~7단계 번호가 매겨진 파이프라인 다이어그램 | 그림 |
| `paper/main.tex`, `paper/refs.bib` | IEEEtran 논문 초안(6단계 수식, Algorithm 1, 평가계획 RQ1–RQ4) | 논문화 |
| `abt/importers.py` | **신규.** MHBench 생성 JSON(`load_mhbench`), APT-Agent 토폴로지 JSON(`load_apt_agent_topology`), 자동판별 `load_network` | 2단계(MHBench 등 기존 네트워크 구성 통합) |

데모 실행 결과(기존 요약): 5-호스트 예제망에서 추천 플랜 적용 시 risk 0.47→0.00, 가용성 1.00 유지, 시뮬레이션 공격 성공률 0.72→0.00.

## 3. 진행 상황 업데이트

> "① ABT 방어 프레임워크 자체 완성 → ② MHBench 같은 기존 네트워크 구성과 통합 → ③ 공격 실행 시 배우고(학습) 방어가 동작하는지 테스트"

- **① 프레임워크 자체 완성**: 핵심 라이브러리(`model/actions/harm/simulator/master`)는 동작 확인됨. 남은 보완 항목은 ③ 항목에 따라 계속 진행.
- **② MHBench 연동 — 구현 완료, 합성 픽스처로 1차 검증함.**
  - `abt/importers.py` 작성. 두 스키마 모두 공통 `abt.model.Network`로 변환:
    - **MHBench**: subnet→host 전개, host별 취약점 "플레이북"을 포트가 할당된 `Service/Vuln`으로 합성, subnet 연결→호스트 단위 flow 전개, `from_host_ip`가 비어있고 외부망 호스트면 attacker 진입점으로 간주, `privilege_escalation` 플레이북이 있는 호스트는 해당 호스트로 들어오는 lateral-movement 취약점의 권한을 root로 격상(자기 루프 없이 "거점 확보 후 로컬 권한상승" 근사), `data_exfiltration`/`host_access` 목표를 `AttackGoal`+`Asset`으로 변환.
    - **APT-Agent 토폴로지**: host/edge(JSON) 그대로 `Host/Service/Vuln`+flow로 매핑, `src=="attacker"`인 edge의 목적지를 entry point로, CVSS/10을 공격성공확률 p로 사용(검증 필요, `\todo` 표시됨), 단일 goal host를 `AttackGoal`로 변환.
    - `load_network(path)`: 최상위 키(`hosts`+`edges` vs `networks`)로 스키마 자동 판별.
  - **검증**: 실제 두 저장소 파일을 복사하지 않고, 동일 스키마의 축소 합성 JSON(2~3 호스트)을 직접 만들어 `load_mhbench`/`load_apt_agent_topology`/`load_network`를 호출 → 호스트·진입점·flow·`attack_paths`/`goal_probability`가 기대대로 계산됨을 확인(세션 로그 기준, 아직 `tests/`에 정식 테스트로 추가되지 않음).
- **③ 공격-학습 루프**: 아직 미구현. 다음 항목 남음:
  - `abt/red.py` 확장: `RedTeamAdapter.run()`이 `bool` 대신 `AttackResult(success, path, goal)`를 반환하도록 변경(하위 호환 유지 검토).
  - `abt/master.py`: `MasterAgent.observe(result, detect_p=...)` 추가 — 공격 성공 시 일정 확률로 경유 호스트를 "탐지됨"으로 반영 후 재계획.
  - `abt/loop.py`: `TrainingLoop` — N 라운드 반복, 라운드별 risk/success 로그, 수렴 확인.
  - `tests/test_importers.py`, `tests/test_loop.py`: 합성 MHBench/APT-Agent 픽스처 + 다라운드 루프를 정식 테스트로 고정.
  - (선택) CLI: `python -m abt.cli --network <file> --rounds N`.

> 주의: 두 저장소(JSON 파일) 자체를 리포지토리에 복사하지 않고, **스키마와 로직만 참고해서 우리 코드로 새로 작성**했습니다. 테스트용 픽스처도 실제 저장소 파일을 복사하지 않고 동일 스키마의 축소판을 직접 작성합니다.

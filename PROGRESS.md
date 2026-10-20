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

데모 실행 결과(기존 요약): 5-호스트 예제망에서 추천 플랜 적용 시 risk 0.47→0.00, 가용성 1.00 유지, 시뮬레이션 공격 성공률 0.72→0.00.

## 3. 이번 턴에서 요청받았지만 아직 구현 전인 것

> "① ABT 방어 프레임워크 자체 완성 → ② MHBench 같은 기존 네트워크 구성과 통합 → ③ 공격 실행 시 배우고(학습) 방어가 동작하는지 테스트"

- **① 프레임워크 자체 완성**: 현재 라이브러리 형태로는 동작하지만 아직 보완이 필요한 부분
  - 네트워크 스펙을 하드코딩된 파이썬(`examples/enterprise.py`) 대신 **외부 JSON/YAML 설정 파일**로 주입 가능하게 (임포터 작업과 직결).
  - `RedTeamAdapter.run()`이 `bool`만 반환 → 어떤 경로/호스트가 뚫렸는지 반환하도록 확장 필요 (학습 루프에 필수).
  - 반복 공격→방어 상호작용을 지원하는 `MasterAgent.observe()` 또는 학습 루프 모듈 없음.
  - CLI 진입점 없음(현재는 `examples/run_demo.py`만 존재).
- **② MHBench 연동**: `abt/importers.py` (미작성) — MHBench 생성 JSON, APT-Agent 토폴로지 JSON을 `abt.model.Network`로 변환.
- **③ 공격-학습 루프 테스트**: `abt/loop.py`(미작성) — 여러 라운드에 걸쳐 공격 실행 → 탐지/경보 반영 → 재계획 → 리스크/성공률 추이를 기록하고, 방어가 수렴하는지 확인하는 테스트.

## 4. 다음 작업 순서(진행 동의 시 바로 착수)

1. `abt/importers.py`: `load_mhbench(path)`, `load_apt_agent_topology(path)` 구현 — 실제 생성 파일 형식을 그대로 반영.
2. `abt/red.py` 확장: `AttackResult(success, path, goal)` 반환으로 변경(하위 호환 유지).
3. `abt/master.py`: `MasterAgent.observe(result, detect_p=...)` 추가 — 공격 성공 시 일정 확률로 경유 호스트를 "탐지됨"으로 반영.
4. `abt/loop.py`: `TrainingLoop` — N 라운드 반복, 라운드별 risk/success 로그.
5. 테스트: 합성 MHBench 스타일 JSON + 합성 APT-Agent 토폴로지 JSON 픽스처로 임포트 → 다라운드 공격-방어 루프 → 방어 후 리스크·성공률 감소를 검증.
6. (선택) CLI: `python -m abt.cli --network <file> --rounds N`.

> 주의: 두 저장소(JSON 파일) 자체를 리포지토리에 복사하지 않고, **스키마와 로직만 참고해서 우리 코드로 새로 작성**합니다. 테스트용 픽스처도 실제 저장소 파일을 복사하지 않고 동일 스키마의 축소판을 직접 작성할 예정입니다.

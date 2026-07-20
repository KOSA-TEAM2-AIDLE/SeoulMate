# [SeoulMate]

> "[서울이 낯선 외국인을 위한 AI 여행 메이트]"

<img width="100%" alt="프로젝트 대표 메인 이미지" src="https://github.com/user-attachments/assets/c70976be-9e3c-4d56-af53-a9c5bfa6ba6e" />

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [프로젝트 기획 배경](#2-프로젝트-기획-배경)
3. [구성원 및 역할](#3-구성원-및-역할)
4. [기술 스택](#4-기술-스택)
5. [주요 기능](#5-주요-기능)
6. [협업 컨벤션](#6-협업-컨벤션-브랜치-전략)
7. [트러블 슈팅](#7-트러블-슈팅)

---

### 1. 프로젝트 개요

* **프로젝트명**: [SeoulMate]
* **한 줄 설명**: [서울이 낯선 외국인을 위한 AI 여행 메이트]
* **진행 기간**: 2026.07.06 ~ 2026.07.20
* **개발 인원**: [4명]
* **팀명**: [(A)i-dle]
* **GitHub Repository**: [https://github.com/KOSA-TEAM2-AIDLE/SeoulMate]

---

### 2. 프로젝트 기획 배경

* **시장/사회적 현황**
  * **외국인 관광객 급증**: 방한 외국인 수가 크게 증가하며 자유여행(개별여행) 비중이 80% 이상을 차지함.
  * **디지털 정보 탐색 증가**: 인터넷 사이트 및 앱을 통한 정보 탐색이 주요 경로(71.1%)로 자리 잡음.

* **기존 서비스의 한계**
  * **정보 파편화 및 언어 장벽**: 서비스 이용, 앱 인증, 언어 문제 등으로 인한 여행객의 페인 포인트 지속 발생.
  * **수동적 정보 제공**: 기존 지도/목록 중심 서비스는 단순 정보만 제공하여 맞춤형 비교 및 결정 지원이 부족함.
  * **실시간성 부족**: 기존 챗봇은 날씨, 혼잡도 등 실시간 데이터를 반영한 장소 추천에 한계가 있음.

* **해결 방안**
  * **AI 기반 맞춤형 웹서비스 (SeoulMate)**: 사용자 위치, 방문 목적, 날씨, 혼잡도를 반영하여 맞춤형 장소를 추천하고 실시간으로 상황별 대체 장소를 제안함.
  * **의사결정 지원 및 정보 제공**: 거리, 평점, 혼잡도 등 설명 가능한 추천 근거와 다국어 챗봇을 제공하여 외국인 관광객의 편의성과 신뢰도를 제고함.

---

### 3. 구성원 및 역할

#### 구성원

| <img width="120" height="160" alt="모수환" src="https://github.com/user-attachments/assets/68500aab-e37d-4a34-8fb9-fd95e7410306" /> | <img width="120" height="160" alt="김윤우" src="https://github.com/user-attachments/assets/8f8fdba6-599a-441d-adc2-1808a66e3297" /> | <img width="120" height="160" alt="신재욱" src="https://github.com/user-attachments/assets/4ae59eaf-9596-43cf-9f4f-d94dc97e3774" /> | <img width="120" height="160" alt="이하영" src="https://github.com/user-attachments/assets/889d906f-186a-4704-b7b5-4ba47a33b7c1" /> |
| :---: | :---: | :---: | :---: |
| **[모수환]** | **[김윤우]** | **[신재욱]** | **[이하영]** |
| [GitHub](https://github.com/suhwan1117) | [GitHub](https://github.com/yunwoooo) | [GitHub](https://github.com/tls427wodnr) | [GitHub](https://github.com/rehayoung) |

#### 역할 분담

| 이름 | 역할 | 핵심 개발 파트 및 담당 업무 |
| --- | -- | -------------------------- |
| [모수환] | 팀장 | • **식단 에이전트 구현**<br>• **백엔드 구현**<br> |
| [김윤우] | 팀원 | • **인텐트 분류 모델 구현**<br>• **HITL 로직 적용**<br>• **카페 에이전트 구현**<br>• **프론트엔드 채팅 구현**<br> |
| [신재욱] | 팀원 | • **Git 형상관리**<br>• **숙박 에이전트 구현(추천,예약)**<br>• **프론트엔드 전역 상태 관리 구현**<br>• **프론트엔드 사이드바 구현**<br> |
| [이하영] | 팀원 | • **관광 및 행사 에이전트 구현**<br>• **프론트엔드 지도 구현**<br> |

---

### 4. 기술 스택

| 구분 | 기술 스택 명칭 |
| ---------------- | ---------------------------------------- |
| **Backend** | Python, FastAPI |
| **Database** | PostgreSQL |
| **Frontend** | React, TailwindCSS |
| **AI** | OpenAI, RAG, MCP |
| **Data / API** | 트립어드바이저(시설 데이터), 기상청 API, kakao API, Naver Map API |
| **Collaboration** | GitHub, Notion, SourceTree |

---

### 5. 주요 기능

<details>
<summary><strong>[장소 검색 및 맞춤형 추천]</strong></summary>

<br>

* 식당, 카페, 숙박, 문화시설 등 다중 도메인 RAG(검색 증강 생성) 기반 맞춤 추천
* 날씨(기상청) 및 혼잡도 MCP(Model Context Protocol) 실시간 연동을 통한 장소 재랭킹
* OpenAI GPT를 활용한 최종 후보 선정 및 구체적인 추천 이유 생성
* Booking.com(숙박) 및 물품보관소 실시간 가용성 확인 API 통합

<br>

</details>

<details>
<summary><strong>[다일/당일 여행 루트 플래닝]</strong></summary>

<br>

* 사용자 질의 분석(Structured Query)을 통한 당일 및 다일 여행 루트 자동 생성
* 방문 시간, 장소 간 이동 거리, 운영 시간, 날씨 제약을 고려한 동적 경로 최적화
* 프론트엔드 상태 관리(Zustand)를 활용한 생성된 루트 내 장소 수동 편집(삽입/삭제) 지원

<br>

</details>

<details>
<summary><strong>[지도 및 위치 기반 서비스]</strong></summary>

<br>

* 카카오 지오코딩 및 로컬 API 연동으로 정확한 위치 지원
* 벡터 DB와 PostgreSQL을 활용한 거리, 가격, 평점, 테마 기반 정밀 필터링
* React 및 TailwindCSS 기반의 지도 워크스페이스(MapWorkspace) 제공

<br>

</details>

<details>
<summary><strong>[실시간 채팅 및 다국어 지원]</strong></summary>

<br>

* Server-Sent Events(SSE)를 활용한 끊김 없는 실시간 스트리밍 채팅 UI (ChatRouter)
* 한국어 및 영어 질의 파싱 지원과 DB 분리 설계로 다국어 맞춤형 검색 결과 제공

<br>

</details>

---

### 7. 협업 컨벤션 (브랜치 전략)

<details>
<summary><strong>1. 브랜치 전략 선정 배경</strong></summary>

<br>

* 프로젝트 기간이 비교적 짧은 미니 프로젝트 특성상 Git-flow를 적용하기에는 브랜치 관리 비용이 크다고 판단하였습니다.
* 반면 GitHub-flow는 빠른 개발이 가능하지만 검증 단계가 부족하여 코드 안정성 측면에서 리스크가 존재하였습니다.
* 따라서 우리 팀은 GitHub-flow의 간결함과 Git-flow의 안정성을 적절히 결합한 **main - develop - feature 브랜치 전략**을 채택하였습니다.

</details>

<details>
<summary><strong>2. 브랜치 구조 및 역할</strong></summary>

<br>

#### main

* 최종 배포가 가능한 안정적인 코드를 관리하는 브랜치입니다.
* 언제든 서비스가 가능한 상태를 유지합니다.

#### develop

* 팀원들의 작업 결과가 통합되는 브랜치입니다.
* 기능 검증 및 충돌 확인을 수행하는 통합 브랜치입니다.
* 검증이 완료된 코드만 main으로 반영합니다.

#### feature

* 실제 기능 개발이 이루어지는 브랜치입니다.
* develop 브랜치에서 생성합니다.
* 작업 완료 후 develop 브랜치로 병합합니다.

</details>

<details>
<summary><strong>3. 이슈 기반 브랜치 관리</strong></summary>

<br>

* 기능 개발 전 GitHub Issue를 먼저 생성하였습니다.
* 생성된 Issue 번호를 기반으로 feature 브랜치를 생성하여 작업 내역과 이슈를 연결하였습니다.

#### 예시

```text
Issue #12 생성
        ↓
feat/#12
```

```text
Issue #27 생성
        ↓
fix/#27
```

</details>

<details>
<summary><strong>4. 워크플로우 (Workflow)</strong></summary>

<br>

```text
1. Issue 생성
        ↓
2. develop 브랜치에서 feature 브랜치 생성
        ↓
3. 기능 개발 및 Commit
        ↓
4. 원격 feature 브랜치 Push
        ↓
5. Pull Request 생성
        ↓
6. 코드 리뷰 및 승인
        ↓
7. develop 브랜치 Merge
        ↓
8. 최종 검증 후 main Merge
```

</details>

<details>
<summary><strong>5. 운영 원칙 (Ground Rules)</strong></summary>

<br>

* 모든 기능 개발은 반드시 feature 브랜치에서 진행합니다.
* 직접 main 또는 develop 브랜치에 작업하지 않습니다.
* 기능 구현 전 반드시 Issue를 생성합니다.
* 브랜치명은 Issue 번호 기반으로 작성합니다.
* 모든 코드는 Pull Request를 통해서만 상위 브랜치에 병합합니다.
* 리뷰가 용이하도록 작은 단위로 작업을 나누어 PR을 생성합니다.
* Issue 및 Pull Request는 팀에서 정의한 템플릿을 사용합니다.
* feature → develop 병합 시 최소 2명의 리뷰를 진행합니다.
* develop → main 병합 시 팀원 전원의 검토 후 PR을 올린 팀원을 제외한 나머지 3명의 리뷰를 작성한 뒤 병합합니다.

</details>

---

### 8. 트러블 슈팅

<details>
<summary><strong>모수환 - 검색 품질·루트 최적화 및 식당 추천 파이프라인 개편</strong></summary>

#### 문제
- 카테고리/평점 오탐, 동선 지그재그 및 다일 일정 중복, 고가 식당 검색 0건, 멀티지역 되물음 루프, 추천 응답 지연(최대 197초).

#### 원인
- 단순 평점 정렬 및 부분 문자열 매칭, 거리(좌표) 개념 부재, 메뉴 중앙값(`median`) 단일 필터링, 거대한 LLM 입력 및 날씨 API 순차 호출.

#### 해결 방안
- **검색 정밀화:** 평점 신뢰도 함수(`min(N, 30)/30`) 및 예산 범위 겹침 매칭(`LATERAL` 조인) 도입, 지명 유형별 차등 반경(2~60km) 적용.
- **동선 최적화:** 서버 기반 빔 서치(Beam Search) 하버사인 거리 최적화 및 서울 10개 권역 가중 배정 적용.
- **성능 최적화:** LLM 역할을 요약·제목 생성으로 축소, 날씨/검색 비동기 병렬 처리(`asyncio.gather`) 적용 (응답 시간 약 70% 단축).

</details>

<details>
<summary><strong>김윤우 - 비결정적 LLM 출력을 결정적 파이프라인으로 안정화</strong></summary>

#### 문제
- LLM이 인텐트 분류, 조건 추출, HITL 판단을 모두 담당하여 동일 질문에도 대답·조건이 바뀌는 비결정성 발생 및 불필요한 되물음·검색 로직 불안정 초래.

#### 원인
- LLM의 역할 과중(조건 추출과 정책 판단 동시 수행), Pydantic 스키마와 비즈니스 필수값 혼재, 명시적 대화 상태(State) 관리 부재.

#### 해결 방안
- **역할 분리:** LLM은 명시 정보 추출만 담당, 비즈니스 정책 검사(`find_missing_fields`)는 애플리케이션 코드로 이관.
- **파이프라인 구축:** Pydantic 기반 타입 검증 + LangGraph 기반 State 관리 및 HITL(`interrupt/resume`) 구조화.
- **검증 강하게 처리:** `StructuredTravelQuery` 단계에서 교차 필드 검증을 수행하여 검색 계층으로의 오염 방지.

</details>

<details>
<summary><strong>신재욱 - 크롤링 데이터 노이즈(비리뷰 데이터) 문제 해결 및 NLP 정제 파이프라인 구축</strong></summary>
  
#### 문제
- 트립어드바이저 크롤링 과정에서 웹 구조적 한계로 인해 실제 리뷰 외에 호텔 안내 문구, 위치 정보, 광고 등의 시스템 노이즈 데이터가 대량 섞여서 수집되는 현상 발생.
  
#### 원인
- 타겟 웹사이트의 UI/DOM 구조가 수시로 변경되어, 크롤러 내부의 하드코딩된 예외 처리 로직(CSS Selector, XPath 등)만으로는 완벽한 방어가 불가능하고 유지보수 비용이 과다하게 발생함.
  
#### 해결 방안
- Data-Centric 접근 방식 전환: 크롤러는 수집에만 집중하고, 전처리 단계에서 해결하도록 파이프라인 변경.
- NLP 검독 모델 학습: 샘플링 데이터 이진 라벨링(1: 정상, 0: 노이즈) 후 klue/roberta-small 모델을 파인튜닝하여 문맥 기반 분류기 구축.
- 효율적 AI 필터링: 전체 데이터 적용 시 unique() 처리를 통해 중복 문장의 반복 추론을 방지하고, Batch 단위 추론을 적용해 수백만 건의 데이터를 단시간에 정제 완료.
  
</details>

<details>
<summary><strong>이하영 - 근거 기반 응답의 토큰 절단 및 Fallback 문제 개선</strong></summary>

#### 문제
- 추천 장소, 리뷰, 혼잡도, 날씨 등을 전체 JSON으로 생성하는 과정에서 `max_tokens` 초과로 출력이 잘려 파싱 오류 및 Fallback 발생.

#### 원인
- 이미 RAG·MCP로 확보한 정제 데이터를 LLM이 다시 출력하도록 중복 설계, 긴 구조화 출력에 대한 엄격한 JSON 검증으로 인한 과도한 Fallback 전환.

#### 해결 방안
- **역할 축소:** LLM은 장소 선택 및 짧은 추천 사유 생성만 담당하도록 프롬프트 최소화.
- **백엔드 직접 조립:** FastAPI 로직이 RAG 데이터(장소·리뷰)와 MCP 데이터(날씨·혼잡도)를 병합해 최종 응답 직접 생성.
- **검증 강화:** 미선택 장소 포함 방지 및 실제 조회 데이터와 응답 간 일치성 검증 로직 적용.

</details>

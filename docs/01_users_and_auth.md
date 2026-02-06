# Database Schema Design: Users & Authentication

## 1. 개요 및 설계 목표
이 문서는 `GPX 코스 생성기` 및 `시뮬레이터` 서비스를 위한 사용자(User) 및 인증(Authentication) 스키마를 정의합니다.

### 핵심 설계 원칙 (Design Principles)
1.  **라이덕(Riduck) 생태계 통합:** 본 서비스는 독자적인 회원 체계가 아닌, 기존 라이덕 서비스의 확장 기능으로 동작합니다. 따라서 **라이덕 계정(`riduck_id`)을 핵심 식별자(Anchor)**로 사용합니다.
2.  **SSO-like 인증 경험:** 별도의 회원가입 절차 없이, 라이덕 로그인만으로 서비스를 이용할 수 있도록 **JWT 기반의 인증 토큰 전달(Handoff)** 방식을 채택합니다.
3.  **확장성(Scalability):** 향후 Google, Strava 등 외부 소셜 로그인 및 데이터 연동 확장을 고려하여, 인증 정보(Token)를 사용자 기본 정보와 분리하여 관리합니다.
4.  **관리 효율성:** 복잡한 다중 기기 세션 관리 비용을 줄이기 위해, 초기 단계에서는 **Provider당 단일 활성 세션(Single Active Session)** 정책을 유지합니다.

---

## 2. Schema Definition

### 2.1 Users (사용자 정보)
**역할:** 서비스 내부에서 사용하는 고유 식별자 및 사용자 프로필 관리.
**특이사항:** 비밀번호 등 민감한 인증 정보는 저장하지 않습니다.

```sql
CREATE TABLE users (
    -- [PK] 시스템 내부 고유 식별자 (모든 FK의 기준)
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- [Unique] 라이덕 서비스의 유저 식별 번호 (Legacy Integer ID)
    -- 외부 시스템(라이덕)과의 데이터 연동(PDC, FTP, 라이딩 기록 등)을 위한 Key
    riduck_id INTEGER UNIQUE NOT NULL,

    -- 화면 표시용 닉네임 (로그인 시점마다 라이덕 정보로 최신화)
    username VARCHAR(50) NOT NULL,

    -- 연락 및 알림용 이메일
    email VARCHAR(255),

    -- 메타 데이터
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index: 로그인 시 빠른 사용자 조회를 위함
CREATE INDEX idx_users_riduck_id ON users(riduck_id);
```

### 2.2 UserTokens (인증 토큰 관리)
**역할:** 외부 서비스(라이덕, 구글 등)의 OAuth/Auth 토큰 관리.
**설계 의도:** `1:N` 구조로 설계하여 향후 다중 Provider 연동에 유연하게 대처합니다.

```sql
CREATE TABLE user_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 소유자 (Users 테이블 참조)
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- 인증 제공자 (예: 'riduck', 'strava', 'google')
    -- 확장성을 위해 Enum보다는 Varchar로 관리
    provider VARCHAR(50) NOT NULL,

    -- Access Token (API 호출용)
    access_token TEXT NOT NULL,

    -- Refresh Token (토큰 갱신용, Provider에 따라 없을 수도 있음)
    refresh_token TEXT,

    -- 토큰 만료 시점
    expires_at TIMESTAMP WITH TIME ZONE,

    -- 토큰 권한 범위 (예: 'read_profile', 'activity:read')
    scope TEXT,

    -- 메타 데이터
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- [정책] Provider당 하나의 토큰 세트만 유지 (단일 기기 정책)
    -- 동일 유저가 다른 기기에서 로그인 시, 기존 레코드를 덮어쓰거나(Update) 재생성(Insert)
    UNIQUE(user_id, provider)
);
```

---

## 3. 인증 흐름 (Authentication Flow)

### 3.1 로그인 (SSO-like Handoff)
OAuth 2.0의 복잡성을 줄이면서도 SSO 효과를 내기 위한 **JWT 전달 방식**을 사용합니다.

1.  **User Action:** 시뮬레이터(FE)에서 "라이덕으로 로그인" 클릭.
2.  **Redirect:** 라이덕 메인 서버(`riduck.com/sso/authorize`)로 이동.
3.  **Riduck Server:**
    *   로그인 상태 확인 (미로그인 시 로그인 화면 노출).
    *   시뮬레이터 전용 Secret Key로 서명된 **JWT 생성**. (Payload: `riduck_id`, `username`, `exp`)
    *   Callback URL(`simulator.com/callback?token={JWT}`)로 Redirect.
4.  **Simulator FE/BE:**
    *   전달받은 JWT 검증.
    *   Payload의 `riduck_id`로 `users` 테이블 조회 (Upsert).
    *   `user_tokens` 테이블 갱신.

### 3.2 토큰 갱신 및 만료 전략
*   **API 호출 시:** 백엔드 미들웨어에서 `user_tokens.expires_at` 체크.
*   **만료 시:**
    *   Refresh Token이 있다면 갱신 시도.
    *   없다면 클라이언트에 `401` 응답 -> 클라이언트는 다시 3.1의 로그인 프로세스를 수행 (Silent Refresh 가능).
#!/usr/bin/env bash
# Claude Code MCP wrapper: prod TimescaleDB(read-only) 접속.
#
# Claude Code가 이 스크립트를 통해 MCP를 띄우면:
#  1. 백그라운드로 SSH 터널 자동 생성 (localhost:54320 -> prod:5432)
#  2. 포트가 열리면 @modelcontextprotocol/server-postgres 실행
#  3. MCP 세션 종료 시 SSH 터널도 자동 정리
#
# 필요한 .env 키 (config/genie/.env.prod-local):
#   PROD_SSH_HOST   prod 호스트 (IP 또는 도메인)
#   PROD_SSH_USER   prod SSH 사용자명 (예: ubuntu)
#   PROD_SSH_KEY    (선택) SSH 키 경로 — 기본은 ssh 기본 키
#   PROD_DB_USER    read-only Postgres 롤 (예: genie_readonly)
#   PROD_DB_PASSWORD
#   PROD_DB_NAME    prod 데이터베이스 이름
#   PROD_DB_LOCAL_PORT (선택) 로컬 포워딩 포트 — 기본 54320

set -euo pipefail

ENV_FILE="/Users/sandeulpark/personal/genie/config/genie/.env.prod-local"
if [ ! -f "$ENV_FILE" ]; then
  echo "❌ $ENV_FILE not found — 자격증명 파일을 먼저 만들어주세요." >&2
  exit 1
fi
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${PROD_SSH_HOST:?PROD_SSH_HOST가 비어 있습니다}"
: "${PROD_SSH_USER:?PROD_SSH_USER가 비어 있습니다}"
: "${PROD_DB_USER:?PROD_DB_USER가 비어 있습니다}"
: "${PROD_DB_PASSWORD:?PROD_DB_PASSWORD가 비어 있습니다}"
: "${PROD_DB_NAME:?PROD_DB_NAME가 비어 있습니다}"
LOCAL_PORT="${PROD_DB_LOCAL_PORT:-54320}"

cleanup() {
  # 자식 프로세스 모두 정리 (SSH 터널 + npx)
  jobs -p | xargs -I{} kill -- -{} 2>/dev/null || true
  jobs -p | xargs kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# 1) SSH 터널 백그라운드 기동
SSH_OPTS=(-N
  -o ExitOnForwardFailure=yes
  -o StrictHostKeyChecking=accept-new
  -o ServerAliveInterval=30
  -o ServerAliveCountMax=3
  -L "${LOCAL_PORT}:localhost:5432")
if [ -n "${PROD_SSH_KEY:-}" ]; then
  SSH_OPTS+=(-i "${PROD_SSH_KEY/#\~/$HOME}")
fi
ssh "${SSH_OPTS[@]}" "${PROD_SSH_USER}@${PROD_SSH_HOST}" &
SSH_PID=$!

# 2) 포트 열릴 때까지 대기 (최대 6초)
for _ in $(seq 1 30); do
  if (echo > /dev/tcp/127.0.0.1/${LOCAL_PORT}) 2>/dev/null; then
    break
  fi
  if ! kill -0 "$SSH_PID" 2>/dev/null; then
    echo "❌ SSH 터널 기동 실패 — PROD_SSH_HOST/USER/KEY 확인" >&2
    exit 1
  fi
  sleep 0.2
done

# 3) Postgres MCP 서버 실행
ENC_PASS=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1], safe=''))" "$PROD_DB_PASSWORD")
URL="postgresql://${PROD_DB_USER}:${ENC_PASS}@127.0.0.1:${LOCAL_PORT}/${PROD_DB_NAME}"

# MCP 서버는 stdin/stdout으로 Claude Code와 JSON-RPC를 주고받는다.
# `npx ... &`만 쓰면 자식의 stdin이 부모 stdin과 분리돼 EOF로 즉시 종료되므로
# `<&0`으로 wrapper의 stdin을 npx에 명시적으로 redirect한다.
# exec를 쓰면 SSH 터널 cleanup trap이 사라져서 background + wait 패턴 유지.
npx -y @modelcontextprotocol/server-postgres "$URL" <&0 &
NPX_PID=$!

# MCP 서버(npx)가 종료될 때까지 대기 — 종료되면 trap이 SSH 터널 정리
# (macOS 기본 bash 3.2는 `wait -n` 미지원이라 npx PID로 직접 대기)
wait "$NPX_PID"

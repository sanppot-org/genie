#!/bin/bash

# 에러 발생 시 스크립트 중단
set -e

# PATH 설정 (uv 명령어 찾기 위함)
export PATH="/root/.local/bin:/home/ubuntu/.cargo/bin:/home/ubuntu/.local/bin:$PATH"

# uv 명령어 확인
if ! command -v uv &> /dev/null; then
    echo "❌ uv를 찾을 수 없습니다. 설치 중..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="/root/.local/bin:$PATH"
fi

echo "✅ uv 위치: $(which uv)"

# 슬랙 웹훅 URL 로드 (config/.env에서)
if [ -f "config/genie/.env" ]; then
    export $(grep -v '^#' config/genie/.env | grep SLACK_WEBHOOK_URL_GENIE_STATUS | xargs)
fi

# 슬랙 알림 전송 함수
send_slack_notification() {
    local message="$1"

    if [ -z "$SLACK_WEBHOOK_URL_GENIE_STATUS" ]; then
        echo "⚠️  슬랙 웹훅 URL이 설정되지 않아 알림을 전송하지 않습니다."
        return 0
    fi

    # 슬랙 메시지 전송
    curl -X POST "$SLACK_WEBHOOK_URL_GENIE_STATUS" \
        -H 'Content-Type: application/json' \
        -d "{\"text\":\"$message\"}" \
        --silent --show-error || {
            echo "⚠️  슬랙 알림 전송 실패 (배포는 계속 진행됩니다)"
            return 0
        }
}

echo "🚀 배포 시작..."

# 작업 디렉토리로 이동
cd /home/ubuntu/genie

# 현재 버전과 이전 버전 확인
echo "💾 버전 정보 확인 중..."
CURRENT_VERSION=$(git describe --tags --abbrev=0 2>/dev/null || git rev-parse HEAD)
# 현재 태그 바로 이전 태그 찾기 (semantic version 기준 정렬)
PREVIOUS_VERSION=$(git tag --sort=-version:refname | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | head -n 2 | tail -n 1)

# 이전 버전이 없으면 현재 커밋의 부모 커밋 사용
if [ -z "$PREVIOUS_VERSION" ]; then
    PREVIOUS_VERSION=$(git rev-parse HEAD^)
    echo "⚠️  이전 태그를 찾을 수 없어 부모 커밋을 사용합니다."
fi

echo "현재 버전: $CURRENT_VERSION"
echo "롤백 대상: $PREVIOUS_VERSION"

# 기존 .venv 디렉토리 삭제 (권한 문제 방지)
if [ -d ".venv" ]; then
    echo "🧹 기존 가상환경 삭제 중..."
    rm -rf .venv
fi

# Python 의존성 설치
echo "📦 의존성 설치 중..."
uv sync

# DB 마이그레이션 적용
echo "🗄️  DB 마이그레이션 적용 중..."
if ! uv run alembic upgrade head; then
    echo "❌ DB 마이그레이션 실패!"
    send_slack_notification "배포 실패 (마이그레이션 적용 실패: $CURRENT_VERSION)"
    exit 1
fi

# systemd 서비스 설치
echo "⚙️  systemd 서비스 설치 중..."
sudo cp genie.service /etc/systemd/system/genie.service
sudo systemctl daemon-reload

# 서비스 활성화 (부팅 시 자동 시작)
echo "🔄 서비스 활성화 중..."
sudo systemctl enable genie

# 서비스 재시작
echo "▶️  서비스 재시작 중..."
sudo systemctl restart genie

# 서비스가 시작될 시간 대기
echo "⏳ 서비스 시작 대기 중..."
sleep 3

# 서비스 상태 확인
echo "📊 서비스 상태 확인..."
if ! sudo systemctl is-active --quiet genie; then
    echo "❌ 서비스가 정상적으로 시작되지 않았습니다!"
    echo "📋 서비스 상태:"
    sudo systemctl status genie --no-pager
    echo ""
    echo "📋 최근 로그:"
    sudo journalctl -u genie -n 20 --no-pager
    echo ""

    # 롤백 시작
    echo "🔄 이전 버전($PREVIOUS_VERSION)으로 롤백 시작..."
    git checkout $PREVIOUS_VERSION

    echo "📦 이전 버전 의존성 재설치 중..."
    uv sync

    echo "▶️  서비스 재시작 중..."
    sudo systemctl restart genie

    echo "⏳ 서비스 시작 대기 중..."
    sleep 3

    # 롤백 후 상태 확인
    if ! sudo systemctl is-active --quiet genie; then
        echo "❌ 롤백도 실패했습니다! 수동 복구가 필요합니다."
        echo "📋 서비스 상태:"
        sudo systemctl status genie --no-pager
        exit 1
    fi

    echo "✅ 이전 버전으로 롤백 완료"
    echo "⚠️  배포는 실패했지만 서비스는 이전 버전으로 정상 실행 중입니다."
    sudo systemctl status genie --no-pager
    send_slack_notification "배포 실패 (롤백 완료: $PREVIOUS_VERSION)"
    exit 1
fi

echo "✅ 서비스가 정상적으로 실행 중입니다."
sudo systemctl status genie --no-pager

echo "✅ 배포 완료!"
send_slack_notification "정상 배포 [$CURRENT_VERSION]"
echo "📊 로그 확인: sudo journalctl -u genie -f"

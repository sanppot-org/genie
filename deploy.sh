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

echo "🚀 배포 시작..."

# 작업 디렉토리로 이동
cd /home/ubuntu/genie

# 현재 커밋 저장 (롤백용)
echo "💾 현재 버전 저장 중..."
PREVIOUS_COMMIT=$(git rev-parse HEAD)
echo "이전 커밋: $PREVIOUS_COMMIT"

# 기존 .venv 디렉토리 삭제 (권한 문제 방지)
if [ -d ".venv" ]; then
    echo "🧹 기존 가상환경 삭제 중..."
    rm -rf .venv
fi

# Python 의존성 설치
echo "📦 의존성 설치 중..."
uv sync

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
    echo "🔄 이전 버전으로 롤백 시작..."
    git checkout $PREVIOUS_COMMIT

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
    exit 1
fi

echo "✅ 서비스가 정상적으로 실행 중입니다."
sudo systemctl status genie --no-pager

echo "✅ 배포 완료!"
echo "📊 로그 확인: sudo journalctl -u genie -f"

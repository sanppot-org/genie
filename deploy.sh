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

# 서비스 상태 확인
echo "📊 서비스 상태 확인..."
sudo systemctl status genie --no-pager || true

echo "✅ 배포 완료!"
echo "📊 로그 확인: sudo journalctl -u genie -f"

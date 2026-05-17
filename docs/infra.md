# 인프라 정보

## 주의사항

- 서버 접속 시 조회만 하고 수정,삭제 등 쓰기 작업은 임의로 금지. 항상 사용자의 허락을 구한다.

## 서버

- OCI
- 접속 방법: ssh -i ~/.ssh/oci-app.key ubuntu@150.230.252.125

## 배포 구조

- 태그 `v*.*.*` push → `.github/workflows/deploy.yml` 실행:
  1. GitHub Actions에서 `web/` 빌드 (`NEXT_PUBLIC_API_BASE_URL=""` + `pnpm build` → `web/out/` 정적 export)
  2. `out/` 내용을 서버 `/var/www/genie/`로 scp
  3. 서버 SSH로 들어가 백엔드 `deploy.sh` 실행 (uv sync + alembic + systemd restart)
- 백엔드: `genie.service` (systemd, uvicorn `127.0.0.1:8000`)
- 프론트: nginx가 `/var/www/genie` 정적 서빙 + `/api/*`를 백엔드로 reverse proxy
- 외부 접근: `http://150.230.252.125/` (도메인 없음, IP 직접)

## 서버 1회 수동 셋업 (genie 프론트)

GitHub Actions 첫 배포 전 서버에서 1회 실행:

```bash
# 1. 정적 파일 디렉토리 생성 + 소유권 (ubuntu가 scp로 쓸 수 있게)
sudo mkdir -p /var/www/genie
sudo chown -R ubuntu:ubuntu /var/www/genie

# 2. nginx config 적용 (repo의 infra/nginx/genie.conf 참조)
sudo cp /home/ubuntu/genie/infra/nginx/genie.conf /etc/nginx/sites-available/genie
sudo ln -sf /etc/nginx/sites-available/genie /etc/nginx/sites-enabled/genie

# 3. 기존 default 비활성 (genie가 default_server 자리 차지)
sudo rm /etc/nginx/sites-enabled/default

# 4. 문법 검사 + reload
sudo nginx -t && sudo systemctl reload nginx
```

## 사용 포트

- 80, 443: nginx (외부 노출, ufw Nginx Full)
- 8000: uvicorn (localhost only, ufw self-IP 한정)
- 8080: 다른 서비스 docker
- 9000: kmooc
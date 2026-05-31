"""KIS 종목추정실적 wrapper — 연간 추정(매출/영업이익/순이익/EPS/PER) 추출.

HantuDomesticAPI(`estimate_perform`)를 wrap해 기간별 행 리스트로 정규화한다.
응답은 행=지표 × 열(data1~5)=기간 매트릭스라 전치(transpose)해서 기간 단위로 만든다.

매핑(공식 명세 '국내주식 종목추정실적' 시트 + 실측 검증, 2026-05-31):
- output4[i].dt = 결산연월(예 '2025.12', '2026.12E'). 'E' suffix → 추정. data{i+1} 열이 대응.
- output2(추정손익계산서, 6행): 0=매출액, 1=매출액증감율, 2=영업이익, 3=영업이익증감율,
  4=순이익, 5=순이익증감율 (금액 억원, 증감율 ×10).
- output3(투자지표, 8행): 0=EBITDA(십억원), 1=EPS, 2=EPS증감율, 3=PER, 4=EV/EBITDA,
  5=ROE, 6=부채비율, 7=이자보상배율 (EPS·PER 등 ×10 → ÷10 정규화). 사용: EPS(1), PER(3).

확정 기간도 함께 반환한다(조회 레이어는 추정 기간만 사용).

커버리지: 명세상 "거래소·코스닥 160여개 기업 한정"(리서치본부 추정종목리스트). 그 밖(보험사
삼성화재 등·소형주)은 rt_cd=0이나 output 전부 빈 응답 → 빈 리스트. 또 은행/증권/금융지주는
output2(손익)만 오고 output3(EPS/PER)는 빈 경우가 있어 EPS/PER은 행별 best-effort로 읽는다.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import logging

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.hantu.domestic_api import HantuDomesticAPI
from src.hantu.model.domestic import estimate_perform
from src.providers.kis_income_statement_client import _RATE_LIMIT_CODE, KisRateLimitError

logger = logging.getLogger(__name__)

# output2/output3 내 지표 행 인덱스 (0-based). 라벨이 없어 위치 고정 매핑.
_ROW_REVENUE = 0
_ROW_REVENUE_GROWTH = 1  # output2: 매출증가율(%×10) — 내부 정합성 검증용
_ROW_OPERATING = 2
_ROW_NET = 4
_ROW_EPS = 1
_ROW_PER = 3
# 매출 YoY(계산) vs 매출증가율 행(보고)의 허용 오차(×10 percent, =5.0%p 또는 10% 상대).
_GROWTH_TOL = Decimal(50)
# 핵심 손익(매출/영업이익/순이익)은 output2만 있으면 된다. output3(EPS/PER)는
# 종목마다 행 수가 달라(예: SK하이닉스는 3행) best-effort로 행별 접근한다.
_MIN_O2_ROWS = _ROW_NET + 1   # 5
# data1~5 → 최대 5개 기간
_MAX_PERIODS = 5
# 추정치 비율/EPS/PER 스케일(÷10)
_SCALE = Decimal(10)


@dataclass(frozen=True)
class EstimatePointData:
    """기간별 추정실적 1건 (억원). is_estimate=False는 확정 기간(안전가드용)."""

    stac_yymm: str                  # 결산년월 YYYYMM
    is_estimate: bool               # True=추정(…E), False=확정(조회 레이어는 추정만 사용)
    revenue: Decimal | None         # 매출액
    operating_profit: Decimal | None  # 영업이익
    net_income: Decimal | None      # 당기순이익
    eps: float | None               # 주당순이익(원)
    per: float | None               # 추정 PER(배)


def _parse(raw: str | None) -> Decimal | None:
    """추정 금액 문자열 → Decimal. 빈값/파싱 실패는 None."""
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _parse_scaled(raw: str | None) -> float | None:
    """×10 스케일 문자열(EPS/PER) → float. 빈값/파싱 실패는 None."""
    v = _parse(raw)
    return float(v / _SCALE) if v is not None else None


def _row_at(rows: list[estimate_perform.EstimateDataRow], idx: int) -> estimate_perform.EstimateDataRow | None:
    """rows[idx] 안전 접근 — 범위 밖이면 None(종목별 output3 행 수 가변 대응)."""
    return rows[idx] if 0 <= idx < len(rows) else None


def _col(row: estimate_perform.EstimateDataRow | None, period_idx: int) -> str | None:
    """기간 인덱스(0-based) → 해당 data 열 값. 행 없거나 범위 밖이면 None."""
    if row is None:
        return None
    return getattr(row, f"data{period_idx + 1}", None)


def _to_stac_yymm(dt: str) -> str | None:
    """'2026.12E' / '2025.12' → '202612'. 형식 불량이면 None."""
    core = dt.rstrip("E").strip()
    digits = core.replace(".", "")
    if len(digits) == 6 and digits.isdigit():
        return digits
    return None


def _internally_consistent(o2: list[estimate_perform.EstimateDataRow], n_periods: int) -> bool:
    """응답 내부 정합성 — 매출 행의 YoY가 매출증가율 행과 산술적으로 맞는지.

    행=지표 위치 고정 매핑이 깨졌는지(예: 행0이 매출이 아닌 다른 지표) 탐지하는,
    cross-source에 의존하지 않는 검증. 금융지주처럼 소스 간 매출 정의가 달라도
    응답 내부에서는 일관되므로 통과한다. 검증 불가(값 결측/전기 0)는 통과로 본다.
    """
    rev = o2[_ROW_REVENUE]
    growth = _row_at(o2, _ROW_REVENUE_GROWTH)
    if growth is None:
        return True
    for i in range(1, n_periods):
        cur, prev = _parse(_col(rev, i)), _parse(_col(rev, i - 1))
        reported = _parse(_col(growth, i))
        if cur is None or prev is None or reported is None or prev == 0:
            continue
        expected = (cur / prev - 1) * 100 * _SCALE  # ×10 percent
        tol = max(_GROWTH_TOL, abs(expected) * Decimal("0.1"))
        if abs(expected - reported) > tol:
            return False
    return True


class KisEstimateClient:
    """KIS 종목추정실적 client (조회 전용, best-effort 호출은 서비스 레이어 담당)."""

    def __init__(self, api: HantuDomesticAPI) -> None:
        self._api = api

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, KisRateLimitError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def fetch(self, ticker: str) -> list[EstimatePointData]:
        """종목 추정실적 조회 → 기간 오름차순 리스트(확정+추정 모두).

        - 일시 네트워크 오류/초당거래 초과는 재시도, 그 외는 전파(서비스가 best-effort 처리).
        - 미커버 종목/행 부족 등 매핑 불가 시 빈 리스트.
        """
        try:
            res = self._api.estimate_perform(ticker)
        except requests.RequestException:
            raise
        except Exception as e:
            if _RATE_LIMIT_CODE in str(e):
                raise KisRateLimitError(str(e)) from e
            raise

        periods = res.output4
        if not periods or len(res.output2) < _MIN_O2_ROWS:
            return []

        o2, o3 = res.output2, res.output3
        if not _internally_consistent(o2, min(len(periods), _MAX_PERIODS)):
            logger.warning("추정실적 내부 정합성 실패(행순서 의심) → skip ticker=%s", ticker)
            return []

        eps_row, per_row = _row_at(o3, _ROW_EPS), _row_at(o3, _ROW_PER)
        points: list[EstimatePointData] = []
        for i, period in enumerate(periods):
            if i >= _MAX_PERIODS or not period.dt:
                continue
            stac_yymm = _to_stac_yymm(period.dt)
            if stac_yymm is None:
                continue
            points.append(EstimatePointData(
                stac_yymm=stac_yymm,
                is_estimate=period.dt.strip().endswith("E"),
                revenue=_parse(_col(o2[_ROW_REVENUE], i)),
                operating_profit=_parse(_col(o2[_ROW_OPERATING], i)),
                net_income=_parse(_col(o2[_ROW_NET], i)),
                eps=_parse_scaled(_col(eps_row, i)),
                per=_parse_scaled(_col(per_row, i)),
            ))
        return points

# trading-bot: 자동매매 봇

정해둔 전략대로 **알아서 매수·매도하는 프로그램**이야. 미국 주식/ETF는 Alpaca, 코인은 Upbit·Binance 같은 CCXT 거래소를 지원해.

- **기본값은 paper trading(모의투자)이야.** 가짜 돈에 실제 시세를 쓰니까 실제 돈은 한 푼도 안 나가.
- 실제 돈으로 거래하려면 두 가지를 **둘 다** 직접 켜야 해: config의 `mode: live`와 환경변수 `LIVE_TRADING_CONFIRM=I_ACCEPT_THE_RISK`. 하나만 켜면 봇이 시작을 거부해.
- 백테스트와 실거래가 **똑같은 전략 코드**를 써. 그래서 테스트한 로직 그대로 매매해.

> ⚠️ **먼저 읽어줘.** 이건 투자 조언이 아니야. 자동매매도 돈을 잃을 수 있고, 버그·거래소 장애·슬리피지 때문에 빠르게 잃을 수도 있어. 백테스트에서 수익이 났다고 미래에도 수익이 나는 건 아니야. 실제로 대부분의 단순 전략은 수수료를 빼고 나면 그냥 사서 들고 있는 것(buy & hold)보다 못해. **최소 몇 주는 paper로 돌려보고**, 잃어도 괜찮은 돈으로만 live를 켜.

---

## 0. 5분 만에 돌려보기 (API 키·인터넷 필요 없음)

```bash
cd trading-bot
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m bot demo
```

`demo`는 두 가지를 해:
1. 가짜 가격 데이터로 기본 전략 3개를 **백테스트**해서 buy & hold와 비교해 줘.
2. 시뮬레이터 위에서 **실제 매매 루프(engine)** 를 3번 돌려서, 봇이 신호를 보고 주문을 넣는 과정을 보여줘.

---

## 1. 이 봇이 하는 일 (한 번의 "tick")

```
kill switch 켜져 있나? ──yes──> 아무것도 안 함
        │no
계좌 조회 → 날짜 바뀌었으면 일일 카운터 리셋
        │
장 열려 있나? (코인은 24/7) ──no──> 대기
        │yes
일일 손실 한도 넘었나? ──yes──> 오늘은 신규 매수 중단 (매도·손절은 계속)
        │
종목마다:
  ├─ 보유 중이면: 손절(stop-loss)/익절(take-profit) 가격 체크 → 걸리면 매도
  │     (제일 먼저 해. 미체결 주문이 있거나 캔들 데이터를 못 받아도 체크해)
  ├─ 봇이 낸 주문이 아직 미체결이면 그 종목은 이번엔 건너뜀
  ├─ "완성된" 마지막 봉으로 전략 신호 계산 (아직 형성 중인 봉은 버림)
  │     SELL + 보유 중 → 전량 매도
  │     BUY  + 미보유 → risk 한도로 수량 계산 → 시장가 매수
  └─ 같은 봉은 두 번 평가 안 함 (중복 주문 방지)
```

`run`은 이 tick을 `poll_interval_seconds`마다 계속 반복하고, `once`는 한 번만 돌고 끝나. `once`는 cron이나 GitHub Actions용이야.

---

## 2. 미국 주식 paper trading (Alpaca)

**① 키 발급.** [alpaca.markets](https://alpaca.markets)에 가입한 다음 **Paper Trading** 계정으로 전환해서 API Keys를 만들어. 무료고 미국 거주자가 아니어도 paper는 돼.

**② `.env` 만들기**
```bash
cp .env.example .env
# .env 열어서 ALPACA_API_KEY, ALPACA_SECRET_KEY 채우기
```
키는 **절대** config YAML에 넣지 마. 넣으면 봇이 에러를 내면서 거부해.

**③ 백테스트 먼저.** Alpaca 과거 데이터로 돌려:
```bash
python -m bot -c configs/stocks.yaml backtest --bars 2000
```
결과는 `results/<시간>/`에 `equity.csv`, `trades.csv`, `metrics.json`으로 저장돼. 요약의 `Trading` 줄은 전략이 지표용 봉을 모으는 warm-up 구간 다음, 실제로 매매할 수 있는 기간이야. CAGR·Sharpe·변동성·Time in market은 buy & hold처럼 이 기간 기준으로 계산해 (warm-up 봉을 넣으면 숫자가 실제보다 낮게 나와).

**④ paper로 자동매매 시작**
```bash
python -m bot -c configs/stocks.yaml once     # 한 번만 돌려서 확인
python -m bot -c configs/stocks.yaml run      # 계속 돌리기 (Ctrl-C로 정지)
python -m bot -c configs/stocks.yaml status   # 계좌·포지션·봇 상태 보기
```

기본 설정(`configs/stocks.yaml`)은 이래:
- SPY와 QQQ를 일봉(1d)으로 봐.
- 전략은 RSI(2) mean reversion이야. 200일선 위(상승 추세)에서 단기로 급락하면 사고, 반등하면 팔아.
- 포지션 하나는 자산의 약 25%, 동시에 최대 2개야. 손절은 -8%(걸리면 자산 기준 약 -2%), 일일 손실 한도는 -3%.
- 일봉 전략이라서 **하루에 종목당 많아야 한 번 정도** 거래해. 장 열린 뒤 첫 tick에서 전날 종가 기준 신호로 주문해.
- 분·시간봉(`1h` 등)으로 바꾸면 **정규장(뉴욕 9:30–16:00) 봉만** 써. Alpaca는 프리마켓·애프터마켓 봉도 주지만, 봇은 장중에만 매매하니까 백테스트도 실거래도 같은 정규장 봉으로 판단해. `1h`·`4h` 봉은 30분봉을 모아서 만들어서, 9시 봉에도 프리마켓 체결이 안 섞여 (9:30–10:00만 들어가). 그래서 백테스트에서 밤사이 낸 주문은 9:30 시가에 체결되고, 프리마켓 저가로 손절되지도 않아.
- 내 설정을 만들 때는 **`configs/` 안에** 복사해 (`cp configs/stocks.yaml configs/my.yaml`). 그리고 모든 명령(`run`, `kill`, `flatten` …)에 항상 `-c configs/my.yaml`을 붙여. `state_dir: ../state/...` 같은 경로는 config 파일이 있는 폴더 기준이라서, 프로젝트 루트로 복사하면 상태·로그가 프로젝트 밖에 생기고 `kill -c configs/...`가 실행 중인 봇이 못 보는 곳에 KILL 파일을 만들어.

---

## 3. 코인 (Upbit / Binance 등, CCXT)

```bash
python -m bot -c configs/crypto.yaml backtest --bars 1000   # 공개 시세라서 키 필요 없음
python -m bot -c configs/crypto.yaml run
```

- `mode: paper`에서는 **키가 없어도 돼.** 거래소 공개 시세를 받아서 **로컬에서 가상 체결**해 (시작 자금 1,000,000 KRW).
- 기본값은 BTC/KRW와 ETH/KRW를 4시간봉으로 보는 Donchian breakout이야. Upbit 최소 주문 금액인 5,000원도 반영돼 있어.
- 거래소를 바꾸려면 `broker.exchange`(`binance`, `bithumb` …)랑 `symbols`(`BTC/USDT` …)를 고치면 돼.
- 실거래 키를 만들 때는 **주문 권한만** 주고, **출금 권한은 절대 주지 마.** Upbit는 API 키에 허용 IP를 등록해야 해서 IP가 고정된 서버(VPS)에서 돌리는 게 맞아. GitHub Actions는 IP가 매번 바뀌어서 안 돼.
- Binance testnet을 쓰려면 `use_sandbox: true`에 testnet 키를 넣어.

---

## 4. 24시간 알아서 돌게 하기

| 방법 | 비용 | 추천 상황 |
|---|---|---|
| **GitHub Actions** (`once`를 15분마다) | 무료 (private repo도 월 ~700분이라 무료 한도 안) | 주식 일봉 전략. 서버 관리가 싫을 때 |
| **Docker** (`docker compose up -d`) | VPS 월 $4–6 (Oracle Cloud free tier도 가능) | 코인 24/7, 분·시간봉 전략 |
| **systemd** (`deploy/trading-bot.service`) | VPS | Docker 없이 리눅스 서버에서 |
| 내 컴퓨터에서 `run` | 0 | 테스트용. 컴퓨터가 꺼지면 봇도 멈춰 |

### GitHub Actions 설정
`.github/workflows/trading-bot.yml`이 이미 들어 있어. **기본은 꺼져 있어.**

1. 이 브랜치를 `main`에 merge해. GitHub schedule은 default branch에서만 돌아.
2. Repo **Settings → Secrets and variables → Actions**로 가서:
   - **Secrets**에 `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`를 넣어. 알림을 받고 싶으면 `NOTIFY_WEBHOOK_URL`이나 `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`도 넣어.
   - **Variables**에 `TRADING_BOT_ENABLED` = `true`를 넣어. 이게 on 스위치야. 다른 config를 쓰고 싶으면 `TRADING_BOT_CONFIG` = `configs/내설정.yaml`도 추가해.
3. **Actions** 탭 → `trading-bot` → **Run workflow**로 한 번 수동 실행해서 로그를 확인해.

평일 미국 장 시간에 15분마다 한 번씩 tick을 돌려. 봇 상태(오늘 거래 수, 마지막으로 평가한 봉, 봇이 산 수량)는 Actions cache로 다음 실행에 넘어가고, 로그는 artifact로 14일 동안 남아. cache는 `trading-bot/state`만 저장하니까 내 config의 `state_dir`도 그 안(예: `state_dir: ../state/my`)이어야 해. 아니면 `once`가 GitHub Actions에서 매매를 거부하고 이유를 알려줘. 끄려면 `TRADING_BOT_ENABLED`를 지우거나 `false`로 바꿔.

### Docker
```bash
cp .env.example .env    # 키 채우기
docker compose up -d    # 백그라운드 실행, 재부팅돼도 자동 재시작
docker compose logs -f  # 로그 보기
```
config를 바꾸려면 `docker-compose.yml`의 `command`를 고쳐. `configs/` 폴더는 컨테이너에 마운트돼 있어서, config 파일을 고친 다음 `docker compose restart`만 하면 바로 적용돼. 코드나 `requirements.txt`를 바꿨을 때만 `docker compose up -d --build`로 다시 빌드해. 상태와 로그는 `./state`, `./logs`에 남아. 컨테이너가 uid 1000으로 돌기 때문에 권한 에러가 나면 `sudo chown -R 1000 state logs`를 실행해.

---

## 5. 전략

```bash
python -m bot strategies   # 목록 + 기본 파라미터
```

| 이름 | 스타일 | 매수 | 매도 |
|---|---|---|---|
| `sma_crossover` | 추세추종 | 단기 SMA > 장기 SMA | 단기 SMA < 장기 SMA |
| `rsi_reversion` | 역추세 (Connors RSI-2) | RSI(2) < 10 **그리고** 종가 > 200일선 | RSI > 70 또는 종가 > 5일선 |
| `donchian_breakout` | 돌파 (Turtle) | 종가가 직전 20봉 최고가 돌파 | 종가가 직전 10봉 최저가 이탈 |

- 전부 **long-only**야. 공매도(short)나 레버리지(margin)는 절대 안 해.
- 신호는 "상태 기반"이야. 조건이 맞는 동안에는 매 봉마다 BUY/SELL을 내. 그래서 tick 하나를 놓쳐도 다음 봉에서 다시 시도해.
- 파라미터는 config의 `strategy.params`에서 바꿔. 오타가 있으면 봇이 시작 전에 에러로 알려줘.
- 새 전략을 추가하려면 `bot/strategies/`에 `Strategy`를 상속한 클래스를 만들고 `STRATEGIES`에 등록해.

---

## 6. Risk 설정 (`risk:`)

| 키 | 의미 |
|---|---|
| `risk_per_trade_pct` | 손절에 걸리면 자산의 몇 %를 잃을지. 포지션 크기는 `risk_per_trade_pct / stop_loss_pct`로 계산돼 |
| `stop_loss_pct` / `take_profit_pct` | 평단가 대비 손절/익절 %. `null`이면 꺼짐 |
| `max_position_pct` | 한 종목 최대 비중 |
| `max_total_exposure_pct` | 전체 투자 비중 상한. 나머지는 현금으로 둬 |
| `max_open_positions` | 동시에 들고 있을 종목 수 |
| `max_daily_loss_pct` | 하루 손실이 이만큼 되면 그날은 신규 매수를 멈춰 |
| `flatten_on_daily_loss` | `true`면 한도에 걸릴 때 `symbols`에서 봇이 산 포지션을 전량 매도까지 해 (계좌의 다른 종목, 내가 산 수량, 내가 건 주문은 안 건드려) |
| `max_trades_per_day` | 하루 신규 진입 횟수 상한. 매도는 제한 없어 |
| `min_order_notional` | 최소 주문 금액. **quote 통화 단위**야 (KRW 마켓은 원, USDT 마켓은 USDT, BTC 마켓은 BTC). 거래소 자체 최소값(Upbit KRW 5000, Alpaca 1)도 따로 적용돼 |
| `cash_buffer_pct` | 수수료·슬리피지에 대비해서 남겨둘 현금 % |

---

## 7. 안전장치 & 비상 정지

```bash
python -m bot -c configs/stocks.yaml kill --reason "휴가"   # 모든 주문 즉시 중단: 손절·익절 매도도 멈춰 (열린 포지션은 보호 안 됨)
python -m bot -c configs/stocks.yaml resume                  # 다시 허용
python -m bot -c configs/stocks.yaml flatten --yes           # 모든 포지션 시장가 청산
```

kill switch가 켜져 있는 동안 봇은 **아무 주문도 안 내.** 신규 매수만이 아니라 손절·익절 매도도 안 나가니까, 휴가처럼 오래 비울 때는 포지션을 `flatten --yes`로 먼저 정리하거나 kill switch 없이 손절에 맡겨. config를 고치다가 틀려도 `kill`/`resume`은 동작해 (config의 `state_dir`만 읽어). 다른 명령이 config 에러를 내면 실행 중인 봇을 멈추는 KILL 파일 경로를 같이 알려줘.

> **GitHub Actions로 돌리는 봇은 `kill`로 안 멈춰.** KILL 파일은 명령을 실행한 컴퓨터의 `state` 폴더에 생기는데, Actions는 매번 Actions cache에서 상태를 가져와서 그 파일을 못 봐. Actions 봇을 멈추려면 repo **Variables**의 `TRADING_BOT_ENABLED`를 `false`로 바꾸거나 `trading-bot` workflow를 disable해 (4장 참고).

- **Paper가 기본이야.** live는 config `mode: live`와 env `LIVE_TRADING_CONFIRM`이 둘 다 있어야 켜져.
- **Margin을 안 써.** Alpaca에서는 `non_marginable_buying_power`(실제 현금)만 써.
- **Short를 안 해.** 매도 수량은 보유 수량을 넘지 않아. 수량은 항상 내림(round down)해. margin 계좌에 내가 직접 연 short 포지션이 있으면 그 종목은 사지 않아 (사면 내 short를 덮어버리니까). 처음 발견하면 알림을 한 번 보내.
- **완성된 봉으로만 판단해.** 형성 중인 봉은 버려. 같은 봉에서는 한 번만 판단하고, 봇이 낸 주문이 아직 미체결이면 그 종목은 건너뛰어.
- **손절·익절은 (kill switch가 꺼져 있을 때) 항상 먼저 체크해.** 같은 종목에 내가 직접 넣은 주문(앱에서 건 지정가 등)이 있어도, 캔들 데이터를 못 받아도 손절은 돌아. 최신 시세 조회가 실패하면 브로커가 알려준 포지션 가격으로 손절을 체크해. 수동 주문이 있는 종목은 신규 매수만 멈춰. 수동 주문이 수량을 잡고 있어서 손절 매도가 거부되면 에러 알림을 보내.
- **체결 전 주문도 한도에 넣어.** 주문이 접수됐는데 아직 체결이 안 됐어도 같은 tick의 다음 종목을 계산할 때 포지션 수·투자 비중·현금 한도에 포함해.
- **봇은 자기가 산 것만 관리하고 팔아.** 봇이 직접 낸 주문으로 산 수량을 상태 파일에 기록해 두고, 손절·익절·전략 매도·`flatten_on_daily_loss`는 그 수량에만 적용해. 봇을 켜기 전부터 계좌에 있던 주식·코인은 `symbols`에 있는 종목이라도 **절대 안 팔고**, 그 종목은 새로 사지도 않아. 처음 발견하면 알림을 한 번 보내고 `status`에도 표시해. 기존 보유분까지 봇이 관리하게(=팔 수도 있게) 하려면 config에 `adopt_existing_positions: true`를 넣어. (로컬 paper 계좌는 봇만 거래하니까 전부 봇 것으로 봐.) 코인 평균 매수가 파일도 계좌별(`ccxt_entries.<거래소>[.sandbox].json`)이라 testnet 기록이 live에 섞이지 않아.
- **주문 결과가 불확실해도 봇 것으로 기록해.** 주문을 보내기 전에 상태 파일에 먼저 기록하고 저장해. 그래서 응답이 끊기거나(timeout) 주문 도중 프로세스가 죽어도, 실제로 체결된 매수는 봇이 산 것으로 남아서 손절이 계속 돌아. 매도는 체결된 만큼만 봇의 수량에서 빼. 주문이 끝나면 브로커에 그 주문의 실제 체결 수량을 조회해서 기록을 맞추고 (Alpaca는 봇이 붙인 주문 ID로 조회해서 응답이 끊긴 주문도 찾아내), 조회가 안 되면 보유 수량 변화로 맞춰. 거래 정지 등으로 매도 주문이 체결 안 되고 만료·취소되면, 남은 수량은 여전히 봇 것이라서 다음 tick에 손절 매도를 다시 보내. 봇의 매수 주문이 아직 체결 중인 동안에는 그 종목을 팔지 않아 (그 사이 내가 산 주식과 구별이 안 되니까).
- **주식 분할(split)·병합도 따라가.** 브로커가 보유 수량과 평단가를 바꾸면(예: 2:1 분할 → 수량 2배, 평단 1/2) 봇이 산 수량과 평단가도 같이 맞추고 알림을 보내. 그래서 분할 때문에 가짜 손절이 나가거나, 병합 뒤에 손절이 꺼지지 않아.
- **`flatten --yes`는 Alpaca에서 계좌 전체야.** 봇이 안 산 종목까지 전부 팔고 모든 미체결 주문을 취소해. 반면 `flatten_on_daily_loss`는 봇이 산 포지션만 팔고, **봇이 낸 매수 주문만** 취소해. 내가 직접 건 주문(내 주식에 건 손절 주문 등)은 그대로 둬.
- **`symbols`에서 뺀 종목은 관리 안 해.** 아직 들고 있으면 손절도 매도도 안 해. 봇이 한 번 알림을 보내고 `status`에도 표시해.
- **일일 손실 한도는 매매 손익만 봐.** 장중에 입금·출금하거나, 봇이 평가하지 않는 자산(코인 계좌에서 `symbols`에 없는 코인)을 직접 사고팔아서 현금이 움직이면, 그만큼 그날의 기준 자산을 조정해. 그래서 손실로 오인해서 멈추거나(청산하거나), 반대로 진짜 손실이 가려지지 않아. 봇의 주문이 체결되는 중에는 (주문 직후 1–2 tick) 계좌 조회와 포지션 조회 사이에 체결이 끼어 봇 자신의 매매가 입출금처럼 보일 수 있어서, 그동안은 입출금 추적을 쉬어. (Alpaca에서 장 마감 후 입출금은 다음 날 기준값인 전일 종가 자산에 반영이 안 될 수 있어.)
- **프로세스가 겹치지 않아.** instance lock이 있어서 봇 두 개가 같은 계좌로 동시에 매매하지 못해 (Windows 포함).
- **에러가 나도 안 죽어.** 에러는 기록하고 재시도해. 계좌 조회 실패처럼 tick 전체가 실패하면 backoff하고, 종목 하나의 에러나 상태 파일 에러는 손절 체크를 늦추지 않아. 연속으로 에러가 나면 마지막 에러 내용과 함께 알림을 보내.
- **상태 파일을 못 저장하거나 못 읽으면 신규 매수를 멈춰.** 주문을 내기 전에 먼저 저장해 보고, 실패하면 (디스크가 꽉 찼을 때 등) 오늘 거래 수·일일 손실 정지는 메모리에서 계속 세면서 저장이 다시 될 때까지 매도·손절만 해. `once`(cron)로 돌릴 때도 마찬가지야. 파일을 못 읽으면(권한 문제 등) 덮어쓰지 않고, 봇이 기억하는 포지션의 손절·매도만 계속해. 상태 파일은 일반 권한(0644)으로 저장돼서 `sudo`로 한 번 돌려도 서비스 사용자가 계속 읽을 수 있어.
- **기록이 남아.** 모든 주문(수동 `flatten` 포함)은 `logs/<이름>/trades.csv`, 전체 로그는 `logs/<이름>/bot.log`에 남아.

### Live 켜기 전 체크리스트
- [ ] paper로 최소 2–4주 돌렸고, `trades.csv`를 보니 의도한 대로 매매했다
- [ ] 백테스트에서 수수료·슬리피지를 넣고도 buy & hold와 비교해서 납득이 된다
- [ ] 알림(Discord/Slack/Telegram)이 실제로 온다
- [ ] 잃어도 괜찮은 금액만 계좌에 넣었다
- [ ] 계좌에 이미 들고 있는 주식·코인이 있다면, 봇은 그걸 안 건드린다는 걸 알고 있다 (같은 종목은 새로 사지도 않아). 봇이 관리하게 하려면 `adopt_existing_positions: true`를 켜야 하고, 그러면 손절·전략 신호로 **팔릴 수 있어**
- [ ] 거래소 키에 출금 권한이 없다
- [ ] config에 `mode: live`, `.env`(또는 GitHub secret)에 `LIVE_TRADING_CONFIRM=I_ACCEPT_THE_RISK`를 넣었다. Alpaca는 live 키가 paper 키와 **다르니까** 키도 바꿔야 해

---

## 8. 알림 (선택)

`.env`에 넣기만 하면 켜져:
- **Discord/Slack**: 채널 설정에서 Incoming Webhook URL을 만들어서 `NOTIFY_WEBHOOK_URL`에 넣어
- **Telegram**: @BotFather에서 받은 토큰은 `TELEGRAM_BOT_TOKEN`, 내 chat id는 `TELEGRAM_CHAT_ID`에 넣어. **둘 다** 있어야 해 (하나만 있으면 봇이 시작 전에 에러로 알려줘)

주문이 나가거나 에러가 나거나 일일 손실 한도에 걸리면 메시지가 와. 켜고 끄는 건 config의 `notify.on_trade`, `notify.on_error`로 해. `run`을 시작할 때 나오는 화면의 `Notify` 줄에서 알림이 어디로 가는지(또는 안 가는지) 확인할 수 있어.

---

## 9. 구조

```
trading-bot/
├── bot/
│   ├── cli.py            # python -m bot <command>
│   ├── engine.py         # 실거래 루프 (tick)
│   ├── backtest.py       # 이벤트 기반 백테스터 (다음 봉 시가 체결, 수수료·슬리피지)
│   ├── risk.py           # 포지션 사이징, 손절/익절, 일일 손실 한도
│   ├── strategies/       # sma_crossover, rsi_reversion, donchian_breakout
│   ├── indicators.py     # SMA, EMA, RSI(Wilder), ATR, 채널
│   ├── brokers/          # alpaca_broker, ccxt_broker, paper(로컬 시뮬)
│   ├── config.py         # YAML 로드 + 검증 + live 이중 확인
│   ├── state.py          # 상태 저장, kill switch
│   ├── notify.py         # Discord/Slack/Telegram
│   └── data.py           # CSV 로더, 합성 데이터
├── configs/              # demo.yaml, stocks.yaml, crypto.yaml
├── tests/                # pytest (오프라인)
├── deploy/               # systemd 유닛
├── Dockerfile, docker-compose.yml
└── .env.example
```

테스트:
```bash
pip install -r requirements-dev.txt
pytest
```

CSV로 백테스트하려면 `date, open, high, low, close, volume` 컬럼이 있어야 해:
```bash
python -m bot -c configs/stocks.yaml backtest --csv SPY=data/spy.csv --csv QQQ=data/qqq.csv
```
CSV의 봉 간격은 config의 `timeframe`과 같아야 해 (다르면 봇이 거부해). 샤프·변동성 연율화는 데이터에 주말 봉이 있으면 1년 365일, 없으면 252일로 계산해.

---

## 10. FAQ

- **`market_closed`만 떠요.** 미국 장 시간(뉴욕 9:30–16:00, 평일)이 아니라서 그래. 정상이야.
- **`warming up`이 떠요.** 지표를 계산할 봉이 아직 부족해서 그래. 예를 들어 `rsi_reversion`은 201봉이 필요해. 거래소가 과거 봉을 그보다 적게 주면(예: 최대 200개만 주는 거래소, 상장한 지 얼마 안 된 종목) 봇이 알림을 한 번 보내. 그럴 땐 전략 기간을 줄이거나 더 긴 timeframe을 써.
- **실제 돈 안 나가는 거 맞아요?** `status`를 치면 맨 위에 모드(PAPER/LIVE)가 나와. Alpaca paper 키는 원래 실계좌에 접근할 수 없어.
- **한국 주식도 돼요?** 지금은 안 돼. 한국투자증권(KIS) Open API 같은 걸 `bot/brokers/`에 adapter로 추가하면 되고, `Broker` 인터페이스만 구현하면 나머지는 그대로 동작해.

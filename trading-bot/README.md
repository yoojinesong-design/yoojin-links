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
결과는 `results/<시간>/`에 `equity.csv`, `trades.csv`, `metrics.json`으로 저장돼.

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

평일 미국 장 시간에 15분마다 한 번씩 tick을 돌려. 봇 상태(오늘 거래 수, 마지막으로 평가한 봉)는 Actions cache로 다음 실행에 넘어가고, 로그는 artifact로 14일 동안 남아. 끄려면 `TRADING_BOT_ENABLED`를 지우거나 `false`로 바꿔.

### Docker
```bash
cp .env.example .env    # 키 채우기
docker compose up -d    # 백그라운드 실행, 재부팅돼도 자동 재시작
docker compose logs -f  # 로그 보기
```
config를 바꾸려면 `docker-compose.yml`의 `command`를 고쳐. 상태와 로그는 `./state`, `./logs`에 남아. 컨테이너가 uid 1000으로 돌기 때문에 권한 에러가 나면 `sudo chown -R 1000 state logs`를 실행해.

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
| `flatten_on_daily_loss` | `true`면 한도에 걸릴 때 전량 매도까지 해 |
| `max_trades_per_day` | 하루 신규 진입 횟수 상한. 매도는 제한 없어 |
| `min_order_notional` | 최소 주문 금액 (Upbit 5000, Alpaca 1) |
| `cash_buffer_pct` | 수수료·슬리피지에 대비해서 남겨둘 현금 % |

---

## 7. 안전장치 & 비상 정지

```bash
python -m bot -c configs/stocks.yaml kill --reason "휴가"   # 즉시 신규 주문 중단 (kill switch)
python -m bot -c configs/stocks.yaml resume                  # 다시 허용
python -m bot -c configs/stocks.yaml flatten --yes           # 모든 포지션 시장가 청산
```

- **Paper가 기본이야.** live는 config `mode: live`와 env `LIVE_TRADING_CONFIRM`이 둘 다 있어야 켜져.
- **Margin을 안 써.** Alpaca에서는 `non_marginable_buying_power`(실제 현금)만 써.
- **Short를 안 해.** 매도 수량은 보유 수량을 넘지 않아. 수량은 항상 내림(round down)해.
- **완성된 봉으로만 판단해.** 형성 중인 봉은 버려. 같은 봉에서는 한 번만 판단하고, 미체결 주문이 있으면 그 종목은 건너뛰어.
- **프로세스가 겹치지 않아.** instance lock이 있어서 봇 두 개가 같은 계좌로 동시에 매매하지 못해.
- **에러가 나도 안 죽어.** 에러는 기록하고 backoff 후에 재시도해. 연속으로 실패하면 알림을 보내.
- **기록이 남아.** 모든 주문은 `logs/<이름>/trades.csv`, 전체 로그는 `logs/<이름>/bot.log`에 남아.

### Live 켜기 전 체크리스트
- [ ] paper로 최소 2–4주 돌렸고, `trades.csv`를 보니 의도한 대로 매매했다
- [ ] 백테스트에서 수수료·슬리피지를 넣고도 buy & hold와 비교해서 납득이 된다
- [ ] 알림(Discord/Slack/Telegram)이 실제로 온다
- [ ] 잃어도 괜찮은 금액만 계좌에 넣었다
- [ ] 거래소 키에 출금 권한이 없다
- [ ] config에 `mode: live`, `.env`(또는 GitHub secret)에 `LIVE_TRADING_CONFIRM=I_ACCEPT_THE_RISK`를 넣었다. Alpaca는 live 키가 paper 키와 **다르니까** 키도 바꿔야 해

---

## 8. 알림 (선택)

`.env`에 넣기만 하면 켜져:
- **Discord/Slack**: 채널 설정에서 Incoming Webhook URL을 만들어서 `NOTIFY_WEBHOOK_URL`에 넣어
- **Telegram**: @BotFather에서 받은 토큰은 `TELEGRAM_BOT_TOKEN`, 내 chat id는 `TELEGRAM_CHAT_ID`에 넣어

주문이 나가거나 에러가 나거나 일일 손실 한도에 걸리면 메시지가 와. 켜고 끄는 건 config의 `notify.on_trade`, `notify.on_error`로 해.

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

---

## 10. FAQ

- **`market_closed`만 떠요.** 미국 장 시간(뉴욕 9:30–16:00, 평일)이 아니라서 그래. 정상이야.
- **`warming up`이 떠요.** 지표를 계산할 봉이 아직 부족해서 그래. 예를 들어 `rsi_reversion`은 201봉이 필요해.
- **실제 돈 안 나가는 거 맞아요?** `status`를 치면 맨 위에 모드(PAPER/LIVE)가 나와. Alpaca paper 키는 원래 실계좌에 접근할 수 없어.
- **한국 주식도 돼요?** 지금은 안 돼. 한국투자증권(KIS) Open API 같은 걸 `bot/brokers/`에 adapter로 추가하면 되고, `Broker` 인터페이스만 구현하면 나머지는 그대로 동작해.

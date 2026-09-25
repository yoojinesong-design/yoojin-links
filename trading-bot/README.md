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
| **GitHub Actions** (`once`를 15분마다) | 무료 (private repo도 월 ~700분이라 무료 한도 안) | 주식 일봉 전략. 서버 관리가 싫을 때 (실거래는 private repo에서만, 아래 주의 참고) |
| **Docker** (`docker compose up -d`) | VPS 월 $4–6 (Oracle Cloud free tier도 가능) | 코인 24/7, 분·시간봉 전략 |
| **systemd** (`deploy/trading-bot.service`) | VPS | Docker 없이 리눅스 서버에서 |
| 내 컴퓨터에서 `run` | 0 | 테스트용. 컴퓨터가 꺼지면 봇도 멈춰 |

### GitHub Actions 설정
`.github/workflows/trading-bot.yml`이 이미 들어 있어. **기본은 꺼져 있어.**

1. 이 브랜치를 `main`에 merge해. GitHub schedule은 default branch에서만 돌아.
2. Repo **Settings → Secrets and variables → Actions**로 가서:
   - **Secrets**에 `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`를 넣어. 알림을 받고 싶으면 `NOTIFY_WEBHOOK_URL`이나 `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`도 넣어.
   - **Variables**에 `TRADING_BOT_ENABLED` = `true`를 넣어. 이게 on 스위치야. 다른 config를 쓰고 싶으면 `TRADING_BOT_CONFIG` = `configs/내설정.yaml`도 추가해.
3. **Actions** 탭 → `trading-bot` → **Run workflow**에서 **`fresh_state`를 체크하고** 한 번 수동 실행해서 로그를 확인해. 처음엔 저장된 봇 상태가 없어서 이걸 체크해야 빈 상태로 시작해. 그다음부터는 체크하지 마. `fresh_state`는 저장된 상태가 있어도 버리고 빈 상태로 시작해서, 봇이 산 기록도 같이 사라져.

평일 미국 장 시간에 15분마다 한 번씩 tick을 돌려 (default branch에서만. 다른 브랜치에서 수동 실행하면 아무것도 안 해). 봇 상태(봇이 산 수량, 오늘 거래 수, 마지막으로 평가한 봉)는 Actions cache로 다음 실행에 넘어가고, 로그는 artifact로 14일 동안 남아. cache는 `trading-bot/state`만 저장하니까 내 config의 `state_dir`도 그 안(예: `state_dir: ../state/my`)이어야 해. 아니면 `once`가 GitHub Actions에서 매매를 거부하고 이유를 알려줘. 끄려면 `TRADING_BOT_ENABLED`를 지우거나 `false`로 바꿔.

> ⚠️ **Actions로 실거래하기 전에 꼭 알아둬** (자세한 건 [docs/SAFETY.md](docs/SAFETY.md)).
> - **public repo면 로그가 전부 공개돼.** 실거래는 **private repo**에서만 돌려.
> - **public repo는 60일 동안 커밋이 없으면 schedule이 자동으로 꺼져.** 그러면 손절 체크도 멈춰.
> - **봇 상태는 Actions cache에만 있고, 7일 넘게 안 돌면 지워져.** 그러면 다음 실행이 일부러 실패해서 알려줘 (빈 상태로 돌면 봇이 산 종목의 손절이 꺼지니까). 봇이 산 종목을 직접 정리하고 `fresh_state`로 다시 시작해. 오래 멈출 거면 포지션부터 정리해.
> - **상태 저장이 실패한 실행이 있으면** 다음 실행부터 봇이 손절까지 포함해서 주문을 멈추고 에러를 알려줘. 앱에서 포지션을 정리하고 `fresh_state`로 다시 시작해.

### Docker
```bash
cp .env.example .env    # 키 채우기
docker compose up -d    # 백그라운드 실행, 재부팅돼도 자동 재시작
docker compose logs -f  # 로그 보기
```
어떤 config를 쓸지는 `docker-compose.yml`의 `command`에서 정해. `configs/` 폴더는 컨테이너에 마운트돼 있어서, 그 안의 config 파일을 고쳤으면 `docker compose restart`만 하면 돼. 하지만 **`command`나 `.env`를 바꿨으면 꼭 `docker compose up -d`를 해.** `restart`는 예전 command와 환경변수 그대로 다시 켜져서, 예를 들어 `.env`에서 `LIVE_TRADING_CONFIRM`을 지우고 `restart`만 하면 계속 실거래해. 코드나 `requirements.txt`를 바꿨을 때는 `docker compose up -d --build`로 다시 빌드해. 상태와 로그는 `./state`, `./logs`에 남아. 컨테이너가 uid 1000으로 돌기 때문에 권한 에러가 나면 `sudo chown -R 1000 state logs`를 실행해.

7장의 `kill`·`resume`·`status`·`flatten --yes`는 **컨테이너 안에서** 실행해. 서버에 Python 패키지를 따로 안 깔았으면 그냥 `python -m bot ...`은 에러가 나:
```bash
docker compose exec trading-bot python -m bot -c configs/stocks.yaml kill   # config는 command에 쓴 것과 같게
docker compose stop     # 봇을 완전히 멈추기 (docker compose start로 다시 켜)
```

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
python -m bot -c configs/stocks.yaml flatten --yes           # 모든 포지션 시장가 청산 (봇이 안 산 것까지!)
```

`kill` 중에는 **손절·익절 매도도 안 나가.** 휴가처럼 오래 비울 거면 포지션부터 정리해. `flatten --yes`는 **봇이 안 산 것까지** 계좌를 정리해. config가 깨져 있어도 `kill`/`resume`은 동작해. Docker면 이 명령들을 컨테이너 안에서 실행해 (4장). **GitHub Actions 봇은 `kill`로 안 멈춰.** repo Variables의 `TRADING_BOT_ENABLED`를 `false`로 바꿔.

**핵심만 요약하면:**
- **Paper가 기본이야.** live는 config `mode: live`와 env `LIVE_TRADING_CONFIRM`이 둘 다 있어야 켜져.
- **Margin·short를 안 해.** 실제 현금만 쓰고, 보유 수량보다 많이 팔지 않고, 수량은 항상 내림해.
- **완성된 봉으로만, 한 봉에 한 번만 판단해.** 봇 주문이 미체결이면 그 종목은 건너뛰어서 중복 주문이 안 나가.
- **손절·익절은 매 tick 제일 먼저 체크해.** 캔들 데이터를 못 받거나 수동 주문이 걸려 있어도 돌아.
- **봇은 자기가 산 것만 관리하고 팔아.** 원래 계좌에 있던 주식·코인은 `symbols`에 있어도 안 건드려 (`adopt_existing_positions: true`로 바꿀 수 있어). 이 기록이 상태 파일(`state/`)에 있으니까 **상태 폴더는 지우지 마.**
- **일일 손실 한도는 매매 손익만 봐.** 장중 입출금은 손실로 안 쳐.
- **한 계좌에는 봇 하나만** 돌려.
- **에러가 나도 안 죽고** 재시도하고 알림을 보내. 모든 주문은 `logs/<이름>/trades.csv`에 남아.

주문 응답이 끊겼을 때, 주식 분할, 상태 파일 문제, paper↔live 전환 같은 경우에 봇이 어떻게 하는지는 **[docs/SAFETY.md](docs/SAFETY.md)**에 자세히 있어.

### Live 켜기 전 체크리스트
- [ ] paper로 최소 2–4주 돌렸고, `trades.csv`를 보니 의도한 대로 매매했다
- [ ] 백테스트에서 수수료·슬리피지를 넣고도 buy & hold와 비교해서 납득이 된다
- [ ] 알림(Discord/Slack/Telegram)이 실제로 온다
- [ ] 잃어도 괜찮은 금액만 계좌에 넣었다
- [ ] 계좌에 이미 들고 있는 주식·코인이 있다면, 봇은 그걸 안 건드린다는 걸 알고 있다 (같은 종목은 새로 사지도 않아). 봇이 관리하게 하려면 `adopt_existing_positions: true`를 켜야 하고, 그러면 손절·전략 신호로 **팔릴 수 있어**
- [ ] 거래소 키에 출금 권한이 없다
- [ ] GitHub Actions로 돌린다면 private repo다 (public repo는 로그가 공개되고 60일 뒤 schedule이 꺼져)
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
CSV의 봉 간격은 config의 `timeframe`과 같아야 해 (다르면 봇이 거부해). 샤프·변동성 연율화는 데이터에 주말 봉이 있으면 1년 365일 × 24시간, 없으면 252일 × 정규장(6.5시간)에 들어가는 봉 수로 계산해 (`1h`는 하루 7개, `4h`는 2개).

백테스트는 일일 손실 한도를 봉의 시가뿐 아니라 **저가**로도 체크해. 실거래 봇은 tick마다 체크하니까, 장중에 한도를 뚫고 종가에 회복한 날도 멈추고, `flatten_on_daily_loss`면 한도를 뚫는 가격에서 팔아.

---

## 10. FAQ

- **`market_closed`만 떠요.** 미국 장 시간(뉴욕 9:30–16:00, 평일)이 아니라서 그래. 정상이야.
- **`warming up`이 떠요.** 지표를 계산할 봉이 아직 부족해서 그래. 예를 들어 `rsi_reversion`은 201봉이 필요해. 거래소가 과거 봉을 그보다 적게 주면(예: 최대 200개만 주는 거래소, 상장한 지 얼마 안 된 종목) 봇이 알림을 한 번 보내. 그럴 땐 전략 기간을 줄이거나 더 긴 timeframe을 써.
- **실제 돈 안 나가는 거 맞아요?** `status`를 치면 맨 위에 모드(PAPER/LIVE)가 나와. Alpaca paper 키는 원래 실계좌에 접근할 수 없어.
- **한국 주식도 돼요?** 지금은 안 돼. 한국투자증권(KIS) Open API 같은 걸 `bot/brokers/`에 adapter로 추가하면 되고, `Broker` 인터페이스만 구현하면 나머지는 그대로 동작해.

---

## 11. 알려진 한계 (Known limitations)

아직 코드로 막지 못한 경우들이야. 해당되면 적힌 대로 피해 가.

- **Alpaca에서 장 마감 후 입출금은 매매 손익으로 계산돼.** 기준값이 전일 종가 자산이라, 장 마감 뒤부터 다음 날 장 열린 첫 tick 전까지 들어오거나 나간 돈은 입출금으로 못 잡아. 한도보다 큰 출금은 다음 날 개장하자마자 일일 손실 한도에 걸리고 (`flatten_on_daily_loss`면 봇 포지션도 팔아), 입금은 그만큼 그날 손실 한도를 넓혀. 입출금은 장중에 하는 게 좋아.
- **내 주문이 봇의 계좌 조회 순간에 체결되면 입출금으로 잘못 계산될 수 있어.** 봇이 계좌와 포지션을 읽는 1초 안쪽에 내 매매가 체결되면 생기는 일이라 드물어. 대부분은 그날 신규 매수만 잘못 멈추는 쪽이고 (`flatten_on_daily_loss`면 봇 포지션을 팔 수도 있어) 다음 날 풀려. 봇이 도는 동안 같은 계좌에서 한도만큼 큰 매매를 직접 하는 건 피해.
- **코인 거래소(ccxt)에서 `symbols`에서 뺀 코인은 알림도 `status` 표시도 없고, 봇이 산 기록도 지워져.** 거래소 잔고를 `symbols`에 있는 코인만 읽어서 그래. 다시 넣어도 봇은 그 코인을 "안 산 것"으로 봐서 손절을 안 해. 코인을 `symbols`에서 빼기 전에 봇이 산 수량을 먼저 팔아.
- **GitHub Actions는 공개·중단 위험이 있어.** public repo는 로그가 누구에게나 보이고, 60일 동안 커밋이 없으면 schedule이 꺼지고, 7일 넘게 안 돌면 봇 상태가 지워져. 실거래는 private repo나 VPS/Docker에서 돌려 (4장 참고).
- **백테스트는 한 봉 안에서 여러 종목의 저가가 동시에, 그리고 익절 가격(고가)보다 먼저 온 것으로 보고 일일 손실 한도를 체크해.** 실제로는 순서가 달라서 실거래 봇은 안 멈췄을 수도 있어. 백테스트에서 한도·청산은 실제보다 조금 보수적(불리하게)으로 나와.
- **같은 브로커·같은 모드의 다른 계좌로 API 키만 바꾸면 봇이 계좌가 바뀐 걸 몰라.** 봇은 계좌를 mode·브로커·거래소·통화로만 구별해. 그래서 Alpaca paper 계좌 두 개나 거래소 본계정↔서브계정을 같은 `state_dir`로 번갈아 쓰면, 한 계좌의 "봇이 산 기록"과 그날의 손실 기준값이 다른 계좌에 그대로 적용돼 (그 계좌의 내 주식을 팔거나, 일일 손실 한도가 꺼지거나 바로 걸릴 수 있어). 원래 계좌에 남은 봇 포지션도 손절이 안 돌아. Alpaca에서는 새 계좌에 이 상태 파일이 모르는 봇 주문이 있으면 매매를 멈추지만, 없으면 못 잡아. 다른 계좌를 쓰려면 config를 복사해서 `state_dir`을 새로 정해 (GitHub Actions면 원래 계좌의 봇 포지션을 먼저 정리하고 `fresh_state`로 실행).
- **상태 파일이 오래됐는지는 Alpaca에서만, 그리고 봇이 주문을 한 번이라도 기록한 뒤부터 확인해.** 코인 거래소는 주문 내역을 그렇게 조회하지 않아서 못 잡아. 코인 봇은 상태가 로컬 디스크에 남는 VPS/Docker에서 돌려.

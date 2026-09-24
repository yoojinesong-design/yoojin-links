"""Tests for bot.risk: config validation, position sizing, exits, daily loss."""
from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest

from bot.models import Account, Action, Position, Signal
from bot.risk import RiskConfig, RiskManager

BUY = Signal(Action.BUY, "test entry")

# A config where no cap binds unless a test lowers it on purpose.
LOOSE = RiskConfig(
    risk_per_trade_pct=100.0,
    max_position_pct=100.0,
    max_total_exposure_pct=100.0,
    max_open_positions=10,
    max_daily_loss_pct=None,
    stop_loss_pct=None,
    take_profit_pct=None,
    min_order_notional=0.0,
    cash_buffer_pct=0.0,
)


def rm(**overrides) -> RiskManager:
    return RiskManager(replace(LOOSE, **overrides))


def account(equity: float = 10_000.0, cash: float | None = None, buying_power: float | None = None) -> Account:
    cash = equity if cash is None else cash
    return Account(equity=equity, cash=cash, buying_power=cash if buying_power is None else buying_power)


def pos(symbol: str = "AAA", qty: float = 10.0, entry: float = 100.0, price: float | None = None) -> Position:
    return Position(symbol=symbol, qty=qty, avg_entry_price=entry, market_price=entry if price is None else price)


# --------------------------------------------------------------------------- validate


def test_default_config_is_valid():
    RiskConfig().validate()
    RiskManager(RiskConfig())


@pytest.mark.parametrize("name", ["risk_per_trade_pct", "max_position_pct", "max_total_exposure_pct"])
@pytest.mark.parametrize("value", [0, -1.0, 100.01, 250, math.nan, math.inf])
def test_required_pct_fields_must_be_in_0_100(name, value):
    with pytest.raises(ValueError, match=name):
        replace(RiskConfig(), **{name: value}).validate()


@pytest.mark.parametrize("name", ["risk_per_trade_pct", "max_position_pct", "max_total_exposure_pct"])
@pytest.mark.parametrize("value", [0.01, 50, 100])
def test_required_pct_fields_accept_values_up_to_100(name, value):
    replace(RiskConfig(), **{name: value}).validate()


@pytest.mark.parametrize("name", ["max_daily_loss_pct", "stop_loss_pct", "take_profit_pct"])
@pytest.mark.parametrize("value", [None, 0, 0.0, 0.5, 100])
def test_optional_pct_fields_accept_none_zero_or_valid(name, value):
    replace(RiskConfig(), **{name: value}).validate()


@pytest.mark.parametrize("name", ["max_daily_loss_pct", "stop_loss_pct", "take_profit_pct"])
@pytest.mark.parametrize("value", [-0.1, -5, math.nan, math.inf])
def test_optional_pct_fields_reject_out_of_range(name, value):
    with pytest.raises(ValueError, match=name):
        replace(RiskConfig(), **{name: value}).validate()


@pytest.mark.parametrize("name", ["max_daily_loss_pct", "stop_loss_pct"])
@pytest.mark.parametrize("value", [100.5, 150])
def test_loss_limits_cannot_exceed_100_pct(name, value):
    with pytest.raises(ValueError, match=name):
        replace(RiskConfig(), **{name: value}).validate()


@pytest.mark.parametrize("value", [100.5, 150, 1000])
def test_take_profit_may_exceed_100_pct(value):
    """A +150% target (sell at 2.5x the entry) is a legitimate setting, e.g. for crypto."""
    manager = RiskManager(replace(RiskConfig(), take_profit_pct=value))
    p = pos(entry=100.0)
    assert manager.take_profit_price(p) == pytest.approx(100.0 * (1 + value / 100))
    assert manager.exit_reason(p, 100.0 * (1 + value / 100)) == "take_profit"


@pytest.mark.parametrize("value", [1000.5, 1e6])
def test_take_profit_above_the_sanity_cap_is_rejected(value):
    with pytest.raises(ValueError, match="take_profit_pct"):
        replace(RiskConfig(), take_profit_pct=value).validate()


@pytest.mark.parametrize("name", ["max_open_positions", "max_trades_per_day"])
@pytest.mark.parametrize("value", [0, -3, 1.5, True, "5", None])
def test_count_fields_must_be_positive_integers(name, value):
    with pytest.raises(ValueError, match=name):
        replace(RiskConfig(), **{name: value}).validate()


@pytest.mark.parametrize("name", ["max_open_positions", "max_trades_per_day"])
def test_count_fields_accept_one_and_numpy_ints(name):
    replace(RiskConfig(), **{name: 1}).validate()
    replace(RiskConfig(), **{name: np.int64(3)}).validate()


@pytest.mark.parametrize("value", [-0.01, -1, math.nan, math.inf, "1"])
def test_min_order_notional_must_be_non_negative_number(value):
    with pytest.raises(ValueError, match="min_order_notional"):
        replace(RiskConfig(), min_order_notional=value).validate()


@pytest.mark.parametrize("value", [0, 0.0, 25.5])
def test_min_order_notional_accepts_zero_and_positive(value):
    replace(RiskConfig(), min_order_notional=value).validate()


@pytest.mark.parametrize("value", [-0.1, 50.01, 100, math.nan])
def test_cash_buffer_must_be_between_0_and_50(value):
    with pytest.raises(ValueError, match="cash_buffer_pct"):
        replace(RiskConfig(), cash_buffer_pct=value).validate()


@pytest.mark.parametrize("value", [0, 0.5, 50])
def test_cash_buffer_accepts_boundaries(value):
    replace(RiskConfig(), cash_buffer_pct=value).validate()


@pytest.mark.parametrize("value", ["yes", 1, None])
def test_flatten_flag_must_be_bool(value):
    with pytest.raises(ValueError, match="flatten_on_daily_loss"):
        replace(RiskConfig(), flatten_on_daily_loss=value).validate()


@pytest.mark.parametrize("name", ["risk_per_trade_pct", "stop_loss_pct"])
@pytest.mark.parametrize("value", ["5", True])
def test_pct_fields_reject_non_numbers(name, value):
    with pytest.raises(ValueError, match=name):
        replace(RiskConfig(), **{name: value}).validate()


def test_validate_reports_every_problem_at_once():
    cfg = RiskConfig(max_position_pct=0, max_open_positions=0, cash_buffer_pct=99)
    with pytest.raises(ValueError) as exc:
        cfg.validate()
    msg = str(exc.value)
    for name in ("max_position_pct", "max_open_positions", "cash_buffer_pct"):
        assert name in msg


def test_risk_manager_refuses_invalid_config():
    with pytest.raises(ValueError, match="max_open_positions"):
        RiskManager(RiskConfig(max_open_positions=0))


# --------------------------------------------------------------------------- sizing caps


def test_risk_based_sizing_binds_when_stop_is_set():
    # 1% risk with a 5% stop -> 20% of equity notional.
    qty, why = rm(risk_per_trade_pct=1.0, stop_loss_pct=5.0).entry_qty("AAA", 50.0, BUY, account(10_000), {})
    assert qty == pytest.approx(2_000 / 50.0)
    assert "risk_per_trade" in why


def test_risk_based_sizing_scales_inversely_with_stop_distance():
    tight = rm(risk_per_trade_pct=1.0, stop_loss_pct=2.0).entry_qty("AAA", 10.0, BUY, account(10_000), {})[0]
    wide = rm(risk_per_trade_pct=1.0, stop_loss_pct=10.0).entry_qty("AAA", 10.0, BUY, account(10_000), {})[0]
    assert tight * 10.0 == pytest.approx(5_000)
    assert wide * 10.0 == pytest.approx(1_000)


@pytest.mark.parametrize("stop", [None, 0])
def test_risk_sizing_is_unbounded_without_stop(stop):
    qty, why = rm(risk_per_trade_pct=0.1, stop_loss_pct=stop, max_position_pct=30.0).entry_qty(
        "AAA", 100.0, BUY, account(10_000), {})
    assert qty == pytest.approx(30.0)  # max_position binds, not the tiny risk %
    assert "max_position" in why


def test_max_position_cap_binds():
    qty, why = rm(max_position_pct=20.0).entry_qty("AAA", 100.0, BUY, account(10_000), {})
    assert qty == pytest.approx(20.0)
    assert "max_position" in why


def test_exposure_room_accounts_for_market_value_of_open_positions():
    # 80% of 10k = 8k allowed; existing positions worth 3k + 4k at MARKET prices.
    held = {"X": pos("X", qty=10, entry=100, price=300), "Y": pos("Y", qty=40, entry=50, price=100)}
    qty, why = rm(max_total_exposure_pct=80.0).entry_qty("AAA", 10.0, BUY, account(10_000), held)
    assert qty * 10.0 == pytest.approx(1_000)
    assert "exposure_cap" in why


@pytest.mark.parametrize("held_value", [8_000, 9_500])
def test_exposure_cap_reached_rejects(held_value):
    held = {"X": pos("X", qty=1, entry=held_value, price=held_value)}
    qty, why = rm(max_total_exposure_pct=80.0).entry_qty("AAA", 10.0, BUY, account(10_000), held)
    assert qty == 0.0
    assert "exposure" in why


def test_buying_power_cap_keeps_cash_buffer():
    acct = account(equity=10_000, cash=1_000)
    qty, why = rm(cash_buffer_pct=1.0).entry_qty("AAA", 10.0, BUY, acct, {})
    assert qty * 10.0 == pytest.approx(990.0)
    assert "buying_power" in why


def test_buying_power_uses_the_lower_of_cash_and_buying_power_no_margin():
    margin_acct = account(equity=10_000, cash=2_000, buying_power=40_000)
    qty, _ = rm().entry_qty("AAA", 10.0, BUY, margin_acct, {})
    assert qty * 10.0 == pytest.approx(2_000)
    reserved = account(equity=10_000, cash=5_000, buying_power=500)  # e.g. part held for open orders
    qty, _ = rm().entry_qty("AAA", 10.0, BUY, reserved, {})
    assert qty * 10.0 == pytest.approx(500)


@pytest.mark.parametrize("cash, bp", [(0.0, 0.0), (-500.0, -500.0), (1_000.0, 0.0), (-10.0, 5_000.0)])
def test_no_or_negative_buying_power_rejects(cash, bp):
    qty, why = rm().entry_qty("AAA", 10.0, BUY, account(10_000, cash=cash, buying_power=bp), {})
    assert qty == 0.0
    assert "buying power" in why


def test_smallest_cap_wins_and_notional_never_exceeds_any_cap():
    cfg = replace(RiskConfig(), risk_per_trade_pct=2.0, stop_loss_pct=4.0, max_position_pct=25.0,
                  max_total_exposure_pct=60.0, cash_buffer_pct=2.0, min_order_notional=0.0)
    manager = RiskManager(cfg)
    for equity in (500.0, 10_000.0, 1_234_567.0):
        for cash_frac in (0.05, 0.3, 1.0):
            for held_frac in (0.0, 0.2, 0.45):
                held = {"H": pos("H", qty=1.0, entry=equity * held_frac, price=equity * held_frac)} if held_frac else {}
                cash = equity * cash_frac
                price = 37.13
                qty, _ = manager.entry_qty("AAA", price, BUY, account(equity, cash=cash), held)
                notional = qty * price
                assert qty >= 0
                caps = [equity * 2.0 / 4.0, equity * 0.25, equity * 0.60 - equity * held_frac, cash * 0.98]
                assert notional <= min(caps) * (1 + 1e-12)
                if min(caps) > 0:
                    assert notional == pytest.approx(min(caps))


# --------------------------------------------------------------------------- minimum notional


def test_below_config_minimum_rejects():
    qty, why = rm(min_order_notional=50.0).entry_qty("AAA", 10.0, BUY, account(10_000, cash=40.0), {})
    assert qty == 0.0
    assert "minimum" in why


def test_broker_minimum_wins_when_larger():
    acct = account(10_000, cash=40.0)
    assert rm(min_order_notional=1.0).entry_qty("AAA", 10.0, BUY, acct, {}, broker_min_notional=5.0)[0] > 0
    qty, why = rm(min_order_notional=1.0).entry_qty("AAA", 10.0, BUY, acct, {}, broker_min_notional=5_000.0)
    assert qty == 0.0
    assert "5000" in why


def test_config_minimum_wins_when_larger_than_broker_minimum():
    qty, _ = rm(min_order_notional=100.0).entry_qty("AAA", 10.0, BUY, account(10_000, cash=60.0), {},
                                                   broker_min_notional=10.0)
    assert qty == 0.0


def test_notional_exactly_at_minimum_is_allowed():
    qty, _ = rm(min_order_notional=100.0).entry_qty("AAA", 10.0, BUY, account(10_000, cash=100.0), {})
    assert qty * 10.0 == pytest.approx(100.0)


def test_zero_minimum_still_requires_positive_notional():
    held = {"X": pos("X", qty=1, entry=10_000)}
    qty, _ = rm(min_order_notional=0.0).entry_qty("AAA", 10.0, BUY, account(10_000), held)
    assert qty == 0.0


@pytest.mark.parametrize("broker_min", [None, 0.0])
def test_missing_broker_minimum_falls_back_to_config(broker_min):
    qty, _ = rm(min_order_notional=1.0).entry_qty("AAA", 10.0, BUY, account(100), {}, broker_min_notional=broker_min)
    assert qty * 10.0 == pytest.approx(100.0)


# --------------------------------------------------------------------------- gates


def test_max_open_positions_reached_rejects():
    held = {s: pos(s, qty=1, entry=1) for s in ("A", "B", "C")}
    qty, why = rm(max_open_positions=3).entry_qty("NEW", 10.0, BUY, account(10_000), held)
    assert qty == 0.0
    assert "max open positions" in why


def test_one_slot_left_allows_entry():
    held = {s: pos(s, qty=1, entry=1) for s in ("A", "B")}
    qty, _ = rm(max_open_positions=3).entry_qty("NEW", 10.0, BUY, account(10_000), held)
    assert qty > 0


def test_zero_qty_positions_do_not_count_toward_limits():
    held = {"A": pos("A", qty=1, entry=1), "B": pos("B", qty=0.0, entry=1_000_000), "NEW": pos("NEW", qty=0.0)}
    qty, _ = rm(max_open_positions=2).entry_qty("NEW", 10.0, BUY, account(10_000), held)
    assert qty > 0


def test_existing_position_in_symbol_rejects():
    qty, why = rm().entry_qty("AAA", 10.0, BUY, account(10_000), {"AAA": pos("AAA", qty=0.5)})
    assert qty == 0.0
    assert "already holding" in why


@pytest.mark.parametrize("action", [Action.SELL, Action.HOLD])
def test_non_buy_signal_never_sizes_an_entry(action):
    qty, _ = rm().entry_qty("AAA", 10.0, Signal(action), account(10_000), {})
    assert qty == 0.0


@pytest.mark.parametrize("price", [0.0, -5.0, math.nan, math.inf])
def test_invalid_price_rejects(price):
    qty, why = rm().entry_qty("AAA", price, BUY, account(10_000), {})
    assert qty == 0.0
    assert "price" in why


@pytest.mark.parametrize("equity", [0.0, -100.0, math.nan])
def test_non_positive_equity_rejects(equity):
    qty, why = rm().entry_qty("AAA", 10.0, BUY, Account(equity=equity, cash=1_000, buying_power=1_000), {})
    assert qty == 0.0
    assert "equity" in why


@pytest.mark.parametrize("field", ["cash", "buying_power"])
def test_nan_account_values_reject(field):
    acct = account(10_000)
    setattr(acct, field, math.nan)
    assert rm().entry_qty("AAA", 10.0, BUY, acct, {})[0] == 0.0


def test_nan_position_price_rejects_rather_than_ignoring_exposure():
    held = {"X": pos("X", qty=1, entry=100, price=math.nan)}
    assert rm().entry_qty("AAA", 10.0, BUY, account(10_000), held)[0] == 0.0


def test_nan_broker_minimum_rejects():
    assert rm().entry_qty("AAA", 10.0, BUY, account(10_000), {}, broker_min_notional=math.nan)[0] == 0.0


def test_numpy_scalars_are_accepted():
    acct = Account(equity=np.float64(10_000), cash=np.float64(10_000), buying_power=np.float64(10_000))
    qty, _ = rm(max_position_pct=10.0).entry_qty("AAA", np.float64(20.0), BUY, acct, {})
    assert qty == pytest.approx(50.0)


def test_entry_qty_does_not_mutate_inputs():
    acct = account(10_000)
    held = {"X": pos("X")}
    before = (replace(acct), {k: replace(v) for k, v in held.items()})
    rm().entry_qty("AAA", 10.0, BUY, acct, held)
    assert (acct, held) == before


# --------------------------------------------------------------------------- exits


def test_stop_and_take_profit_prices():
    manager = rm(stop_loss_pct=5.0, take_profit_pct=10.0)
    p = pos(entry=200.0)
    assert manager.stop_price(p) == pytest.approx(190.0)
    assert manager.take_profit_price(p) == pytest.approx(220.0)


@pytest.mark.parametrize("value", [None, 0])
def test_disabled_levels_return_none(value):
    manager = rm(stop_loss_pct=value, take_profit_pct=value)
    p = pos(entry=100.0)
    assert manager.stop_price(p) is None
    assert manager.take_profit_price(p) is None
    assert manager.exit_reason(p, 0.01) is None
    assert manager.exit_reason(p, 1_000_000.0) is None


@pytest.mark.parametrize("entry", [0.0, -1.0, math.nan])
def test_unknown_entry_price_gives_no_levels(entry):
    manager = rm(stop_loss_pct=5.0, take_profit_pct=10.0)
    p = pos(entry=entry, price=50.0)
    assert manager.stop_price(p) is None
    assert manager.take_profit_price(p) is None
    assert manager.exit_reason(p, 50.0) is None


@pytest.mark.parametrize("entry, stop_pct", [(100.0, 5.0), (0.1, 3.0), (43_210.55, 7.5), (1.23456789, 1.0)])
def test_stop_loss_triggers_exactly_at_the_level(entry, stop_pct):
    manager = rm(stop_loss_pct=stop_pct)
    level = entry * (1 - stop_pct / 100)
    p = pos(entry=entry)
    assert manager.exit_reason(p, level) == "stop_loss"
    assert manager.exit_reason(p, level * 0.999) == "stop_loss"
    assert manager.exit_reason(p, level * 1.0001) is None


def test_stop_loss_with_literal_boundary_price():
    # 0.1 * 0.97 is not exactly 0.097 in binary floating point.
    assert rm(stop_loss_pct=3.0).exit_reason(pos(entry=0.1), 0.097) == "stop_loss"
    assert rm(stop_loss_pct=5.0).exit_reason(pos(entry=100.0), 95.0) == "stop_loss"
    assert rm(stop_loss_pct=5.0).exit_reason(pos(entry=100.0), 95.01) is None


@pytest.mark.parametrize("entry, tp_pct", [(100.0, 10.0), (0.1, 3.0), (43_210.55, 25.0)])
def test_take_profit_triggers_exactly_at_the_level(entry, tp_pct):
    manager = rm(take_profit_pct=tp_pct, stop_loss_pct=5.0)
    level = entry * (1 + tp_pct / 100)
    p = pos(entry=entry)
    assert manager.exit_reason(p, level) == "take_profit"
    assert manager.exit_reason(p, level * 1.01) == "take_profit"
    assert manager.exit_reason(p, level * 0.9999) is None


def test_no_exit_between_levels():
    manager = rm(stop_loss_pct=5.0, take_profit_pct=10.0)
    p = pos(entry=100.0)
    for price in (95.01, 99.0, 100.0, 105.0, 109.99):
        assert manager.exit_reason(p, price) is None


def test_stop_is_checked_before_take_profit():
    manager = rm(stop_loss_pct=5.0, take_profit_pct=10.0)
    assert manager.exit_reason(pos(entry=100.0), 10.0) == "stop_loss"


def test_exit_uses_entry_price_not_positions_market_price():
    manager = rm(stop_loss_pct=5.0)
    stale = pos(entry=100.0, price=50.0)  # market_price on the object is stale
    assert manager.exit_reason(stale, 99.0) is None
    assert manager.exit_reason(stale, 94.0) == "stop_loss"


@pytest.mark.parametrize("price", [0.0, -1.0, math.nan])
def test_invalid_price_never_triggers_an_exit(price):
    assert rm(stop_loss_pct=5.0, take_profit_pct=10.0).exit_reason(pos(entry=100.0), price) is None


def test_flat_position_has_no_exit():
    assert rm(stop_loss_pct=5.0).exit_reason(pos(qty=0.0, entry=100.0), 10.0) is None


# --------------------------------------------------------------------------- daily loss


@pytest.mark.parametrize(
    "equity, expected",
    [
        (97_000.0, True),       # exactly -3%
        (96_999.99, True),
        (50_000.0, True),
        (97_000.01, False),     # just inside the limit
        (99_000.0, False),
        (100_000.0, False),
        (120_000.0, False),     # gains never breach
    ],
)
def test_daily_loss_boundaries(equity, expected):
    assert rm(max_daily_loss_pct=3.0).daily_loss_breached(equity, 100_000.0) is expected


def test_daily_loss_exact_boundary_with_awkward_floats():
    manager = rm(max_daily_loss_pct=3.0)
    for start in (0.3, 123.45, 9_999.99, 1e7 / 3):
        assert manager.daily_loss_breached(start * 0.97, start)
        assert manager.daily_loss_breached(start * (1 - 0.03), start)
        assert not manager.daily_loss_breached(start * 0.9701, start)


@pytest.mark.parametrize("limit", [None, 0])
def test_daily_loss_disabled(limit):
    assert rm(max_daily_loss_pct=limit).daily_loss_breached(1.0, 100_000.0) is False


@pytest.mark.parametrize("start", [0.0, -100.0, None, math.nan])
def test_daily_loss_needs_a_positive_baseline(start):
    assert rm(max_daily_loss_pct=3.0).daily_loss_breached(50.0, start) is False


def test_daily_loss_total_wipeout_breaches():
    assert rm(max_daily_loss_pct=3.0).daily_loss_breached(0.0, 1_000.0) is True
    assert rm(max_daily_loss_pct=100.0).daily_loss_breached(0.0, 1_000.0) is True
    assert rm(max_daily_loss_pct=100.0).daily_loss_breached(1.0, 1_000.0) is False

"""Generates synthetic B2B gaming events for Aurora Games.

Design notes (see also data-foundation/README.md):
- One JSON Lines file per simulated day, emitted event-by-event in time order.
- Two scripted scenarios are embedded so downstream modules have something
  concrete to detect: a retention/revenue drop on one site (module 1, EWMA)
  and a multi-account arbitrage ring (module 1, rule-based detection).
- A `scenario_manifest.json` is written alongside the output with the ground
  truth (which players, which dates) so demo scripts can assert against it
  instead of eyeballing the result.
"""
import json
import random
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

from . import config


@dataclass
class Player:
    player_id: str
    home_site_id: str
    registration_day: int
    base_activity_prob: float
    churn_day: int
    device_pool: list
    ip_pool: list
    acquisition_channel: str
    is_ring_member: bool = False


def _weighted_choice(rng: random.Random, weights: dict) -> str:
    keys = list(weights.keys())
    return rng.choices(keys, weights=[weights[k] for k in keys], k=1)[0]


def _new_id(rng: random.Random, prefix: str, n: int = 10) -> str:
    return f"{prefix}_{uuid.UUID(int=rng.getrandbits(128)).hex[:n]}"


class EventSimulator:
    def __init__(self, seed: int = config.SEED):
        self.rng = random.Random(seed)
        self.players: list[Player] = []
        self.ring_shared_devices: list[str] = []
        self.ring_shared_ips: list[str] = []
        self._build_population()

    # -- population setup -------------------------------------------------

    def _build_population(self):
        rng = self.rng
        num_normal = config.NUM_PLAYERS - config.ARBITRAGE_RING_SIZE
        site_ids = list(config.CLIENT_SITES.keys())

        for i in range(num_normal):
            reg_day = int(
                min(
                    config.NUM_DAYS - 1,
                    max(0, rng.triangular(0, config.NUM_DAYS - 1, config.NUM_DAYS * 0.2)),
                )
            )
            lifespan = max(1, int(rng.expovariate(1 / 25)))
            device_pool = [_new_id(rng, "dev")]
            if rng.random() < 0.15:
                device_pool.append(_new_id(rng, "dev"))
            ip_pool = [_new_id(rng, "ip", 8) for _ in range(rng.randint(1, 3))]

            self.players.append(
                Player(
                    player_id=f"p_{i:06d}",
                    home_site_id=rng.choice(site_ids),
                    registration_day=reg_day,
                    base_activity_prob=rng.betavariate(2, 5),
                    churn_day=reg_day + lifespan,
                    device_pool=device_pool,
                    ip_pool=ip_pool,
                    acquisition_channel=rng.choice(config.ACQUISITION_CHANNELS),
                )
            )

        # Arbitrage ring: shared device/IP fingerprints are the fraud signal.
        self.ring_shared_devices = [_new_id(rng, "dev") for _ in range(2)]
        self.ring_shared_ips = [_new_id(rng, "ip", 8) for _ in range(2)]
        for i in range(config.ARBITRAGE_RING_SIZE):
            self.players.append(
                Player(
                    player_id=f"p_ring_{i:02d}",
                    home_site_id=config.ARBITRAGE_RING_SITE,
                    registration_day=config.ARBITRAGE_RING_REGISTRATION_DAY,
                    base_activity_prob=0.0,  # driven entirely by the scenario, not organic activity
                    churn_day=config.NUM_DAYS,
                    device_pool=self.ring_shared_devices,
                    ip_pool=self.ring_shared_ips,
                    acquisition_channel="affiliate",
                    is_ring_member=True,
                )
            )

    # -- helpers ------------------------------------------------------------

    def _envelope(self, event_type, ts, player, session_id, game_id, device_id, ip_hash, platform, payload):
        site = config.CLIENT_SITES[player.home_site_id]
        return {
            "event_id": str(uuid.UUID(int=self.rng.getrandbits(128))),
            "event_type": event_type,
            "event_ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "player_id": player.player_id,
            "session_id": session_id,
            "game_id": game_id,
            "client_site_id": player.home_site_id,
            "region": site["region"],
            "platform": platform,
            "device_id": device_id,
            "ip_hash": ip_hash,
            "payload": payload,
        }

    def _day_start_dt(self, day_offset: int) -> datetime:
        return datetime.combine(config.START_DATE + timedelta(days=day_offset), time(0, 0, 0))

    # -- event generation -----------------------------------------------------

    def _registration_event(self, player: Player, day_offset: int) -> dict:
        ts = self._day_start_dt(day_offset) + timedelta(seconds=self.rng.randint(0, 86399))
        return self._envelope(
            "player_registered", ts, player, None, None,
            self.rng.choice(player.device_pool), self.rng.choice(player.ip_pool),
            _weighted_choice(self.rng, config.PLATFORM_WEIGHTS),
            {"acquisition_channel": player.acquisition_channel},
        )

    def _normal_session_events(self, player: Player, day_offset: int, bet_factor: float = 1.0) -> list:
        rng = self.rng
        events = []
        t = self._day_start_dt(day_offset) + timedelta(seconds=rng.randint(0, 86399))
        device_id = rng.choice(player.device_pool)
        ip_hash = rng.choice(player.ip_pool)
        platform = _weighted_choice(rng, config.PLATFORM_WEIGHTS)

        events.append(self._envelope("funnel_step", t, player, None, None, device_id, ip_hash, platform,
                                      {"step": "landing", "auth_method": None, "fail_reason": None}))
        t += timedelta(seconds=rng.randint(2, 15))
        auth_method = rng.choice(config.AUTH_METHODS)
        events.append(self._envelope("funnel_step", t, player, None, None, device_id, ip_hash, platform,
                                      {"step": "login_attempt", "auth_method": auth_method, "fail_reason": None}))
        t += timedelta(seconds=rng.randint(1, 5))

        if rng.random() < 0.05:
            events.append(self._envelope("funnel_step", t, player, None, None, device_id, ip_hash, platform,
                                          {"step": "login_fail", "auth_method": auth_method,
                                           "fail_reason": rng.choice(["invalid_password", "otp_timeout"])}))
            return events  # session abandoned after a failed login

        events.append(self._envelope("funnel_step", t, player, None, None, device_id, ip_hash, platform,
                                      {"step": "login_success", "auth_method": auth_method, "fail_reason": None}))

        session_id = str(uuid.UUID(int=rng.getrandbits(128)))
        t += timedelta(seconds=rng.randint(1, 3))
        session_start_t = t
        events.append(self._envelope("session_start", t, player, session_id, None, device_id, ip_hash, platform, {}))

        catalog = config.SITE_GAME_CATALOG[player.home_site_id]
        for _ in range(rng.randint(1, 8)):
            t += timedelta(seconds=rng.randint(5, 120))
            game_id = rng.choice(catalog)
            bet_amount = round(rng.lognormvariate(1.5, 0.8) * bet_factor, 2)
            won = rng.random() < 0.45
            win_amount = round(bet_amount * rng.uniform(1.2, 3.0), 2) if won else 0.0
            events.append(self._envelope(
                "bet_settled", t, player, session_id, game_id, device_id, ip_hash, platform,
                {
                    "game_round_id": str(uuid.UUID(int=rng.getrandbits(128))),
                    "bet_amount": bet_amount,
                    "win_amount": win_amount,
                    "currency": config.CLIENT_SITES[player.home_site_id]["currency"],
                },
            ))

        if rng.random() < 0.12:
            t += timedelta(seconds=rng.randint(5, 60))
            amount = round(rng.lognormvariate(3.4, 0.6), 2)
            status = rng.choices(["completed", "initiated", "failed"], weights=[0.92, 0.05, 0.03])[0]
            events.append(self._envelope(
                "deposit", t, player, session_id, None, device_id, ip_hash, platform,
                {"amount": amount, "currency": config.CLIENT_SITES[player.home_site_id]["currency"],
                 "payment_method": rng.choice(config.PAYMENT_METHODS), "status": status},
            ))

        if rng.random() < 0.05:
            t += timedelta(seconds=rng.randint(5, 60))
            amount = round(rng.lognormvariate(3.0, 0.6), 2)
            status = rng.choices(["completed", "initiated", "failed"], weights=[0.90, 0.05, 0.05])[0]
            events.append(self._envelope(
                "withdrawal", t, player, session_id, None, device_id, ip_hash, platform,
                {"amount": amount, "currency": config.CLIENT_SITES[player.home_site_id]["currency"],
                 "payment_method": rng.choice(config.PAYMENT_METHODS), "status": status},
            ))

        if rng.random() < 0.08:
            t += timedelta(seconds=rng.randint(5, 60))
            events.append(self._envelope(
                "bonus_claimed", t, player, session_id, None, device_id, ip_hash, platform,
                {"bonus_id": rng.choice(config.BONUS_POOL), "bonus_amount": round(rng.lognormvariate(1.8, 0.5), 2)},
            ))

        t += timedelta(seconds=rng.randint(5, 30))
        events.append(self._envelope(
            "session_end", t, player, session_id, None, device_id, ip_hash, platform,
            {"duration_sec": int((t - session_start_t).total_seconds())},
        ))
        return events

    def _arbitrage_cycle_events(self, player: Player, day_offset: int) -> list:
        """A deliberately abnormal deposit -> minimal play -> withdrawal cycle,
        with device/IP fingerprints shared across the whole ring."""
        rng = self.rng
        events = []
        t = self._day_start_dt(day_offset) + timedelta(seconds=rng.randint(0, 86399))
        device_id = rng.choice(player.device_pool)
        ip_hash = rng.choice(player.ip_pool)
        platform = _weighted_choice(rng, config.PLATFORM_WEIGHTS)

        events.append(self._envelope("funnel_step", t, player, None, None, device_id, ip_hash, platform,
                                      {"step": "landing", "auth_method": None, "fail_reason": None}))
        t += timedelta(seconds=3)
        events.append(self._envelope("funnel_step", t, player, None, None, device_id, ip_hash, platform,
                                      {"step": "login_attempt", "auth_method": "password", "fail_reason": None}))
        t += timedelta(seconds=2)
        events.append(self._envelope("funnel_step", t, player, None, None, device_id, ip_hash, platform,
                                      {"step": "login_success", "auth_method": "password", "fail_reason": None}))

        session_id = str(uuid.UUID(int=rng.getrandbits(128)))
        t += timedelta(seconds=2)
        session_start_t = t
        events.append(self._envelope("session_start", t, player, session_id, None, device_id, ip_hash, platform, {}))

        currency = config.CLIENT_SITES[player.home_site_id]["currency"]
        t += timedelta(seconds=rng.randint(5, 20))
        deposit_amount = round(rng.uniform(80, 150), 2)
        events.append(self._envelope(
            "deposit", t, player, session_id, None, device_id, ip_hash, platform,
            {"amount": deposit_amount, "currency": currency, "payment_method": rng.choice(config.PAYMENT_METHODS),
             "status": "completed"},
        ))

        catalog = config.SITE_GAME_CATALOG[player.home_site_id]
        for _ in range(rng.randint(1, 2)):
            t += timedelta(seconds=rng.randint(10, 40))
            bet_amount = round(rng.uniform(1, 3), 2)
            won = rng.random() < 0.3
            win_amount = round(bet_amount * rng.uniform(1.0, 1.5), 2) if won else 0.0
            events.append(self._envelope(
                "bet_settled", t, player, session_id, rng.choice(catalog), device_id, ip_hash, platform,
                {"game_round_id": str(uuid.UUID(int=rng.getrandbits(128))), "bet_amount": bet_amount,
                 "win_amount": win_amount, "currency": currency},
            ))

        t += timedelta(seconds=rng.randint(10, 30))
        withdrawal_amount = round(deposit_amount * rng.uniform(0.85, 0.95), 2)
        events.append(self._envelope(
            "withdrawal", t, player, session_id, None, device_id, ip_hash, platform,
            {"amount": withdrawal_amount, "currency": currency, "payment_method": rng.choice(config.PAYMENT_METHODS),
             "status": "completed"},
        ))

        t += timedelta(seconds=rng.randint(5, 15))
        events.append(self._envelope(
            "session_end", t, player, session_id, None, device_id, ip_hash, platform,
            {"duration_sec": int((t - session_start_t).total_seconds())},
        ))
        return events

    # -- top-level driver -----------------------------------------------------

    def generate_day(self, day_offset: int) -> list:
        events = []
        for player in self.players:
            if player.registration_day == day_offset:
                events.append(self._registration_event(player, day_offset))

            if player.is_ring_member:
                if config.ARBITRAGE_RING_START_DAY <= day_offset <= config.ARBITRAGE_RING_END_DAY:
                    events.extend(self._arbitrage_cycle_events(player, day_offset))
                continue

            if not (player.registration_day <= day_offset <= player.churn_day):
                continue

            activity_prob = player.base_activity_prob
            weekday = (config.START_DATE + timedelta(days=day_offset)).weekday()
            if weekday >= 5:
                activity_prob *= 1.2
            if (
                player.home_site_id == config.RETENTION_DROP_SITE
                and config.RETENTION_DROP_START_DAY <= day_offset <= config.RETENTION_DROP_END_DAY
            ):
                activity_prob *= config.RETENTION_DROP_ACTIVITY_FACTOR

            if self.rng.random() < activity_prob:
                bet_factor = 1.0
                if (
                    player.home_site_id == config.RETENTION_DROP_SITE
                    and config.RETENTION_DROP_START_DAY <= day_offset <= config.RETENTION_DROP_END_DAY
                ):
                    bet_factor = config.RETENTION_DROP_BET_FACTOR
                events.extend(self._normal_session_events(player, day_offset, bet_factor))

        events.sort(key=lambda e: e["event_ts"])
        return events

    def scenario_manifest(self) -> dict:
        ring_players = [p.player_id for p in self.players if p.is_ring_member]
        drop_start = config.START_DATE + timedelta(days=config.RETENTION_DROP_START_DAY)
        drop_end = config.START_DATE + timedelta(days=config.RETENTION_DROP_END_DAY)
        ring_start = config.START_DATE + timedelta(days=config.ARBITRAGE_RING_START_DAY)
        ring_end = config.START_DATE + timedelta(days=config.ARBITRAGE_RING_END_DAY)
        ring_reg = config.START_DATE + timedelta(days=config.ARBITRAGE_RING_REGISTRATION_DAY)
        return {
            "retention_drop": {
                "client_site_id": config.RETENTION_DROP_SITE,
                "start_date": drop_start.isoformat(),
                "end_date": drop_end.isoformat(),
                "activity_factor": config.RETENTION_DROP_ACTIVITY_FACTOR,
                "bet_factor": config.RETENTION_DROP_BET_FACTOR,
            },
            "arbitrage_ring": {
                "client_site_id": config.ARBITRAGE_RING_SITE,
                "player_ids": ring_players,
                "shared_device_ids": self.ring_shared_devices,
                "shared_ip_hashes": self.ring_shared_ips,
                "registration_date": ring_reg.isoformat(),
                "start_date": ring_start.isoformat(),
                "end_date": ring_end.isoformat(),
            },
        }


def run(output_dir: Path, seed: int = config.SEED, num_days: int = config.NUM_DAYS) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    sim = EventSimulator(seed=seed)
    total_events = 0

    for day_offset in range(num_days):
        events = sim.generate_day(day_offset)
        total_events += len(events)
        day = config.START_DATE + timedelta(days=day_offset)
        out_path = output_dir / f"dt={day.isoformat()}" / "events.jsonl"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    manifest = sim.scenario_manifest()
    manifest["total_events"] = total_events
    manifest["num_players"] = len(sim.players)
    with (output_dir / "scenario_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest

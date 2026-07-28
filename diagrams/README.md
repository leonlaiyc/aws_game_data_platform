# Architecture Diagrams

Mermaid rather than exported images: GitHub renders these natively, they diff meaningfully in
version control, and they can't drift out of sync with the code the way a stale PNG does.

Each diagram reflects what is actually deployed (verified against `aws glue get-tables`,
`aws stepfunctions list-state-machines`, and the CDK stacks in [`infra/infra/`](../infra/infra/)),
not an aspirational design.

---

## 1. The platform as one closed loop

The four pieces are not four separate demos. They form a loop: the governed foundation feeds
detection, detection hands off to investigation, investigation produces a hypothesis, and the
experimentation platform validates that hypothesis before a change is trusted — which then shows
up back in the foundation's numbers.

```mermaid
flowchart LR
    subgraph F["data-foundation — governed multi-tenant lake"]
        LAKE[("S3 medallion lake<br/>Bronze / Silver / Gold")]
        KPI["KPI_DEFINITIONS.md<br/>single source of truth"]
    end

    subgraph M1["Module 1 — Detect"]
        EWMA["EWMA anomaly detector"]
        ARB["Arbitrage detector"]
    end

    subgraph M3["Module 3 — Investigate and self-serve"]
        ASK["ask_answer<br/>NL question answering<br/>over the semantic layer"]
        FLR["first_look_report"]
    end

    subgraph M2["Module 2 — Optimize"]
        EXP["Experiment lifecycle<br/>Step Functions"]
    end

    ANALYST(["Analyst / client success"])

    LAKE --> EWMA
    LAKE --> ARB
    LAKE --> ASK
    EWMA -->|"SNS alert"| FLR
    FLR -->|"pre-investigated report"| ANALYST
    ASK -->|"grounded answer"| ANALYST
    ARB -->|"flagged players"| ANALYST
    ANALYST -->|"forms a hypothesis"| EXP
    EXP -->|"validated change<br/>+ traceable readout"| ANALYST

    KPI -.->|governs| LAKE
    KPI -.->|governs| ASK
    KPI -.->|governs| EXP
```

The dotted lines matter as much as the solid ones: one metric-definition document governs the
lake's Gold tables, Module 3's semantic layer, and Module 2's experiment metrics. That's what
stops "GGR" from meaning three different things in three different places.

---

## 2. Data foundation, catalog, and client isolation

```mermaid
flowchart TB
    SIM["event_simulator<br/>(stands in for client-site SDKs)"]

    subgraph S3["S3 — aurora-games-lake"]
        BRONZE["bronze/ → bronze_events<br/>raw JSON, partition projection"]
        SILVER["silver/ → silver_events<br/>typed and cleaned"]
        GOLD["gold/ → gold_daily_kpi,<br/>gold_cohort_retention,<br/>gold_player_features,<br/>gold_experiment_assignments"]
    end

    SIM -->|"direct-to-S3, no ingestion service"| BRONZE
    BRONZE -->|"Athena CTAS"| SILVER
    SILVER -->|"Athena CTAS"| GOLD

    GLUE["Glue Data Catalog<br/>database: aurora_games_lake"]
    LF["Lake Formation<br/>row-level data cell filters"]

    S3 --- GLUE
    GLUE --- LF

    LF -->|"client_site_id = 'site_a'"| RA["analyst role — site_a"]
    LF -->|"client_site_id = 'site_b'"| RB["analyst role — site_b"]
    LF -->|"client_site_id = 'site_c'"| RC["analyst role — site_c"]

    GLUE --> WG["Athena workgroup<br/>aurora-games-wg<br/>bytes-scanned cap"]
    WG --> MODULES["Module 1 / 2 / 3 Lambdas"]
```

**Why direct-to-S3 rather than Kinesis Firehose for ingestion:** at this project's volume the
buffering service would be pure overhead and permanent cost. See
[ARCHITECTURE.md](../ARCHITECTURE.md) for the scale threshold at which that flips.

**Isolation is enforced at the catalog, not in application code.** Each analyst role is
physically unable to read another client's rows — verified by assuming each role via STS and
confirming it sees only its own site
([`data-foundation/governance/verify_isolation.py`](../data-foundation/governance/verify_isolation.py)).
Application-level filtering would be a bug away from a cross-tenant leak; this is not.

---

## 3. Module 1 — dual detection path

```mermaid
flowchart LR
    subgraph BATCH["Steady state — batch (always on)"]
        EB1["EventBridge<br/>daily schedule"]
        EWMA["data_anomaly<br/>EWMA, k=3σ"]
        ARB["arbitrage_detection<br/>two independent signals"]
        EB1 --> EWMA
        EB1 --> ARB
    end

    subgraph STREAM["Short-lived demo only — deployed, demoed, destroyed"]
        KIN["Kinesis Data Streams<br/>1 shard, provisioned"]
        AGG["aggregator Lambda<br/>rolling window"]
        DDB["DynamoDB<br/>atomic counters + TTL"]
        KIN --> AGG
        AGG <--> DDB
    end

    GOLD[("gold_daily_kpi<br/>gold_player_features<br/>silver_events")]
    GOLD --> EWMA
    GOLD --> ARB

    SNS{{"SNS — aurora-games-anomaly-alerts"}}
    EWMA --> SNS
    AGG -->|"RTP / volume breach<br/>de-duplicated per window"| SNS
    ARB --> EVID["gold/flagged_players/"]
    EWMA --> EVID2["gold/anomaly_alerts/"]

    SNS --> M3["Module 3 first_look_report"]
```

The streaming path exists to demonstrate the capability and the reasoning, **not** as part of the
steady-state architecture — Kinesis bills per shard-hour with no free tier, so it is deployed and
torn down around its demo. The batch path is what actually runs.

---

## 4. Module 2 — experiment lifecycle

```mermaid
flowchart TB
    API["API Gateway + Lambda<br/>experiment registry CRUD"]
    DDB[("DynamoDB<br/>aurora-games-experiments")]
    API <--> DDB

    subgraph SFN["Step Functions — aurora-games-experiment-lifecycle"]
        A["assignment"]
        S["srm_check"]
        C{"SRM passed?"}
        M["monitoring<br/>(Map, guardrail checks)"]
        AN["analysis<br/>statistics + caveat flags"]
        R["readout<br/>Bedrock synthesis"]
        A --> S --> C
        C -->|no| STOP["halt — SRM violation"]
        C -->|yes| M --> AN --> R
    end

    DDB --> A
    FEAT[("gold_player_features<br/>FEATURES.md registry")] --> A
    R --> OUT["Readout: every number code-rendered,<br/>LLM writes only qualitative text"]
```

`analysis` computes deterministic caveat flags (`SAMPLE_IMBALANCE`, `SMALL_SAMPLE`,
`GUARDRAIL_NEAR_THRESHOLD`, `SUSPICIOUSLY_LARGE_EFFECT`, `WIDE_UNCERTAINTY`) in code. The readout
prompt *requires* the model to address every flag present — it chooses only how to phrase the
caveat, never whether to mention it.

---

## 5. Module 3 — two capabilities, one grounding rule

```mermaid
flowchart TB
    subgraph CAPA["Capability A — ask_answer"]
        Q["NL question"]
        APIGW["API Gateway"]
        L1["ask_answer Lambda"]
        GR["Bedrock Guardrail<br/>PROMPT_ATTACK + denied topics"]
        BR["Nova Lite<br/>classify + extract slots"]
        VAL["slot re-validation<br/>whitelist / regex"]
        TPL["semantic layer<br/>5 pre-approved SQL templates"]
        ATH["Athena"]
        ANS["code-rendered answer<br/>+ KPI_DEFINITIONS source footer"]

        Q --> APIGW --> L1 --> GR --> BR --> VAL --> TPL --> ATH --> ANS
    end

    subgraph CAPB["Capability B — first_look_report"]
        SNSIN{{"SNS anomaly alert<br/>(MessageAttributes)"}}
        L2["first_look_report Lambda"]
        DRILL["baseline comparison<br/>per-game breakdown<br/>co-movement check"]
        HEAD["Nova Lite:<br/>one qualitative headline, no numbers"]
        RPT["gold/first_look_reports/"]

        SNSIN --> L2 --> DRILL --> HEAD --> RPT
    end

    GOLD2[("gold_daily_kpi / silver_events")] --> ATH
    GOLD2 --> DRILL
```

**The model never writes SQL and never states a number.** It picks a template and fills slots from
a closed set; those slots are re-validated against a whitelist before substitution. Every figure
in the response comes from a query result rendered by Python.

---

## 6. Trust boundary

```mermaid
flowchart TB
    subgraph UNTRUSTED["Untrusted input"]
        UQ["End-user natural-language question"]
    end

    subgraph CONTROLS["Enforced controls, in order"]
        G["1. Bedrock Guardrails<br/>prompt attack, denied topics"]
        SC["2. caller_scope check<br/>cross-client request → refused"]
        WL["3. slot whitelist / regex<br/>no raw model output reaches SQL"]
        LFB["4. Lake Formation row filter<br/>catalog-level, not app-level"]
        CAP["5. Athena bytes-scanned cap<br/>runaway-query cost ceiling"]
    end

    DATA[("Client data")]

    UQ --> G --> SC --> WL --> LFB --> CAP --> DATA

    AUDIT["CloudWatch audit log<br/>category, slots, model reasoning"]
    G -.-> AUDIT
    SC -.-> AUDIT
    WL -.-> AUDIT
```

Five independent controls, each of which would have to fail for a cross-tenant leak or an
injection to reach data. Note that control 4 sits *below* the application — even a fully
compromised Lambda cannot read another client's rows, because the filter is enforced by Lake
Formation when the query is planned.

const translations = {
  zh: {
    pageTitle: "Leon Lai · AWS Solutions Architect 作品集",
    pageDescription: "從四個真實營運問題出發，介紹一套成本可控、可治理、可驗證的 AWS 遊戲數據平台。",
    skip: "跳到主要內容",
    navProblems: "營運問題",
    navArchitecture: "系統架構",
    navWorkflows: "四個工作流",
    navDemo: "Demo",
    navEvidence: "驗證證據",
    heroEyebrow: "LEON LAI · BUSINESS-FIRST AWS SA PORTFOLIO",
    heroTitle1: "一套治理模型，",
    heroTitle2: "支撐四種遊戲營運工作流。",
    heroLede: "將異常偵測、實驗運營、臨時分析與合作夥伴支援，建立在共用的資料定義、權限邊界與成本控制上。",
    seeArchitecture: "理解系統架構",
    seeDemo: "查看 Demo 路徑",
    heroScope: "Synthetic data · Verified PoC · 不宣稱 production workload 經驗",
    snapshot: "PROJECT SNAPSHOT",
    publicStatus: "Public · CI passing",
    statWorkflows: "operating workflows",
    statTests: "offline tests",
    statCost: "monthly gross model",
    statAlwaysOn: "always-on compute",
    snapshotFoot: "ap-northeast-1 · Serverless-first · Cost-bounded",
    problemsKicker: "THE OPERATING REALITY",
    problemsTitle: "先有營運問題，才有架構。",
    problemsIntro: "這些不是為了套 AWS 服務而整理出的抽象需求，而是會反覆消耗分析、營運、客服與工程資源的工作情境。",
    m1Short: "異常／風險訊號",
    p1Title: "沒有主動監控，只能被動發現。",
    p1Body: "數據缺乏主動監控；一旦留存或營收下滑，通常要等到人為發現才開始處理。已知套利風險也缺少一致、可回溯的證據格式，調查品質容易依賴個人經驗。",
    m2Short: "實驗運營",
    p2Title: "並行實驗的狀態存在每個人的腦中。",
    p2Body: "不同遊戲的 A/B testing 同時進行時，沒有中央化方式查看並行實驗狀態，得一個一個問人，或等到站會才知道。",
    p2SecondaryIntro: "這個核心問題同時還伴隨兩個次要、但會持續增加營運成本的問題：",
    p2Secondary1: "SRM、guardrail 依賴人工抽查，異常實驗停止有延遲。",
    p2Secondary2: "相同 data feature 因為由不同組員負責而重複開發。",
    m3Short: "臨時分析",
    p3Title: "Dashboard 回答不了突然出現的「為什麼」。",
    p3Body: "Dashboard 可以回答固定問題，但當老闆、業務或客戶突然詢問「今天營收為什麼掉了？」時，現有 dashboard 往往無法直接回答。",
    p3Impact: "這類提問通常伴隨急迫性，又會在不可預期的時間出現，進一步加重分析人員的工作負擔；當客戶數量增加，問題頻率也會隨之上升。",
    m4Short: "合作夥伴支援",
    p4Title: "重複問題一路升級到工程師。",
    p4Body: "不同時區的合作夥伴經常反覆詢問類似的產品對接與整合問題：一方面客服需要重複回答；另一方面，若客服無法處理，問題就會升級到工程師層面，進一步增加開發負擔。",
    architectureKicker: "SYSTEM SHAPE & BOUNDARIES",
    architectureTitle: "三條工作流共用資料湖；第四條走獨立知識路徑。",
    architectureIntro: "這裡只呈現元件、資料流與邊界；為什麼暫時不用其他服務，留到 Decisions 再談。",
    dataLaneLabel: "M1 · M2 · M3 共用",
    sourceLabel: "INPUT",
    sourceTitle: "Game events",
    sourceBody: "Simulated · scripted scenarios",
    foundationLabel: "GOVERNED FOUNDATION",
    foundationTitle: "同一套資料定義與租戶邊界",
    metricDefinition: "KPI_DEFINITIONS.md · 共用指標邏輯",
    lakeIsolation: "Glue Catalog · Lake Formation row filters",
    architectureM1: "偵測",
    architectureM2: "實驗運營",
    architectureM3: "分析",
    supportLaneLabel: "M4 · RAG-style knowledge path",
    partnerDocsTitle: "Partner documents",
    partnerDocsBody: "Game provider · client operator",
    supportNodeTitle: "RAG-style partner support",
    supportNodeBody: "Scope corpus · relevance gate · grounded answer",
    engineeringTitle: "客服／工程師",
    engineeringBody: "只有需要判斷時才介入",
    sharedRailTitle: "SHARED CONTROL PLANE",
    sharedIdentity: "身份決定可見範圍",
    sharedFacts: "Code 決定數字、路由與揭露",
    sharedCost: "預設部署受成本邊界約束",
    implementedLegend: "已實作整合",
    humanLegend: "人工決策／升級",
    architectureBoundary: "M4 不讀取 Gold tables；它與資料工作流共用控制原則，但不是同一條資料管線。",
    workflowsKicker: "SYSTEM OWNS REPETITION · PEOPLE OWN JUDGEMENT",
    workflowsTitle: "四個工作流，改變四種人的工作方式。",
    workflowsIntro: "每張卡依序說明：原本怎麼做、系統接手什麼、人保留什麼決策，以及這條工作流如何運行。",
    beforeLabel: "原本怎麼做",
    systemLabel: "系統接手",
    humanLabel: "人保留決策",
    wf1Title: "KPI 異常與已知風險訊號",
    wf1Before: "依賴人主動查看報表，發現下滑後才開始追查；已知套利訊號的調查證據也不一致。",
    wf1System: "每日檢查 DAU／GGR 與已知雙訊號風險模式；每週檢查成熟的 D1／D7 cohort 留存，並附上 baseline、threshold 與證據。",
    wf1Human: "判斷根因、採取營運處置；風險玩家只進入人工審查，不由模型自動定罪。",
    wf1OpsLabel: "掃描與告警窗口",
    wf1Ops: "DAU／GGR 每 24 小時只檢查最新完整發布日，使用前 20 天建立 baseline；成功完成後以 published_at 記錄消費進度。7/31 告警 7/30 後，8/1 正常只檢查 7/31；舊日期重發為新版本時才重新評估。",
    wf3Title: "Analytics NL Assistant",
    wf3Before: "突發的 what／why 問題打斷分析師，還要重新查基線、遊戲別與共變動。",
    wf3System: "允許清單 SQL 回答 what；first-look 與 diagnose 組合證據回答 why；答不了就建 ticket。",
    wf3Human: "判讀營運脈絡、確認根因，並決定後續處置。",
    wf3ScopeLabel: "答案品質控制",
    wf3Scope: "答案只從受治理 KPI 與 allow-listed templates 產生；無法回答就建立 ticket，不生成任意 SQL，也不碰未治理的 country／player 維度。",
    wf2Title: "實驗運營平台",
    wf2Before: "並行實驗狀態散落在人與站會中；SRM、guardrail 靠人工抽查，共用 feature 重複開發。",
    wf2System: "中央 registry、IAM-derived owner、SRM、guardrail、allocation kill switch 與共享 feature registry。",
    wf2Human: "決定假設、指標、是否採納結果，以及異常實驗後的產品處置。",
    wf2StateLabel: "狀態觸發與儲存",
    wf2State: "負責人以簽名 API／CLI 建立 draft、PATCH 編輯並按 Start；DynamoDB 保存唯一現況，Streams 同步 S3／Athena snapshot。Start 觸發 running，Step Functions／每小時監控再寫入 stopped_early、completed、analyzed；dashboard 每 15 秒刷新。",
    wf4Title: "RAG-style 合作夥伴支援",
    wf4Before: "客服重複回答整合問題；無法處理時再把缺乏脈絡的問題轉給工程師。",
    wf4System: "RAG-style 流程先依 IAM 身份選定 provider／operator corpus，再做 relevance gate、把受控文件放入 context，交給 Bedrock 回答；不足就澄清或建 ticket。",
    wf4Human: "處理文件無法回答、需要產品判斷或真正涉及工程變更的案件。",
    wf4RagLabel: "RAG 路徑與上線準備",
    wf4Rag: "PoC 使用小型模擬文件，將所選 corpus 全量放入 context；正式上線要換成有版本與權限 metadata 的正式文件，文件量增長後再導入 chunking、向量檢索或 managed knowledge base。",
    demoKicker: "FOUR CHAPTERS · UNDER TWO MINUTES",
    demoTitle: "先理解工作流，再看它實際輸出什麼。",
    demoIntro: "這個互動導覽同時是最終兩分鐘影片的章節設計：每段呈現痛點、執行結果、人的決策與運行方式。",
    demoM1: "M1 · Detect",
    demoM1Time: "25 秒",
    demoM3: "M3 · Investigate",
    demoM3Time: "25 秒",
    demoM2: "M2 · Experiment Ops",
    demoM2Time: "35 秒",
    demoM4: "M4 · Support",
    demoM4Time: "25 秒",
    demoPainLabel: "PAIN",
    demoResultLabel: "RESULT",
    demoHumanLabel: "HUMAN DECISION",
    loopDetect: "Detect",
    loopFirstLook: "First look",
    loopInvestigate: "Investigate",
    loopAct: "Act",
    loopValidate: "Validate",
    loopNote: "這條閉環只適用 KPI／留存異常；已知風險訊號走獨立的 flagged players → human review；M2 只在適合以受控實驗驗證時介入。",
    decisionsKicker: "SYSTEM DESIGN TRADE-OFFS & COST OPTIMIZATION",
    decisionsTitle: "系統設計取捨與成本最佳化。",
    decisionsIntro: "從使用頻率、延遲需求與服務完整度三個問題，決定現階段最合適的 AWS 能力；量測條件改變時再升級。",
    decision1Category: "WORKLOAD ECONOMICS",
    decision1Title: "依照現有使用頻率，該如何選擇運算模式？",
    nowLabel: "NOW",
    flipLabel: "DECISION FLIPS WHEN",
    decision1Now: "資料量小、查詢間歇；預設採用 request-priced 或 scale-to-zero 元件，Kinesis 只做短生命週期示範。",
    decision1Flip: "出現持續查詢併發、穩定高流量，或 sub-minute SLA 成為正式需求。",
    decision2Category: "DATA ACCESS PATTERN",
    decision2Title: "這個使用情境需要多低的延遲？",
    decision2Now: "Feature 用於 batch analysis；合作夥伴 corpus 小且可受控放入 context，現階段不需要新增 serving 與 retrieval 平面。",
    decision2Flip: "Feature 需要毫秒級線上查詢，或文件量超出 in-context 方法可治理的範圍。",
    decision3Category: "MANAGED WORKFLOW VS CONTROL",
    decision3Title: "這個團隊需要多完整的服務能力？",
    decision3Now: "PoC 使用窄範圍自訂流程，展示 SQL allowlist、數字所有權、tenant scope 與 disclosure control。",
    decision3Flip: "真實團隊需要完整 BI、自助報表、企業搜尋、內容維護與使用者管理，managed workflow 的組織價值開始更高。",
    learningsKicker: "THREE IMPLEMENTATION TRAPS",
    learningsTitle: "分享實作中遇到的三個小坑。",
    learningsIntro: "這些問題是在建置與驗證這個 PoC 時發現，不是宣稱來自 production incident。",
    learning1Title: "看得到 row filter，不代表租戶真的被隔離。",
    assumedLabel: "I ASSUMED",
    learning1Assumed: "建立 Lake Formation row-level filter 後，各 tenant 就只能看到自己的資料。",
    learning1Found: "Glue table 的向下相容 grant 仍可能把權限交回 IAM，讓 filter 看起來存在、實際卻是 no-op；直接 S3 GetObject 也是另一條繞過路徑。",
    changedLabel: "DESIGN CHANGED",
    learning1Changed: "撤銷該表的 compatibility grant、移除 analyst 的直接 S3 data access，再同時驗證 Athena 只看得到自己的 site，且 GetObject 必須被拒。",
    learning1Takeaway: "租戶隔離只有在繞過路徑也失敗時才是真的。",
    learning2Title: "同一場異常，第一天會響，第三天可能不再響。",
    learning2Assumed: "只要 DAU 持續低迷，EWMA detector 就會持續認為它異常。",
    learning2Day1: "約 3.9σ → ALERT",
    learning2Day3Strong: "2 個低迷日已進入 window",
    learning2Day3: "baseline 下移、標準差擴大 → NO ALERT",
    learning2Changed: "將目前 detector 明確定義為 onset detection：負責盡早觸發第一次調查，不假裝它同時管理持續事件狀態；production 若要持續告警，需另保留不會適應的 reference baseline。",
    learning2Takeaway: "偵測「事件開始」與追蹤「事件仍在發生」是兩個不同問題。",
    learning3Title: "Prompt 說不能洩漏，模型仍然洩漏了。",
    learning3Assumed: "明確要求模型不得顯示內部文件名稱與 ID，就足以保護對外回答。",
    learning3Leak: "“Document ID: [internal identifier]”",
    learning3Changed: "在送給合作夥伴前，由 deterministic validator 檢查並替換不安全輸出；完整證據只保留在內部 audit path。",
    learning3Takeaway: "Prompt 是要求；code validator 才是 enforcement boundary。",
    evidenceKicker: "CLAIMS NEED EVIDENCE",
    evidenceTitle: "系統驗證：讓每個主張都有可重現的證據。",
    evidenceIntro: "以下數字都能回到測試、AWS 紀錄或程式輸出重新檢查。",
    evidenceTests: "offline tests passing",
    evidenceStacks: "default CDK stacks synthesize",
    evidenceAws: "baseline exercised against AWS",
    evidenceCost: "gross Cost Explorer usage snapshot",
    evidenceIsolation: "Athena scoped · direct S3 denied",
    evidenceRing: "scripted ring players flagged",
    evidenceAnswer: "assistant answer matched Athena",
    evidenceTeardown: "Kinesis teardown independently verified",
    architectureLink: "Architecture & trade-offs",
    costLink: "Cost evidence & scale model",
    isolationLink: "Tenant isolation proof",
    lessonsLink: "Designs changed by testing",
    scopeTitle: "Honest scope",
    scopeBody: "這是使用 synthetic data 的 verified PoC。最新版增量已通過本機與 CI 驗證，但沒有重新部署到付費 AWS 帳號，因此不宣稱目前 commit 是 production deployment。",
    closingKicker: "THE TAKEAWAY",
    closingTitle: "如何在實際需求與限制中，評估並設計最合適的 AWS 服務組合。",
    closingBody: "這個專案展示我如何把營運摩擦翻譯成可治理的系統、把人的判斷留在人手上，並在增加服務以前先說清楚成本、控制與採用門檻。",
    exploreRepo: "Explore the repository",
    backTop: "回到頂部",
    footerNote: "Synthetic data · Verified PoC · Public repository",
    languageChanged: "已切換為繁體中文",
  },
  en: {
    pageTitle: "Leon Lai · AWS Solutions Architect Portfolio",
    pageDescription: "A business-first walkthrough of a governed, cost-conscious and verifiable AWS game data platform.",
    skip: "Skip to main content",
    navProblems: "Problems",
    navArchitecture: "Architecture",
    navWorkflows: "Workflows",
    navDemo: "Demo",
    navEvidence: "Evidence",
    heroEyebrow: "LEON LAI · BUSINESS-FIRST AWS SA PORTFOLIO",
    heroTitle1: "One governance model.",
    heroTitle2: "Four game-operations workflows.",
    heroLede: "Anomaly detection, experiment operations, ad-hoc analytics and partner support share clear data definitions, access boundaries and cost controls.",
    seeArchitecture: "Understand the architecture",
    seeDemo: "Explore the demo path",
    heroScope: "Synthetic data · Verified PoC · No production-workload claim",
    snapshot: "PROJECT SNAPSHOT",
    publicStatus: "Public · CI passing",
    statWorkflows: "operating workflows",
    statTests: "offline tests",
    statCost: "monthly gross model",
    statAlwaysOn: "always-on compute",
    snapshotFoot: "ap-northeast-1 · Serverless-first · Cost-bounded",
    problemsKicker: "THE OPERATING REALITY",
    problemsTitle: "The operating problem comes before the architecture.",
    problemsIntro: "These are not abstract requirements reverse-engineered to fit AWS services. They are recurring situations that consume analyst, operations, support and engineering time.",
    m1Short: "Anomaly / risk signals",
    p1Title: "Without active monitoring, discovery stays reactive.",
    p1Body: "Data was not actively monitored. When retention or revenue dropped, the team waited for someone to notice before investigation began. Reviews of known arbitrage signals also lacked a consistent, traceable evidence format.",
    m2Short: "Experiment operations",
    p2Title: "Parallel experiment status lived in people's heads.",
    p2Body: "When different games ran A/B tests at the same time, there was no central way to see their status. People had to ask each owner or wait for the stand-up.",
    p2SecondaryIntro: "That core problem came with two smaller issues that kept adding operating cost:",
    p2Secondary1: "SRM and guardrails were spot-checked manually, delaying abnormal experiment stops.",
    p2Secondary2: "Shared data features were rebuilt by different owners.",
    m3Short: "Ad-hoc analytics",
    p3Title: "Dashboards did not answer a sudden “why?”",
    p3Body: "Dashboards handled fixed questions, but they could not directly answer an executive, commercial lead or client asking, “Why did revenue drop today?”",
    p3Impact: "These questions were urgent and arrived at unpredictable times, increasing analyst workload. As the client base grew, so did their frequency.",
    m4Short: "Partner support",
    p4Title: "Repeated questions escalated all the way to engineering.",
    p4Body: "Partners across time zones repeatedly asked similar product-integration questions. Support had to answer the same issues, and anything it could not resolve escalated to engineers, adding development workload.",
    architectureKicker: "SYSTEM SHAPE & BOUNDARIES",
    architectureTitle: "Three workflows share the lake. The fourth follows a separate knowledge path.",
    architectureIntro: "This section shows components, data flow and boundaries only. Why other services are not used yet belongs in Decisions.",
    dataLaneLabel: "Shared by M1 · M2 · M3",
    sourceLabel: "INPUT",
    sourceTitle: "Game events",
    sourceBody: "Simulated · scripted scenarios",
    foundationLabel: "GOVERNED FOUNDATION",
    foundationTitle: "One data definition, one tenant boundary",
    metricDefinition: "KPI_DEFINITIONS.md · shared metric logic",
    lakeIsolation: "Glue Catalog · Lake Formation row filters",
    architectureM1: "Detect",
    architectureM2: "Experiment Ops",
    architectureM3: "Analytics",
    supportLaneLabel: "M4 · RAG-style knowledge path",
    partnerDocsTitle: "Partner documents",
    partnerDocsBody: "Game provider · client operator",
    supportNodeTitle: "RAG-style partner support",
    supportNodeBody: "Scope corpus · relevance gate · grounded answer",
    engineeringTitle: "Support / engineering",
    engineeringBody: "Only when judgement is required",
    sharedRailTitle: "SHARED CONTROL PLANE",
    sharedIdentity: "Identity determines scope",
    sharedFacts: "Code owns facts, routing and disclosure",
    sharedCost: "The default deployment is cost-bounded",
    implementedLegend: "Implemented integration",
    humanLegend: "Human decision / escalation",
    architectureBoundary: "M4 does not read Gold tables. It shares control principles with the data workflows, but it is not part of the same data pipeline.",
    workflowsKicker: "SYSTEM OWNS REPETITION · PEOPLE OWN JUDGEMENT",
    workflowsTitle: "Four workflows change how four groups of people work.",
    workflowsIntro: "Each card explains what happened before, what the system takes over, what people still decide, and how that workflow operates.",
    beforeLabel: "BEFORE",
    systemLabel: "SYSTEM TAKES OVER",
    humanLabel: "PEOPLE DECIDE",
    wf1Title: "KPI anomalies & known risk signals",
    wf1Before: "People checked reports and began investigation after noticing a drop; known arbitrage reviews also lacked consistent evidence.",
    wf1System: "Daily DAU/GGR and known two-signal risk checks, plus weekly mature D1/D7 cohort retention checks, emit baselines, thresholds and evidence.",
    wf1Human: "People identify root cause and choose the operational response; flagged players enter human review and are never auto-convicted by a model.",
    wf1OpsLabel: "SCAN & ALERT WINDOW",
    wf1Ops: "Every 24 hours, DAU/GGR checks only the latest complete published date and uses up to 20 prior days as baseline. A successful run records published_at progress: after alerting on 7/30 on 7/31, the 8/1 run normally checks 7/31 only. A newly republished version is re-evaluated.",
    wf3Title: "Analytics NL Assistant",
    wf3Before: "Sudden what/why questions interrupted analysts, who had to rebuild baseline, per-game and co-movement analysis.",
    wf3System: "Allow-listed SQL answers what; first-look and diagnose assemble evidence for why; unsupported work becomes a durable ticket.",
    wf3Human: "People interpret operating context, confirm root cause and choose what to do next.",
    wf3ScopeLabel: "ANSWER QUALITY CONTROL",
    wf3Scope: "Answers come only from governed KPIs and allow-listed templates. Unsupported work becomes a ticket instead of arbitrary SQL, and ungoverned country/player dimensions stay out of scope.",
    wf2Title: "Experiment operations platform",
    wf2Before: "Parallel experiment status lived in people and stand-ups; SRM and guardrails were manual, and shared features were rebuilt.",
    wf2System: "A central registry, IAM-derived ownership, SRM, guardrails, an allocation kill switch and a shared feature registry.",
    wf2Human: "People choose hypotheses and metrics, decide whether to trust a result, and own the product response.",
    wf2StateLabel: "STATE TRIGGERS & STORAGE",
    wf2State: "An owner uses the signed API/CLI to create draft, PATCH it and press Start. DynamoDB holds the single current state; Streams sync an S3/Athena snapshot. Start writes running, then Step Functions and hourly monitoring write stopped_early, completed or analyzed. The dashboard refreshes every 15 seconds.",
    wf4Title: "RAG-style partner support",
    wf4Before: "Support repeated integration answers and forwarded unresolved questions to engineers without enough context.",
    wf4System: "The RAG-style path uses IAM identity to select the provider/operator corpus, applies a relevance gate, injects controlled documents into context, and asks Bedrock to answer; gaps trigger clarification or a ticket.",
    wf4Human: "People handle questions the documentation cannot answer, product judgement and real engineering changes.",
    wf4RagLabel: "RAG PATH & PRODUCTION SWAP",
    wf4Rag: "The PoC uses small simulated documents and passes the selected corpus in full context. Production replaces them with official, versioned, access-tagged content; chunking, vector retrieval or a managed knowledge base becomes useful as the corpus grows.",
    demoKicker: "FOUR CHAPTERS · UNDER TWO MINUTES",
    demoTitle: "Understand the workflow first; then inspect what it actually outputs.",
    demoIntro: "This interactive walkthrough is also the chapter plan for the final two-minute recording. Each chapter shows the pain, run result, human decision and operating detail.",
    demoM1: "M1 · Detect",
    demoM1Time: "25 sec",
    demoM3: "M3 · Investigate",
    demoM3Time: "25 sec",
    demoM2: "M2 · Experiment Ops",
    demoM2Time: "35 sec",
    demoM4: "M4 · Support",
    demoM4Time: "25 sec",
    demoPainLabel: "PAIN",
    demoResultLabel: "RESULT",
    demoHumanLabel: "HUMAN DECISION",
    loopDetect: "Detect",
    loopFirstLook: "First look",
    loopInvestigate: "Investigate",
    loopAct: "Act",
    loopValidate: "Validate",
    loopNote: "This loop covers KPI and retention anomalies only. Known risk signals follow a separate flagged players → human review path; M2 appears only when a controlled experiment is the right validation method.",
    decisionsKicker: "SYSTEM DESIGN TRADE-OFFS & COST OPTIMIZATION",
    decisionsTitle: "System design trade-offs and cost optimization.",
    decisionsIntro: "Usage frequency, latency needs and service completeness determine the right AWS capability now; measured changes trigger the next upgrade.",
    decision1Category: "WORKLOAD ECONOMICS",
    decision1Title: "Which compute model fits the current usage frequency?",
    nowLabel: "NOW",
    flipLabel: "DECISION FLIPS WHEN",
    decision1Now: "Data is small and queries are intermittent. Defaults are request-priced or scale-to-zero; Kinesis is an ephemeral demonstration only.",
    decision1Flip: "Sustained query concurrency, steady high throughput or a formal sub-minute SLA appears.",
    decision2Category: "DATA ACCESS PATTERN",
    decision2Title: "How much latency can this use case accept?",
    decision2Now: "Features serve batch analysis. The partner corpus is small enough for controlled in-context use, so another serving or retrieval plane adds no value yet.",
    decision2Flip: "Features need millisecond online lookups or the corpus outgrows a governable in-context approach.",
    decision3Category: "MANAGED WORKFLOW VS CONTROL",
    decision3Title: "How complete does the team need the service to be?",
    decision3Now: "The PoC uses a narrow custom path to demonstrate SQL allowlists, numeric ownership, tenant scope and disclosure control.",
    decision3Flip: "A real team needs full BI, self-service reporting, enterprise search, content operations and user management—making the managed workflow more valuable.",
    learningsKicker: "THREE IMPLEMENTATION TRAPS",
    learningsTitle: "Three small implementation traps worth sharing.",
    learningsIntro: "These were discovered while building and validating this PoC. They are not presented as production incidents.",
    learning1Title: "A visible row filter did not prove tenant isolation.",
    assumedLabel: "I ASSUMED",
    learning1Assumed: "Once a Lake Formation row-level filter existed, every tenant could only see its own rows.",
    learning1Found: "A Glue table's backward-compatibility grant could defer access back to IAM, leaving a visible filter as a no-op. Direct S3 GetObject was a second bypass path.",
    changedLabel: "DESIGN CHANGED",
    learning1Changed: "Revoke that table's compatibility grant, remove direct analyst access to the data, then verify both outcomes: Athena sees one site and GetObject is denied.",
    learning1Takeaway: "Tenant isolation is real only when the bypass path fails too.",
    learning2Title: "The same incident alerted on day one—but not on day three.",
    learning2Assumed: "If DAU stayed depressed, the EWMA detector would keep treating it as abnormal.",
    learning2Day1: "about 3.9σ → ALERT",
    learning2Day3Strong: "2 depressed days entered the window",
    learning2Day3: "baseline fell, deviation widened → NO ALERT",
    learning2Changed: "Define this detector as onset detection: it starts the first investigation but does not pretend to manage persistent incident state. Production persistence would require a separate non-adapting reference baseline.",
    learning2Takeaway: "Detecting an incident's onset and tracking that it remains active are different problems.",
    learning3Title: "The prompt prohibited a leak. The model leaked anyway.",
    learning3Assumed: "Explicitly telling the model not to show internal document names or IDs was enough to protect an external answer.",
    learning3Leak: "“Document ID: [internal identifier]”",
    learning3Changed: "A deterministic validator now checks and replaces unsafe output before delivery; full evidence remains only on the internal audit path.",
    learning3Takeaway: "A prompt is a request. Code validation is the enforcement boundary.",
    evidenceKicker: "CLAIMS NEED EVIDENCE",
    evidenceTitle: "System verification: every claim has reproducible evidence.",
    evidenceIntro: "Every number below can be checked again in tests, AWS records or program output.",
    evidenceTests: "offline tests passing",
    evidenceStacks: "default CDK stacks synthesize",
    evidenceAws: "baseline exercised against AWS",
    evidenceCost: "gross Cost Explorer usage snapshot",
    evidenceIsolation: "Athena scoped · direct S3 denied",
    evidenceRing: "scripted ring players flagged",
    evidenceAnswer: "assistant answer matched Athena",
    evidenceTeardown: "Kinesis teardown independently verified",
    architectureLink: "Architecture & trade-offs",
    costLink: "Cost evidence & scale model",
    isolationLink: "Tenant isolation proof",
    lessonsLink: "Designs changed by testing",
    scopeTitle: "Honest scope",
    scopeBody: "This is a verified PoC using synthetic data. The latest increment passed local and CI validation but was not redeployed to the paid AWS account, so the current commit is not presented as a production deployment.",
    closingKicker: "THE TAKEAWAY",
    closingTitle: "Evaluate and design the right AWS service mix within real needs and constraints.",
    closingBody: "This project shows how I translate operating friction into a governed system, keep human judgement with people, and state cost, control and adoption thresholds before adding services.",
    exploreRepo: "Explore the repository",
    backTop: "Back to top",
    footerNote: "Synthetic data · Verified PoC · Public repository",
    languageChanged: "Language changed to English",
  },
};

const demoChapters = {
  zh: {
    m1: {
      title: "M1 / VERIFIED DEMO OUTPUT",
      pain: "留存／營收下滑需要等人發現；已知風險訊號缺少一致、可解釋的調查證據。",
      result: "首日 KPI 下滑被標示；6 個 scripted ring players 全數進入 REVIEW_REQUIRED。",
      terminal: [
        "$ run module1 demo --as-of 2026-06-10",
        "site_b / dau",
        "actual=91 · EWMA baseline=204 · deviation≈3.9σ",
        "status=ALERT · evidence_window=preserved",
        "",
        "arbitrage review",
        "flagged=6/6 · decision=REVIEW_REQUIRED",
      ].join("\n"),
      human: "確認根因、選擇營運處置，並審查被標示玩家。",
      detailLabel: "掃描與告警窗口",
      detail: "DAU／GGR 每 24 小時只檢查最新完整發布日；相同 published_at 不重複。成熟 D1／D7 留存另於每週一檢查最近的完整 cohort 週。",
    },
    m3: {
      title: "M3 / GOVERNED ANALYTICS OUTPUT",
      pain: "急迫的 what／why 問題會打斷分析師，dashboard 無法直接回答。",
      result: "Allow-listed SQL 回答數字；first-look 在 alert 後自動整理基線與共變動。",
      terminal: [
        '$ ask "What was GGR for site_a in the last week?"',
        "category=answerable",
        "answer=891.83 USD",
        "direct Athena cross-check=891.83 USD · MATCH",
        "",
        "site_b first-look",
        "DAU 91 vs 7d avg 205.5714 (-55.73%)",
        "DAU and GGR moved in the same direction",
      ].join("\n"),
      human: "結合營運脈絡判斷根因，再決定行動。",
      detailLabel: "答案品質控制",
      detail: "只支援受治理 KPI 與模板；答不了就建立 ticket，不生成任意 SQL。",
    },
    m2: {
      title: "M2 / THREE CONCURRENT EXPERIMENTS",
      pain: "並行實驗狀態分散，SRM 與 guardrail 依賴人工抽查。",
      result: "三種生命週期同時可見：正常分析、guardrail 自動停止、SRM hard fail。",
      terminal: [
        "$ run 3 concurrent experiments",
        "clean_winner    state=analyzed · lift=564.1%",
        "                 caveats=SMALL_SAMPLE,LARGE_EFFECT",
        "guardrail_stop  state=stopped_early",
        "                 ggr_usd_7d=-98.2912 < 0",
        "srm_violation   state=stopped_early",
        "                 p=0.000415 · analysis skipped",
        "grounding_check_passed=true",
      ].join("\n"),
      human: "判斷結果是否可信、要不要重跑，以及產品是否採納。",
      detailLabel: "狀態來源",
      detail: "簽名 API／CLI 建立與啟動；DynamoDB 保存單一真實狀態，Step Functions 與每小時監控寫入後續轉換，dashboard 每 15 秒刷新。",
    },
    m4: {
      title: "M4 / RAG-STYLE SUPPORT & LEAKAGE CONTROL",
      pain: "重複整合問題消耗客服；處理不了的問題缺乏結構就轉給工程師。",
      result: "系統先澄清、再回答或建立 ticket；模型洩漏被 code validator 擋下。",
      terminal: [
        "$ run partner-support demo",
        "ambiguous question → NEEDS_CLARIFICATION",
        "engineering case   → ESCALATION · ticket=created",
        "out-of-scope       → deterministic refusal",
        "",
        "model output       → internal identifier detected",
        "validation         → FAILED_SAFE",
        "identifier reaching partner → NONE",
      ].join("\n"),
      human: "處理真正需要產品判斷或工程變更的 ticket。",
      detailLabel: "RAG 上線準備",
      detail: "PoC 以小型模擬文件跑 audience-scoped full-context RAG；正式上線要替換成有版本與權限 metadata 的正式文件，文件增長後再加入向量檢索。",
    },
  },
  en: {
    m1: {
      title: "M1 / VERIFIED DEMO OUTPUT",
      pain: "Retention and revenue drops waited for human discovery; known risk-signal reviews lacked consistent, explainable evidence.",
      result: "The first-day KPI drop was flagged; all six scripted ring players entered REVIEW_REQUIRED.",
      terminal: [
        "$ run module1 demo --as-of 2026-06-10",
        "site_b / dau",
        "actual=91 · EWMA baseline=204 · deviation≈3.9σ",
        "status=ALERT · evidence_window=preserved",
        "",
        "arbitrage review",
        "flagged=6/6 · decision=REVIEW_REQUIRED",
      ].join("\n"),
      human: "Confirm root cause, choose an operating response and review flagged players.",
      detailLabel: "SCAN & ALERT WINDOW",
      detail: "DAU/GGR runs every 24 hours against the latest complete published date and does not repeat the same published_at. Mature D1/D7 retention checks the latest complete cohort week every Monday.",
    },
    m3: {
      title: "M3 / GOVERNED ANALYTICS OUTPUT",
      pain: "Urgent what/why questions interrupted analysts and did not fit dashboards.",
      result: "Allow-listed SQL owns the number; first-look assembles baseline and co-movement evidence after an alert.",
      terminal: [
        '$ ask "What was GGR for site_a in the last week?"',
        "category=answerable",
        "answer=891.83 USD",
        "direct Athena cross-check=891.83 USD · MATCH",
        "",
        "site_b first-look",
        "DAU 91 vs 7d avg 205.5714 (-55.73%)",
        "DAU and GGR moved in the same direction",
      ].join("\n"),
      human: "Combine operating context with evidence, identify root cause and decide what to do.",
      detailLabel: "ANSWER QUALITY CONTROL",
      detail: "Only governed KPI templates are supported. Unsupported work creates a ticket instead of arbitrary SQL.",
    },
    m2: {
      title: "M2 / THREE CONCURRENT EXPERIMENTS",
      pain: "Parallel status was scattered; SRM and guardrails depended on manual checks.",
      result: "Three lifecycles stay visible together: normal analysis, guardrail stop and SRM hard fail.",
      terminal: [
        "$ run 3 concurrent experiments",
        "clean_winner    state=analyzed · lift=564.1%",
        "                 caveats=SMALL_SAMPLE,LARGE_EFFECT",
        "guardrail_stop  state=stopped_early",
        "                 ggr_usd_7d=-98.2912 < 0",
        "srm_violation   state=stopped_early",
        "                 p=0.000415 · analysis skipped",
        "grounding_check_passed=true",
      ].join("\n"),
      human: "Decide whether the result is trustworthy, whether to rerun and whether the product should adopt it.",
      detailLabel: "STATE SOURCE",
      detail: "The signed API/CLI creates and starts experiments; DynamoDB holds the single current state. Step Functions and hourly monitoring write later transitions, and the dashboard refreshes every 15 seconds.",
    },
    m4: {
      title: "M4 / RAG-STYLE SUPPORT & LEAKAGE CONTROL",
      pain: "Repeated integration questions consumed support; unresolved cases reached engineers without structure.",
      result: "The system clarifies, answers or creates a ticket; code blocks a model-authored internal identifier.",
      terminal: [
        "$ run partner-support demo",
        "ambiguous question → NEEDS_CLARIFICATION",
        "engineering case   → ESCALATION · ticket=created",
        "out-of-scope       → deterministic refusal",
        "",
        "model output       → internal identifier detected",
        "validation         → FAILED_SAFE",
        "identifier reaching partner → NONE",
      ].join("\n"),
      human: "Handle tickets that genuinely require product judgement or an engineering change.",
      detailLabel: "RAG PRODUCTION SWAP",
      detail: "The PoC uses simulated documents in an audience-scoped full-context RAG path. Production swaps in official, versioned and access-tagged content, then adds vector retrieval as the corpus grows.",
    },
  },
};

let activeLanguage = "zh";
let activeDemo = "m1";

const languageButtons = [...document.querySelectorAll("[data-lang]")];
const demoButtons = [...document.querySelectorAll("[data-demo]")];
const announcer = document.querySelector(".language-announcer");
const metaDescription = document.querySelector('meta[name="description"]');

function renderDemo() {
  const chapter = demoChapters[activeLanguage][activeDemo];
  document.querySelector("#demo-window-title").textContent = chapter.title;
  document.querySelector("#demo-pain").textContent = chapter.pain;
  document.querySelector("#demo-result").textContent = chapter.result;
  document.querySelector("#demo-terminal").textContent = chapter.terminal;
  document.querySelector("#demo-human").textContent = chapter.human;
  document.querySelector("#demo-detail-label").textContent = chapter.detailLabel;
  document.querySelector("#demo-detail").textContent = chapter.detail;

  demoButtons.forEach((button) => {
    const selected = button.dataset.demo === activeDemo;
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
  });
}

function applyLanguage(language, announce = true) {
  activeLanguage = language;
  const copy = translations[language];
  document.documentElement.lang = language === "zh" ? "zh-Hant" : "en";
  document.title = copy.pageTitle;
  metaDescription.setAttribute("content", copy.pageDescription);

  document.querySelectorAll("[data-i18n]").forEach((element) => {
    const key = element.dataset.i18n;
    if (Object.hasOwn(copy, key)) {
      element.textContent = copy[key];
    }
  });

  languageButtons.forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.lang === language));
  });

  localStorage.setItem("leon-portfolio-language", language);
  renderDemo();

  if (announce) {
    announcer.textContent = copy.languageChanged;
  }
}

languageButtons.forEach((button) => {
  button.addEventListener("click", () => applyLanguage(button.dataset.lang));
});

demoButtons.forEach((button, index) => {
  button.addEventListener("click", () => {
    activeDemo = button.dataset.demo;
    renderDemo();
  });
  button.addEventListener("keydown", (event) => {
    if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      return;
    }
    event.preventDefault();
    let nextIndex = index;
    if (["ArrowDown", "ArrowRight"].includes(event.key)) {
      nextIndex = (index + 1) % demoButtons.length;
    } else if (["ArrowUp", "ArrowLeft"].includes(event.key)) {
      nextIndex = (index - 1 + demoButtons.length) % demoButtons.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = demoButtons.length - 1;
    }
    demoButtons[nextIndex].focus();
    demoButtons[nextIndex].click();
  });
});

document.addEventListener("keydown", (event) => {
  const tag = document.activeElement?.tagName;
  if (event.key.toLowerCase() === "l" && !["INPUT", "TEXTAREA", "SELECT"].includes(tag)) {
    applyLanguage(activeLanguage === "zh" ? "en" : "zh");
  }
});

const storedLanguage = localStorage.getItem("leon-portfolio-language");
applyLanguage(storedLanguage === "en" ? "en" : "zh", false);

const progress = document.querySelector(".scroll-progress span");
const navigationLinks = [...document.querySelectorAll("nav a")];
const sections = [...document.querySelectorAll("[data-section]")];

function updateScrollState() {
  const scrollable = document.documentElement.scrollHeight - window.innerHeight;
  const ratio = scrollable > 0 ? window.scrollY / scrollable : 0;
  progress.style.transform = `scaleX(${Math.min(Math.max(ratio, 0), 1)})`;

  const marker = window.scrollY + window.innerHeight * 0.35;
  let current = "overview";
  sections.forEach((section) => {
    if (section.offsetTop <= marker) {
      current = section.id;
    }
  });
  navigationLinks.forEach((link) => {
    link.classList.toggle("active", link.getAttribute("href") === `#${current}`);
  });
}

window.addEventListener("scroll", updateScrollState, { passive: true });
window.addEventListener("resize", updateScrollState);
updateScrollState();

const revealElements = [...document.querySelectorAll(".reveal")];
if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.08, rootMargin: "0px 0px -36px" },
  );
  revealElements.forEach((element) => observer.observe(element));
} else {
  revealElements.forEach((element) => element.classList.add("is-visible"));
}

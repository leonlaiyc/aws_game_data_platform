const translations = {
  zh: {
    pageTitle: "Leon Lai · AWS Solutions Architect 作品集",
    pageDescription: "以雲端資料與 AI 技術鏈接四大實務痛點，呈現一套成本可控、可治理、可驗證的 AWS 架構。",
    skip: "跳到主要內容",
    navProblems: "營運問題",
    navArchitecture: "系統架構",
    navWorkflows: "四個工作流",
    navDemo: "Demo",
    navEvidence: "驗證證據",
    heroEyebrow: "LEON LAI · BUSINESS-FIRST AWS SA PORTFOLIO",
    heroTitle1: "一套雲端系統架構，",
    heroTitle2: "解決四個實際營運痛點。",
    heroLede: "以 Serverless 為主的設計，建構於資料共用、權限邊界與成本控制之上，解決異常偵測、實驗運營、臨時分析與合作夥伴整合支援問題。",
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
    problemsTitle: "雲端 AI 技術鏈接實務痛點",
    problemsIntro: "針對過去重複耗損資源的四大情境，進行架構設計與 PoC 驗證。",
    m1Short: "異常／品質訊號",
    p1Title: "沒有主動監控，只能被動發現。",
    p1Body: "數據缺乏主動監控；一旦活躍度或轉換表現下滑，通常要等到人為發現才開始處理。已知資料品質訊號也缺少一致、可回溯的證據格式，調查品質容易依賴個人經驗。",
    m2Short: "實驗運營",
    p2Title: "並行實驗的狀態存在每個人的腦中。",
    p2Body: "不同產品體驗的 A/B testing 同時進行時，沒有中央化方式查看並行實驗狀態，得一個一個問人，或等到站會才知道。",
    p2SecondaryIntro: "這個核心問題同時還伴隨兩個次要、但會持續增加營運成本的問題：",
    p2Secondary1: "SRM、guardrail 依賴人工抽查，異常實驗停止有延遲。",
    p2Secondary2: "相同 data feature 因為由不同組員負責而重複開發。",
    m3Short: "臨時分析",
    p3Title: "Dashboard 回答不了突然出現的「為什麼」。",
    p3Body: "Dashboard 可以回答固定問題，但當老闆、業務或客戶突然詢問「今天核心指標為什麼掉了？」時，現有 dashboard 往往無法直接回答。",
    p3Impact: "這類提問通常伴隨急迫性，又會在不可預期的時間出現，進一步加重分析人員的工作負擔；當客戶數量增加，問題頻率也會隨之上升。",
    m4Short: "整合支援",
    p4Title: "重複的整合問題消耗支援與工程資源。",
    p4Body: "不同時區的合作夥伴經常詢問相似的 API 驗證、Webhook、環境設定、服務更新與維護資訊；常見問題需要反覆回覆，複雜案件則占用工程團隊時間。",
    architectureKicker: "SYSTEM SHAPE & BOUNDARIES",
    architectureTitle: "三條工作流共用資料湖；第四條走獨立知識路徑。",
    architectureIntro: "整合統一資料定義、多租戶隔離與 RAG 輔助決策的完整系統型態。",
    sourceLabel: "INPUT",
    foundationMapKicker: "END-TO-END DATA FOUNDATION",
    foundationMapTitle: "資料生成、治理與發布路徑",
    sourceStageBody: "模擬 client SDK 事件與可重播情境",
    bronzeStageBody: "Raw JSON · 日期／租戶分區",
    directBatchBadge: "Direct batch write · 零閒置運算",
    transformStageBody: "Schema cast · 清理 · 可重跑轉換",
    silverStageBody: "Typed Parquet events",
    silverBadge: "分析與已知品質特徵來源",
    goldStageBody: "每日／每小時 KPI · 留存 · 實體特徵 · 實驗資料",
    publicationBadge: "Publication marker 驗證完整版本",
    catalogControl: "固定 Bronze → Silver → Gold 結構與欄位定義",
    tenantControl: "依 client_site_id 套用 row-level data cell filter",
    queryControl: "查詢結果隔離與 1 GB 單次掃描上限",
    definitionControl: "同一套指標與特徵定義供 M1、M2、M3 使用",
    moduleMapKicker: "AUTOMATION & DECISION PATHS",
    moduleMapTitle: "四個模組如何消費資料並交付結果",
    architectureM1Title: "使用異常與品質訊號偵測",
    architectureM1Body: "每日活躍度、每週留存與雙訊號品質檢查；告警自動觸發 M3 first-look，需要判讀的紀錄另交人工審查。",
    architectureM2Title: "實驗生命週期與安全停止",
    architectureM2Body: "Lambda 執行 assignment、SRM、guardrail、analysis 與 readout；Gold features 與 registry state 一起決定實驗是否繼續。",
    architectureM2Branch: "SRM hard fail · hourly guardrail · allocation kill switch",
    architectureM3Title: "受治理問答與事件初判",
    architectureM3Body: "Guardrails 與 allow-listed templates 限制問題範圍；所有數字由 SQL 產生，無法回答的工作寫入 DynamoDB ticket。",
    architectureM3Branch: "Grounded answer · first-look report · durable ticket",
    architectureM4Title: "身份隔離的整合支援",
    architectureM4Body: "IAM 身份先限定可用的支援知識；問題通過範圍與安全檢查後才產生回答，資訊不足時要求澄清，不支援的問題則拒絕回答或建立 OPEN ticket。",
    architectureM4Branch: "不讀取 Gold tables · SNS/SQS 僅作帳號內稽核",
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
    wf1Title: "KPI 異常與已知品質訊號",
    wf1Before: "依賴人主動查看報表，發現下滑後才開始追查；已知資料品質訊號的調查證據也不一致。",
    wf1System: "每日檢查活躍度與互動量的異常模式；每週檢查成熟的 D1／D7 cohort 留存，並附上 baseline、threshold 與證據。",
    wf1Human: "判斷根因、採取營運處置；需要判讀的紀錄進入人工審查，不由系統自動下結論。",
    wf1OpsLabel: "掃描與告警窗口",
    wf1Ops: "每日 KPI 每 24 小時只檢查最新完整發布日，使用前 20 天建立 baseline；成功完成後以 published_at 記錄消費進度。每小時 Guardrail 讀取 gold_hourly_kpi；舊資料重發為新版本時才重新評估。",
    wf3Title: "Analytics NL Assistant",
    wf3Before: "突發的 what／why 問題打斷分析師；得先算過去常態是多少、再拆開看是哪幾款產品出問題，最後交叉比對各個相關變數之間是哪裡出錯。",
    wf3System: "允許清單 SQL 回答 what；first-look 與 diagnose 組合證據回答 why；答不了就建 ticket。",
    wf3Human: "判讀營運脈絡、確認根因，並決定後續處置。",
    wf3ScopeLabel: "答案品質控制",
    wf3Scope: "答案只從受治理 KPI 與 allow-listed templates 產生；無法回答就建立 ticket，不生成任意 SQL，也不碰未治理的地區／個別使用者維度。",
    wf2Title: "實驗運營平台",
    wf2Before: "並行實驗狀態散落在人與站會中；SRM、guardrail 靠人工抽查，共用 feature 重複開發。",
    wf2System: "中央註冊表、IAM 身分權限歸屬、數據品質檢查（SRM）、安全護欄監控、緊急熔斷開關與共享特徵註冊表。",
    wf2Human: "決定假設、指標、是否採納結果，以及異常實驗後的產品處置。",
    wf2StateLabel: "狀態觸發與儲存",
    wf2State: "實驗需要有正規的自動化與治理流程：具備專案權限的負責人，透過身分驗證的 API 或 CLI 指令建立實驗草稿，設定相關實驗參數後正式啟動，而不是由工程師簡單上傳一包數據。DynamoDB 保存當下最新狀態，並透過 Streams 即時同步至 S3／Athena snapshot，供 Dashboard 每 15 秒刷新。啟動後由 Step Functions 接管正常工作流，同時搭配每小時監控進行防護。目前可查建立、啟動、停止與分析完成時間，但尚未保存每次狀態變更的完整不可竄改事件紀錄。",
    wf4Title: "受治理的整合支援",
    wf4Before: "合作夥伴反覆詢問相似的整合與服務資訊；複雜問題常在缺少結構化脈絡時直接占用工程資源。",
    wf4System: "系統先以 IAM 確認合作夥伴身份，再檢查問題是否屬於可支援範圍。合格問題由受限制的知識內容與 AWS Bedrock 產生回答；資訊不足時要求澄清，範圍外問題則明確拒絕。",
    wf4Human: "只有需要產品／工程判斷、或安全驗證未通過的案件才建立 OPEN ticket 供人工接手。目前 PoC 將工單存進 DynamoDB，尚未串接 Email、Slack 或 CRM 通知。",
    wf4RagLabel: "RAG 路徑與上線準備",
    wf4Rag: "現在做 PoC 只是拿少量的測試檔案給 AI 看；未來正式上線時，要幫真實檔案加上「版本」與「權限」標籤。若文件量持續增長，再導入 Chunking 與向量搜尋，形成正規的大型 RAG 架構。",
    demoKicker: "FOUR CHAPTERS · TWO MINUTES",
    demoTitle: "兩分鐘實機操作：四組工作流實際運行",
    demoIntro: "實際開啟四組模組介面，操作問題觸發條件並呈現 AWS 自動處置結果。",
    demoVideoTitle: "實機操作字幕版 · 02:00",
    demoVideoNote: "2026-08-02 實際操作 AWS 路徑 · 1080p · 無聲版本",
    demoVideoDownload: "下載中文字幕",
    demoM1: "M1 · Detect",
    demoM1Time: "23 秒",
    demoM3: "M3 · Investigate",
    demoM3Time: "22 秒",
    demoM2: "M2 · Experiment Ops",
    demoM2Time: "32 秒",
    demoM4: "M4 · 整合支援",
    demoM4Time: "27 秒",
    demoPainLabel: "PAIN",
    demoResultLabel: "RESULT",
    demoHumanLabel: "HUMAN DECISION",
    loopDetect: "Detect",
    loopFirstLook: "First look",
    loopInvestigate: "Investigate",
    loopAct: "Act",
    loopValidate: "Validate",
    loopNote: "這條閉環只適用 KPI／留存異常；已知品質訊號走獨立的 flagged records → human review；M2 只在適合以受控實驗驗證時介入。",
    decisionsKicker: "SYSTEM DESIGN TRADE-OFFS & COST OPTIMIZATION",
    decisionsTitle: "系統設計取捨與成本最佳化。",
    decisionsIntro: "從使用頻率、延遲需求與服務完整度三個問題，決定現階段最合適的 AWS 能力；量測條件改變時再升級。",
    decision1Category: "WORKLOAD ECONOMICS",
    decision1Title: "依照現有使用頻率，該如何選擇運算模式？",
    currentLightweightLabel: "目前的省錢／輕量做法",
    currentControlLabel: "目前的控制優先做法",
    adjustWhenLabel: "何時需要調整？",
    decision1Situation: "狀況：現在資料量很小，且使用者只是偶爾查一次。",
    decision1Action: "做法：採用「用多少算多少」或「沒人用就自動降為 0 費用」的元件（例如 Lambda、Athena）。像 Kinesis 這種持續按小時收費的即時串流元件，現在只做短暫展示，不長期開著燒錢。",
    decision1Trigger: "當未來出現持續高併發查詢（幾百個人同時在查）、穩定大流量，或商業上要求低於 1 分鐘的即時資料處理時。",
    decision1Upgrade: "👉 升級動作：這時才正式引入長期開著的 Redshift（大型資料倉庫）、EMR（大數據 Spark 集群）或 Persistent Kinesis（長期資料串流）。",
    decision2Category: "DATA ACCESS PATTERN",
    decision2Title: "目前需求需要即時服務，還是批次處理就足夠？",
    decision2Situation: "狀況：目前資料／特徵只是拿來做批次分析（例如每天跑一次分析），而且合作夥伴的文檔庫很小，直接整包塞進 AI 提示詞處理就好。",
    decision2Action: "做法：現階段不需要額外架設即時服務系統與向量檢索系統。",
    decision2Trigger: "當未來前端應用（例如推薦系統）要求毫秒級的即時特徵查詢，或者公司文件量大到再也無法「整包塞給 AI」時。",
    decision2Upgrade: "👉 升級動作：這時才正式引進 SageMaker Feature Store 與 OpenSearch／Vector Store。",
    decision3Category: "MANAGED WORKFLOW VS CONTROL",
    decision3Title: "該直接用現成的 AI 套裝工具，還是自己開發並掌握控制權？",
    decision3Situation: "狀況：PoC 階段需精細控管安全性。",
    decision3Action: "做法：採用窄範圍的自訂流程，親自寫程式碼展示 SQL 白名單過濾、數據權限歸屬、多租戶隔離以及敏感數據遮蔽。",
    decision3Trigger: "當未來要推廣給非技術團隊，需要完整的 BI、視覺化報表、企業內部搜尋、內容維護與權限管理介面時（工程團隊不想自己從頭刻 UI 與權限系統）。",
    decision3Upgrade: "👉 升級動作：這時才正式引進 Amazon Quick 與 Amazon Q Business。",
    learningsKicker: "THREE IMPLEMENTATION TRAPS",
    learningsTitle: "分享實作中遇到的三個小坑。",
    learning1Title: "看得到 row filter，不代表租戶真的被隔離。",
    assumedLabel: "當初天真的假設",
    learning1Assumed: "在 AWS Lake Formation 設了列級過濾器後，每個客戶就只能看到自己的資料。",
    learning1Found: "Glue Table 的向下相容設定和 Athena 可以直接存取 S3 的權限，讓這個過濾器形同虛設。",
    changedLabel: "架構修正",
    learning1Changed: "把 Glue Table 上預設的 IAM_ALLOWED_PRINCIPALS 權限移除，拿掉分析師帳號直接讀取 S3 檔案的權限，並使用正向／反向邏輯的雙重驗證。",
    learning1Takeaway: "租戶隔離的資安測試只有在走後門也失敗時，才算真正生效。",
    learning2Title: "同一個異常，第一天會響，第三天可能不再響。",
    learning2Assumed: "只要 DAU 持續低迷，EWMA detector 就會持續認為它異常。",
    learning2Day1: "約 3.9σ → ALERT",
    learning2Day3Strong: "2 個低迷日已進入 window",
    learning2Day3: "baseline 下移、標準差擴大 → NO ALERT",
    learning2Changed: "將目前 detector 明確定義為 onset detection：負責盡早觸發第一次調查，不假裝它同時管理持續事件狀態；production 若要持續告警，需另保留不會適應的 reference baseline。",
    learning2Takeaway: "偵測「事件開始」與追蹤「事件仍在發生」是兩個不同問題。",
    learning3Title: "Prompt 說不能洩漏，模型仍然洩漏了。",
    learning3Assumed: "以為只要在 System Prompt 裡面下達明確指令，LLM 就能 100% 聽話、不會洩漏內部機密。",
    learning3Leak: "“Document ID: [internal identifier]”",
    learning3Changed: "導入確定性驗證器：在 AI 產生的文字發送給客戶之前，先經過一道用傳統程式碼寫死的驗證過濾器；只要掃描到違規內容就自動調整。",
    learning3Audit: "讀寫分離的稽核路徑：完整的洩漏證據只保留在內部安全的 Log 中供工程師除錯，不發給外部使用者。",
    learning3Takeaway: "Prompt 只是軟性要求，程式碼驗證器才是硬性的實體邊界。",
    evidenceKicker: "CLAIMS NEED EVIDENCE",
    evidenceTitle: "工程驗證與架構文件",
    evidenceIntro: "包含單元測試結果、AWS 成本紀錄與核心設計文件。",
    evidenceTests: "測試通過率（100%）",
    evidenceCost: "雲端實測成本 Snapshot",
    evidenceTestsNote: "離線單元測試、資安邊界與 CDK assertions",
    evidenceCostNote: "2026-07-29 已部署基線的 Cost Explorer 紀錄",
    architectureLink: "Architecture & trade-offs",
    costLink: "Cost evidence & scale model",
    isolationLink: "Tenant isolation proof",
    lessonsLink: "Designs changed by testing",
    scopeTitle: "Honest scope",
    scopeBody: "這是使用 synthetic data 的 verified PoC。成片中的四組 AWS 操作路徑已於 2026-08-02 實際操作驗證；本專案仍不宣稱 production workload 經驗。",
    closingKicker: "THE TAKEAWAY",
    closingTitle: "如何在實際需求與限制中，評估並設計最合適的 AWS 服務組合。",
    closingBody: "本專案的核心價值在於：將營運痛點轉化為系統化治理、確保關鍵決策的人工主導權，並在擴充架構前，嚴格評估成本與團隊落地門檻。",
    exploreRepo: "Explore the repository",
    backTop: "回到頂部",
    footerNote: "Synthetic data · Verified PoC · Public repository",
    languageChanged: "已切換為繁體中文",
  },
  en: {
    pageTitle: "Leon Lai · AWS Solutions Architect Portfolio",
    pageDescription: "A governed, cost-conscious AWS architecture connecting cloud data and AI capabilities to four recurring operating pain points.",
    skip: "Skip to main content",
    navProblems: "Problems",
    navArchitecture: "Architecture",
    navWorkflows: "Workflows",
    navDemo: "Demo",
    navEvidence: "Evidence",
    heroEyebrow: "LEON LAI · BUSINESS-FIRST AWS SA PORTFOLIO",
    heroTitle1: "One cloud system architecture,",
    heroTitle2: "solving four practical operating pain points.",
    heroLede: "Built primarily on serverless services, the design combines shared data, access boundaries and cost controls to address anomaly detection, experiment operations, ad-hoc analytics and partner integration support.",
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
    problemsTitle: "Cloud and AI technology, connected to practical pain points.",
    problemsIntro: "Architecture design and PoC validation focus on four recurring situations that historically consumed team capacity.",
    m1Short: "Anomaly / quality signals",
    p1Title: "Without active monitoring, discovery stays reactive.",
    p1Body: "Data was not actively monitored. When engagement or conversion dropped, the team waited for someone to notice before investigation began. Reviews of known data-quality signals also lacked a consistent, traceable evidence format.",
    m2Short: "Experiment operations",
    p2Title: "Parallel experiment status lived in people's heads.",
    p2Body: "When different product experiences ran A/B tests at the same time, there was no central way to see their status. People had to ask each owner or wait for the stand-up.",
    p2SecondaryIntro: "That core problem came with two smaller issues that kept adding operating cost:",
    p2Secondary1: "SRM and guardrails were spot-checked manually, delaying abnormal experiment stops.",
    p2Secondary2: "Shared data features were rebuilt by different owners.",
    m3Short: "Ad-hoc analytics",
    p3Title: "Dashboards did not answer a sudden “why?”",
    p3Body: "Dashboards handled fixed questions, but they could not directly answer an executive, commercial lead or client asking, “Why did the core KPI drop today?”",
    p3Impact: "These questions were urgent and arrived at unpredictable times, increasing analyst workload. As the client base grew, so did their frequency.",
    m4Short: "Integration support",
    p4Title: "Repeated integration questions consume support and engineering capacity.",
    p4Body: "Partners across time zones repeatedly ask about API authentication, webhooks, environment setup, service updates and maintenance. Common questions require repeated answers, while complex cases consume engineering time.",
    architectureKicker: "SYSTEM SHAPE & BOUNDARIES",
    architectureTitle: "Three workflows share the lake. The fourth follows a separate knowledge path.",
    architectureIntro: "A complete system shape integrating shared data definitions, multi-tenant isolation and RAG-assisted decision support.",
    sourceLabel: "INPUT",
    foundationMapKicker: "END-TO-END DATA FOUNDATION",
    foundationMapTitle: "Data generation, governance and publication path",
    sourceStageBody: "Simulated client SDK events and replayable scenarios",
    bronzeStageBody: "Raw JSON · date and tenant partitions",
    directBatchBadge: "Direct batch write · zero idle compute",
    transformStageBody: "Schema cast · cleaning · rerunnable transforms",
    silverStageBody: "Typed Parquet events",
    silverBadge: "Source for analytics and known quality features",
    goldStageBody: "daily/hourly KPI · retention · entity features · experiment data",
    publicationBadge: "Publication marker proves a complete version",
    catalogControl: "Fixes the Bronze → Silver → Gold structure and field definitions",
    tenantControl: "Applies row-level data cell filters by client_site_id",
    queryControl: "Isolates query results and caps each scan at 1 GB",
    definitionControl: "One metric and feature definition set serves M1, M2 and M3",
    moduleMapKicker: "AUTOMATION & DECISION PATHS",
    moduleMapTitle: "How four modules consume data and deliver outcomes",
    architectureM1Title: "Usage anomaly and quality-signal detection",
    architectureM1Body: "Daily engagement, weekly retention and two-signal quality checks; alerts automatically trigger M3 first-look, while ambiguous records follow a separate human-review path.",
    architectureM2Title: "Experiment lifecycle and safety stops",
    architectureM2Body: "Lambda runs assignment, SRM, guardrail, analysis and readout; Gold features and registry state together determine whether an experiment continues.",
    architectureM2Branch: "SRM hard fail · hourly guardrail · allocation kill switch",
    architectureM3Title: "Governed Q&A and incident first look",
    architectureM3Body: "Guardrails and allow-listed templates bound the question space. SQL owns every number; unsupported work becomes a DynamoDB ticket.",
    architectureM3Branch: "Grounded answer · first-look report · durable ticket",
    architectureM4Title: "Identity-isolated integration support",
    architectureM4Body: "IAM identity limits the available support knowledge. In-scope questions must pass scope and safety checks before an answer is generated; insufficient input triggers clarification, while unsupported questions are refused or opened as a ticket.",
    architectureM4Branch: "No Gold-table access · SNS/SQS is account-local audit only",
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
    wf1Title: "KPI anomalies & known quality signals",
    wf1Before: "People checked reports and began investigation after noticing a drop; known data-quality reviews also lacked consistent evidence.",
    wf1System: "Daily engagement and known two-signal quality checks, plus weekly mature D1/D7 cohort retention checks, emit baselines, thresholds and evidence.",
    wf1Human: "People identify root cause and choose the operational response; ambiguous records enter human review and are never automatically judged by the system.",
    wf1OpsLabel: "SCAN & ALERT WINDOW",
    wf1Ops: "Daily KPI checks inspect only the latest complete publication and use up to 20 prior days as baseline. Hourly guardrails read gold_hourly_kpi. A successful run records published_at progress, and only a newly republished version is re-evaluated.",
    wf3Title: "Analytics NL Assistant",
    wf3Before: "Sudden what/why questions interrupted analysts. They first had to calculate the normal baseline, split the issue by product, and then cross-check related variables to locate what went wrong.",
    wf3System: "Allow-listed SQL answers what; first-look and diagnose assemble evidence for why; unsupported work becomes a durable ticket.",
    wf3Human: "People interpret operating context, confirm root cause and choose what to do next.",
    wf3ScopeLabel: "ANSWER QUALITY CONTROL",
    wf3Scope: "Answers come only from governed KPIs and allow-listed templates. Unsupported work becomes a ticket instead of arbitrary SQL, and ungoverned region/individual-user dimensions stay out of scope.",
    wf2Title: "Experiment operations platform",
    wf2Before: "Parallel experiment status lived in people and stand-ups; SRM and guardrails were manual, and shared features were rebuilt.",
    wf2System: "A central registry, IAM-based ownership, sample-ratio mismatch checks (SRM), safety guardrail monitoring, an emergency allocation kill switch and a shared feature registry.",
    wf2Human: "People choose hypotheses and metrics, decide whether to trust a result, and own the product response.",
    wf2StateLabel: "STATE TRIGGERS & STORAGE",
    wf2State: "Experiments follow a governed automated workflow rather than an engineer uploading a data package. An authorized owner uses an authenticated API or CLI to create a draft, configure the experiment and start it. DynamoDB stores the latest state, while Streams sync an S3/Athena snapshot for the dashboard to refresh every 15 seconds. Step Functions then runs the workflow with hourly protection checks. The current PoC records created, started, stopped and analyzed timestamps, but it does not yet retain a complete immutable event history for every state transition.",
    wf4Title: "Governed integration support",
    wf4Before: "Partners repeated the same integration and service questions, while complex requests reached engineering without structured context.",
    wf4System: "The system authenticates the partner with IAM and checks whether the question is within the supported scope. Qualified questions use restricted knowledge and AWS Bedrock to produce an answer; missing details trigger clarification, while out-of-scope questions are explicitly refused.",
    wf4Human: "An OPEN ticket is created only when product or engineering judgement is required, or when safety validation fails. The PoC stores tickets in DynamoDB but does not yet send Email, Slack or CRM notifications.",
    wf4RagLabel: "RAG PATH & PRODUCTION SWAP",
    wf4Rag: "The PoC simply gives a small set of test files to the AI. Production content needs version and permission tags; as the document set grows, Chunking and vector search can form a full-scale RAG architecture.",
    demoKicker: "FOUR CHAPTERS · TWO MINUTES",
    demoTitle: "Two-minute hands-on demo: four workflows in action.",
    demoIntro: "Open and operate all four module interfaces, trigger each scenario, and show the resulting AWS response.",
    demoVideoTitle: "Hands-on subtitled cut · 02:00",
    demoVideoNote: "AWS paths operated live on 2026-08-02 · 1080p · silent cut",
    demoVideoDownload: "Download captions",
    demoM1: "M1 · Detect",
    demoM1Time: "23 sec",
    demoM3: "M3 · Investigate",
    demoM3Time: "22 sec",
    demoM2: "M2 · Experiment Ops",
    demoM2Time: "32 sec",
    demoM4: "M4 · Integration Support",
    demoM4Time: "27 sec",
    demoPainLabel: "PAIN",
    demoResultLabel: "RESULT",
    demoHumanLabel: "HUMAN DECISION",
    loopDetect: "Detect",
    loopFirstLook: "First look",
    loopInvestigate: "Investigate",
    loopAct: "Act",
    loopValidate: "Validate",
    loopNote: "This loop covers KPI and retention anomalies only. Known quality signals follow a separate flagged records → human review path; M2 appears only when a controlled experiment is the right validation method.",
    decisionsKicker: "SYSTEM DESIGN TRADE-OFFS & COST OPTIMIZATION",
    decisionsTitle: "System design trade-offs and cost optimization.",
    decisionsIntro: "Usage frequency, latency needs and service completeness determine the right AWS capability now; measured changes trigger the next upgrade.",
    decision1Category: "WORKLOAD ECONOMICS",
    decision1Title: "Which compute model fits the current usage frequency?",
    currentLightweightLabel: "CURRENT COST-SAVING / LIGHTWEIGHT APPROACH",
    currentControlLabel: "CURRENT CONTROL-FIRST APPROACH",
    adjustWhenLabel: "WHEN SHOULD THIS CHANGE?",
    decision1Situation: "Situation: Data volume is small and users query only occasionally.",
    decision1Action: "Approach: Use pay-per-request or scale-to-zero components such as Lambda and Athena. An hourly-billed streaming component such as Kinesis appears only in short demonstrations instead of staying on and burning budget.",
    decision1Trigger: "Change when sustained high concurrency reaches hundreds of simultaneous users, throughput becomes consistently large, or the business requires data processing in under one minute.",
    decision1Upgrade: "👉 Upgrade: Only then introduce always-on Redshift (data warehouse), EMR (Spark cluster) or Persistent Kinesis (long-running data stream).",
    decision2Category: "DATA ACCESS PATTERN",
    decision2Title: "Does the current need require real-time service, or is batch processing enough?",
    decision2Situation: "Situation: Data and features currently support batch analysis, such as a daily run. The partner document library is small enough to place directly in the AI prompt.",
    decision2Action: "Approach: Do not add a real-time serving system or vector retrieval system yet.",
    decision2Trigger: "Change when a front-end application such as recommendations needs millisecond feature lookups, or the company document set becomes too large to place in the AI prompt as a whole.",
    decision2Upgrade: "👉 Upgrade: Only then introduce SageMaker Feature Store and OpenSearch / Vector Store.",
    decision3Category: "MANAGED WORKFLOW VS CONTROL",
    decision3Title: "Use a ready-made AI suite, or build the workflow and keep direct control?",
    decision3Situation: "Situation: The PoC needs fine-grained security control.",
    decision3Action: "Approach: Build a narrow custom workflow in code to demonstrate SQL allow-list filtering, data ownership, tenant isolation and sensitive-data masking.",
    decision3Trigger: "Change when non-technical teams need full BI, visual reporting, enterprise search, content maintenance and permission-management interfaces—and engineering no longer wants to build the UI and access system from scratch.",
    decision3Upgrade: "👉 Upgrade: Only then introduce Amazon Quick and Amazon Q Business.",
    learningsKicker: "THREE IMPLEMENTATION TRAPS",
    learningsTitle: "Three small implementation traps worth sharing.",
    learning1Title: "A visible row filter did not prove tenant isolation.",
    assumedLabel: "THE NAIVE ASSUMPTION",
    learning1Assumed: "After configuring row-level filtering in AWS Lake Formation, each customer would only be able to see its own data.",
    learning1Found: "The Glue Table backward-compatibility setting and permission for Athena to access S3 directly could make the filter ineffective.",
    changedLabel: "ARCHITECTURE FIX",
    learning1Changed: "Remove the default IAM_ALLOWED_PRINCIPALS permission from the Glue Table, remove direct S3 file access from the analyst account, and verify both the allowed path and the denied bypass path.",
    learning1Takeaway: "A tenant-isolation security test is valid only when the back door fails too.",
    learning2Title: "The same anomaly alerted on day one—but not on day three.",
    learning2Assumed: "If DAU stayed depressed, the EWMA detector would keep treating it as abnormal.",
    learning2Day1: "about 3.9σ → ALERT",
    learning2Day3Strong: "2 depressed days entered the window",
    learning2Day3: "baseline fell, deviation widened → NO ALERT",
    learning2Changed: "Define this detector as onset detection: it starts the first investigation but does not pretend to manage persistent incident state. Production persistence would require a separate non-adapting reference baseline.",
    learning2Takeaway: "Detecting an incident's onset and tracking that it remains active are different problems.",
    learning3Title: "The prompt prohibited a leak. The model leaked anyway.",
    learning3Assumed: "I assumed that a clear System Prompt could make an LLM obey 100% of the time and never expose internal secrets.",
    learning3Leak: "“Document ID: [internal identifier]”",
    learning3Changed: "Deterministic validator: before AI-generated text reaches a customer, a hard-coded conventional filter scans it and automatically replaces policy-violating content.",
    learning3Audit: "Separated audit path: complete leakage evidence stays only in secure internal logs for engineering diagnostics and is never sent to external users.",
    learning3Takeaway: "A prompt is a soft request; the code validator is the hard enforcement boundary.",
    evidenceKicker: "CLAIMS NEED EVIDENCE",
    evidenceTitle: "Engineering Validation & Architecture Documents",
    evidenceIntro: "Includes unit-test results, AWS cost records and core design documents.",
    evidenceTests: "test pass rate (100%)",
    evidenceCost: "measured cloud cost snapshot",
    evidenceTestsNote: "Offline unit tests, security boundaries and CDK assertions",
    evidenceCostNote: "Cost Explorer record for the baseline deployed on 2026-07-29",
    architectureLink: "Architecture & trade-offs",
    costLink: "Cost evidence & scale model",
    isolationLink: "Tenant isolation proof",
    lessonsLink: "Designs changed by testing",
    scopeTitle: "Honest scope",
    scopeBody: "This is a verified PoC using synthetic data. The four AWS operation paths shown in the video were operated and verified on 2026-08-02; this project still makes no production-workload claim.",
    closingKicker: "THE TAKEAWAY",
    closingTitle: "Evaluate and design the right AWS service mix within real needs and constraints.",
    closingBody: "The project's core value is turning operational pain into systematic governance, preserving human ownership of critical decisions, and rigorously evaluating cost and team adoption thresholds before expanding the architecture.",
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
      pain: "活躍度／轉換表現下滑需要等人發現；已知品質訊號缺少一致、可解釋的調查證據。",
      result: "首日 KPI 下滑被標示；6 筆 scripted quality records 全數進入 REVIEW_REQUIRED。",
      terminal: [
        "$ run module1 demo --as-of 2026-06-10",
        "site_b / dau",
        "actual=91 · EWMA baseline=204 · deviation≈3.9σ",
        "status=ALERT · evidence_window=preserved",
        "",
        "data-quality review",
        "flagged=6/6 · decision=REVIEW_REQUIRED",
      ].join("\n"),
      human: "確認根因、選擇營運處置，並審查需要判讀的紀錄。",
      detailLabel: "掃描與告警窗口",
      detail: "每日 KPI 每 24 小時只檢查最新完整發布日；相同 published_at 不重複。成熟 D1／D7 留存另於每週一檢查最近的完整 cohort 週。",
    },
    m3: {
      title: "M3 / GOVERNED ANALYTICS OUTPUT",
      pain: "急迫的 what／why 問題會打斷分析師，得重新計算常態、拆分產品，再交叉比對相關變數。",
      result: "Allow-listed SQL 回答數字；first-look 在 alert 後自動整理基線與共變動。",
      terminal: [
        '$ ask "What was DAU for site_b on 2026-06-10?"',
        "category=answerable",
        "answer=91 active users",
        "direct Athena cross-check=91 · MATCH",
        "",
        "site_b first-look",
        "DAU 91 vs 7d avg 205.5714 (-55.73%)",
        "active users and sessions moved together",
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
        "clean_winner    state=analyzed · lift=431.58%",
        "                 caveats=SMALL_SAMPLE,LARGE_EFFECT",
        "hourly_guardrail state=stopped_early",
        "                 source=gold_hourly_kpi · threshold crossed",
        "srm_violation   state=stopped_early",
        "                 p=0.0 · analysis skipped",
        "grounding_check_passed=true",
      ].join("\n"),
      human: "判斷結果是否可信、要不要重跑，以及產品是否採納。",
      detailLabel: "狀態來源",
      detail: "具備權限的負責人透過驗證 API／CLI 建立與啟動；DynamoDB 保存最新狀態，Step Functions 與每小時監控寫入後續轉換。現有關鍵時間欄位可查，但還沒有完整不可竄改的狀態事件歷史。",
    },
    m4: {
      title: "M4 / 受治理的整合支援",
      pain: "重複的整合問題消耗支援資源；複雜案件缺少結構化脈絡就轉給工程師。",
      result: "系統先澄清、再回答或建立 ticket；模型洩漏被 code validator 擋下。",
      terminal: [
        "$ run integration-support demo",
        "ambiguous question → NEEDS_CLARIFICATION",
        "engineering case   → ESCALATION · ticket=created",
        "out-of-scope       → deterministic refusal",
        "",
        "model output       → internal identifier detected",
        "validation         → FAILED_SAFE",
        "identifier reaching partner → NONE",
      ].join("\n"),
      human: "OPEN ticket 標示真正需要產品判斷、工程變更或安全覆核的案件；PoC 尚未串接外部通知。",
      detailLabel: "RAG 上線準備",
      detail: "PoC 只把少量測試檔案交給 AI；正式文件需加入版本與權限標籤，文件增長後再加入 Chunking 與向量搜尋。",
    },
  },
  en: {
    m1: {
      title: "M1 / VERIFIED DEMO OUTPUT",
      pain: "Engagement and conversion drops waited for human discovery; known quality-signal reviews lacked consistent, explainable evidence.",
      result: "The first-day KPI drop was flagged; all six scripted quality records entered REVIEW_REQUIRED.",
      terminal: [
        "$ run module1 demo --as-of 2026-06-10",
        "site_b / dau",
        "actual=91 · EWMA baseline=204 · deviation≈3.9σ",
        "status=ALERT · evidence_window=preserved",
        "",
        "data-quality review",
        "flagged=6/6 · decision=REVIEW_REQUIRED",
      ].join("\n"),
      human: "Confirm root cause, choose an operating response and review ambiguous records.",
      detailLabel: "SCAN & ALERT WINDOW",
      detail: "Daily KPI checks run against the latest complete published date and do not repeat the same published_at. Mature D1/D7 retention checks the latest complete cohort week every Monday.",
    },
    m3: {
      title: "M3 / GOVERNED ANALYTICS OUTPUT",
      pain: "Urgent what/why questions interrupted analysts, forcing them to recalculate normal baselines, split results by product and cross-check related variables.",
      result: "Allow-listed SQL owns the number; first-look assembles baseline and co-movement evidence after an alert.",
      terminal: [
        '$ ask "What was DAU for site_b on 2026-06-10?"',
        "category=answerable",
        "answer=91 active users",
        "direct Athena cross-check=91 · MATCH",
        "",
        "site_b first-look",
        "DAU 91 vs 7d avg 205.5714 (-55.73%)",
        "active users and sessions moved together",
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
        "clean_winner    state=analyzed · lift=431.58%",
        "                 caveats=SMALL_SAMPLE,LARGE_EFFECT",
        "hourly_guardrail state=stopped_early",
        "                 source=gold_hourly_kpi · threshold crossed",
        "srm_violation   state=stopped_early",
        "                 p=0.0 · analysis skipped",
        "grounding_check_passed=true",
      ].join("\n"),
      human: "Decide whether the result is trustworthy, whether to rerun and whether the product should adopt it.",
      detailLabel: "STATE SOURCE",
      detail: "An authorized owner creates and starts experiments through an authenticated API/CLI. DynamoDB stores the latest state, while Step Functions and hourly monitoring write later transitions. Key timestamps exist, but a complete immutable state-event history does not yet.",
    },
    m4: {
      title: "M4 / GOVERNED INTEGRATION SUPPORT",
      pain: "Repeated integration questions consumed support capacity; complex cases reached engineers without structured context.",
      result: "The system clarifies, answers or creates a ticket; code blocks a model-authored internal identifier.",
      terminal: [
        "$ run integration-support demo",
        "ambiguous question → NEEDS_CLARIFICATION",
        "engineering case   → ESCALATION · ticket=created",
        "out-of-scope       → deterministic refusal",
        "",
        "model output       → internal identifier detected",
        "validation         → FAILED_SAFE",
        "identifier reaching partner → NONE",
      ].join("\n"),
      human: "OPEN tickets mark cases requiring product judgement, engineering change or safety review; the PoC does not yet send an external notification.",
      detailLabel: "RAG PRODUCTION SWAP",
      detail: "The PoC gives the AI a small set of test files. Production documents need version and permission tags; Chunking and vector search follow as the corpus grows.",
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

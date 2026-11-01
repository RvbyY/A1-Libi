# Feature checklist

Une case est cochée quand le cœur de la feature est implémenté et vérifié par des tests.
Quand une partie de la description manque encore, la ligne « Statut SensAI » commence par « Fait, avec une limite ».
Sous chaque feature, la ligne « Statut SensAI » indique ce qui est fait et renvoie vers la fiche de preuves
(code, tests à relancer, démonstration manuelle) et les user stories.

- [x] [B1] Functional CLI chatbot
  - The common starting point. A command-line chatbot connected to a local model via Ollama, with response
streaming and conversation history management within a session.
Real-world examples: Claude CLI, LM Studio terminal interfaces, some local chat scripts you'll find on
GitHub.
  - Statut SensAI : Fait. Preuves et user stories : [B1-socle-mvp.md](B1-socle-mvp.md).
- [x] [M1] Session Persistence & Profiles
  - Save and reload the messages history across distinct sessions, plus a persistent user profile (preferences,
custom instructions) auto-injected at init.
Real-world examples: ChatGPT's ”custom instructions”. A medical assistant that knows a user is allergic
to penicillin without them mentioning it every time. A code assistant that knows you work in Python without
you repeating it.
  - Statut SensAI : Fait. Preuves et user stories : [M1-persistance-profils.md](M1-persistance-profils.md).
- [ ] [M2] Token Budgeting & Semantic Compression
  - Count token consumption per turn against a set budget. As you approach the cap, trigger a sliding-window
summarization pass that condenses the oldest turns into a compact block, freeing space while preserving
critical facts.
Real-world examples: Claude Projects summarizing older exchanges to maintain coherence over long
working sessions. Customer support AI systems condensing a long ticket's history.
  - Statut SensAI : non implémenté.
- [ ] [M3] External Structured Memory
  - Move memory from flat files to a real database (SQLite/NoSQL). The agent reads, writes, and updates
structured records — facts, entities, relationships — through CRUD operations it drives itself across longterm interactions.
Real-world examples: A CRM AI that updates a client record throughout interactions. A research assistant that maintains an enriched fact base across sessions. ”Second Brain” architectures (coleam00/secondbrain-starter).
  - Statut SensAI : non implémenté.
- [ ] [M4] Artifact & State Document
  - The agent maintains a separate living document that it updates incrementally across turns, distinct from
the raw chat history. The document is a deliverable, not a transcript. The model must update the right
section without rewriting or corrupting the whole document each turn, and emit those edits in a parseable
form your code can apply.
Real-world examples: Claude maintaining a specification document updated with each exchange. Cursor
maintaining a codebase summary during a development session. A writing assistant building an article
section by section
  - Statut SensAI : non implémenté.
- [x] [T1] MCP
  - The model decides mid-generation to call an external function instead of answering: it emits a structured
request (tool name + arguments), your code executes it, returns the result, and the model continues with
it.
Real-world examples: Claude deciding to use its calculator when you ask a math question. A booking
agent calling a calendar API to check availability
This will be tested with both your own and a preexisting MCP tool.
  - Statut SensAI : Fait, avec une limite. L'appel d'outils fonctionne de bout en bout (requête structurée, exécution, résultat renvoyé au modèle, relance). Il manque un client MCP pour brancher un outil MCP existant, ce que demande le test. Preuves et user stories : [T1-appel-outils.md](T1-appel-outils.md).
  - Reste à faire : client MCP (JSON-RPC sur stdio : initialize, tools/list, tools/call), adaptateur `McpTool`, serveurs déclarés dans `config.yaml`, et notre propre serveur MCP. Détail dans la section « Ce qu'il reste à faire » de [T1-appel-outils.md](T1-appel-outils.md).
- [ ] [T2] Sandboxed Code Execution
  - Give the agent a sandboxed runtime (Docker or isolated subprocess) where it runs code it generated, captures stdout and tracebacks, and feeds them back to fix its own errors.
Real-world examples: ChatGPT Code Interpreter executing Python to analyze a CSV. Devin generating,
executing, and correcting code in an autonomous loop.
  - Statut SensAI : non implémenté.
- [ ] [T3] Web Search
  - Let the agent run a live web query, parse the results, and inject them into context.
Real-world examples: Perplexity AI citing web sources in real time. ChatGPT Search. A monitoring agent
tracking industry news and producing daily summaries.
  - Statut SensAI : non implémenté.
- [ ] [T4] FIle Access within Permissions
  - Filesystem operations (read, write, create... ) + A permission layer defining which files and directories the
agent may read or touch, checked before any filesystem operation.
Real-world examples: A code review agent authorized to read and write in /src. Claude Cowork requesting explicit permissions before accessing system folders.
  - Statut SensAI : non implémenté.
- [ ] [T5] Structured Output
  - Force the model to output valid JSON conforming to a defined schema, instead of free-form natural language prose.
Real-world examples: OpenAI's Structured Outputs API. Any pipeline that parses LLM responses to feed
a database or interface.
  - Statut SensAI : non implémenté.
- [ ] [R1] Basic RAG
  - Full pipeline: ingest local documents, chunk them, generate embeddings, store in a local vector store,
retrieve by semantic similarity, and inject the top chunks into context. The canonical way to give an agent
knowledge it was not trained on.
Real-world examples: A legal assistant answering from a contract database. Google's NotebookLM enabling conversation with uploaded documents. A support chatbot drawing from product documentation.
  - Statut SensAI : Partiel. Vectorisation, stockage et recherche sémantique sont faits sur les conversations. Il manque l'ingestion de documents locaux et leur découpage en fragments. Preuves et user stories : [R1-rag-basique.md](R1-rag-basique.md).
  - Reste à faire : lecture de fichiers locaux, découpage en fragments, table `DocumentChunk` vectorisée, bloc « Extraits de documents » dans le prompt et commande `/ingest`. Détail dans la section « Ce qu'il reste à faire » de [R1-rag-basique.md](R1-rag-basique.md).
- [ ] [R2] Advanced RAG
  - Extends R1 with reranking of retrieved chunks, metadata filtering, and per-chunk relevance scoring to drop
near-misses before they reach the context.
Real-world examples: An enterprise document search system filtering by date, author, and department
before answering. AI search engines combining vector retrieval and semantic reranking.
  - Statut SensAI : non implémenté.
- [ ] [A1] Reasoning Loops (ReAct)
  - A family of loops that make the model's thinking explicit and iterative. Central to agentic understanding.
Real-world examples: Claude's o1/o3 ”thinking” mode. Code generation systems that verify their own
output before proposing it. Anthropic's Constitutional AI uses a similar principle. Any context where reasoning traceability is as important as the result (medical, legal, financial).
  - Statut SensAI : non implémenté.
- [ ] [A2] Multi-Agent Orchestration
  - Multi-agent orchestration has several specialized agents coordinate on a task, passing work between
them.
Real-world examples: A support system routing technical questions to an expert agent and billing questions to a commercial agent. Production LLM Routers sending simple requests to lightweight models and
complex requests to powerful ones to optimize costs. Microsoft's AutoGen where agents debate to refine
a response. CrewAI where a researcher agent, a writer agent, and a critic agent collaborate on an article.
  - Statut SensAI : non implémenté.
- [x] [A3] Human-in-the-Loop
  - Before executing a critical or irreversible action, the agent suspends, presents its plan to the user, and only
proceeds after explicit confirmation.
Real-world examples: Claude Cowork asking for confirmation before modifying system files. Automated
trading agents presenting their strategy before execution. Any automation system where an irreversible
action is at stake.
  - Statut SensAI : Fait en CLI : l'outil et ses arguments sont affichés, et rien n'est exécuté sans réponse explicite `o`/`oui`. Dans la webapp, les actions critiques sont toujours refusées. Preuves et user stories : [A3-human-in-the-loop.md](A3-human-in-the-loop.md).
- [ ] [A4] Prompt Versioning
  - Treat prompts as versioned artifacts: each version timestamped, comparable, and rollback-able. Run
controlled comparisons and measure differences in quality, latency, or behavior.
Real-world examples: Every team maintaining production prompts uses some form of versioning. PromptLayer, Langfuse, and other LLM observability tools integrate this natively.
  - Statut SensAI : non implémenté.
- [ ] [A5] Persona
  - The agent's name, tone, role, and response scope are configurable without modifying the code. A configuration file is enough to turn the same system into a legal assistant or a mathematics tutor.
The system manages multiple distinct agent profiles, dynamically selectable and switchable at runtime
without clearing the conversation history — the agent changes persona mid-session while retaining full
context.
Real-world examples: A support system that routes to a technical agent or a commercial agent based on
the client profile. An educational platform with one agent per subject.
  - Statut SensAI : non implémenté.
- [ ] [A6] Semantic Cache
  - Cache responses and serve them directly for semantically similar queries (matched via embeddings), skipping the model entirely. Cuts latency and CPU load on repetitive requests.
Real-world examples: GPTCache, Redis AI's semantic cache. A support assistant that instantly answers
frequent questions without querying the model each time.
  - Statut SensAI : non implémenté.
- [ ] [A7] Automated Prompt Optimization
  - Build prompts dynamically from context: auto-selected few-shot examples, adaptive reformulation, or
iterative optimization against a quality signal.
Real-world examples: Stanford's DSPy which automatically optimizes prompt pipelines. Systems that
dynamically select the best few-shot examples based on the incoming request.
  - Statut SensAI : non implémenté.
- [ ] [EV1] Automated Eval & Hallucination Detection
  - A system automatically evaluates the quality of the agent's responses: relevance, coherence, source faithfulness. An LLM acts as judge and produces usable scores for comparing system versions. Unverifiable or
source-contradicted statements are identified and flagged.
Real-world examples: RAGAS for evaluating RAG pipelines. The internal benchmarks all AI teams use
to validate their changes before deployment. Princeton's FActScore evaluating response factuality. RAG
systems comparing responses to retrieved sources to detect discrepancies
  - Statut SensAI : Partiel. Un LLM juge détecte les réponses non fondées et les fait régénérer. Il manque les scores (pertinence, cohérence) utilisables pour comparer des versions. Preuves et user stories : [EV1-evaluation-automatique.md](EV1-evaluation-automatique.md).
  - Reste à faire : scores du juge (pertinence, cohérence, fidélité), réponse « non vérifiée » si le juge échoue, table des scores et script de comparaison sur un jeu de questions. Détail dans la section « Ce qu'il reste à faire » de [EV1-evaluation-automatique.md](EV1-evaluation-automatique.md).
- [ ] [EV2] Content & Privacy Guardrails
  - Interceptors on input and output. On input: detect and block unsafe or out-of-scope prompts before
they reach the model. On output: detect PII or other inapropriate content, and anonymize or refuse, per
configurable rules.
Real-world examples: OpenAI Moderation API content filters. Nvidia NeMo Guardrails. An HR assistant
that refuses to answer questions about individual colleagues' salaries. A medical assistant anonymizing
patient data before sending it to the model.
  - Statut SensAI : Partiel. Le filtre en entrée est fait (classification et blocage). Il manque le filtre en sortie (détection et anonymisation des données personnelles). Preuves et user stories : [EV2-guardrails.md](EV2-guardrails.md).
  - Reste à faire : filtre en sortie qui anonymise ou refuse (email, téléphone, IBAN…), règles dans `config.yaml`, option `--guardrail`, et retrait des règles contradictoires du prompt. Détail dans la section « Ce qu'il reste à faire » de [EV2-guardrails.md](EV2-guardrails.md).
- [ ] [EV3] Logging & Monitoring Dashboard
  - Structured logging of every interaction — prompt sent, response, tools called, latency, token counts —
feeding a simple metrics view (call volume, latency, error rate, drift over time).
Real-world examples: Langfuse, LangSmith, Helicone — all LLM observability tools are built on this principle. A dashboard that reveals a prompt modified yesterday has doubled average latency.
  - Statut SensAI : Partiel. Les étapes, la taille du prompt, les tokens et la durée des outils sont suivis, avec un visualiseur en direct. Il manque la journalisation structurée persistante et la vue des métriques dans le temps. Preuves et user stories : [EV3-monitoring.md](EV3-monitoring.md).
  - Reste à faire : table `InteractionLog` remplie à chaque tour, calcul des métriques (volume, latence, erreurs, tokens), onglet Monitoring dans la webapp et commande `/stats`. Détail dans la section « Ce qu'il reste à faire » de [EV3-monitoring.md](EV3-monitoring.md).
- [ ] [EV4] Adversarial Testing
  - A test suite that attacks your own agent: jailbreak attempts, prompt injections, malformed inputs. Documents where it breaks and where it holds.
Real-world examples: Anthropic, OpenAI, and Google red teams testing their models before deployment.
Public adversarial benchmarks (AdvBench, HarmBench)
  - Statut SensAI : non implémenté.
- [x] [X1] Web UI
  - A decoupled web frontend over the CLI backend: message input, streaming conversation display, live
token/context usage, basic agent switching, configuration... The backend logic stays unchanged.
  - Statut SensAI : Fait, avec une limite. Frontend Gradio découplé, réponse en streaming, configuration du pipeline. Il manque le changement d'agent et l'affichage des tokens consommés. Preuves et user stories : [X1-interface-web.md](X1-interface-web.md).
  - Reste à faire : affichage des tokens et du contexte après chaque réponse, changement d'agent (dépend de A5), boîte de confirmation pour les outils sensibles. Détail dans la section « Ce qu'il reste à faire » de [X1-interface-web.md](X1-interface-web.md).
- [ ] [X2] Branching - Resume & Interrupt
  - Resume: edit a past message and fork an alternative branch, preserving the original history.
Interrupt: abort a generation mid-stream and redirect it with new instructions without waiting for it to
finish.
Real-world examples: ChatGPT's and Claude's ”Edit message” button generating a new branch. Prompt
prototyping tools that allow exploring multiple directions from the same point. A long-form writing agent
whose direction can be corrected mid-stream without waiting for completion
  - Statut SensAI : non implémenté.
- [ ] [X3] Export & Publication
  - Export conversation history and artifacts to usable formats (JSON, Markdown, PDF), and generate a public,
no-auth link to view a shared conversation or artifact in a browser.
Real-world examples: ChatGPT's and Claude's ”Share conversation” button generating a public link. PDF
export of a working session for archiving or transmission.
  - Statut SensAI : non implémenté.
- [ ] [X4] Questions & Forms
  - Add a way for users to answer questions asked by your LLM in a seemless way
  - Statut SensAI : non implémenté.
- [ ] [X5] Scheduling
  - The agent can be set up to automatically execute tasks at defined intervals, without manual intervention.
Daily summaries, weekly reports, continuous monitoring.
Real-world examples: A monitoring agent sending a news summary every morning. A system monitoring
agent checking status every hour and alerting on anomalies.
  - Statut SensAI : Partiel. Les tâches (ponctuelles et récurrentes) sont créées et enregistrées, et le `TaskRunner` sait les exécuter, mais il n'est démarré ni par la CLI ni par la webapp. Preuves et user stories : [X5-planification.md](X5-planification.md).
  - Reste à faire : démarrer le `TaskRunner` dans un thread, lui donner sa propre session et un chat « Tâches planifiées », et prévenir l'utilisateur du résultat. Détail dans la section « Ce qu'il reste à faire » de [X5-planification.md](X5-planification.md).

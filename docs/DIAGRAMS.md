# Diagrams

Visual reference for the architecture and the main flows. Each diagram is a
rendered PNG plus its Mermaid source (which renders inline on GitHub/GitLab).
Regenerate the PNGs with `mmdc -i <file>.mmd -o <file>.png -b white`.

## System architecture

Two front doors (web app + MCP server) over one shared engine. The engine is the only thing that talks to PDC — read-only, over the public REST API — and to the LLM endpoint. PDC's internal stores (OpenSearch, MongoDB, BIDB) sit behind that API and are never touched directly.

![System architecture](diagrams/01-architecture.png)

<details><summary>Mermaid source</summary>

```mermaid
%% System architecture — two front doors over one shared engine
flowchart TB
  subgraph clients[" "]
    direction LR
    U1["Browser<br/>(analysts, stewards)"]
    U2["LLM / agent<br/>(Claude Desktop, IDE)"]
  end

  subgraph insights["Catalog Insights (you deploy this)"]
    direction TB
    WEB["Web app<br/>Flask · :5002<br/>dashboards · Designer · AI drawer"]
    MCP["MCP server<br/>:8765 / stdio<br/>tools: recommend · generate · save"]
    subgraph engine["Shared engine (app/)"]
      direction LR
      SEC["security.py<br/>auth · roles · audit"]
      PC["pdc_client.py<br/>read-only"]
      GEN["generator.py<br/>ground·validate·repair"]
      CAT["catalog.py<br/>snapshot + query library"]
      REC["recommend.py<br/>suggestions"]
    end
    WEB --> engine
    MCP --> engine
  end

  subgraph pdc["Pentaho Data Catalog (already exists)"]
    direction TB
    API["Public REST API"]
    OS[("OpenSearch<br/>search / facets")]
    MG[("MongoDB<br/>metadata<br/>→ FerretDB in 11.0")]
    BI[("BIDB<br/>JDBC / ODBC")]
    API --> OS
    API --> MG
    API --> BI
  end

  LLM["LLM endpoint<br/>Ollama (local GPU)<br/>or commercial API"]

  U1 --> WEB
  U2 --> MCP
  PC -- "HTTPS (read-only)" --> API
  GEN -- "complete()" --> LLM

  classDef store fill:#eef2f7,stroke:#9aa4b2,color:#14181f;
  classDef ours fill:#e3f1ef,stroke:#0f766e,color:#0a443f;
  classDef ext fill:#fbf1e2,stroke:#dd8a26,color:#5c3b00;
  class OS,MG,BI store; class WEB,MCP,SEC,PC,GEN,CAT,REC ours; class API,LLM ext;
```
</details>

## Dashboard spec lifecycle

The `.studio.json` spec is the single contract. Three producers (a prompt, the Designer, the standard templates) converge on one validated spec, which the Designer refines, the exporters turn into CDF/CDE/CDA, and the web app renders.

![Dashboard spec lifecycle](diagrams/02-spec-lifecycle.png)

<details><summary>Mermaid source</summary>

```mermaid
%% The dashboard spec is the single contract every path speaks
flowchart LR
  A["Natural-language<br/>prompt"] --> G
  B["Hand-built<br/>in Designer"] --> S
  C["Standard templates<br/>app/dashboards/*.studio.json"] --> S
  G["generator.py<br/>ground → generate"] --> V{"validate<br/>schema +<br/>catalog refs"}
  V -- errors --> R["repair once"] --> V
  V -- ok --> S["dashboard spec<br/>(.studio.json)"]
  S --> ED["Designer<br/>(human refines)"]
  S --> EX["Export<br/>CDF / CDE / CDA"]
  S --> UI["Renders in<br/>web app"]
  classDef spec fill:#e3f1ef,stroke:#0f766e,color:#0a443f;
  class S spec;
```
</details>

## LLM generate–validate–repair loop

Why generation is low-risk: the model targets one JSON schema, is grounded on the real query library, and every result is validated (schema + catalog references) with a single repair pass before it's returned.

![LLM generate–validate–repair loop](diagrams/03-generate-loop.png)

<details><summary>Mermaid source</summary>

```mermaid
%% LLM generate–validate–repair loop (low-risk because the target is one schema)
flowchart TB
  P["prompt + Query Library"] --> GR["GROUND<br/>real DA names + columns<br/>+ chart vocabulary + schema"]
  GR --> GEN["GENERATE<br/>provider.complete(json_mode)"]
  GEN --> VAL{"VALIDATE<br/>① JSON schema<br/>② query/columns exist?"}
  VAL -- "valid" --> OUT["return {spec, valid:true}"]
  VAL -- "errors (first time)" --> REP["REPAIR<br/>feed errors back once"]
  REP --> GEN
  VAL -- "errors (after repair)" --> OUTBAD["return {spec, valid:false, errors}"]
  classDef good fill:#e7f4ec,stroke:#1c8f4d,color:#0a3d1f;
  classDef bad fill:#fbeaea,stroke:#d64545,color:#5c1010;
  class OUT good; class OUTBAD bad;
```
</details>

## Suggest-then-build over MCP

The agentic loop: the host asks the MCP server to recommend dashboards from live scan/connection state, the user picks one, and generate → validate → save drops a new dashboard into the app. Saving requires the steward role and is audited.

![Suggest-then-build over MCP](diagrams/04-mcp-sequence.png)

<details><summary>Mermaid source</summary>

```mermaid
%% Suggest-then-build over MCP
sequenceDiagram
  participant U as User
  participant H as Host LLM (Claude)
  participant M as MCP server
  participant E as Shared engine
  participant P as PDC API

  U->>H: "What dashboards should we build?"
  H->>M: recommend_dashboards()
  M->>E: catalog_snapshot()
  E->>P: facets / data-sources (read)
  P-->>E: scan & connection state
  E-->>M: snapshot
  M-->>H: ranked suggestions (+ why, template, prompt)
  H-->>U: "S3 is 52% unowned — build Exposure · S3?"
  U->>H: "Yes, build it"
  H->>M: generate_dashboard(prompt)
  M->>E: ground → generate → validate
  E-->>M: {spec, valid}
  H->>M: save_dashboard(spec)
  Note over M: requires 'steward' role + audit
  M-->>H: saved → app/dashboards/sensitivity/
  H-->>U: "Done — it's in the Sensitivity section"
```
</details>

## Security model

One model enforced by both front doors: authenticate (none/apikey/jwt) → authorize (viewer < steward < admin) → audit → handler. The PDC service account stays read-only and scoped in PDC as the real backstop.

![Security model](diagrams/05-security-flow.png)

<details><summary>Mermaid source</summary>

```mermaid
%% One security model, enforced by both front doors
flowchart TB
  REQ["Request / tool call<br/>Authorization: Bearer …"] --> AUTH{"authenticate()<br/>mode: none / apikey / jwt"}
  AUTH -- "no / bad token" --> E401["401 Unauthorized<br/>(audited)"]
  AUTH -- "ok" --> PR["Principal<br/>id · role · source"]
  PR --> AUTHZ{"authorize(role)<br/>viewer < steward < admin"}
  AUTHZ -- "role too low" --> E403["403 Forbidden<br/>(audited: denied)"]
  AUTHZ -- "ok" --> AUD["audit(ok)"] --> H["handler / tool<br/>reads = viewer<br/>save·generate = steward"]
  H --> PDC["PDC service account<br/>(read-only, scoped in PDC)"]
  classDef bad fill:#fbeaea,stroke:#d64545,color:#5c1010;
  classDef ok fill:#e7f4ec,stroke:#1c8f4d,color:#0a3d1f;
  class E401,E403 bad; class AUD,H ok;
```
</details>

# ZorkBurr System Diagrams

## Orchestrator Loop

```mermaid
flowchart TD
    subgraph Phase0["Phase 0 — Setup"]
        S1[Create docs/orchestrator/]
        S2[Verify run_episode.py]
        S3[Start Burr tracker :7241]
        S4[Init journal.md]
        S5["Archive journal if >1500 lines<br/>(move old entries → journal_archive.md)"]
        S1 --> S2 --> S3 --> S4 --> S5
    end

    Phase0 --> Launch

    subgraph EpisodeLoop["Episode Loop"]
        Launch["Phase 1: Launch Episode<br/>uv run run_episode.py --max-turns 100<br/>stdout → run_log_epNN.txt"]
        Poll["Poll every 60s<br/>grep -c TURN + grep EPISODE_END"]

        Launch --> Poll

        subgraph Checkpoint["Phase 2: Checkpoint Review (every 25 turns)"]
            Metrics["Parse log: scores, locations,<br/>critic avg, rejection rate"]
            Burr["Query Burr scripts: trace,<br/>gameplay, learning, pathfinding"]
            Quality["Gameplay quality:<br/>LEARNING / DRIFTING / IGNORING<br/>(memory use, KB alignment,<br/>objective quality+pursuit,<br/>learning output quality,<br/>pathfinding coherence)"]
            Triggers["Check triggers: stuck loop,<br/>rejection spiral, early death,<br/>KB noise, stale objectives,<br/>memory noise, nav drift,<br/>retrying failed exits,<br/>map data corruption"]
            Journal["Append checkpoint → journal.md"]
            Metrics --> Burr --> Quality --> Triggers --> Journal
        end

        Poll -->|"25-turn boundary<br/>or EPISODE_END"| Checkpoint

        Decision{Trigger fired?}
        Checkpoint --> Decision

        Decision -->|No| Poll

        subgraph Improve["Phase 3: Improvement"]
            Kill[Kill running episode]
            Classify["Classify: BLOCKER or INCREMENTAL<br/>(one INCREMENTAL per episode;<br/>BLOCKERs can combine)"]
            Escalation{"3+ prior failed attempts<br/>on same root cause?"}
            Dispatch["Dispatch Opus subagent with:<br/>• problem diagnosis<br/>• log + Burr evidence<br/>• journal context<br/>• prior failed hypotheses"]
            DispatchCode["Shift subagent to investigate<br/>Python pipeline instead of prompts<br/>(include 3 failed hypotheses)"]
            Fixtures["Extract validation fixtures<br/>(problem + healthy turns)"]
            Edit2["Subagent edits ONE of:<br/>• prompts/*.md<br/>• pyproject.toml config"]
            Validate["Run validate_prompt.py<br/>(structural checks must pass;<br/>judge comparison output)<br/>Up to 3 attempts, else revert"]
            Review["Review diff:<br/>no game knowledge in prompts,<br/>one logical change,<br/>authorized files only,<br/>validation passed"]
            Commit2["Subagent commits + journals"]
            Kill --> Classify --> Escalation
            Escalation -->|No| Fixtures
            Escalation -->|Yes| DispatchCode
            Fixtures --> Dispatch --> Edit2 --> Validate --> Review --> Commit2
            DispatchCode --> Edit2
        end

        Decision -->|Yes| Improve

        subgraph Complete["Phase 4: Episode Complete"]
            Summary[Write episode summary]
            Trend["Update score trend table<br/>(via burr_episodes.py --last 10)<br/>+ mandatory trend analysis"]
            ResolvePending["Resolve ALL PENDING improvements<br/>→ IMPROVED / NEUTRAL / DEGRADED<br/>(grep both journal + archive)"]
            Revert["If DEGRADED → revert change"]
            KeyLearn{"Every 5 episodes?"}
            UpdateKL["Rewrite Key Learnings section:<br/>best score, bottleneck,<br/>what works, falsified hypotheses,<br/>open problems, subsystems investigated"]
            Summary --> Trend --> ResolvePending --> Revert --> KeyLearn
            KeyLearn -->|Yes| UpdateKL
        end

        Poll -->|EPISODE_END| Complete
        Improve --> Complete
        Complete -->|"Next episode<br/>(ep02, ep03...)"| Launch
    end

    Terminate["Terminate when:<br/>• User says stop, OR<br/>• 3 consecutive HEALTHY +<br/>score > previous best"]
    Complete --> Terminate
```

## Burr Turn Graph (Inside Each Episode)

```mermaid
flowchart TD
    subgraph Lifecycle["Episode Lifecycle (run_episode.py)"]
        Init["initialize_episode()<br/>(load KB, memories, map from disk)<br/>— called before graph starts"]
        Build["build_turn_app()<br/>(construct Burr graph)"]
        Init --> Build --> TurnGraph
        TurnGraph --> FIN["finalize_episode()<br/>(save KB, memories, map to disk)<br/>— called after graph halts"]
    end

    subgraph TurnGraph["Burr Turn Graph (11 action nodes)"]
        AC["assemble_context<br/>game state + memories + KB<br/>+ objectives + action history<br/>+ map + exits → prompt"]

        AC --> GA["generate_action<br/>(LLM proposes a command)"]

        GA --> EA["evaluate_action<br/>(critic LLM scores it)"]

        EA -->|"score ≥ threshold"| EX
        EA -->|"rejection_count ≥ max_rejections"| EX
        EA -->|"rejected (default → retry)"| GA

        EX["execute_action<br/>(send command to Jericho Z-machine)"]

        EX --> EI["extract_info<br/>(parse game response via LLM)"]
        EI --> RR["record_results<br/>(log turn, reset rejection count)"]
        RR --> RM["record_memory<br/>(LLM synthesizes memory<br/>if score/location/death changed)"]
        RM --> CO["check_objective_completion"]

        CO -->|game_over == True| TC["turn_complete (halt)"]
        CO -->|"turn_count > 0 AND<br/>turn_count % obj_interval == 0<br/>AND NOT game_over"| UO["update_objectives<br/>(LLM periodic)"]
        CO -->|default| AC

        UO -->|"turn_count % kb_interval == 0"| UK["update_knowledge<br/>(LLM periodic)"]
        UO -->|default| AC

        UK --> AC
    end
```

## Data Flow

```mermaid
flowchart LR
    subgraph LLM["LLM (API via Instructor)"]
        Agent[Agent model]
        Critic[Critic model]
        Memory[Memory synthesis]
        KB[Knowledge updater]
        Obj[Objective discovery]
    end

    subgraph BurrGraph["Burr State Machine"]
        States["Immutable state<br/>(S.* keys)"]
        Actions["Action nodes<br/>(11 nodes per turn)"]
    end

    subgraph Jericho["Jericho (Z-machine)"]
        Zork["zork1.z5 ROM<br/>Ground truth:<br/>location, score,<br/>inventory, game_over"]
    end

    subgraph Outputs["Outputs"]
        Stdout["stdout log<br/>(TURN lines)<br/>parsed by orchestrator"]
        Tracker["Burr tracker :7241<br/>full state snapshots<br/>agent reasoning"]
        Disk["Disk persistence<br/>data/knowledge.md<br/>data/memories.json<br/>data/map.json<br/>(cross-episode learning)"]
    end

    subgraph Orchestrator["Claude Code Orchestrator"]
        Monitor["Monitor &<br/>checkpoint review"]
        Subagent["Opus subagent<br/>(prompt/config edits)"]
    end

    LLM <-->|"structured Pydantic<br/>responses"| BurrGraph
    BurrGraph <-->|"commands ↔<br/>game state"| Jericho
    BurrGraph --> Stdout
    BurrGraph --> Tracker
    BurrGraph --> Disk
    Stdout --> Monitor
    Tracker --> Monitor
    Monitor -->|"trigger fired"| Subagent
    Subagent -->|"edit prompts/<br/>pyproject.toml"| LLM
    Disk -->|"loaded at<br/>episode start"| BurrGraph
```

## Learning Systems

```mermaid
flowchart TD
    subgraph PerTurn["Per-Turn Learning"]
        Action[Agent takes action] --> ScoreChange{Score, location,<br/>or death changed?}
        ScoreChange -->|Yes| Synthesize["record_memory<br/>(LLM synthesizes insight)"]
        ScoreChange -->|No| Skip[No memory recorded]
        Synthesize --> LocMem["memories_by_location<br/>(keyed by location_id)"]
    end

    subgraph Periodic["Periodic Learning (every N turns)"]
        ObjUpdate["update_objectives<br/>(every objective_update_interval turns)<br/>discover/refine goals"]
        KBUpdate["update_knowledge<br/>(every knowledge_update_interval turns)<br/>strategic summary from action history"]
    end

    subgraph CrossEpisode["Cross-Episode Persistence"]
        KBFile["data/knowledge.md"]
        MemFile["data/memories.json"]
        MapFile["data/map.json"]
        EpEnd["finalize_episode()<br/>(save to disk)"] --> KBFile
        EpEnd --> MemFile
        EpEnd --> MapFile
        KBFile -->|"initialize_episode()<br/>(load from disk)"| NextEp[Next episode start]
        MemFile --> NextEp
        MapFile --> NextEp
    end

    subgraph Context["assemble_context (fed to agent each turn)"]
        GameState["Game response +<br/>location + inventory"]
        MemView["Location memories<br/>(current + nearby)"]
        KBView["Knowledge base<br/>(strategic guidance)"]
        ObjView["Active objectives"]
        History["Recent action history"]
    end

    LocMem --> MemView
    KBUpdate --> KBView
    ObjUpdate --> ObjView

    Context -->|"formatted prompt"| Agent2["generate_action (LLM)"]
```

import streamlit as st
import json
import time
import os
import io
import sys
from datetime import datetime
from utils.cache import save, load, CACHE_DIR

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="VMARO Research Orchestrator", layout="wide")

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .main-title {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.4rem;
        font-weight: 700;
        margin-bottom: 0;
    }
    .subtitle {
        color: #888;
        font-size: 1rem;
        margin-top: -8px;
        margin-bottom: 24px;
    }
    .paper-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #2a2a4a;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 12px;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .paper-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(102, 126, 234, 0.15);
    }
    .paper-card h4 { color: #a78bfa; margin-bottom: 8px; }
    .paper-card .year-badge {
        display: inline-block;
        background: #7c3aed33;
        color: #c4b5fd;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 500;
    }
    .gap-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-left: 4px solid #f59e0b;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 10px;
        transition: transform 0.2s;
    }
    .gap-card:hover {
        transform: translateX(4px);
    }
    .score-big {
        font-size: 4rem;
        font-weight: 700;
        text-align: center;
        line-height: 1;
    }
    .score-label {
        text-align: center;
        font-size: 1rem;
        color: #888;
        margin-top: 4px;
    }

    /* Grant sections */
    .grant-section { margin-bottom: 20px; }
    .grant-section h3 {
        color: #a78bfa;
        border-bottom: 1px solid #2a2a4a;
        padding-bottom: 6px;
    }

    /* Pipeline stage badges */
    .stage-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
        margin: 3px 0;
    }
    .stage-complete {
        background: rgba(34, 197, 94, 0.15);
        color: #22c55e;
        border: 1px solid rgba(34, 197, 94, 0.3);
    }
    .stage-running {
        background: rgba(234, 179, 8, 0.15);
        color: #eab308;
        border: 1px solid rgba(234, 179, 8, 0.3);
        animation: pulse 1.5s ease-in-out infinite;
    }
    .stage-pending {
        background: rgba(100, 100, 100, 0.1);
        color: #666;
        border: 1px solid rgba(100, 100, 100, 0.2);
    }
    .stage-error {
        background: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }

    div[data-testid="stMetricValue"] { font-size: 3rem; }

    /* Smooth tab transitions */
    .stTabs [data-baseweb="tab-panel"] {
        animation: fadeIn 0.3s ease-in;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* Debug console styles */
    .debug-console {
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px;
        font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
        font-size: 0.78rem;
        max-height: 500px;
        overflow-y: auto;
        line-height: 1.6;
    }
    .log-line {
        padding: 2px 0;
        border-bottom: 1px solid #161b22;
    }
    .log-ts { color: #484f58; }
    .log-info { color: #58a6ff; }
    .log-warn { color: #d29922; }
    .log-error { color: #f85149; }
    .log-rate { color: #f0883e; font-weight: 600; }
    .log-ok { color: #3fb950; }
    .log-stage {
        color: #bc8cff;
        font-weight: 600;
        border-top: 1px solid #30363d;
        margin-top: 4px;
        padding-top: 4px;
    }
    .log-timing { color: #79c0ff; font-style: italic; }
</style>
""", unsafe_allow_html=True)

# ── Session State Init ───────────────────────────────────────────────────────
# All pipeline results are stored in session_state so they survive reruns.
RESULT_KEYS = ["papers", "tree", "qg1", "trends", "gaps", "qg2", "methodology", "grant", "novelty"]

if "pipeline_run" not in st.session_state:
    st.session_state.pipeline_run = False
if "pipeline_topic" not in st.session_state:
    st.session_state.pipeline_topic = ""
if "pipeline_errors" not in st.session_state:
    st.session_state.pipeline_errors = {}
if "stage_status" not in st.session_state:
    st.session_state.stage_status = {}
if "debug_logs" not in st.session_state:
    st.session_state.debug_logs = []
if "stage_timings" not in st.session_state:
    st.session_state.stage_timings = {}


class StreamCapture:
    """Captures stdout/print output and logs it with timestamps."""
    def __init__(self, original_stdout):
        self.original = original_stdout
        self.buffer = io.StringIO()

    def write(self, text):
        self.original.write(text)  # still print to terminal
        if text.strip():  # skip empty lines
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            line = text.strip()
            # Classify the log line
            if "429" in line:
                level = "rate"
            elif any(w in line.lower() for w in ["error", "failed", "fail", "invalid", "exception"]):
                level = "error"
            elif any(w in line.lower() for w in ["warning", "warn", "revise", "retry", "swapping", "unavailable", "503"]):
                level = "warn"
            elif any(w in line.lower() for w in ["pass", "complete", "success", "ok"]):
                level = "ok"
            elif line.startswith("["):
                level = "stage"
            else:
                level = "info"
            st.session_state.debug_logs.append((ts, level, line))

    def flush(self):
        self.original.flush()


def format_debug_html(logs):
    """Convert log tuples to styled HTML for the debug console."""
    if not logs:
        return '<div class="debug-console"><span class="log-info">No logs captured yet. Run the pipeline to see output.</span></div>'
    lines = []
    for ts, level, text in logs:
        lines.append(
            f'<div class="log-line">'
            f'<span class="log-ts">[{ts}]</span> '
            f'<span class="log-{level}">{text}</span>'
            f'</div>'
        )
    return '<div class="debug-console">' + ''.join(lines) + '</div>'

# Auto-load cached results on first visit
for key in RESULT_KEYS:
    if key not in st.session_state:
        cached = load(key)
        if cached:
            st.session_state[key] = cached
            st.session_state.pipeline_run = True
        else:
            st.session_state[key] = None

# Load topic from cache if available
if not st.session_state.pipeline_topic:
    topic_file = os.path.join(CACHE_DIR, "_topic.txt")
    if os.path.exists(topic_file):
        st.session_state.pipeline_topic = open(topic_file).read().strip()

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown('<p class="main-title">🔬 VMARO Research Orchestrator</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">AI-powered research pipeline — from literature to grant proposal in minutes</p>', unsafe_allow_html=True)

# ── Pipeline Stages Definition ───────────────────────────────────────────────
STAGES = [
    ("", "Literature Mining",       "papers"),
    ("", "Thematic Clustering",     "tree"),
    ("", "Quality Gate 1",          "qg1"),
    ("", "Trend Analysis",          "trends"),
    ("", "Gap Identification",      "gaps"),
    ("", "Quality Gate 2",          "qg2"),
    ("", "Methodology Design",     "methodology"),
    ("", "Grant Writing",          "grant"),
    ("", "Novelty Scoring",        "novelty"),
]

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Configuration")
    topic = st.text_input(
        "Research Topic",
        value=st.session_state.pipeline_topic,
        placeholder="e.g. Federated Learning in Healthcare"
    )

    st.markdown("---")
    run_btn = st.button("Run Analysis", use_container_width=True, type="primary")

    st.markdown("---")
    st.markdown("##### Pipeline Stages")

    # Show dynamic stage status
    for emoji, name, key in STAGES:
        status = st.session_state.stage_status.get(key, "pending")
        if status == "complete":
            badge_class = "stage-complete"
            icon = "[✓]"
        elif status == "running":
            badge_class = "stage-running"
            icon = "[>]"
        elif status == "error":
            badge_class = "stage-error"
            icon = "[X]"
        else:
            badge_class = "stage-pending"
            icon = "[ ]"
        st.markdown(
            f'<div class="stage-badge {badge_class}">{icon} {name}</div>',
            unsafe_allow_html=True
        )

    # Debug toggle
    st.markdown("---")
    st.markdown("##### Developer")
    show_debug = st.checkbox("Show Debug Console", value=True, key="show_debug")

    # Clear cache button
    st.markdown("---")
    if st.button("Clear Cache & Reset", use_container_width=True):
        import shutil
        if os.path.exists(CACHE_DIR):
            shutil.rmtree(CACHE_DIR)
        for key in RESULT_KEYS:
            st.session_state[key] = None
        st.session_state.pipeline_run = False
        st.session_state.pipeline_topic = ""
        st.session_state.pipeline_errors = {}
        st.session_state.stage_status = {}
        st.session_state.debug_logs = []
        st.session_state.stage_timings = {}
        st.rerun()

    if st.button("Clear Logs", use_container_width=True):
        st.session_state.debug_logs = []
        st.session_state.stage_timings = {}
        st.rerun()


# ── Helpers ──────────────────────────────────────────────────────────────────
def is_fallback(data, required_keys):
    """Check if result is a fallback/empty dict that shouldn't be cached."""
    if not data or not isinstance(data, dict):
        return True
    for k in required_keys:
        v = data.get(k)
        if v is None or v == "" or v == [] or v == {}:
            return True
    return False


def set_stage(key, status):
    """Update stage status in session state."""
    st.session_state.stage_status[key] = status


# ── Run Pipeline ─────────────────────────────────────────────────────────────
if run_btn:
    if not topic.strip():
        st.error("Please enter a research topic.")
        st.stop()

    # Clear cache if topic changed
    last_topic_file = os.path.join(CACHE_DIR, "_topic.txt")
    if os.path.exists(CACHE_DIR) and os.path.exists(last_topic_file):
        prev_topic = open(last_topic_file).read().strip()
        if prev_topic != topic.strip():
            import shutil
            shutil.rmtree(CACHE_DIR)
            for key in RESULT_KEYS:
                st.session_state[key] = None

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(last_topic_file, "w") as f:
        f.write(topic.strip())

    st.session_state.pipeline_topic = topic.strip()
    st.session_state.pipeline_errors = {}
    st.session_state.stage_status = {}
    st.session_state.debug_logs = []
    st.session_state.stage_timings = {}

    # Start capturing stdout for the debug console
    _original_stdout = sys.stdout
    sys.stdout = StreamCapture(_original_stdout)

    # Lazy imports
    from agents.literature_agent import run as run_literature
    from agents.tree_agent import run as run_tree
    from agents.trend_agent import run as run_trend
    from agents.gap_agent import run as run_gap
    from agents.methodology_agent import run as run_methodology
    from agents.grant_agent import run as run_grant
    from agents.novelty_agent import run as run_novelty
    from utils.quality_gate import evaluate_quality

    progress_bar = st.progress(0, text="Initializing pipeline...")
    status_container = st.status("🚀 **Running VMARO Pipeline**", expanded=True)

    total = len(STAGES)

    def update_progress(step_idx, label):
        pct = int((step_idx / total) * 100)
        progress_bar.progress(pct, text=f"Stage {step_idx}/{total} — {label}")

    with status_container:
        # ── Stage 1: Literature ──
        set_stage("papers", "running")
        update_progress(1, "Literature Mining")
        st.write("**Fetching papers sequentially**: Semantic Scholar → arXiv → CrossRef → OpenAlex...")
        _t0 = time.time()
        try:
            papers = load("papers")
            if papers and not is_fallback(papers, ["papers"]):
                st.write("  ↳ _Loaded from cache_")
            else:
                papers = run_literature(topic)
                if not is_fallback(papers, ["papers"]):
                    save("papers", papers)
                time.sleep(1)
            st.session_state.papers = papers
            n_papers = len(papers.get("papers", []))
            st.write(f"  ↳ Retrieved **{n_papers} papers**")
            set_stage("papers", "complete")
        except Exception as e:
            st.write(f"  ↳ Error: {e}")
            st.session_state.pipeline_errors["papers"] = str(e)
            set_stage("papers", "error")
        st.session_state.stage_timings["papers"] = round(time.time() - _t0, 1)

        # ── Stage 2: Tree ──
        set_stage("tree", "running")
        update_progress(2, "Thematic Clustering")
        st.write("**Clustering** papers into thematic groups...")
        _t0 = time.time()
        try:
            tree = load("tree")
            if tree and not is_fallback(tree, ["themes"]):
                st.write("  ↳ _Loaded from cache_")
            else:
                papers_data = st.session_state.papers or {"topic": topic, "papers": []}
                tree = run_tree(papers_data)
                if not is_fallback(tree, ["themes"]):
                    save("tree", tree)
                time.sleep(1)
            st.session_state.tree = tree
            n_themes = len(tree.get("themes", []))
            st.write(f"  ↳ Built **{n_themes} themes**")
            set_stage("tree", "complete")
        except Exception as e:
            st.write(f"  ↳ Error: {e}")
            st.session_state.pipeline_errors["tree"] = str(e)
            set_stage("tree", "error")
        st.session_state.stage_timings["tree"] = round(time.time() - _t0, 1)

        # ── Stage 3: Quality Gate 1 ──
        set_stage("qg1", "running")
        update_progress(3, "Quality Gate 1")
        st.write("**Quality Gate 1** — evaluating literature tree...")
        _t0 = time.time()
        try:
            qg1 = load("qg1")
            if qg1 and not is_fallback(qg1, ["decision", "confidence"]):
                st.write("  ↳ _Loaded from cache_")
            else:
                tree_data = st.session_state.tree or {}
                qg1 = evaluate_quality("post_literature", tree_data)
                if not is_fallback(qg1, ["decision", "confidence"]):
                    save("qg1", qg1)
                time.sleep(1)
            st.session_state.qg1 = qg1
            qg1_decision = qg1.get("decision", "?")
            qg1_conf = qg1.get("confidence", 0)
            st.write(f"  ↳ Gate: **{qg1_decision}** (confidence {qg1_conf})")
            set_stage("qg1", "complete")
        except Exception as e:
            st.write(f"  ↳ Error: {e}")
            st.session_state.pipeline_errors["qg1"] = str(e)
            set_stage("qg1", "error")
        st.session_state.stage_timings["qg1"] = round(time.time() - _t0, 1)

        # ── Stage 4: Trends ──
        set_stage("trends", "running")
        update_progress(4, "Trend Analysis")
        st.write("**Analyzing trends** in the research landscape...")
        _t0 = time.time()
        try:
            trends = load("trends")
            if trends and not is_fallback(trends, ["dominant_clusters", "emerging_trends"]):
                st.write("  ↳ _Loaded from cache_")
            else:
                tree_data = st.session_state.tree or {}
                trends = run_trend(tree_data)
                if not is_fallback(trends, ["dominant_clusters", "emerging_trends"]):
                    save("trends", trends)
                time.sleep(1)
            st.session_state.trends = trends
            st.write(f"  ↳ Found **{len(trends.get('dominant_clusters', []))} clusters**, **{len(trends.get('emerging_trends', []))} trends**")
            set_stage("trends", "complete")
        except Exception as e:
            st.write(f"  ↳ Error: {e}")
            st.session_state.pipeline_errors["trends"] = str(e)
            set_stage("trends", "error")
        st.session_state.stage_timings["trends"] = round(time.time() - _t0, 1)

        # ── Stage 5: Gaps ──
        set_stage("gaps", "running")
        update_progress(5, "Gap Identification")
        st.write("**Identifying research gaps** at theme intersections...")
        _t0 = time.time()
        try:
            gaps = load("gaps")
            if gaps and not is_fallback(gaps, ["identified_gaps"]):
                st.write("  ↳ _Loaded from cache_")
            else:
                tree_data = st.session_state.tree or {}
                trends_data = st.session_state.trends or {}
                gaps = run_gap(tree_data, trends_data)
                if not is_fallback(gaps, ["identified_gaps"]):
                    save("gaps", gaps)
                time.sleep(1)
            st.session_state.gaps = gaps
            st.write(f"  ↳ Found **{len(gaps.get('identified_gaps', []))} gaps**, selected: **{gaps.get('selected_gap', '?')}**")
            set_stage("gaps", "complete")
        except Exception as e:
            st.write(f"  ↳ Error: {e}")
            st.session_state.pipeline_errors["gaps"] = str(e)
            set_stage("gaps", "error")
        st.session_state.stage_timings["gaps"] = round(time.time() - _t0, 1)

        # ── Stage 6: Quality Gate 2 ──
        set_stage("qg2", "running")
        update_progress(6, "Quality Gate 2")
        st.write("**Quality Gate 2** — evaluating gap analysis...")
        _t0 = time.time()
        try:
            qg2 = load("qg2")
            if qg2 and not is_fallback(qg2, ["decision", "confidence"]):
                st.write("  ↳ _Loaded from cache_")
            else:
                gaps_data = st.session_state.gaps or {}
                qg2 = evaluate_quality("post_gap", gaps_data)
                if not is_fallback(qg2, ["decision", "confidence"]):
                    save("qg2", qg2)
                time.sleep(1)
            st.session_state.qg2 = qg2
            qg2_decision = qg2.get("decision", "?")
            qg2_conf = qg2.get("confidence", 0)
            st.write(f"  ↳ Gate: **{qg2_decision}** (confidence {qg2_conf})")
            set_stage("qg2", "complete")
        except Exception as e:
            st.write(f"  ↳ Error: {e}")
            st.session_state.pipeline_errors["qg2"] = str(e)
            set_stage("qg2", "error")
        st.session_state.stage_timings["qg2"] = round(time.time() - _t0, 1)

        # ── Stage 7: Methodology ──
        set_stage("methodology", "running")
        update_progress(7, "Methodology Design")
        st.write("**Designing experimental methodology** for the selected gap...")
        _t0 = time.time()
        try:
            methodology = load("methodology")
            if methodology and not is_fallback(methodology, ["suggested_datasets", "experimental_design"]):
                st.write("  ↳ _Loaded from cache_")
            else:
                gaps_data = st.session_state.gaps or {}
                selected_gap_id = gaps_data.get("selected_gap", "")
                gap_desc = next(
                    (g["description"] for g in gaps_data.get("identified_gaps", []) if g.get("gap_id") == selected_gap_id),
                    selected_gap_id
                )
                methodology = run_methodology(gap_desc, topic)
                if not is_fallback(methodology, ["suggested_datasets", "experimental_design"]):
                    save("methodology", methodology)
                time.sleep(1)
            st.session_state.methodology = methodology
            st.write(f"  ↳ Methodology ready — **{len(methodology.get('suggested_datasets', []))} datasets**, **{len(methodology.get('baseline_models', []))} baselines**")
            set_stage("methodology", "complete")
        except Exception as e:
            st.write(f"  ↳ Error: {e}")
            st.session_state.pipeline_errors["methodology"] = str(e)
            set_stage("methodology", "error")
        st.session_state.stage_timings["methodology"] = round(time.time() - _t0, 1)

        # ── Stage 8: Grant ──
        set_stage("grant", "running")
        update_progress(8, "Grant Writing")
        st.write("**Drafting grant proposal**...")
        _t0 = time.time()
        try:
            grant = load("grant")
            if grant and not is_fallback(grant, ["problem_statement", "proposed_methodology"]):
                st.write("  ↳ _Loaded from cache_")
            else:
                gaps_data = st.session_state.gaps or {}
                selected_gap_id = gaps_data.get("selected_gap", "")
                gap_desc = next(
                    (g["description"] for g in gaps_data.get("identified_gaps", []) if g.get("gap_id") == selected_gap_id),
                    selected_gap_id
                )
                meth_data = st.session_state.methodology or {}
                grant = run_grant(topic, gap_desc, meth_data)
                if not is_fallback(grant, ["problem_statement", "proposed_methodology"]):
                    save("grant", grant)
                time.sleep(1)
            st.session_state.grant = grant
            st.write("  ↳ Grant proposal drafted")
            set_stage("grant", "complete")
        except Exception as e:
            st.write(f"  ↳ Error: {e}")
            st.session_state.pipeline_errors["grant"] = str(e)
            set_stage("grant", "error")
        st.session_state.stage_timings["grant"] = round(time.time() - _t0, 1)

        # ── Stage 9: Novelty ──
        set_stage("novelty", "running")
        update_progress(9, "Novelty Scoring")
        st.write("**Scoring novelty** against existing literature...")
        _t0 = time.time()
        try:
            novelty = load("novelty")
            if novelty and not is_fallback(novelty, ["closest_papers", "score_justification"]):
                st.write("  ↳ _Loaded from cache_")
            else:
                grant_data = st.session_state.grant or {}
                tree_data = st.session_state.tree or {}
                novelty = run_novelty(grant_data, tree_data)
                if not is_fallback(novelty, ["closest_papers", "score_justification"]):
                    save("novelty", novelty)
                time.sleep(1)
            st.session_state.novelty = novelty
            score = novelty.get("novelty_score", 0)
            st.write(f"  ↳ Novelty score: **{score}/100**")
            set_stage("novelty", "complete")
        except Exception as e:
            st.write(f"  ↳ Error: {e}")
            st.session_state.pipeline_errors["novelty"] = str(e)
            set_stage("novelty", "error")
        st.session_state.stage_timings["novelty"] = round(time.time() - _t0, 1)

    # Restore stdout
    sys.stdout = _original_stdout

    progress_bar.progress(100, text="Pipeline complete!")
    status_container.update(label="**Pipeline Complete**", state="complete", expanded=False)
    st.session_state.pipeline_run = True
    st.balloons()


# ══════════════════════════════════════════════════════════════════════════════
#  RESULTS DISPLAY  (reads from session_state, survives reruns)
# ══════════════════════════════════════════════════════════════════════════════

# Check if we have any results to display
has_results = st.session_state.pipeline_run and any(
    st.session_state.get(k) for k in RESULT_KEYS
)

if has_results:
    st.markdown("---")

    # Show errors if any
    if st.session_state.pipeline_errors:
        with st.expander("Pipeline Errors", expanded=False):
            for stage, err in st.session_state.pipeline_errors.items():
                st.error(f"**{stage}**: {err}")

    tabs = st.tabs([
        "Literature",
        "Tree Index",
        "Trends & Gaps",
        "Methodology",
        "Grant Proposal",
        "Novelty Score"
    ])

    display_topic = st.session_state.pipeline_topic or "Unknown"

    # ── Tab 1: Literature ────────────────────────────────────────────────────
    with tabs[0]:
        papers_data = st.session_state.papers or {}
        if papers_data:
            st.markdown("## Retrieved Literature")
            paper_list = papers_data.get("papers", [])
            st.caption(f"Topic: **{papers_data.get('topic', display_topic)}** · {len(paper_list)} papers")

            for p in paper_list:
                st.markdown(f"""
<div class="paper-card">
    <h4>{p.get('title', 'Unknown')}</h4>
    <span class="year-badge">{p.get('year', 'N/A')}</span>
    <p style="margin-top:10px; color:#ccc;">{p.get('summary', '')}</p>
    <p style="color:#a78bfa;"><strong>Contribution:</strong> {p.get('contribution', '')}</p>
    <a href="{p.get('url', '#')}" style="color:#667eea;">Source</a>
</div>
                """, unsafe_allow_html=True)
        else:
            st.info("No literature data available. Run the pipeline to generate results.")

    # ── Tab 2: Tree Index ────────────────────────────────────────────────────
    with tabs[1]:
        tree_data = st.session_state.tree or {}
        if tree_data:
            st.markdown("## Thematic Tree Index")
            st.markdown(f"**Root:** {tree_data.get('root', 'Unknown')}")

            for theme in tree_data.get("themes", []):
                with st.expander(f"{theme.get('theme_id')}: {theme.get('theme_name')}", expanded=True):
                    for idx, p in enumerate(theme.get('papers', [])):
                        title = p.get('title', p) if isinstance(p, dict) else p
                        year = p.get('year', '') if isinstance(p, dict) else ''
                        year_str = f" ({year})" if year else ""
                        st.markdown(f"&nbsp;&nbsp;&nbsp;{idx+1}. {title}{year_str}")

            st.markdown("### Emerging Directions")
            for d in tree_data.get("emerging_directions", []):
                st.markdown(f"- {d}")
        else:
            st.info("No tree data available. Run the pipeline to generate results.")

    # ── Tab 3: Trends & Gaps ─────────────────────────────────────────────────
    with tabs[2]:
        trends_data = st.session_state.trends or {}
        gaps_data = st.session_state.gaps or {}

        if trends_data or gaps_data:
            st.markdown("## Trends & Gaps")
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("### Dominant Clusters")
                for i, c in enumerate(trends_data.get("dominant_clusters", [])):
                    st.markdown(f"**{i+1}.** {c}")

                st.markdown("### Emerging Trends")
                for t in trends_data.get("emerging_trends", []):
                    st.info(f"{t}")

            with col2:
                st.markdown("### Identified Gaps")
                for g in gaps_data.get("identified_gaps", []):
                    st.markdown(f"""
<div class="gap-card">
    <strong style="color:#f59e0b;">{g.get('gap_id', '')}</strong>
    <p style="color:#e2e8f0; margin: 6px 0;">{g.get('description', '')}</p>
    <p style="color:#94a3b8; font-size:0.85rem;"><em>Why underexplored:</em> {g.get('why_underexplored', '')}</p>
</div>
                    """, unsafe_allow_html=True)

                selected = gaps_data.get('selected_gap', '?')
                st.success(f"**Selected Gap:** {selected}")
        else:
            st.info("No trends/gaps data available. Run the pipeline to generate results.")

    # ── Tab 4: Methodology ───────────────────────────────────────────────────
    with tabs[3]:
        meth = st.session_state.methodology or {}
        if meth:
            st.markdown("## Experimental Methodology")

            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("### Datasets")
                for d in meth.get("suggested_datasets", []):
                    st.markdown(f"- {d}")
            with c2:
                st.markdown("### Metrics")
                for m in meth.get("evaluation_metrics", []):
                    st.markdown(f"- {m}")
            with c3:
                st.markdown("### Baselines")
                for b in meth.get("baseline_models", []):
                    st.markdown(f"- {b}")

            st.markdown("### Experimental Design")
            st.markdown(meth.get("experimental_design", "_No design generated._"))

            st.markdown("### Tools & Frameworks")
            tools = meth.get("tools_and_frameworks", [])
            if tools:
                st.markdown(" · ".join([f"`{t}`" for t in tools]))
        else:
            st.info("No methodology data available. Run the pipeline to generate results.")

    # ── Tab 5: Grant Proposal ────────────────────────────────────────────────
    with tabs[4]:
        grant_data = st.session_state.grant or {}
        if grant_data:
            st.markdown("## Grant Proposal")

            sections = [
                ("Problem Statement", "problem_statement"),
                ("Proposed Methodology", "proposed_methodology"),
                ("Evaluation Plan", "evaluation_plan"),
                ("Expected Contribution", "expected_contribution"),
                ("Timeline", "timeline"),
                ("Budget Estimate", "budget_estimate"),
            ]
            for title, key in sections:
                content = grant_data.get(key, "")
                if content:
                    st.markdown(f'<div class="grant-section"><h3>{title}</h3><p>{content}</p></div>', unsafe_allow_html=True)

            st.markdown("---")
            col_dl1, col_dl2 = st.columns([1, 3])
            with col_dl1:
                st.download_button(
                    label="Download JSON",
                    data=json.dumps(grant_data, indent=2),
                    file_name=f"{display_topic.replace(' ', '_').lower()}_grant.json",
                    mime="application/json",
                    use_container_width=True
                )
        else:
            st.info("No grant proposal data available. Run the pipeline to generate results.")

    # ── Tab 6: Novelty Score ─────────────────────────────────────────────────
    with tabs[5]:
        nov = st.session_state.novelty or {}
        if nov:
            st.markdown("## Novelty Assessment")
            score = nov.get("novelty_score", 0)

            if score < 40:
                color, emoji, label = "#ef4444", "[LOW]", "Low Novelty"
            elif score < 70:
                color, emoji, label = "#eab308", "[MOD]", "Moderate Novelty"
            else:
                color, emoji, label = "#22c55e", "[HIGH]", "High Novelty"

            col_s1, col_s2 = st.columns([1, 2])
            with col_s1:
                st.markdown(f'<p class="score-big" style="color:{color};">{emoji} {score}</p>', unsafe_allow_html=True)
                st.markdown(f'<p class="score-label">{label} · out of 100</p>', unsafe_allow_html=True)

            with col_s2:
                st.markdown("### Justification")
                st.markdown(nov.get("score_justification", "_No justification available._"))

            st.markdown("### Similarity Reasoning")
            st.markdown(nov.get("similarity_reasoning", "_No reasoning available._"))

            st.markdown("### Closest Papers")
            closest = nov.get("closest_papers", [])
            if closest:
                for p in closest:
                    st.markdown(f"- {p}")
            else:
                st.caption("No closest papers identified.")
        else:
            st.info("No novelty data available. Run the pipeline to generate results.")

elif not st.session_state.pipeline_run:
    # ── Welcome Screen ──
    st.markdown("---")
    col_w1, col_w2, col_w3 = st.columns(3)
    with col_w1:
        st.markdown("""
        ### Literature Mining
        Fetch from **multiple academic databases** (Semantic Scholar, arXiv, CrossRef, OpenAlex, PubMed) with automatic deduplication.
        """)
    with col_w2:
        st.markdown("""
        ### Gap Analysis
        Identify underexplored intersections and select the most promising research gaps.
        """)
    with col_w3:
        st.markdown("""
        ### Grant Writing
        Generate a funding-ready research proposal with methodology and novelty scoring.
        """)
    st.markdown("---")
    st.markdown(
        '<p style="text-align:center; color:#888; font-size:1.1rem;">'
        'Enter a research topic in the sidebar and click <b>Run Analysis</b> to get started.'
        '</p>',
        unsafe_allow_html=True
    )

# ══════════════════════════════════════════════════════════════════════════════
#  DEBUG CONSOLE  (always at bottom when enabled)
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.get("show_debug", False):
    st.markdown("---")
    st.markdown("### Debug Console")

    # Stage timing summary
    timings = st.session_state.stage_timings
    if timings:
        st.markdown("#### Stage Timings")
        timing_cols = st.columns(min(len(timings), 5))
        stage_labels = {
            "papers": "Literature",
            "tree": "Tree",
            "qg1": "QG1",
            "trends": "Trends",
            "gaps": "Gaps",
            "qg2": "QG2",
            "methodology": "Methodology",
            "grant": "Grant",
            "novelty": "Novelty",
        }
        for i, (stage_key, elapsed) in enumerate(timings.items()):
            col_idx = i % min(len(timings), 5)
            with timing_cols[col_idx]:
                label = stage_labels.get(stage_key, stage_key)
                color = "#f85149" if elapsed > 30 else "#d29922" if elapsed > 10 else "#3fb950"
                st.markdown(
                    f'<div style="text-align:center;">'
                    f'<span style="font-size:1.6rem; font-weight:700; color:{color};">{elapsed}s</span><br>'
                    f'<span style="font-size:0.8rem; color:#888;">{label}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )
        total_time = sum(timings.values())
        st.caption(f"Total pipeline time: **{total_time:.1f}s**")

    # Log output
    st.markdown("#### Pipeline Logs")
    n_429 = sum(1 for _, level, _ in st.session_state.debug_logs if level == "rate")
    n_errors = sum(1 for _, level, _ in st.session_state.debug_logs if level == "error")
    n_warns = sum(1 for _, level, _ in st.session_state.debug_logs if level == "warn")
    total_logs = len(st.session_state.debug_logs)

    summary_parts = [f"{total_logs} entries"]
    if n_429:
        summary_parts.append(f"[ERROR] {n_429} rate-limits (429)")
    if n_errors:
        summary_parts.append(f"❌ {n_errors} errors")
    if n_warns:
        summary_parts.append(f"⚠️ {n_warns} warnings")
    st.caption(" · ".join(summary_parts))

    # Filter buttons
    filter_col1, filter_col2, filter_col3, filter_col4, filter_col5 = st.columns(5)
    with filter_col1:
        show_all = st.button("All", use_container_width=True, key="dbg_all")
    with filter_col2:
        show_429 = st.button(f"429s ({n_429})", use_container_width=True, key="dbg_429")
    with filter_col3:
        show_errs = st.button(f"Errors ({n_errors})", use_container_width=True, key="dbg_err")
    with filter_col4:
        show_warns = st.button(f"Warns ({n_warns})", use_container_width=True, key="dbg_warn")
    with filter_col5:
        dl_logs = st.download_button(
            "⬇️ Export",
            data="\n".join(f"[{ts}] [{level.upper()}] {text}" for ts, level, text in st.session_state.debug_logs),
            file_name="vmaro_debug_logs.txt",
            mime="text/plain",
            use_container_width=True,
            key="dbg_export"
        )

    # Apply filter
    filtered_logs = st.session_state.debug_logs
    if show_429:
        filtered_logs = [(ts, lv, tx) for ts, lv, tx in filtered_logs if lv == "rate"]
    elif show_errs:
        filtered_logs = [(ts, lv, tx) for ts, lv, tx in filtered_logs if lv == "error"]
    elif show_warns:
        filtered_logs = [(ts, lv, tx) for ts, lv, tx in filtered_logs if lv in ("warn", "rate")]

    st.markdown(format_debug_html(filtered_logs), unsafe_allow_html=True)

import streamlit as st
import json
import time
import os
import io
import sys
from datetime import datetime
import plotly.graph_objects as go
from streamlit_agraph import agraph, Node, Edge, Config
from utils.cache import save, load, CACHE_DIR
from utils.format_loader import load_all_formats, register_custom_format
from agents.format_matcher import run as run_format_matcher
from utils.latex_exporter import generate_pdf_bytes, generate_latex_source

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="VMARO Research Orchestrator", layout="wide")

# Reset sys.stdout if an old StreamCapture was left hanging by Streamlit hot-reloading
if hasattr(sys.stdout, "original"):
    sys.stdout = sys.__stdout__

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
    
    /* Layout & Sidebar Customization */
    .gate-banner {
        background: #78350f; 
        color: white; 
        padding: 12px 20px; 
        border-radius: 8px; 
        margin-bottom: 20px;
    }
    .step-complete { color: #4ade80; cursor: pointer; }
    .step-awaiting { color: #a78bfa; animation: pulse 2s infinite; cursor: pointer; }
    .step-pending { color: #4b5563; }
    .step-running { color: #eab308; }

    .format-card-recommended { box-shadow: 0 0 0 2px #7c3aed; border-radius: 12px; }
    .methodology-winner { border: 1px solid #4ade80; border-radius: 12px; }
    .methodology-loser { opacity: 0.6; }

    .pull-quote { 
        border-left: 3px solid #7c3aed; 
        padding-left: 16px; 
        color: #9ca3af; 
        font-style: italic; 
        margin: 20px 0; 
    }

    /* Badges */
    .source-badge-arxiv { background: #7c2d12; color: #fed7aa; }
    .source-badge-pubmed { background: #1e3a5f; color: #bfdbfe; }
    .source-badge-semantic { background: #3b0764; color: #e9d5ff; }
    .source-badge-crossref { background: #134e4a; color: #99f6e4; }
    .source-badge-openalex { background: #1c1917; color: #d6d3d1; }
    .source-badge-default { background: #333; color: #ccc; }
    
    .source-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 500;
        margin-left: 8px;
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
        position: relative;
    }
    .gap-card:hover { transform: translateX(4px); }
    .gap-auto-selected { border: 1px solid #7c3aed; }
    
    .score-big { font-size: 4rem; font-weight: 700; text-align: center; line-height: 1; }
    .score-label { text-align: center; font-size: 1rem; color: #888; margin-top: 4px; }

    .grant-section { margin-bottom: 20px; }
    .grant-section h3 { color: #a78bfa; border-bottom: 1px solid #2a2a4a; padding-bottom: 6px; }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }
    div[data-testid="stMetricValue"] { font-size: 3rem; }
    
    /* Hide streamer elements we don't need */
    button[title="View fullscreen"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ── Constants & Helpers ──────────────────────────────────────────────────────
RESULT_KEYS = ["papers", "tree", "qg1", "trends", "gaps", "qg2", "user_gap_selection", "methodology_a", "methodology_b", "methodology_eval", "format_match", "grant", "novelty"]

def is_fallback(data, required_keys):
    """Check if result is a fallback/empty dict that shouldn't be cached."""
    if not data or not isinstance(data, dict):
        return True
    for k in required_keys:
        v = data.get(k)
        if v is None or v == "" or v == [] or v == {}:
            return True
    return False

def get_source_badge_class(url_or_source):
    if not url_or_source: return "source-badge-default"
    s = url_or_source.lower()
    if "arxiv" in s: return "source-badge-arxiv"
    if "pubmed" in s or "ncbi" in s: return "source-badge-pubmed"
    if "semantic" in s or "semanticscholar" in s: return "source-badge-semantic"
    if "crossref" in s or "doi.org" in s: return "source-badge-crossref"
    if "openalex" in s: return "source-badge-openalex"
    return "source-badge-default"

def get_source_name(url_or_source):
    if not url_or_source: return "Source"
    s = url_or_source.lower()
    if "arxiv" in s: return "arXiv"
    if "pubmed" in s or "ncbi" in s: return "PubMed"
    if "semantic" in s or "semanticscholar" in s: return "Semantic Scholar"
    if "crossref" in s or "doi.org" in s: return "CrossRef"
    if "openalex" in s: return "OpenAlex"
    return "Source"

# ── Session State Init ───────────────────────────────────────────────────────
if "pipeline_run" not in st.session_state: st.session_state.pipeline_run = False
if "pipeline_topic" not in st.session_state: st.session_state.pipeline_topic = ""
if "pipeline_errors" not in st.session_state: st.session_state.pipeline_errors = {}
if "stage_status" not in st.session_state: st.session_state.stage_status = {}
if "formats" not in st.session_state: st.session_state.formats = load_all_formats()
if "user_format_override" not in st.session_state: st.session_state.user_format_override = None
if "active_step" not in st.session_state: st.session_state.active_step = 1
if "debug_logs" not in st.session_state: st.session_state.debug_logs = []
if "is_running_pipeline" not in st.session_state: st.session_state.is_running_pipeline = False

class StreamCapture:
    def __init__(self, original_stdout):
        self.original = original_stdout
        self.buffer = io.StringIO()
    def write(self, text):
        self.original.write(text)
    def flush(self):
        self.original.flush()

# Auto-load cached results
for key in RESULT_KEYS:
    if key not in st.session_state:
        cached = load(key)
        if cached:
            st.session_state[key] = cached
            st.session_state.pipeline_run = True
        else:
            st.session_state[key] = None

if not st.session_state.pipeline_topic:
    topic_file = os.path.join(CACHE_DIR, "_topic.txt")
    if os.path.exists(topic_file):
        st.session_state.pipeline_topic = open(topic_file).read().strip()

if st.session_state.pipeline_run and "active_step" not in st.session_state:
    st.session_state.active_step = 1

def set_stage(key, status):
    st.session_state.stage_status[key] = status

# ── Layout structure ─────────────────────────────────────────────────────────
col_main = st.container()

# ── Sidebar: Navigator ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Configuration")
    topic = st.text_input(
        "Research Topic",
        value=st.session_state.pipeline_topic,
        placeholder="e.g. Federated Learning in Healthcare"
    )
    c1, c2 = st.columns(2)
    with c1:
        run_btn = st.button("Run Analysis", use_container_width=True, type="primary")
    with c2:
        if st.button("Clear Cache & Restart", use_container_width=True):
            import shutil
            if os.path.exists(CACHE_DIR):
                shutil.rmtree(CACHE_DIR)
            for key in RESULT_KEYS:
                st.session_state[key] = None
            st.session_state.pipeline_run = False
            st.session_state.active_step = 1
            st.session_state.debug_logs = []
            st.rerun()
    
    st.markdown("---")
    st.markdown("##### Pipeline")
    
    pipeline_placeholder = st.empty()
    
    def update_pipeline_sidebar():
        with pipeline_placeholder.container():
            # Define steps logic
            STEPS = [
                (1, "Literature Mining", "papers"),
                (2, "Thematic Tree", "tree"),
                (3, "Trends & Gaps", "gaps"),
                (4, "Gap Selection", "user_gap_selection"),
                (5, "Methodology", "methodology_eval"),
                (6, "Format Selection", "format_match"),
                (7, "Grant Proposal", "grant"),
                (8, "Novelty Score", "novelty"),
            ]
            
            # Calculate state of each step
            def get_step_state(step_num, cache_key):
                if step_num == 4:
                    if load("user_gap_selection"): return "complete"
                    if load("gaps"): return "awaiting"
                if step_num == 6:
                    # Grant format wait state -- Actually wait till user generates the grant proposal
                    if load("grant"): return "complete"
                    if load("methodology_eval"): return "awaiting"
                
                # Methodology step relies on methodology_a existing or eval
                if step_num == 5:
                    if load("methodology_a") or load("methodology_eval"): return "complete"
                
                # Trends & Gaps relies on gaps or trends
                if step_num == 3:
                    if load("trends") or load("gaps"): return "complete"
                    
                # General state
                if load(cache_key): return "complete"
                # Check if any associated stage is running
                for k in st.session_state.stage_status:
                    if st.session_state.stage_status[k] == "running":
                        # Rough mapping
                        if step_num == 1 and k == "papers": return "running"
                        if step_num == 2 and k == "tree": return "running"
                        if step_num == 3 and k in ["trends", "gaps"]: return "running"
                        if step_num == 5 and k in ["methodology_a", "methodology_b", "methodology_eval"]: return "running"
                        if step_num == 7 and k == "grant": return "running"
                        if step_num == 8 and k == "novelty": return "running"
                return "pending"
            
            for step_num, label, key in STEPS:
                state = get_step_state(step_num, key)
                
                if state == "complete":
                    icon = "✓"
                    css_class = "step-complete"
                    is_clickable = True
                elif state == "running":
                    icon = "▶"
                    css_class = "step-running"
                    is_clickable = False
                elif state == "awaiting":
                    icon = "⬡"
                    css_class = "step-awaiting"
                    is_clickable = True
                else:
                    icon = "○"
                    css_class = "step-pending"
                    is_clickable = False
                    
                # Add visual indication for active step
                active_style = "background: rgba(124, 58, 237, 0.2); border-left: 3px solid #7c3aed; padding-left: 8px;" if st.session_state.active_step == step_num else ""
                
                if getattr(st.session_state, "is_running_pipeline", False):
                    is_clickable = False
                
                # Clickable buttons disguised as markdown using Streamlit buttons without background
                if is_clickable:
                    if st.button(f"{icon}  {step_num}  {label}", key=f"nav_{step_num}", use_container_width=True):
                        st.session_state.active_step = step_num
                        st.rerun()
                else:
                    st.markdown(f'<div style="padding: 4px 0; color: #4b5563; {active_style}"> {icon}  {step_num}  {label}</div>', unsafe_allow_html=True)
                    
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Quality Gates Pills
            qg1 = load("qg1") or {}
            qg2 = load("qg2") or {}
            
            qg1_dec = qg1.get("decision", "PENDING")
            qg2_dec = qg2.get("decision", "PENDING")
            
            def get_qg_color(dec):
                if dec == "PASS": return "#4ade80"
                if dec == "REVISE": return "#eab308"
                if dec == "FAIL": return "#ef4444"
                return "#4b5563"
                
            st.markdown(f"""
            <div style="font-size: 0.8rem; margin-bottom: 4px; display: flex; justify-content: space-between;">
                <span>Quality Gate 1:</span>
                <span style="color: {get_qg_color(qg1_dec)}; font-weight: bold;">[{qg1_dec}]</span>
            </div>
            <div style="font-size: 0.8rem; display: flex; justify-content: space-between;">
                <span>Quality Gate 2:</span>
                <span style="color: {get_qg_color(qg2_dec)}; font-weight: bold;">[{qg2_dec}]</span>
            </div>
            """, unsafe_allow_html=True)

    update_pipeline_sidebar()
    
    st.markdown("---")
    st.markdown("### Custom Grant Format")
    try:
        with open("schemas_for_user/custom_grant_format_template.json", "r") as f:
            template_content = f.read()
        st.download_button(
            label="Download Blank Template (JSON)",
            data=template_content,
            file_name="custom_grant_format_template.json",
            mime="application/json",
            help="Fill in this template and upload below to use your own grant format."
        )
    except FileNotFoundError:
        st.caption("Custom format template not found.")

    uploaded_file = st.file_uploader(
        "Upload Custom Format (JSON)",
        type=["json"]
    )
    if uploaded_file:
        try:
            custom_fmt = json.load(uploaded_file)
            success, errors = register_custom_format(custom_fmt, st.session_state.formats)
            if success:
                st.success(f"Format '{custom_fmt['format_id']}' loaded.")
            else:
                st.error("Validation failed.")
        except json.JSONDecodeError:
            st.error("Invalid JSON.")


# ── Run Pipeline Logic ───────────────────────────────────────────────────────
if run_btn:
    if not topic.strip():
        st.error("Please enter a research topic.")
        st.stop()

    st.session_state.is_running_pipeline = True

    last_topic_file = os.path.join(CACHE_DIR, "_topic.txt")
    if os.path.exists(CACHE_DIR) and os.path.exists(last_topic_file):
        prev_topic = open(last_topic_file).read().strip()
        if prev_topic != topic.strip():
            import shutil
            shutil.rmtree(CACHE_DIR)
            for key in RESULT_KEYS:
                st.session_state[key] = None
            st.session_state.active_step = 1

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(last_topic_file, "w") as f:
        f.write(topic.strip())

    st.session_state.pipeline_topic = topic.strip()
    st.session_state.pipeline_run = True
    st.session_state.active_step = 1

    from agents.literature_agent import run as run_literature
    from agents.tree_agent import run as run_tree
    from agents.trend_agent import run as run_trend
    from agents.gap_agent import run as run_gap
    from utils.quality_gate import evaluate_quality
    
    _original_stdout = sys.stdout
    sys.stdout = StreamCapture(_original_stdout)

    with col_main:
        with st.status("🚀 **Running Phase 1 Pipeline**", expanded=True):
            set_stage("papers", "running")
            update_pipeline_sidebar()
            st.write("**Fetching papers parallely...**")
            papers = load("papers") or run_literature(topic)
            if not load("papers"): save("papers", papers)
            st.session_state.papers = papers
            set_stage("papers", "complete")
            update_pipeline_sidebar()

            set_stage("tree", "running")
            update_pipeline_sidebar()
            st.write("**Clustering papers...**")
            tree = load("tree") or run_tree(papers)
            if not load("tree"): save("tree", tree)
            st.session_state.tree = tree
            set_stage("tree", "complete")
            update_pipeline_sidebar()

            set_stage("qg1", "running")
            update_pipeline_sidebar()
            qg1 = load("qg1") or evaluate_quality("post_literature", tree)
            if not load("qg1"): save("qg1", qg1)
            st.session_state.qg1 = qg1
            set_stage("qg1", "complete")
            update_pipeline_sidebar()

            set_stage("trends", "running")
            update_pipeline_sidebar()
            st.write("**Analyzing trends...**")
            trends = load("trends") or run_trend(tree)
            if not load("trends"): save("trends", trends)
            st.session_state.trends = trends
            set_stage("trends", "complete")
            update_pipeline_sidebar()
            
            set_stage("gaps", "running")
            update_pipeline_sidebar()
            st.write("**Identifying research gaps...**")
            gaps = load("gaps") or run_gap(tree, trends)
            if not load("gaps"): save("gaps", gaps)
            st.session_state.gaps = gaps
            set_stage("gaps", "complete")
            update_pipeline_sidebar()
            
            set_stage("qg2", "running")
            update_pipeline_sidebar()
            qg2 = load("qg2") or evaluate_quality("post_gap", gaps)
            if not load("qg2"): save("qg2", qg2)
            st.session_state.qg2 = qg2
            set_stage("qg2", "complete")
            update_pipeline_sidebar()

    st.session_state.is_running_pipeline = False
    sys.stdout = _original_stdout
    st.session_state.active_step = 4
    st.rerun()

# ── Right Column: Content Area ───────────────────────────────────────────────
with col_main:
    # Header
    st.markdown('<p class="main-title">🔬 VMARO Research Orchestrator</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">AI-powered research pipeline — from literature to grant proposal in minutes</p>', unsafe_allow_html=True)
    
    if not st.session_state.pipeline_run and not load("papers"):
        st.markdown("---")
        st.markdown("### Welcome to VMARO")
        st.markdown("Enter a topic on the left and click **Run Analysis** to start.")
        st.stop()
        
    st.markdown("---")
    step = st.session_state.active_step
    
    if step == 1:
        papers_data = load("papers") or {}
        paper_list = papers_data.get("papers", [])
        
        st.markdown("## Retrieved Literature")
        
        # Stat row
        if paper_list:
            sources = set([p.get("url").split("/")[2] if p.get("url") and isinstance(p.get("url"), str) and "//" in p.get("url") else "Unknown" for p in paper_list])
            years = [p.get("year") for p in paper_list if p.get("year")]
            yr_str = f"{min(years)}–{max(years)}" if years else "N/A"
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Papers", len(paper_list))
            c2.metric("Sources", len(sources))
            c3.metric("Year Range", yr_str)
            
        for p in paper_list:
            source_badge = f'<span class="source-badge {get_source_badge_class(p.get("url", ""))}">{get_source_name(p.get("url", ""))}</span>'
            st.markdown(f"""
            <div class="paper-card">
                <h4>{p.get('title', 'Unknown')}</h4>
                <span class="year-badge">{p.get('year', 'N/A')}</span>{source_badge}
                <p style="margin-top:10px; color:#ccc;">{p.get('summary', '')}</p>
                <p style="color:#a78bfa;"><strong>Contribution:</strong> {p.get('contribution', '')}</p>
                <a href="{p.get('url', '#')}" style="color:#667eea;">Source Link</a>
            </div>
            """, unsafe_allow_html=True)

    elif step == 2:
        tree = load("tree") or {}
        if tree and tree.get("themes"):
            nodes = []
            edges = []
            
            root_val = tree.get("root", "Topic string")
            root_label = root_val[:30] + "\\n" + root_val[30:] if len(root_val) > 30 else root_val
            nodes.append(Node(
                id="root",
                label=root_label,
                size=30,
                color="#7c3aed",
                font={"color": "#ffffff", "size": 14, "face": "Inter"},
                shape="ellipse",
                title=root_val
            ))
            
            theme_colors = ["#6d28d9", "#1d4ed8", "#0f766e", "#b45309", "#be123c"]
            paper_colors = ["#a78bfa", "#93c5fd", "#5eead4", "#fcd34d", "#fca5a5"]
            
            for i, theme in enumerate(tree.get("themes", [])):
                theme_id = theme.get("theme_id", f"T{i}")
                theme_name = theme.get("theme_name", "Theme")
                papers = theme.get("papers", [])
                
                t_color = theme_colors[i % len(theme_colors)]
                p_color = paper_colors[i % len(paper_colors)]
                
                t_label = theme_name[:25] + "\\n" + theme_name[25:] if len(theme_name) > 25 else theme_name
                t_title = f"{theme_name} — {len(papers)} papers"
                if len(papers) == 0:
                    t_title += " (no papers)"
                    
                nodes.append(Node(
                    id=theme_id,
                    label=t_label,
                    size=22,
                    color=t_color,
                    font={"color": "#ffffff", "size": 12, "face": "Inter"},
                    shape="box",
                    title=t_title
                ))
                
                edges.append(Edge(
                    source="root",
                    target=theme_id,
                    color="#4b5563",
                    width=2,
                    arrows="to",
                    smooth={"type": "cubicBezier"}
                ))
                
                for p_idx, paper in enumerate(papers):
                    title = paper.get("title", "Untitled paper") if isinstance(paper, dict) else str(paper)
                    year = paper.get("year", "") if isinstance(paper, dict) else ""
                    summary = paper.get("summary", "") if isinstance(paper, dict) else ""
                    
                    p_label = title[:35] + "…" if len(title) > 35 else title
                    p_id = f"{theme_id}_{p_idx}"
                    
                    p_title = f"{title}\\n{year}\\n\\n{summary[:150]}…"
                    
                    nodes.append(Node(
                        id=p_id,
                        label=p_label,
                        size=14,
                        color=p_color,
                        font={"color": "#1f2937", "size": 11, "face": "Inter"},
                        shape="box",
                        title=p_title
                    ))
                    
                    edges.append(Edge(
                        source=theme_id,
                        target=p_id,
                        color="#374151",
                        width=1,
                        arrows="to",
                        smooth={"type": "cubicBezier"}
                    ))
                    
            config = Config(
                width="100%",
                height=900,
                directed=True,
                physics=True,
                hierarchical=True,
                hierarchical_layout={
                    "enabled": True,
                    "direction": "UD",
                    "sortMethod": "directed",
                    "levelSeparation": 180,
                    "nodeSpacing": 150,
                    "treeSpacing": 200,
                    "blockShifting": True,
                    "edgeMinimization": True,
                    "parentCentralization": True,
                },
                nodeHighlightBehavior=True,
                highlightColor="#a78bfa",
                backgroundColor="rgba(0,0,0,0)",
                stabilization=True,
            )
            
            agraph(nodes=nodes, edges=edges, config=config)
            
            directions = tree.get("emerging_directions", [])
            if directions:
                st.markdown("#### Emerging Directions")
                pills_html = []
                for d in directions:
                    pills_html.append(f'<span style="background:#3b0764; color:#e9d5ff; padding:4px 12px; border-radius:20px; font-size:0.85rem; margin:4px; display:inline-block;">{d}</span>')
                st.markdown("".join(pills_html), unsafe_allow_html=True)
            
            st.markdown("---")
            with st.expander("Raw tree JSON", expanded=False):
                st.json(tree)
        else:
            st.info("No tree data available.")

    elif step == 3:
        trends_data = load("trends") or {}
        gaps_data = load("gaps") or {}
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Dominant Trends")
            for i, c in enumerate(trends_data.get("dominant_clusters", [])):
                st.markdown(f'<div class="paper-card" style="padding:12px;"><strong>{c}</strong></div>', unsafe_allow_html=True)
            for t in trends_data.get("emerging_trends", []):
                st.markdown(f'<div class="paper-card" style="padding:12px;"><em>{t}</em></div>', unsafe_allow_html=True)
                
        with c2:
            st.markdown("### Identified Gaps")
            selected = gaps_data.get('selected_gap', '?')
            for g in gaps_data.get("identified_gaps", []):
                hl = "gap-auto-selected" if g.get('gap_id') == selected else ""
                rank = g.get('priority_rank', '')
                fnote = g.get('feasibility_note', '')
                f_html = f'<p style="color:#94a3b8; font-size:0.85rem; margin-top:8px;"><em>Rank {rank}</em> — {fnote}</p>' if fnote else ''
                st.markdown(f"""
                <div class="gap-card {hl}">
                    <strong style="color:#f59e0b;">{g.get('gap_id', '')}</strong>
                    <p style="color:#e2e8f0; margin: 6px 0;">{g.get('description', '')}</p>
                    {f_html}
                </div>
                """, unsafe_allow_html=True)
                
        st.markdown("---")
        if st.button("Proceed to Gap Selection →"):
            st.session_state.active_step = 4
            st.rerun()

    elif step == 4:
        st.markdown('<div class="gate-banner">Your input is needed — select or define the research gap to develop.</div>', unsafe_allow_html=True)
        gaps_data = load("gaps") or {}
        all_gaps = gaps_data.get("identified_gaps", [])
        llm_selected_id = gaps_data.get("selected_gap", "")
        
        if all_gaps:
            for g in all_gaps:
                gid = g.get("gap_id")
                rank = g.get("priority_rank", 3)
                stars = "★" * (4 - rank) + "☆" * (rank - 1) if isinstance(rank, int) and 1 <= rank <= 3 else ""
                llm_badge = '<span style="background:#7c3aed; padding:2px 8px; border-radius:12px; font-size:0.8rem; margin-left:8px;">LLM Recommended</span>' if gid == llm_selected_id else ''
                
                with st.container():
                    st.markdown(f"""
                    <div class="paper-card" style="position:relative;">
                        <div style="display:flex; justify-content:space-between;">
                            <div><strong style="background:#475569; padding:2px 6px; border-radius:4px;">{gid}</strong>{llm_badge}</div>
                            <div style="color:#f59e0b;">{stars}</div>
                        </div>
                        <p style="margin:12px 0;">{g.get('description', '')}</p>
                        <p style="color:#94a3b8; font-size:0.85rem;">{g.get('feasibility_note', '')}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button(f"Select {gid}", key=f"sel_{gid}"):
                        selection = {
                            "gap_id": gid,
                            "source": "user_selected" if gid != llm_selected_id else "llm_suggested",
                            "description": g["description"],
                            "is_custom": False
                        }
                        save("user_gap_selection", selection)
                        st.success("Gap confirmed — pipeline continuing")
                        time.sleep(1)
                        # Trigger methodology run
                        from agents.methodology_agent import run as run_methodology
                        from agents.methodology_evaluator import run as run_evaluator
                        topic = st.session_state.pipeline_topic
                        
                        meth_a = run_methodology(selection["description"], topic)
                        save("methodology_a", meth_a)
                        st.session_state.methodology_a = meth_a
                        
                        sorted_gaps = sorted(all_gaps, key=lambda x: x.get("priority_rank", 3))
                        chs = [x for x in sorted_gaps if x["gap_id"] != gid]
                        if chs:
                            meth_b = run_methodology(chs[0]["description"], topic)
                            save("methodology_b", meth_b)
                            st.session_state.methodology_b = meth_b
                            eval_res = run_evaluator(topic, selection["description"], meth_a, chs[0]["description"], meth_b)
                            save("methodology_eval", eval_res)
                        
                        st.session_state.active_step = 5
                        st.rerun()
                        
            st.markdown("---")
            st.markdown('<div class="paper-card" style="border:1px dashed #7c3aed;"><h4>Define your own gap</h4></div>', unsafe_allow_html=True)
            custom_desc = st.text_area("Describe a research gap you've identified that isn't listed above")
            if st.button("Use my gap →", disabled=not custom_desc.strip()):
                selection = {
                    "gap_id": "custom",
                    "source": "user_custom",
                    "description": custom_desc.strip(),
                    "is_custom": True
                }
                save("user_gap_selection", selection)
                st.success("Gap confirmed — pipeline continuing")
                time.sleep(1)
                
                from agents.methodology_agent import run as run_methodology
                from agents.methodology_evaluator import run as run_evaluator
                topic = st.session_state.pipeline_topic
                
                meth_a = run_methodology(selection["description"], topic)
                save("methodology_a", meth_a)
                st.session_state.methodology_a = meth_a
                
                sorted_gaps = sorted(all_gaps, key=lambda x: x.get("priority_rank", 3))
                if sorted_gaps:
                    meth_b = run_methodology(sorted_gaps[0]["description"], topic)
                    save("methodology_b", meth_b)
                    st.session_state.methodology_b = meth_b
                    eval_res = run_evaluator(topic, selection["description"], meth_a, sorted_gaps[0]["description"], meth_b)
                    save("methodology_eval", eval_res)
                
                st.session_state.active_step = 5
                st.rerun()

    elif step == 5:
        mev = load("methodology_eval") or {}
        meth_a = load("methodology_a") or {}
        meth_b = load("methodology_b") or {}
        
        def render_meth(m, label, is_winner):
            cls = "methodology-winner" if is_winner else "methodology-loser"
            badge = '<span style="background:#4ade80; color:#064e3b; padding:2px 8px; border-radius:12px; font-size:0.8rem; float:right;">Selected</span>' if is_winner else '<span style="background:#4b5563; padding:2px 8px; border-radius:12px; font-size:0.8rem; float:right;">Challenger</span>'
            html = f'<div class="paper-card {cls}"><h4>{label}</h4>{badge}<br>'
            if m:
                html += f"<b>Datasets:</b> {', '.join(m.get('suggested_datasets', []))}<br>"
                html += f"<b>Metrics:</b> {', '.join(m.get('evaluation_metrics', []))}<br>"
                html += f"<b>Baselines:</b> {', '.join(m.get('baseline_models', []))}<br><br>"
                html += f"<b>Experimental Design:</b><br>{m.get('experimental_design', '')}<br><br>"
                html += f"<b>Tools/Frameworks:</b> {', '.join(m.get('tools_and_frameworks', []))}"
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)
            
        if mev and mev.get("parallel_was_run") and meth_a and meth_b:
            # We must stack them vertically
            win_label = mev.get("winner")
            render_meth(meth_a, "Primary Gap Methodology", win_label == "A")
            
            st.markdown(f'<div class="pull-quote">{mev.get("reasoning", "")}</div>', unsafe_allow_html=True)
            
            render_meth(meth_b, "Challenger Gap Methodology", win_label == "B")
            
            if st.button("Use challenger methodology instead"):
                mev["winner"] = "B" if win_label == "A" else "A"
                mev["winning_methodology"] = meth_b if win_label == "A" else meth_a
                save("methodology_eval", mev)
                for k in ["format_match", "grant", "novelty"]:
                    st.session_state[k] = None
                    p = f"cache/{k}.json"
                    if os.path.exists(p): os.remove(p)
                st.rerun()
            
            st.markdown("---")
            if st.button("Proceed to Format Selection →"):
                st.session_state.active_step = 6
                st.rerun()
        else:
            meth = mev.get("winning_methodology") if mev else meth_a
            if meth:
                render_meth(meth, "Experimental Methodology", 1)
                st.markdown("---")
                if st.button("Proceed to Format Selection →"):
                    st.session_state.active_step = 6
                    st.rerun()

    elif step == 6:
        st.markdown('<div class="gate-banner">Your input is needed — select a grant format.</div>', unsafe_allow_html=True)
        
        fm = load("format_match")
        if not fm:
            with st.spinner("Analyzing methodology to recommend best grant format..."):
                meth = load("methodology_eval").get("winning_methodology") if load("methodology_eval") else load("methodology_a")
                fm = run_format_matcher(st.session_state.pipeline_topic, meth, st.session_state.formats, None)
                save("format_match", fm)
                st.rerun()
                
        llm_default = fm.get("selected_format_id")
        formats = st.session_state.formats
        
        # Grid layout
        cols = st.columns(3)
        for i, (fid, fmt) in enumerate(formats.items()):
            with cols[i % 3]:
                is_rec = (fid == llm_default)
                cls = "format-card-recommended" if is_rec else "paper-card"
                badge = '<br><span style="background:#7c3aed; padding:2px 8px; border-radius:12px; font-size:0.75rem;">LLM recommended</span>' if is_rec else ''
                award = f'<span style="background:#064e3b; color:#34d399; padding:2px 8px; border-radius:12px; font-size:0.75rem;">{fmt.get("typical_award_usd", "Varies")}</span>'
                emph = fmt.get("emphasis", "")
                emph_html = "".join([f'<span style="background:#334155; padding:2px 6px; border-radius:4px; font-size:0.75rem; margin-right:4px;">{e}</span>' for e in emph.split()[:3]])
                
                st.markdown(f"""
                <div class="{cls}" style="padding:16px; margin-bottom:12px;">
                    <h4 style="margin:0;">{fmt['name']}</h4>
                    <p style="color:#94a3b8; font-size:0.85rem; margin:4px 0;">{fmt['funding_body']}</p>
                    {award} {badge}
                    <div style="margin-top:12px;">{emph_html}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"Select {fid}", key=f"sel_{fid}"):
                    st.session_state.user_format_override = fid
                    save("format_match", run_format_matcher(st.session_state.pipeline_topic, load("methodology_eval").get("winning_methodology") if load("methodology_eval") else load("methodology_a"), st.session_state.formats, fid))
                    st.success("Format confirmed — generating grant")
                    
                    from agents.grant_agent import run as run_grant
                    from agents.novelty_agent import run as run_novelty
                    
                    topic = st.session_state.pipeline_topic
                    user_gap = load("user_gap_selection") or {}
                    meth_data = load("methodology_eval").get("winning_methodology") if load("methodology_eval") else load("methodology_a")
                    format_match = load("format_match")
                    
                    grant = run_grant(topic, user_gap.get("description", ""), meth_data, format_match)
                    save("grant", grant)
                    
                    novelty = run_novelty(grant, load("tree"))
                    save("novelty", novelty)
                    
                    st.session_state.active_step = 7
                    st.rerun()

    elif step == 7:
        grant_data = load("grant") or {}
        fm = load("format_match") or {}
        if grant_data:
            topic = st.session_state.pipeline_topic
            fmt_id = fm.get("selected_format_id", "Unknown")
            fmt_name = (st.session_state.formats or {}).get(fmt_id, {}).get("name", fmt_id)
            is_auto = "" if st.session_state.user_format_override else " — LLM selected"
            
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"# {topic}")
                st.markdown(f'<span style="background:#4b5563; padding:4px 10px; border-radius:12px; font-size:0.85rem;">Format: {fmt_id}{is_auto}</span>', unsafe_allow_html=True)
            with c2:
                # ── PDF download ──────────────────────────────────────────
                try:
                    pdf_bytes = generate_pdf_bytes(grant_data, topic, fmt_name)
                    st.download_button(
                        label="⬇ Download as PDF",
                        data=pdf_bytes,
                        file_name="grant_proposal.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                except Exception as _pdf_err:
                    st.warning(f"PDF generation unavailable: {_pdf_err}")

                # ── LaTeX source download ─────────────────────────────────
                tex_source = generate_latex_source(grant_data, topic, fmt_name)
                st.download_button(
                    label="⬇ Download as LaTeX (.tex)",
                    data=tex_source,
                    file_name="grant_proposal.tex",
                    mime="text/x-tex",
                    use_container_width=True,
                )

                # ── Raw JSON fallback ─────────────────────────────────────
                with st.expander("Raw JSON export"):
                    st.download_button(
                        "Download JSON",
                        data=json.dumps(grant_data, indent=2),
                        file_name="grant_proposal.json",
                        mime="application/json",
                    )
                
            st.markdown("---")
            for key, val in grant_data.items():
                if key in ["title", "format_used", "sections"]: continue
                title = key.replace("_", " ").title()
                if isinstance(val, list): val = "<br>• " + "<br>• ".join(str(v) for v in val)
                st.markdown(f'<div class="grant-section"><h3>{title}</h3><p>{val}</p></div>', unsafe_allow_html=True)
                
            if "sections" in grant_data:
                for title, content in grant_data["sections"].items():
                    if isinstance(content, str):
                        content = content.replace("\\n", "<br>")
                    st.markdown(f'<div class="grant-section"><h3>{title}</h3><p>{content}</p></div>', unsafe_allow_html=True)
        else:
            st.info("No grant generated yet.")

    elif step == 8:
        nov = load("novelty") or {}
        if nov:
            score = nov.get("novelty_score", 0)
            
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = score,
                domain = {'x': [0, 1], 'y': [0, 1]},
                gauge = {
                    'axis': {'range': [None, 100]},
                    'bar': {'color': "white"},
                    'steps' : [
                        {'range': [0, 40], 'color': "#ef4444"},
                        {'range': [40, 70], 'color': "#eab308"},
                        {'range': [70, 100], 'color': "#22c55e"}],
                }
            ))
            fig.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown(f'<div class="pull-quote">{nov.get("score_justification", "")}</div>', unsafe_allow_html=True)
            
            st.markdown("### Closest Existing Papers")
            closest = nov.get("closest_papers", [])
            for p in closest:
                st.markdown(f"""
                <div class="paper-card">
                    <h4>{p}</h4>
                    <p style="color:#94a3b8; font-style:italic;">{nov.get('similarity_reasoning', '')}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No novelty score generated yet.")

# ── Debug Console (Full Width at Bottom) ─────────────────────────────────────
st.markdown("---")
with st.expander("Terminal Logs", expanded=False):
    if not st.session_state.debug_logs:
        st.markdown("*(No logs yet...)*")
    else:
        log_html = '<div style="background:#0f172a; padding:12px; border-radius:6px; font-family:monospace; font-size:0.85rem; max-height:400px; overflow-y:auto;">'
        for ts, level, msg in st.session_state.debug_logs:
            color = "#94a3b8"
            if level == "stage": color = "#a78bfa"
            elif level == "error": color = "#ef4444"
            elif level == "warning": color = "#eab308"
            elif level == "success": color = "#4ade80"
            
            log_html += f'<div style="margin-bottom:4px;"><span style="color:#64748b; font-size:0.75rem;">[{ts}]</span> <span style="color:{color};">{msg}</span></div>'
        log_html += '</div>'
        st.markdown(log_html, unsafe_allow_html=True)
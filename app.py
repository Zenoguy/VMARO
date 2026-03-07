import streamlit as st
import json
import time
import os
from utils.cache import save, load, CACHE_DIR

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="VMARO Research Orchestrator", layout="wide", page_icon="🔬")

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
    .phase-complete { color: #22c55e; }
    .phase-running  { color: #eab308; }
    .phase-pending  { color: #555; }
    
    /* Tighter spacing for grant sections */
    .grant-section { margin-bottom: 20px; }
    .grant-section h3 { 
        color: #a78bfa; 
        border-bottom: 1px solid #2a2a4a; 
        padding-bottom: 6px; 
    }
    
    div[data-testid="stMetricValue"] { font-size: 3rem; }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown('<p class="main-title">🔬 VMARO Research Orchestrator</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">AI-powered research pipeline — from literature to grant proposal in minutes</p>', unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    topic = st.text_input("Research Topic", placeholder="e.g. Federated Learning in Healthcare")
    
    st.markdown("---")
    run_btn = st.button("▶  Run Analysis", use_container_width=True, type="primary")
    
    st.markdown("---")
    st.markdown("##### Pipeline Stages")
    st.markdown("""
    1. 📚 Literature Mining  
    2. 🌳 Thematic Clustering  
    3. ✅ Quality Gate 1  
    4. 📈 Trend Analysis  
    5. 🔍 Gap Identification  
    6. ✅ Quality Gate 2  
    7. 🧪 Methodology Design  
    8. 📝 Grant Writing  
    9. ⭐ Novelty Scoring
    """)

# ── Pipeline Stages Definition ───────────────────────────────────────────────
STAGES = [
    ("📚", "Literature Mining",       "Searching Semantic Scholar and summarizing papers with Gemini..."),
    ("🌳", "Thematic Clustering",     "Clustering papers into 3–5 themes and identifying emerging directions..."),
    ("✅", "Quality Gate 1",          "Evaluating thematic tree quality..."),
    ("📈", "Trend Analysis",          "Identifying dominant clusters and emerging research trends..."),
    ("🔍", "Gap Identification",      "Finding underexplored intersections between themes and trends..."),
    ("✅", "Quality Gate 2",          "Evaluating gap analysis quality..."),
    ("🧪", "Methodology Design",     "Designing experimental methodology for the selected gap..."),
    ("📝", "Grant Writing",          "Drafting a funding-ready research proposal..."),
    ("⭐", "Novelty Scoring",        "Comparing proposal against existing literature for novelty..."),
]

# ── Run Pipeline with Progress ───────────────────────────────────────────────
if run_btn:
    if not topic.strip():
        st.error("Please enter a research topic.")
        st.stop()
    
    # Clear cache if topic changed
    last_topic_file = os.path.join(CACHE_DIR, "_topic.txt")
    if os.path.exists(CACHE_DIR):
        prev_topic = open(last_topic_file).read() if os.path.exists(last_topic_file) else ""
        if prev_topic != topic:
            import shutil
            shutil.rmtree(CACHE_DIR)
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(last_topic_file, "w") as f:
        f.write(topic)
    
    # Lazy imports to avoid circular issues
    from agents.literature_agent import run as run_literature
    from agents.tree_agent import run as run_tree
    from agents.trend_agent import run as run_trend
    from agents.gap_agent import run as run_gap
    from agents.methodology_agent import run as run_methodology
    from agents.grant_agent import run as run_grant
    from agents.novelty_agent import run as run_novelty
    from utils.quality_gate import evaluate_quality

    results = {}
    progress_bar = st.progress(0, text="Initializing pipeline...")
    status_container = st.status("🚀 **Running VMARO Pipeline**", expanded=True)
    
    total = len(STAGES)
    
    def update_progress(step_idx, label):
        pct = int((step_idx / total) * 100)
        progress_bar.progress(pct, text=f"Stage {step_idx}/{total} — {label}")
    
    with status_container:
        # ── Stage 1: Literature ──
        update_progress(1, "Literature Mining")
        st.write("📚 **Searching Semantic Scholar** and summarizing papers...")
        papers = load("papers")
        if papers:
            st.write("  ↳ _Loaded from cache_")
        else:
            papers = run_literature(topic)
            save("papers", papers)
            time.sleep(2)
        results["papers"] = papers
        n_papers = len(papers.get("papers", []))
        st.write(f"  ↳ ✅ Retrieved **{n_papers} papers**")
        
        # ── Stage 2: Tree ──
        update_progress(2, "Thematic Clustering")
        st.write("🌳 **Clustering** papers into thematic groups...")
        tree = load("tree")
        if tree:
            st.write("  ↳ _Loaded from cache_")
        else:
            tree = run_tree(papers)
            save("tree", tree)
            time.sleep(2)
        results["tree"] = tree
        n_themes = len(tree.get("themes", []))
        st.write(f"  ↳ ✅ Built **{n_themes} themes**")
        
        # ── Stage 3: Quality Gate 1 ──
        update_progress(3, "Quality Gate 1")
        st.write("✅ **Quality Gate 1** — evaluating literature tree...")
        qg1 = evaluate_quality("post_literature", tree)
        time.sleep(2)
        qg1_decision = qg1.get("decision", "?")
        qg1_conf = qg1.get("confidence", 0)
        st.write(f"  ↳ Gate: **{qg1_decision}** (confidence {qg1_conf})")
        
        # ── Stage 4: Trends ──
        update_progress(4, "Trend Analysis")
        st.write("📈 **Analyzing trends** in the research landscape...")
        trends = load("trends")
        if trends:
            st.write("  ↳ _Loaded from cache_")
        else:
            trends = run_trend(tree)
            save("trends", trends)
            time.sleep(2)
        results["trends"] = trends
        st.write(f"  ↳ ✅ Found **{len(trends.get('dominant_clusters', []))} clusters**, **{len(trends.get('emerging_trends', []))} trends**")
        
        # ── Stage 5: Gaps ──
        update_progress(5, "Gap Identification")
        st.write("🔍 **Identifying research gaps** at theme intersections...")
        gaps = load("gaps")
        if gaps:
            st.write("  ↳ _Loaded from cache_")
        else:
            gaps = run_gap(tree, trends)
            save("gaps", gaps)
            time.sleep(2)
        results["gaps"] = gaps
        st.write(f"  ↳ ✅ Found **{len(gaps.get('identified_gaps', []))} gaps**, selected: **{gaps.get('selected_gap', '?')}**")
        
        # ── Stage 6: Quality Gate 2 ──
        update_progress(6, "Quality Gate 2")
        st.write("✅ **Quality Gate 2** — evaluating gap analysis...")
        qg2 = evaluate_quality("post_gap", gaps)
        time.sleep(2)
        qg2_decision = qg2.get("decision", "?")
        qg2_conf = qg2.get("confidence", 0)
        st.write(f"  ↳ Gate: **{qg2_decision}** (confidence {qg2_conf})")
        
        # ── Stage 7: Methodology ──
        update_progress(7, "Methodology Design")
        st.write("🧪 **Designing experimental methodology** for the selected gap...")
        methodology = load("methodology")
        if methodology:
            st.write("  ↳ _Loaded from cache_")
        else:
            selected_gap_id = gaps.get("selected_gap", "")
            gap_desc = next(
                (g["description"] for g in gaps.get("identified_gaps", []) if g["gap_id"] == selected_gap_id),
                selected_gap_id
            )
            methodology = run_methodology(gap_desc, topic)
            save("methodology", methodology)
            time.sleep(2)
        results["methodology"] = methodology
        st.write(f"  ↳ ✅ Methodology ready — **{len(methodology.get('suggested_datasets', []))} datasets**, **{len(methodology.get('baseline_models', []))} baselines**")
        
        # ── Stage 8: Grant ──
        update_progress(8, "Grant Writing")
        st.write("📝 **Drafting grant proposal**...")
        grant = load("grant")
        if grant:
            st.write("  ↳ _Loaded from cache_")
        else:
            selected_gap_id = gaps.get("selected_gap", "")
            gap_desc = next(
                (g["description"] for g in gaps.get("identified_gaps", []) if g["gap_id"] == selected_gap_id),
                selected_gap_id
            )
            grant = run_grant(topic, gap_desc, methodology)
            save("grant", grant)
            time.sleep(2)
        results["grant"] = grant
        st.write("  ↳ ✅ Grant proposal drafted")
        
        # ── Stage 9: Novelty ──
        update_progress(9, "Novelty Scoring")
        st.write("⭐ **Scoring novelty** against existing literature...")
        novelty = load("novelty")
        if novelty:
            st.write("  ↳ _Loaded from cache_")
        else:
            novelty = run_novelty(grant, tree)
            save("novelty", novelty)
            time.sleep(2)
        results["novelty"] = novelty
        score = novelty.get("novelty_score", 0)
        st.write(f"  ↳ ✅ Novelty score: **{score}/100**")

    progress_bar.progress(100, text="✅ Pipeline complete!")
    status_container.update(label="✅ **Pipeline Complete**", state="complete", expanded=False)
    
    st.balloons()

    # ══════════════════════════════════════════════════════════════════════════
    #  RESULTS DISPLAY
    # ══════════════════════════════════════════════════════════════════════════
    
    st.markdown("---")
    
    tabs = st.tabs([
        "📚 Literature", 
        "🌳 Tree Index", 
        "📈 Trends & Gaps", 
        "🧪 Methodology", 
        "📝 Grant Proposal", 
        "⭐ Novelty Score"
    ])

    # ── Tab 1: Literature ────────────────────────────────────────────────────
    with tabs[0]:
        st.markdown("## 📚 Retrieved Literature")
        papers_data = results.get("papers", {})
        st.caption(f"Topic: **{papers_data.get('topic', topic)}** · {len(papers_data.get('papers', []))} papers")
        
        for p in papers_data.get("papers", []):
            st.markdown(f"""
<div class="paper-card">
    <h4>{p.get('title', 'Unknown')}</h4>
    <span class="year-badge">📅 {p.get('year', 'N/A')}</span>
    <p style="margin-top:10px; color:#ccc;">{p.get('summary', '')}</p>
    <p style="color:#a78bfa;"><strong>Contribution:</strong> {p.get('contribution', '')}</p>
    <a href="{p.get('source', '#')}" style="color:#667eea;">🔗 Source</a>
</div>
            """, unsafe_allow_html=True)

    # ── Tab 2: Tree Index ────────────────────────────────────────────────────
    with tabs[1]:
        tree_data = results.get("tree", {})
        st.markdown(f"## 🌳 Thematic Tree Index")
        st.markdown(f"**Root:** {tree_data.get('root', 'Unknown')}")
        
        for theme in tree_data.get("themes", []):
            with st.expander(f"🏷️ {theme.get('theme_id')}: {theme.get('theme_name')}", expanded=True):
                for idx, p in enumerate(theme.get('papers', [])):
                    title = p.get('title', p) if isinstance(p, dict) else p
                    year = p.get('year', '') if isinstance(p, dict) else ''
                    year_str = f" ({year})" if year else ""
                    st.markdown(f"&nbsp;&nbsp;&nbsp;{idx+1}. {title}{year_str}")
                    
        st.markdown("### 🚀 Emerging Directions")
        for d in tree_data.get("emerging_directions", []):
            st.markdown(f"- {d}")

    # ── Tab 3: Trends & Gaps ─────────────────────────────────────────────────
    with tabs[2]:
        st.markdown("## 📈 Trends & Gaps")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Dominant Clusters")
            trends_data = results.get("trends", {})
            for i, c in enumerate(trends_data.get("dominant_clusters", [])):
                st.markdown(f"**{i+1}.** {c}")
            
            st.markdown("### Emerging Trends")
            for t in trends_data.get("emerging_trends", []):
                st.info(f"📈 {t}")
                
        with col2:
            st.markdown("### Identified Gaps")
            gaps_data = results.get("gaps", {})
            for g in gaps_data.get("identified_gaps", []):
                st.markdown(f"""
<div class="gap-card">
    <strong style="color:#f59e0b;">{g.get('gap_id', '')}</strong>
    <p style="color:#e2e8f0; margin: 6px 0;">{g.get('description', '')}</p>
    <p style="color:#94a3b8; font-size:0.85rem;"><em>Why underexplored:</em> {g.get('why_underexplored', '')}</p>
</div>
                """, unsafe_allow_html=True)
            
            selected = gaps_data.get('selected_gap', '?')
            st.success(f"🎯 **Selected Gap:** {selected}")

    # ── Tab 4: Methodology ───────────────────────────────────────────────────
    with tabs[3]:
        st.markdown("## 🧪 Experimental Methodology")
        meth = results.get("methodology", {})
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("### 📊 Datasets")
            for d in meth.get("suggested_datasets", []):
                st.markdown(f"- {d}")
        with c2:
            st.markdown("### 📏 Metrics")
            for m in meth.get("evaluation_metrics", []):
                st.markdown(f"- {m}")
        with c3:
            st.markdown("### 🏗️ Baselines")
            for b in meth.get("baseline_models", []):
                st.markdown(f"- {b}")
                
        st.markdown("### 🔬 Experimental Design")
        st.markdown(meth.get("experimental_design", "_No design generated._"))
        
        st.markdown("### 🛠️ Tools & Frameworks")
        tools = meth.get("tools_and_frameworks", [])
        if tools:
            st.markdown(" · ".join([f"`{t}`" for t in tools]))

    # ── Tab 5: Grant Proposal ────────────────────────────────────────────────
    with tabs[4]:
        st.markdown("## 📝 Grant Proposal")
        grant_data = results.get("grant", {})
        
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
                label="⬇️ Download JSON",
                data=json.dumps(grant_data, indent=2),
                file_name=f"{topic.replace(' ', '_').lower()}_grant.json",
                mime="application/json",
                use_container_width=True
            )

    # ── Tab 6: Novelty Score ─────────────────────────────────────────────────
    with tabs[5]:
        st.markdown("## ⭐ Novelty Assessment")
        nov = results.get("novelty", {})
        score = nov.get("novelty_score", 0)
        
        if score < 40:
            color, emoji, label = "#ef4444", "🔴", "Low Novelty"
        elif score < 70:
            color, emoji, label = "#eab308", "🟡", "Moderate Novelty"
        else:
            color, emoji, label = "#22c55e", "🟢", "High Novelty"
        
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
                st.markdown(f"- 📄 {p}")
        else:
            st.caption("No closest papers identified.")

import argparse
import time
import os
from agents.literature_agent import run as run_literature
from agents.tree_agent import run as run_tree
from agents.trend_agent import run as run_trend
from agents.gap_agent import run as run_gap
from agents.methodology_agent import run as run_methodology
from agents.grant_agent import run as run_grant
from agents.novelty_agent import run as run_novelty
from utils.cache import save, load, CACHE_DIR
from utils.quality_gate import evaluate_quality

def delay():
    print("Cooling down for 2s to allow rotating keys to reset limits...")
    time.sleep(2)

def run_pipeline(topic: str) -> dict:
    print(f"Starting pipeline for topic: '{topic}'\n")
    
    # Write topic marker so Streamlit can detect topic changes
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(os.path.join(CACHE_DIR, "_topic.txt"), "w") as f:
        f.write(topic)

    # Agent 1
    papers = load("papers")
    if not papers:
        papers = run_literature(topic)
        save("papers", papers)
        delay()

    # Tree Builder
    tree = load("tree")
    if not tree:
        tree = run_tree(papers)
        save("tree", tree)
        delay()

    # Quality Gate 1
    evaluate_quality("post_literature", tree)
    delay()

    # Agent 2
    trends = load("trends")
    if not trends:
        trends = run_trend(tree)
        save("trends", trends)
        delay()

    # Agent 3
    gaps = load("gaps")
    if not gaps:
        gaps = run_gap(tree, trends)
        save("gaps", gaps)
        delay()

    # Quality Gate 2
    evaluate_quality("post_gap", gaps)
    delay()

    # Agent 4
    methodology = load("methodology")
    if not methodology:
        selected_gap_id = gaps.get("selected_gap", "")
        gap_desc = next(
            (g["description"] for g in gaps.get("identified_gaps", []) 
             if g["gap_id"] == selected_gap_id),
            selected_gap_id  # fallback to ID if lookup fails
        )
        methodology = run_methodology(gap_desc, topic)
        save("methodology", methodology)
        delay()

    # Agent 5
    grant = load("grant")
    if not grant:
        selected_gap_id = gaps.get("selected_gap", "")
        gap_desc = next(
            (g["description"] for g in gaps.get("identified_gaps", []) 
             if g["gap_id"] == selected_gap_id),
            selected_gap_id  # fallback to ID if lookup fails
        )
        grant = run_grant(topic, gap_desc, methodology)
        save("grant", grant)
        delay()

    # Agent 6
    novelty = load("novelty")
    if not novelty:
        novelty = run_novelty(grant, tree)
        save("novelty", novelty)
        delay()

    return {
        "papers": papers,
        "tree": tree,
        "trends": trends,
        "gaps": gaps,
        "methodology": methodology,
        "grant": grant,
        "novelty": novelty
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VMARO Orchestrator Pipeline")
    parser.add_argument("--topic", type=str, required=True, help="The research topic to analyze.")
    args = parser.parse_args()

    results = run_pipeline(args.topic)
    print("\nPipeline execution complete. Results saved to cache/ directory.")

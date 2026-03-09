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
from agents.grant_agent import run as run_grant
from agents.novelty_agent import run as run_novelty
from utils.cache import save, load, CACHE_DIR
from utils.quality_gate import evaluate_quality

try:
    from crewai import Agent, Task, Crew, Process
except ImportError:
    pass

def execute_task_wrapper(func, args_getter, cache_key):
    """A helper to wrap our python functions inside a CrewAI Task execution."""
    def wrapper(context=None):
        cached = load(cache_key)
        if cached:
            return cached
        result = func(*args_getter(context))
        save(cache_key, result)
        delay()
        return result
    return wrapper

def delay():
    print("Cooling down for 2s to allow rotating keys to reset limits...")
    time.sleep(2)

def run_pipeline(topic: str) -> dict:
    print(f"Starting pipeline for topic: '{topic}'\n")
    
    # Write topic marker so Streamlit can detect topic changes
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(os.path.join(CACHE_DIR, "_topic.txt"), "w") as f:
        f.write(topic)

    # Mock OpenAI key to satisfy CrewAI's default Agent(llm=ChatOpenAI()) instantiation without errors
    os.environ["OPENAI_API_KEY"] = "sk-mock-key-for-crewai-init"

    # State container for dicts
    state = {}

    # Define minimal Agents (they don't need real LLMs because we override task.execute)
    dummy_agent = Agent(
        role="VMARO Orchestrator",
        goal="Run the pipeline",
        backstory="Automated pipeline runner",
        allow_delegation=False
    )

    class CustomTask(Task):
        func: object = None
        def execute_sync(self, *args, **kwargs):
            import crewai.task
            # Return a mocked TaskOutput
            try:
                self.func()
                return "Task Complete"
            except Exception as e:
                return f"Task Failed: {e}"

    # Agent 1
    t1 = CustomTask(
        description="Literature Mining",
        expected_output="JSON with papers",
        agent=dummy_agent,
        func=lambda: state.setdefault("papers", load("papers") or (save("papers", run_literature(topic)) or delay()) or load("papers"))
    )

    # Tree Builder
    t2 = CustomTask(
        description="Thematic Clustering",
        expected_output="Tree hierarchy JSON",
        agent=dummy_agent,
        func=lambda: state.setdefault("tree", load("tree") or (save("tree", run_tree(state.get("papers"))) or delay()) or load("tree"))
    )
    
    t2_gate = CustomTask(description="Quality Gate 1", expected_output="QG output", agent=dummy_agent, 
        func=lambda: state.setdefault("qg1", load("qg1") or (save("qg1", evaluate_quality("post_literature", state.get("tree"))) or delay()) or load("qg1")))

    # Agent 2
    t3 = CustomTask(
        description="Trend Analysis",
        expected_output="Trends JSON",
        agent=dummy_agent,
        func=lambda: state.setdefault("trends", load("trends") or (save("trends", run_trend(state.get("tree"))) or delay()) or load("trends"))
    )

    # Agent 3
    t4 = CustomTask(
        description="Gap Identification",
        expected_output="Gaps JSON",
        agent=dummy_agent,
        func=lambda: state.setdefault("gaps", load("gaps") or (save("gaps", run_gap(state.get("tree"), state.get("trends"))) or delay()) or load("gaps"))
    )

    t4_gate = CustomTask(description="Quality Gate 2", expected_output="QG output", agent=dummy_agent,
        func=lambda: state.setdefault("qg2", load("qg2") or (save("qg2", evaluate_quality("post_gap", state.get("gaps"))) or delay()) or load("qg2")))

    def get_gap_desc():
        selected = state["gaps"].get("selected_gap", "")
        return next((g["description"] for g in state["gaps"].get("identified_gaps", []) if g["gap_id"] == selected), selected)

    # Agent 4
    t5 = CustomTask(
        description="Methodology Design",
        expected_output="Methodology JSON",
        agent=dummy_agent,
        func=lambda: state.setdefault("methodology", load("methodology") or (save("methodology", run_methodology(get_gap_desc(), topic)) or delay()) or load("methodology"))
    )

    # Agent 5
    t6 = CustomTask(
        description="Grant Writing",
        expected_output="Grant JSON",
        agent=dummy_agent,
        func=lambda: state.setdefault("grant", load("grant") or (save("grant", run_grant(topic, get_gap_desc(), state.get("methodology"))) or delay()) or load("grant"))
    )

    # Agent 6
    t7 = CustomTask(
        description="Novelty Scoring",
        expected_output="Novelty Score JSON",
        agent=dummy_agent,
        func=lambda: state.setdefault("novelty", load("novelty") or (save("novelty", run_novelty(state.get("grant"), state.get("tree"))) or delay()) or load("novelty"))
    )

    # Orchestrate with CrewAI
    crew = Crew(
        agents=[dummy_agent],
        tasks=[t1, t2, t2_gate, t3, t4, t4_gate, t5, t6, t7],
        process=Process.sequential,
        verbose=True
    )
    
    print("[CrewAI] Triggering Crew kickoff...")
    try:
        crew.kickoff()
    except Exception as e:
        print(f"[CrewAI] Real Crew kickoff encountered an error (likely due to mock LLM auth): {e}")
        print("[CrewAI] Falling back to sequential execution of custom tasks...")
        for task in crew.tasks:
            try:
                task.func()
                print(f"[CrewAI] Executed {task.description} successfully.")
            except Exception as e2:
                print(f"[CrewAI] Error executing {task.description}: {e2}")

    return state

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VMARO Orchestrator Pipeline")
    parser.add_argument("--topic", type=str, required=True, help="The research topic to analyze.")
    args = parser.parse_args()

    results = run_pipeline(args.topic)
    print("\nPipeline execution complete. Results saved to cache/ directory.")

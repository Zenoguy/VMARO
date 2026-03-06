def run(topic: str) -> dict:
    """
    Literature Mining Agent.
    Retrieves papers from Semantic Scholar and summarises with Gemini Flash.
    """
    return {
        "topic": topic,
        "papers": []
    }

import os
from agents.literature_agent import run

if __name__ == "__main__":
    import agents.literature_agent
    original_call = agents.literature_agent.call_gemini_with_retry
    
    def wrapped_call(prompt, system_instruction=None):
        print("--- PROMPT ---")
        print(prompt[:500] + "... (truncated)")
        res = original_call(prompt, system_instruction)
        print("--- RESPONSE ---")
        print(res.text)
        return res

    agents.literature_agent.call_gemini_with_retry = wrapped_call
    
    result = run("AI in High frequency trading")
    print(result)

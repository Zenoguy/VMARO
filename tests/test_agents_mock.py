import unittest
import os
import json
from unittest.mock import patch

from agents import (
    literature_agent,
    tree_agent,
    trend_agent,
    gap_agent,
    methodology_agent,
    grant_agent,
    novelty_agent
)

class TestAgentsMock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set environment variables for all tests in this suite
        os.environ["MOCK_MODE"] = "true"
        os.environ["DEMO_MODE"] = "true"
        os.environ["GROQ_API_KEY_1"] = "mock_key"
        
        # Load all mocks
        with open("mock_data/mock_papers.json") as f:
            cls.mock_papers = json.load(f)
        with open("mock_data/mock_tree.json") as f:
            cls.mock_tree = json.load(f)
        with open("mock_data/mock_gaps.json") as f: # trend agent returns first half of this roughly
            # Not exact, but we will mock a trend object specifically
            pass
            
        with open("mock_data/mock_trends.json") as f:
            cls.mock_trends = json.load(f)
            
        with open("mock_data/mock_gaps.json") as f:
            cls.mock_gaps = json.load(f)
            
        with open("mock_data/mock_methodology.json") as f:
            cls.mock_methodology = json.load(f)
            
        with open("mock_data/mock_grant.json") as f:
            cls.mock_grant = json.load(f)

    def test_literature_agent(self):
        res = literature_agent.run("Federated Learning in Healthcare")
        self.assertIsInstance(res, dict)
        self.assertIn("topic", res)
        self.assertIn("papers", res)

    def test_tree_agent_live(self):
        res = tree_agent.run(self.mock_papers)
        self.assertIsInstance(res, dict)
        self.assertIn("root", res)
        self.assertIn("themes", res)
        self.assertIn("emerging_directions", res)

    def test_trend_agent_live(self):
        res = trend_agent.run(self.mock_tree)
        self.assertIsInstance(res, dict)
        self.assertIn("dominant_clusters", res)
        self.assertIn("emerging_trends", res)

    def test_gap_agent_live(self):
        res = gap_agent.run(self.mock_tree, self.mock_trends)
        self.assertIsInstance(res, dict)
        self.assertIn("identified_gaps", res)
        self.assertIn("selected_gap", res)

    def test_methodology_agent_live(self):
        topic = "Federated Learning in Healthcare"
        gap_desc = self.mock_gaps["identified_gaps"][0]["description"]
        res = methodology_agent.run(gap_desc, topic)
        self.assertIsInstance(res, dict)
        self.assertIn("suggested_datasets", res)
        self.assertIn("evaluation_metrics", res)
        self.assertIn("baseline_models", res)
        self.assertIn("experimental_design", res)
        self.assertIn("tools_and_frameworks", res)

    def test_grant_agent_live(self):
        topic = "Federated Learning in Healthcare"
        gap_desc = self.mock_gaps["identified_gaps"][0]["description"]
        res = grant_agent.run(topic, gap_desc, self.mock_methodology)
        self.assertIsInstance(res, dict)
        self.assertIn("problem_statement", res)
        self.assertIn("proposed_methodology", res)
        self.assertIn("evaluation_plan", res)
        self.assertIn("expected_contribution", res)
        self.assertIn("timeline", res)
        self.assertIn("budget_estimate", res)

    def test_novelty_agent_live(self):
        res = novelty_agent.run(self.mock_grant, self.mock_tree)
        self.assertIsInstance(res, dict)
        self.assertIn("closest_papers", res)
        self.assertIn("similarity_reasoning", res)
        self.assertIn("novelty_score", res)
        self.assertIn("score_justification", res)

if __name__ == '__main__':
    unittest.main()

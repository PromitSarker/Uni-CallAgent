import threading
import time
import unittest
from unittest import mock

from api import service


class BackgroundSummaryTests(unittest.TestCase):
    def setUp(self):
        # fresh single-thread executor so tests don't interfere
        self._old = service._summary_executor
        service._summary_executor = service.ThreadPoolExecutor(max_workers=1, thread_name_prefix="summary")
        self.addCleanup(self.cleanup)

    def cleanup(self):
        service._summary_executor.shutdown(wait=True)
        service._summary_executor = self._old

    def test_runs_off_the_calling_thread_and_does_not_block(self):
        ran = threading.Event()
        who = []

        def slow(state):
            who.append(threading.current_thread().name)
            time.sleep(0.3)
            ran.set()

        with mock.patch.object(service, "summarize_conversation_node", slow):
            t0 = time.monotonic()
            service._summarize_in_background("c1", {"conversation_id": "c1"})
            self.assertLess(time.monotonic() - t0, 0.1)  # returned immediately
            self.assertTrue(ran.wait(3))
        self.assertTrue(who[0].startswith("summary"))

    def test_superseded_summary_is_skipped_and_order_is_fifo(self):
        gate = threading.Event()
        seen = []

        def fake(state):
            if state["n"] == 0:
                gate.wait(3)  # hold the worker so jobs 1 and 2 queue up
            seen.append(state["n"])

        with mock.patch.object(service, "summarize_conversation_node", fake):
            service._summarize_in_background("c2", {"n": 0})
            time.sleep(0.05)
            service._summarize_in_background("c2", {"n": 1})  # superseded by 2
            service._summarize_in_background("c2", {"n": 2})
            gate.set()
            service._summary_executor.shutdown(wait=True)
            service._summary_executor = service.ThreadPoolExecutor(max_workers=1)
        # job 0 was already running; 1 skipped; 2 runs last
        self.assertEqual(seen, [0, 2])
        self.assertNotIn("c2", service._summary_latest)

    def test_different_conversations_both_run(self):
        seen = []
        with mock.patch.object(service, "summarize_conversation_node", lambda s: seen.append(s["id"])):
            service._summarize_in_background("a", {"id": "a"})
            service._summarize_in_background("b", {"id": "b"})
            service._summary_executor.shutdown(wait=True)
            service._summary_executor = service.ThreadPoolExecutor(max_workers=1)
        self.assertEqual(sorted(seen), ["a", "b"])

    def test_errors_in_summary_are_swallowed(self):
        def boom(state):
            raise RuntimeError("llm down")

        with mock.patch.object(service, "summarize_conversation_node", boom):
            service._summarize_in_background("c3", {})
            service._summary_executor.shutdown(wait=True)
            service._summary_executor = service.ThreadPoolExecutor(max_workers=1)
        self.assertNotIn("c3", service._summary_latest)


class GraphShapeTests(unittest.TestCase):
    def test_summarize_is_no_longer_a_graph_node(self):
        from agent.graph import agent
        self.assertNotIn("summarize", agent.get_graph().nodes)

    def test_no_tool_turn_ends_without_extra_llm_calls(self):
        from langchain_core.messages import AIMessage, HumanMessage
        from agent import graph, nodes

        calls = {"model": 0, "summ": 0}

        def fake_model(state):
            calls["model"] += 1
            return {"messages": [AIMessage(content="hi there")], "final_response": "hi there"}

        # build the graph with the patched node reference used by the graph module
        with mock.patch.object(graph, "call_model_node", fake_model), \
             mock.patch.object(nodes, "summarize_conversation_node", lambda s: calls.__setitem__("summ", calls["summ"] + 1)):
            g = graph.build_graph()
            out = g.invoke({"conversation_id": "x", "messages": [HumanMessage(content="hello")],
                            "escalate": False, "session_summary": ""})
        self.assertEqual(out["final_response"], "hi there")
        self.assertEqual(calls, {"model": 1, "summ": 0})


if __name__ == "__main__":
    unittest.main()

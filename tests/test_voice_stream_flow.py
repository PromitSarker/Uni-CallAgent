"""End-to-end tests of /api/voice/ws against a fake Gemini Live server.

No real Gemini, DB or Chroma access: stores/KB/greeting loaders are patched.
"""
import asyncio
import base64
import json
import signal
import threading
import time
import unittest
from unittest import mock

from starlette.testclient import TestClient
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from api.main import app
from api.routers import voice_stream as vs

KB = "Dhaka Active-Active Cluster: three (3) data centers.\n\nISO 27001:2022 certified."
GREETING_PCM = base64.b64encode(b"\x01\x00" * 24000 * 2).decode()  # 2 s
AUDIO_CHUNK = base64.b64encode(b"\x02\x00" * 2400).decode()


class FakeGemini:
    def __init__(self, reject_vad=False, tool=None, setup_delay=0.0):
        self.reject_vad, self.tool, self.setup_delay = reject_vad, tool, setup_delay
        self.sessions = []
        self.ready = threading.Event()
        self.port = None

    async def _speak(self, ws):
        for _ in range(2):
            await ws.send(json.dumps({"serverContent": {"modelTurn": {"parts": [
                {"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": AUDIO_CHUNK}}]}}}))
        await ws.send(json.dumps({"serverContent": {"turnComplete": True}}))

    async def _handler(self, ws):
        sess = {"setup": None, "messages": []}
        setup = json.loads(await ws.recv())
        sess["setup"] = setup
        self.sessions.append(sess)
        if self.reject_vad and "realtimeInputConfig" in setup["setup"]:
            await ws.close(code=1007, reason="invalid argument")
            return
        await asyncio.sleep(self.setup_delay)
        await ws.send(json.dumps({"setupComplete": {}}))
        try:
            async for raw in ws:
                m = json.loads(raw)
                sess["messages"].append(m)
                if "clientContent" in m:
                    text = m["clientContent"]["turns"][0]["parts"][0]["text"]
                    if "greet" in text.lower():
                        await self._speak(ws)
                elif "realtimeInput" in m and not sess.get("replied"):
                    sess["replied"] = True
                    if self.tool:
                        await ws.send(json.dumps({"toolCall": {"functionCalls": [
                            {"id": "call-1", "name": self.tool, "args": {}}]}}))
                    else:
                        await self._speak(ws)
                elif "toolResponse" in m:
                    sess["tool_response"] = m
                    await self._speak(ws)
        except ConnectionClosed:
            pass

    def start(self):
        def run():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            async def main():
                self.stop = asyncio.Event()
                async with serve(self._handler, "127.0.0.1", 0) as server:
                    self.port = server.sockets[0].getsockname()[1]
                    self.ready.set()
                    await self.stop.wait()

            self.loop.run_until_complete(main())

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        assert self.ready.wait(5)

    def shutdown(self):
        self.loop.call_soon_threadsafe(self.stop.set)
        self.thread.join(5)


def system_text(session):
    return session["setup"]["setup"]["systemInstruction"]["parts"][0]["text"]


def tool_names(session):
    tools = session["setup"]["setup"].get("tools") or []
    return [d["name"] for t in tools for d in t.get("functionDeclarations", [])]


class VoiceFlowBase(unittest.TestCase):
    cached = GREETING_PCM
    kb = KB
    fake_kwargs = {}

    def setUp(self):
        signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError("test hung")))
        signal.alarm(40)
        self.addCleanup(signal.alarm, 0)
        self.fake = FakeGemini(**self.fake_kwargs)
        self.fake.start()
        self.addCleanup(self.fake.shutdown)
        patches = [
            mock.patch.object(vs, "GEMINI_WS_URL", f"ws://127.0.0.1:{self.fake.port}"),
            mock.patch.object(vs.admin_store, "get_setting", lambda k, d="": "English"),
            mock.patch.object(vs.conversation_store, "get_session_summary", lambda cid: ""),
            mock.patch.object(vs.conversation_store, "get_messages", lambda cid: []),
            mock.patch.object(vs.conversation_store, "record_token_usage", lambda *a, **k: None),
            mock.patch.object(vs, "get_kb_text", lambda max_chars=0: self.kb),
            mock.patch.object(vs, "load_cached_greeting", lambda lang: self.cached),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.client = TestClient(app)

    def converse(self, ws):
        """Send one chunk of 'speech' and return the next server message."""
        ws.send_text(json.dumps({"audioB64": "AAAA"}))
        return ws.receive_json()


class CachedGreetingTests(VoiceFlowBase):
    fake_kwargs = {"setup_delay": 0.8}

    def test_greeting_plays_before_gemini_is_ready_and_model_is_told(self):
        t0 = time.monotonic()
        with self.client.websocket_connect("/api/voice/ws/t-cached") as ws:
            first = ws.receive_json()
            elapsed = time.monotonic() - t0
            self.assertEqual(first, {"audioB64": GREETING_PCM})
            self.assertLess(elapsed, 0.6, "greeting must not wait for the 0.8s Gemini setup")
            self.assertEqual(ws.receive_json(), {"turnComplete": True})
            reply = self.converse(ws)  # live session works afterwards
            self.assertIn("audioB64", reply)
        s = self.fake.sessions[0]
        self.assertIn("ALREADY been greeted", system_text(s))
        self.assertNotIn("MUST start exactly with", system_text(s))
        self.assertFalse([m for m in s["messages"] if "clientContent" in m],
                         "model must not be asked to greet when the greeting was already played")

    def test_inline_kb_and_tools_and_vad(self):
        with self.client.websocket_connect("/api/voice/ws/t-kb") as ws:
            ws.receive_json(); ws.receive_json()
            self.converse(ws)
        s = self.fake.sessions[0]
        txt = system_text(s)
        self.assertIn("three (3) data centers", txt)
        self.assertIn("--- KNOWLEDGE BASE", txt)
        self.assertNotIn("search_knowledge_base", tool_names(s))
        self.assertIn("save_collected_information", tool_names(s))
        self.assertIn("end_call", tool_names(s))
        aad = s["setup"]["setup"]["realtimeInputConfig"]["automaticActivityDetection"]
        self.assertEqual(aad["silenceDurationMs"], vs.VAD_SILENCE_MS)
        self.assertEqual(aad["endOfSpeechSensitivity"], vs.VAD_END_SENSITIVITY)

    def test_after_cached_greeting_model_audio_is_streamed_not_buffered(self):
        with self.client.websocket_connect("/api/voice/ws/t-stream") as ws:
            ws.receive_json(); ws.receive_json()
            ws.send_text(json.dumps({"audioB64": "AAAA"}))
            m1, m2, m3 = ws.receive_json(), ws.receive_json(), ws.receive_json()
        self.assertEqual([("audioB64" in m) for m in (m1, m2)], [True, True])
        self.assertEqual(m3, {"turnComplete": True})


class LiveGreetingFallbackTests(VoiceFlowBase):
    cached = None  # no usable cached greeting

    def test_model_is_asked_to_greet_and_audio_is_merged(self):
        with self.client.websocket_connect("/api/voice/ws/t-live") as ws:
            first = ws.receive_json()
            self.assertIn("audioB64", first)
            merged = base64.b64decode(first["audioB64"])
            self.assertEqual(len(merged), 2 * len(base64.b64decode(AUDIO_CHUNK)))  # old behaviour: one chunk
            self.assertEqual(ws.receive_json(), {"turnComplete": True})
        s = self.fake.sessions[0]
        self.assertIn('you MUST start exactly with "Hello! Thank you for calling Unified Cloud. How can I help you today?"',
                      system_text(s))
        self.assertNotIn("ALREADY been greeted", system_text(s))
        self.assertTrue([m for m in s["messages"] if "clientContent" in m])


class ToolSearchFallbackTests(VoiceFlowBase):
    kb = None  # KB missing / too large -> search tool path

    def test_search_tool_offered_and_chat_style_rules_kept(self):
        with self.client.websocket_connect("/api/voice/ws/t-tool") as ws:
            ws.receive_json(); ws.receive_json()
            self.converse(ws)
        s = self.fake.sessions[0]
        self.assertIn("search_knowledge_base", tool_names(s))
        self.assertIn("ALWAYS call the `search_knowledge_base` tool first", system_text(s))
        self.assertNotIn("--- KNOWLEDGE BASE", system_text(s))


class VadRejectionTests(VoiceFlowBase):
    fake_kwargs = {"reject_vad": True}

    def test_retries_without_realtime_input_config(self):
        with self.client.websocket_connect("/api/voice/ws/t-vad") as ws:
            ws.receive_json(); ws.receive_json()
            reply = self.converse(ws)
            self.assertIn("audioB64", reply)
        self.assertEqual(len(self.fake.sessions), 2)
        self.assertIn("realtimeInputConfig", self.fake.sessions[0]["setup"]["setup"])
        self.assertNotIn("realtimeInputConfig", self.fake.sessions[1]["setup"]["setup"])


class VadDisabledTests(VoiceFlowBase):
    def test_zero_silence_means_gemini_defaults(self):
        with mock.patch.object(vs, "VAD_SILENCE_MS", 0):
            with self.client.websocket_connect("/api/voice/ws/t-novad") as ws:
                ws.receive_json(); ws.receive_json()
                self.converse(ws)
        self.assertNotIn("realtimeInputConfig", self.fake.sessions[0]["setup"]["setup"])


class ToolExecutionTests(VoiceFlowBase):
    fake_kwargs = {"tool": "escalate"}

    def test_tool_runs_in_worker_thread_and_result_returns_to_model(self):
        seen = {}

        def fake_tool(args):
            seen["thread"] = threading.current_thread().name
            return "tool-ok"

        with mock.patch.dict(vs.LIVE_TOOLS_MAP, {"escalate": fake_tool}):
            with self.client.websocket_connect("/api/voice/ws/t-exec") as ws:
                ws.receive_json(); ws.receive_json()
                reply = self.converse(ws)
                self.assertIn("audioB64", reply)
        self.assertIn("AnyIO worker", seen["thread"])
        resp = self.fake.sessions[0]["tool_response"]["toolResponse"]["functionResponses"][0]
        self.assertEqual(resp["id"], "call-1")
        self.assertEqual(resp["response"], {"result": "tool-ok"})


class EndCallTests(VoiceFlowBase):
    fake_kwargs = {"tool": "end_call"}

    def test_end_call_still_signals_client(self):
        with self.client.websocket_connect("/api/voice/ws/t-end") as ws:
            ws.receive_json(); ws.receive_json()
            ws.send_text(json.dumps({"audioB64": "AAAA"}))
            self.assertEqual(ws.receive_json(), {"end_call": True})


class ResilienceTests(VoiceFlowBase):
    def test_lookup_failures_do_not_break_the_call(self):
        def boom(cid):
            raise RuntimeError("db down")

        with mock.patch.object(vs.conversation_store, "get_session_summary", boom), \
             mock.patch.object(vs.conversation_store, "get_messages", boom), \
             mock.patch.object(vs, "get_kb_text", boom):
            with self.client.websocket_connect("/api/voice/ws/t-dbfail") as ws:
                self.assertEqual(ws.receive_json(), {"audioB64": GREETING_PCM})
                ws.receive_json()
                self.assertIn("audioB64", self.converse(ws))
        s = self.fake.sessions[0]
        self.assertIn("search_knowledge_base", tool_names(s))  # KB failed -> tool mode

    def test_client_disconnect_during_setup_is_clean(self):
        self.fake.setup_delay = 1.0
        with self.client.websocket_connect("/api/voice/ws/t-early") as ws:
            ws.receive_json()
        time.sleep(1.5)  # server-side cleanup finishes without raising


class RealtimeConfigTests(unittest.TestCase):
    def test_config_shape_and_env_controls(self):
        cfg = vs._realtime_input_config()
        self.assertEqual(cfg["automaticActivityDetection"]["silenceDurationMs"], vs.VAD_SILENCE_MS)
        with mock.patch.object(vs, "VAD_START_SENSITIVITY", "START_SENSITIVITY_HIGH"):
            self.assertEqual(vs._realtime_input_config()["automaticActivityDetection"]["startOfSpeechSensitivity"],
                             "START_SENSITIVITY_HIGH")
        with mock.patch.object(vs, "VAD_SILENCE_MS", 0):
            self.assertIsNone(vs._realtime_input_config())


if __name__ == "__main__":
    unittest.main()

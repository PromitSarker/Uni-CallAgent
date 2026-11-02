import base64
import json
import os
import tempfile
import unittest

from agent import greetings

CFG = {"greeting": "Hello there.", "voice": "Aoede", "code": "en-US"}


def pcm_b64(seconds):
    return base64.b64encode(b"\x01\x00" * int(greetings.OUTPUT_SAMPLE_RATE * seconds)).decode()


class ValidateEntryTests(unittest.TestCase):
    def entry(self, **kw):
        e = {"text": CFG["greeting"], "voice": "Aoede", "audioB64": pcm_b64(3)}
        e.update(kw)
        return e

    def test_good_entry(self):
        e = self.entry()
        self.assertEqual(greetings.validate_entry(e, CFG), e["audioB64"])

    def test_legacy_entry_without_voice_is_ok(self):
        e = self.entry()
        del e["voice"]
        self.assertIsNotNone(greetings.validate_entry(e, CFG))

    def test_text_mismatch_rejected(self):
        self.assertIsNone(greetings.validate_entry(self.entry(text="Other"), CFG))

    def test_voice_mismatch_rejected(self):
        self.assertIsNone(greetings.validate_entry(self.entry(voice="Leda"), CFG))

    def test_too_long_rejected(self):  # the old 74 s Portuguese render
        self.assertIsNone(greetings.validate_entry(self.entry(audioB64=pcm_b64(40)), CFG))

    def test_too_short_rejected(self):
        self.assertIsNone(greetings.validate_entry(self.entry(audioB64=pcm_b64(0.2)), CFG))

    def test_garbage_rejected(self):
        for bad in (None, "not a dict", {}, self.entry(audioB64="!!!"), self.entry(audioB64=""),
                    self.entry(audioB64=base64.b64encode(b"\x00" * 100001).decode())):
            self.assertIsNone(greetings.validate_entry(bad, CFG))


class LoadTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "greetings.json")
        self._old = greetings.GREETINGS_PATH
        greetings.GREETINGS_PATH = self.path
        self.addCleanup(setattr, greetings, "GREETINGS_PATH", self._old)

    def write(self, data):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        # make the mtime differ so the cache notices
        st = os.stat(self.path)
        os.utime(self.path, (st.st_atime, st.st_mtime + 5 + len(json.dumps(data)) % 7))

    def test_missing_file_gives_none(self):
        self.assertIsNone(greetings.load_cached_greeting("English"))

    def test_corrupt_file_gives_none(self):
        with open(self.path, "w") as f:
            f.write("{not json")
        self.assertIsNone(greetings.load_cached_greeting("English"))

    def test_valid_entry_loaded_and_reloaded_on_change(self):
        cfg = greetings.LANGUAGE_CONFIGS["English"]
        good = {"text": cfg["greeting"], "voice": cfg["voice"], "audioB64": pcm_b64(3)}
        self.write({"English": good})
        self.assertEqual(greetings.load_cached_greeting("English"), good["audioB64"])
        self.write({"English": dict(good, text="changed")})
        self.assertIsNone(greetings.load_cached_greeting("English"))

    def test_unknown_language_uses_default(self):
        cfg = greetings.LANGUAGE_CONFIGS[greetings.DEFAULT_LANGUAGE]
        good = {"text": cfg["greeting"], "voice": cfg["voice"], "audioB64": pcm_b64(3)}
        self.write({greetings.DEFAULT_LANGUAGE: good})
        self.assertEqual(greetings.load_cached_greeting("Klingon"), good["audioB64"])

    def test_every_language_has_complete_config(self):
        for name, cfg in greetings.LANGUAGE_CONFIGS.items():
            self.assertTrue(all(cfg.get(k) for k in ("code", "greeting", "voice")), name)


if __name__ == "__main__":
    unittest.main()

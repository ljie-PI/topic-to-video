import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cmd(*args, cwd=ROOT):
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


class ScriptContractTests(unittest.TestCase):
    def test_scene_anchor_fails_when_any_anchor_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            transcript = tmp_path / "transcript.json"
            scenes = tmp_path / "scenes.json"
            output = tmp_path / "scene-timing.json"

            transcript.write_text(
                json.dumps(
                    [
                        {
                            "begin": 0,
                            "end": 2500,
                            "text": "第一段第二段",
                            "words": [
                                {"text": "第一段", "begin": 0, "end": 1000},
                                {"text": "第二段", "begin": 1000, "end": 2500},
                            ],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            scenes.write_text(
                json.dumps(
                    [
                        {"id": "s1", "anchor": "第一段"},
                        {"id": "s2", "anchor": "不存在"},
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = run_cmd(sys.executable, ROOT / "scripts/scene-anchor.py", transcript, scenes, output)

            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["success"])
            self.assertIn("anchor", payload["error"])
            self.assertFalse(output.exists())

    def test_scene_anchor_keeps_exact_adjacent_durations_without_fudge(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            transcript = tmp_path / "transcript.json"
            scenes = tmp_path / "scenes.json"
            output = tmp_path / "scene-timing.json"

            transcript.write_text(
                json.dumps(
                    [
                        {
                            "begin": 0,
                            "end": 2500,
                            "text": "第一段第二段",
                            "words": [
                                {"text": "第一段", "begin": 0, "end": 1000},
                                {"text": "第二段", "begin": 1000, "end": 2500},
                            ],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            scenes.write_text(
                json.dumps(
                    [
                        {"id": "s1", "anchor": "第一段"},
                        {"id": "s2", "anchor": "第二段"},
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = run_cmd(sys.executable, ROOT / "scripts/scene-anchor.py", transcript, scenes, output)

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(data["scenes"]), 2)
            self.assertEqual(data["scenes"][0]["duration_s"], 1.0)
            self.assertEqual(data["scenes"][1]["duration_s"], 1.5)
            self.assertNotIn("0.999", output.read_text(encoding="utf-8"))

    def test_voice_clone_cli_documents_file_voice_and_rate(self):
        result = run_cmd(sys.executable, ROOT / "scripts/voice-clone.py", "--help")

        self.assertEqual(result.returncode, 0)
        self.assertIn("--input-file", result.stdout)
        self.assertIn("--voice", result.stdout)
        self.assertIn("--speech-rate", result.stdout)

    def test_fonts_dawn_dry_run_reports_css_without_fonttools_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cmd("bash", ROOT / "scripts/fonts-download.sh", tmp, "dawn", "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("rose-pine-dawn-fonts.css", result.stderr)

    def test_merge_paper_manifest_helper_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            harvest = Path(tmp) / "harvest_page"
            harvest.mkdir()
            (harvest / "manifest_papers.json").write_text(
                json.dumps(
                    {
                        "success": True,
                        "entries": [
                            {"slug": "main-paper", "source_type": "paper_pdf", "title": "Main"},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (harvest / "manifest.json").write_text(
                json.dumps(
                    {
                        "success": True,
                        "entries": [
                            {"slug": "old-paper", "source_type": "paper_pdf", "title": "Old"},
                            {"slug": "web", "source_type": "web", "title": "Web"},
                        ],
                        "pending_downloads": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = run_cmd(sys.executable, ROOT / "scripts/merge-paper-manifest.py", "--harvest-dir", harvest)

            self.assertEqual(result.returncode, 0, result.stderr)
            merged = json.loads((harvest / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual([entry["slug"] for entry in merged["entries"]], ["main-paper", "web"])

    def test_apply_video_download_result_updates_manifest_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            harvest = Path(tmp) / "harvest_page"
            source = harvest / "source-a"
            source.mkdir(parents=True)
            video = {
                "url": "https://www.youtube.com/watch?v=abc123",
                "download_required": True,
                "id": "pending_001",
            }
            entry = {"slug": "source-a", "videos": [video.copy()]}
            manifest = {
                "success": True,
                "entries": [entry],
                "pending_downloads": [
                    {"url": video["url"], "source_slug": "source-a", "suggested_output_dir": str(source / "videos")}
                ],
            }
            (harvest / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            (source / "metadata.json").write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")

            result_json = Path(tmp) / "download.json"
            result_json.write_text(
                json.dumps(
                    {
                        "success": True,
                        "files": [
                            str(source / "videos" / "abc123.mp4"),
                            str(source / "videos" / "abc123.en.vtt"),
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = run_cmd(
                sys.executable,
                ROOT / "scripts/apply-video-download-result.py",
                "--harvest-dir",
                harvest,
                "--source-slug",
                "source-a",
                "--url",
                video["url"],
                "--result-json",
                result_json,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            updated_manifest = json.loads((harvest / "manifest.json").read_text(encoding="utf-8"))
            updated_video = updated_manifest["entries"][0]["videos"][0]
            self.assertFalse(updated_video["download_required"])
            self.assertEqual(updated_video["id"], "abc123")
            self.assertTrue(updated_video["local_path"].endswith("abc123.mp4"))
            self.assertTrue(updated_video["subtitle_path"].endswith("abc123.en.vtt"))

    def test_check_cjk_fonts_ignores_script_and_style_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = Path(tmp) / "index.html"
            html.write_text(
                """
                <html>
                  <head>
                    <style>
                      .latin { font-family: Caveat; }
                      /* 中文注释 should not be treated as rendered text */
                    </style>
                  </head>
                  <body>
                    <script>const message = "中文脚本";</script>
                    <div class="latin">Latin only</div>
                  </body>
                </html>
                """,
                encoding="utf-8",
            )

            result = run_cmd(sys.executable, ROOT / "scripts/check-cjk-fonts.py", html)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["findings_count"], 0)


if __name__ == "__main__":
    unittest.main()

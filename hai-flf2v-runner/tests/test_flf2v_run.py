import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import flf2v_run


class Flf2VRunTests(unittest.TestCase):
    def test_parse_prompt_file_splits_positive_and_negative(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt_file = Path(tmp) / "prompt.txt"
            prompt_file.write_text(
                "正向提示词\n\n画面稳定，角色自然呼吸。\n\n负面提示词\n\n模糊，闪烁，水印。",
                encoding="utf-8",
            )

            parsed = flf2v_run.parse_prompt_file(prompt_file)

        self.assertEqual(parsed.positive, "画面稳定，角色自然呼吸。")
        self.assertEqual(parsed.negative, "模糊，闪烁，水印。")

    def test_extract_history_outputs_returns_current_prompt_files(self):
        history = {
            "older": {"outputs": {"9": {"images": [{"filename": "old.webp", "type": "output"}]}}},
            "abc123": {
                "outputs": {
                    "18": {
                        "images": [
                            {
                                "filename": "flf2v_test_001_00001.webp",
                                "subfolder": "",
                                "type": "output",
                            }
                        ]
                    }
                }
            },
        }

        outputs = flf2v_run.extract_history_outputs(history, "abc123")

        self.assertEqual(len(outputs), 1)
        self.assertEqual(outputs[0].filename, "flf2v_test_001_00001.webp")
        self.assertEqual(outputs[0].kind, "output")

    def test_build_view_url_encodes_filename_and_subfolder(self):
        output = flf2v_run.RemoteOutput(
            filename="flf2v test 001.webp",
            subfolder="nested folder",
            kind="output",
        )

        url = flf2v_run.build_view_url("http://1.2.3.4:6889", output)

        self.assertEqual(
            url,
            "http://1.2.3.4:6889/view?"
            "filename=flf2v+test+001.webp&subfolder=nested+folder&type=output",
        )

    def test_load_job_reads_standard_files_and_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp) / "job"
            job_dir.mkdir()
            (job_dir / "start_720x1280.jpg").write_bytes(b"start")
            (job_dir / "end_720x1280.jpg").write_bytes(b"end")
            (job_dir / "prompt.txt").write_text("正向提示词\nA\n负面提示词\nB", encoding="utf-8")
            (job_dir / "config.json").write_text(json.dumps({"steps": 12}, ensure_ascii=False), encoding="utf-8")

            job = flf2v_run.load_job(job_dir)

        self.assertEqual(job.start_image.name, "start_720x1280.jpg")
        self.assertEqual(job.end_image.name, "end_720x1280.jpg")
        self.assertEqual(job.prompt.positive, "A")
        self.assertEqual(job.prompt.negative, "B")
        self.assertEqual(job.settings["width"], 720)
        self.assertEqual(job.settings["height"], 1280)
        self.assertEqual(job.settings["steps"], 12)

    def test_convert_outputs_converts_animated_webp_with_pillow_fallback(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp) / "job"
            job_dir.mkdir()
            webp = job_dir / "sample.webp"
            frames = [
                Image.new("RGB", (32, 32), (255, 0, 0)),
                Image.new("RGB", (32, 32), (0, 255, 0)),
            ]
            frames[0].save(webp, save_all=True, append_images=frames[1:], duration=100, loop=0)
            (job_dir / "job.json").write_text("{}", encoding="utf-8")
            job = flf2v_run.Job(
                job_dir=job_dir,
                start_image=job_dir / "start.jpg",
                end_image=job_dir / "end.jpg",
                prompt=flf2v_run.PromptParts("positive", "negative"),
                settings={"fps": 10},
                state_path=job_dir / "job.json",
            )

            flf2v_run.convert_outputs(job, [str(webp)])

            mp4 = job_dir / "sample.mp4"
            self.assertGreater(mp4.stat().st_size, 0)
            state = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
            self.assertEqual(state["converted_outputs"], [str(mp4)])


if __name__ == "__main__":
    unittest.main()

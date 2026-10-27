from scripts import setup_local


def test_setup_fills_empty_values_but_preserves_explicit_local_choices(tmp_path, monkeypatch):
    example = tmp_path / ".env.example"
    env_file = tmp_path / ".env"
    example.write_text(
        "JWT_SECRET=\nENVIRONMENT=development\nDEMO_MODE=true\nLLM_PROVIDER=mock\nEMBEDDING_MODEL_PATH=\n",
        encoding="utf-8",
    )
    env_file.write_text("DEMO_MODE=false\nLLM_PROVIDER=anthropic\n", encoding="utf-8")
    monkeypatch.setattr(setup_local, "ROOT", tmp_path)

    values = setup_local.write_local_env()

    assert len(values["JWT_SECRET"].encode("utf-8")) >= 32
    assert values["ENVIRONMENT"] == "development"
    assert values["DEMO_MODE"] == "false"
    assert values["LLM_PROVIDER"] == "anthropic"
    assert values["EMBEDDING_MODEL_PATH"] == "./data/models/all-MiniLM-L6-v2"
    assert (tmp_path / ".env").stat().st_mode & 0o077 == 0


def test_setup_replaces_blank_defaults_without_overwriting_nonempty_values():
    source = "DEMO_MODE=\nOCR_BACKEND=tesseract\n"

    updated = setup_local.set_env_value(source, "DEMO_MODE", "true", replace=False)
    updated = setup_local.set_env_value(updated, "OCR_BACKEND", "rapidocr", replace=False)

    assert setup_local.parse_env(updated) == {"DEMO_MODE": "true", "OCR_BACKEND": "tesseract"}


def test_large_wheels_are_installed_after_base_requirements():
    source = """\
fastapi==1.0
sentence-transformers==2.0
opencv-python==4.0
rapidocr-onnxruntime==1.0; python_version < "3.13"
onnxruntime==1.0
"""

    base, large = setup_local.partition_requirements(source)

    assert base == ["fastapi==1.0"]
    assert large == [
        "sentence-transformers==2.0",
        "opencv-python==4.0",
        'rapidocr-onnxruntime==1.0; python_version < "3.13"',
        "onnxruntime==1.0",
    ]
    assert sorted(base + large) == sorted(source.strip().splitlines())


def test_setup_gives_large_downloads_a_reliable_timeout(monkeypatch):
    for key in (
        "PIP_DEFAULT_TIMEOUT",
        "PIP_RETRIES",
        "HF_HUB_DOWNLOAD_TIMEOUT",
        "HF_HUB_ETAG_TIMEOUT",
    ):
        monkeypatch.delenv(key, raising=False)

    env = setup_local.command_env({})

    assert env["PIP_DEFAULT_TIMEOUT"] == "120"
    assert env["PIP_RETRIES"] == "5"
    assert env["HF_HUB_DOWNLOAD_TIMEOUT"] == "120"
    assert env["HF_HUB_ETAG_TIMEOUT"] == "30"

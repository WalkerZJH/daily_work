from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "front_end"


def test_vue_uses_single_scss_entrypoint():
    main_js = (FRONTEND / "src" / "main.js").read_text(encoding="utf-8")

    assert "import './styles/main.scss'" in main_js
    assert "import './style.css'" not in main_js
    assert "import './styles/base.css'" not in main_js
    assert "import './styles/layout.css'" not in main_js
    assert "import './styles/components.css'" not in main_js
    assert "import './styles/utilities.css'" not in main_js
    assert "import '../styles.css'" not in main_js


def test_scss_style_library_has_clear_layers():
    main_scss = FRONTEND / "src" / "styles" / "main.scss"
    assert main_scss.exists()
    text = main_scss.read_text(encoding="utf-8")

    expected_imports = [
        "@use './library/tokens'",
        "@use './library/base'",
        "@use './library/layout'",
        "@use './library/components'",
        "@use './library/modules'",
        "@use './library/utilities'",
    ]
    for expected in expected_imports:
        assert expected in text

    library_dir = FRONTEND / "src" / "styles" / "library"
    for name in ["_tokens.scss", "_base.scss", "_layout.scss", "_components.scss", "_modules.scss", "_utilities.scss"]:
        assert (library_dir / name).exists()


def test_vue_components_do_not_keep_scoped_style_blocks():
    vue_files = list((FRONTEND / "src").rglob("*.vue"))
    assert vue_files

    offenders = []
    for file in vue_files:
        text = file.read_text(encoding="utf-8")
        if "<style" in text:
            offenders.append(file.relative_to(FRONTEND).as_posix())

    assert offenders == []


def test_legacy_split_css_files_are_removed_from_vue_source():
    legacy_paths = [
        FRONTEND / "src" / "style.css",
        FRONTEND / "src" / "styles" / "base.css",
        FRONTEND / "src" / "styles" / "layout.css",
        FRONTEND / "src" / "styles" / "components.css",
        FRONTEND / "src" / "styles" / "utilities.css",
    ]

    existing = [path.relative_to(FRONTEND).as_posix() for path in legacy_paths if path.exists()]
    assert existing == []

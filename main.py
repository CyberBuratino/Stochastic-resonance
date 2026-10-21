"""Запуск: python main.py. Сборка: pyinstaller stochastic_resonance.spec."""
from pathlib import Path
import argparse
import sys


def resource_path(relative_path: str) -> Path:
    """Ресурсы доступны и из исходников, и внутри сборки PyInstaller."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Stochastic resonance learning lab")
    parser.add_argument("--smoke-test", action="store_true", help="Check bundled resources without opening a window")
    args = parser.parse_args()
    if args.smoke_test:
        import tkinter
        from stochlab.model import Model, Parameters
        logo = resource_path("assets/vmk-logo.png")
        if logo.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError("Missing or invalid logo")
        model = Model(Parameters())
        model.step()
        print(f"OK: model, Tk {tkinter.TkVersion}, logo {logo.name}")
        return
    from stochlab.app import Application
    Application(resource_path("assets/vmk-logo.png")).mainloop()


if __name__ == "__main__":
    main()

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
    parser.add_argument("--smoke-test-gui", action="store_true", help="Open a window and verify packaged graph rendering")
    args = parser.parse_args()
    if args.smoke_test:
        import tkinter
        from stochlab.model import Model, Parameters
        logo = resource_path("assets/vmk-logo.png")
        if logo.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError("Missing or invalid logo")
        from stochlab.plotting import Scene
        from stochlab.rendering import render_scene
        model = Model(Parameters())
        model.step()
        # Проверяем и Pillow, и включённый шрифт с кириллицей без окна.
        scene = Scene(160, 50)
        scene.text(80, 25, "Проверка x²", "#000000")
        render_scene(scene)
        print(f"OK: model, Tk {tkinter.TkVersion}, logo, Pillow and bundled font")
        return
    from stochlab.app import Application
    application = Application(resource_path("assets/vmk-logo.png"))
    if args.smoke_test_gui:
        # Проверяем стартовую иллюстрацию и оба графика через мост Pillow → Tk.
        from PIL import Image, ImageChops, ImageTk
        errors = []
        application.report_callback_exception = lambda kind, value, trace: errors.append(str(value))

        def check_frame(canvas):
            items = canvas.find_all()
            if len(items) != 1 or canvas.type(items[0]) != "image":
                raise RuntimeError("Frame was not displayed")
            # Элемент Canvas сам по себе не доказывает, что картинка не пустая.
            frame = ImageTk.getimage(canvas._scene_photo).convert("RGB")
            background = Image.new("RGB", frame.size, canvas.cget("background"))
            histogram = ImageChops.difference(frame, background).convert("L").histogram()
            if sum(histogram[1:]) < 100:
                raise RuntimeError("Displayed frame is blank")

        def check_home():
            try:
                check_frame(application.title_canvas)
            except Exception as error:
                errors.append(str(error))
            application.show_page("lab")
            application.advance_steps(1000)
            application.after(250, finish_check)

        def finish_check():
            try:
                for canvas in (application.potential_canvas, application.trajectory_canvas):
                    check_frame(canvas)
            except Exception as error:
                errors.append(str(error))
            finally:
                application.destroy()

        application.after(250, check_home)
        application.mainloop()
        if errors:
            raise RuntimeError("; ".join(errors))
        print("OK: GUI, nonblank home illustration and both graph frames")
        return
    application.mainloop()


if __name__ == "__main__":
    main()

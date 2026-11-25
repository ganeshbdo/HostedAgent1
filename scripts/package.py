"""Build a flat, source-only Foundry ZIP without uploading anything."""

import hashlib
import io
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

SOURCE_FILES = ("main.py", "requirements.txt")


def build_package(source: Path, destination: Path) -> str:
    payload = io.BytesIO()
    with ZipFile(payload, "w", compression=ZIP_DEFLATED) as archive:
        for name in SOURCE_FILES:
            path = source / name
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"Required package input is not a regular file: {name}")
            info = ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())

    data = payload.getvalue()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    destination = root / "dist" / "agent-code.zip"
    digest = build_package(root / "src", destination)
    print(f"Package: {destination}")
    print(f"SHA-256: {digest}")
    print(f"Files: {', '.join(SOURCE_FILES)}")


if __name__ == "__main__":
    main()

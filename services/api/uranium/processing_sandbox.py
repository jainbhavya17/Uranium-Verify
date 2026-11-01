"""OS resource caps plus wall-clock/output budgets; no application environment in child."""

import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path


def windows_job(process, memory_mb):
    import ctypes as c
    from ctypes import wintypes as w

    class Basic(c.Structure):
        _fields_ = [
            ("process_time", c.c_longlong),
            ("job_time", c.c_longlong),
            ("flags", w.DWORD),
            ("minimum", c.c_size_t),
            ("maximum", c.c_size_t),
            ("active", w.DWORD),
            ("affinity", c.c_size_t),
            ("priority", w.DWORD),
            ("scheduling", w.DWORD),
        ]

    class IO(c.Structure):
        _fields_ = [
            (name, c.c_ulonglong)
            for name in ("read", "write", "other", "readbytes", "writebytes", "otherbytes")
        ]

    class Extended(c.Structure):
        _fields_ = [
            ("basic", Basic),
            ("io", IO),
            ("process_memory", c.c_size_t),
            ("job_memory", c.c_size_t),
            ("peak_process", c.c_size_t),
            ("peak_job", c.c_size_t),
        ]

    kernel = c.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.SetInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    info = Extended()
    info.basic.flags = 0x2000 | 0x200 | 0x8 | 0x4  # kill descendants, job memory, active count, job CPU
    info.basic.active, info.basic.job_time = 4, 100 * 10_000_000
    info.job_memory = memory_mb * 1024**2
    if not kernel.SetInformationJobObject(
        job, 9, c.byref(info), c.sizeof(info)
    ) or not kernel.AssignProcessToJobObject(job, int(process._handle)):
        kernel.CloseHandle(job)
        raise OSError("Resource isolation unavailable")
    return lambda: kernel.CloseHandle(job)


def extract_isolated(path, policy, expected_sha256=None, *, operation="extract", options=None):
    with tempfile.TemporaryDirectory(prefix="uranium-worker-") as tmp:
        directory = Path(tmp)
        if path.stat().st_size > max(policy.pdf_bytes, policy.image_bytes):
            return {"ok": False, "code": "RESOURCE_LIMIT"}
        shutil.copyfile(path, directory / "input")
        if (
            expected_sha256
            and hashlib.sha256((directory / "input").read_bytes()).hexdigest() != expected_sha256
        ):
            return {"ok": False, "code": "FILE_INTEGRITY"}
        config = asdict(policy)
        config["tesseract"] = shutil.which(policy.tesseract) or policy.tesseract
        config["options"] = options or {}
        (directory / "policy.json").write_text(json.dumps(config), encoding="utf-8")
        env = {
            key: value
            for key, value in os.environ.items()
            if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "TESSDATA_PREFIX"}
        }
        env.update(OMP_THREAD_LIMIT="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        scripts = {
            "extract": "document_parser.py",
            "provenance": "provenance_worker.py",
            "render": "evidence_renderer.py",
        }
        script = Path(__file__).with_name(scripts[operation])
        process = subprocess.Popen(
            [sys.executable, "-I", str(script), tmp],
            cwd=tmp,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=os.name != "nt",
        )

        def close():
            return None

        try:
            if os.name == "nt":
                close = windows_job(process, policy.memory_mb)
            (directory / "go").touch()
            process.wait(timeout=policy.timeout)
            result = directory / "result.json"
            if process.returncode or not result.exists() or result.stat().st_size > 4_000_000:
                return {"ok": False, "code": "RESOURCE_LIMIT"}
            return json.loads(result.read_text(encoding="utf-8"))
        except (OSError, subprocess.TimeoutExpired):
            return {"ok": False, "code": "RESOURCE_LIMIT"}
        finally:
            if process.poll() is None:
                if os.name != "nt":
                    import signal

                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait()
            close()

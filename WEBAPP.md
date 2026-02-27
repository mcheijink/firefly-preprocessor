# Web App Notes

Primary documentation is in `README.md`.

Use `tools/capture_ui.py` for screenshot capture during UI checks:

```bash
python tools/capture_ui.py --base-url http://localhost:8080 --out-dir output_check/ui
```

If Playwright is not installed:

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium
```

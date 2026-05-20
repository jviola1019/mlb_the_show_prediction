# MLB Show Investment Terminal

React + FastAPI terminal for MLB The Show card-market decisions.

Project app: `mlb-show-investment-terminal/`

The current build implements a strategy ontology:

- spread flips
- directional holds
- inventory quality
- composite final action

`INVESTABLE` is directional-only. A bearish/negative-EV forecast cannot produce an investable final action; a positive spread with bearish direction becomes `INSTANT FLIP ONLY`.

## Quick Run

```powershell
cd mlb-show-investment-terminal
python -m pip install -e ".[test]"
cd frontend
npm ci
npm run build
cd ..
$env:MLB_SHOW_STATIC_DIR = "$PWD\frontend\dist"
python -m uvicorn mlb_show_terminal.api:app --host 127.0.0.1 --port 7860
```

## Verify

```powershell
cd mlb-show-investment-terminal
python -m pytest python/tests/ -v
cd frontend
npx tsc -b --noEmit
npm test -- --run
npm run build
$env:PLAYWRIGHT_BASE_URL="http://127.0.0.1:7860"
npm run smoke
```

## Deploy

```powershell
cd mlb-show-investment-terminal
python -m pip install -e ".[deploy]"
$env:HF_TOKEN = "<write token>"
python scripts/publish_hf_space.py --repo-id jviola1019/mlb-show-investment-terminal
```

See `mlb-show-investment-terminal/README.md` and `mlb-show-investment-terminal/FINAL_AUDIT.md` for the full sprint audit.

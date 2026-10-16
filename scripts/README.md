# scripts

Developer utilities that aren't part of Keeper itself.

`test_tokenfactory.py` is the phase 1 probe. It checks that each Nemotron model on Token Factory can chat and return a structured tool call. Run it from the repo root:

```powershell
py -m pip install -r requirements.txt
py scripts\test_tokenfactory.py
```

It reads `TOKENFACTORY_API_KEY` from the environment. Set `KEEPER_MODELS` to a comma-separated list of model ids if you want to probe a different set.

# Play Chess

A tiny click-to-move chess app with a simple [alpha-beta](https://en.wikipedia.org/wiki/Alpha%E2%80%93beta_pruning) engine.
No terminal play. No extra GUI libs.

<img width="400" height="400" alt="image" src="https://github.com/user-attachments/assets/0cd102c7-78dc-4057-86f6-6f6b69c8c2cb" />


## Requirements

Install:
```bash
pip3 install python-chess
```

## Run using the ``àlpha-beta```

```bash
python mini_chess.py
```

## Settings

Open ```mini_chees.py``` the file and edit:

- ENGINE_DEPTH = 3       # 2–5 (higher = stronger/slower)
- HUMAN_IS_WHITE = True  # False to let engine start


## Run using the LLM

Note : LLM is a bad chess player

```bash
python3 ai_chess.py
```

<img width="400" height="400" alt="image" src="https://github.com/user-attachments/assets/5ad5d182-2b0f-43d9-81f0-606e7e29cd17" />



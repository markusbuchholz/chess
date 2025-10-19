# chess_gui_llm_ollama.py
# Play chess vs a local LLM via Ollama using a Tkinter board.
# The LLM receives FEN + legal UCI moves and must return exactly ONE legal UCI move.
# Requirements: python-chess, requests, a running Ollama server with a pulled model.

import re
import time
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog

import requests
import chess
import chess.pgn
import subprocess

# ===================== CONFIG =====================

OLLAMA_URL = "http://localhost:11434/api/generate"
TEMPERATURE = 0               # keep 0 for deterministic single-move output
NUM_CTX = 2048                # context window; adjust if your model supports larger
REQUEST_TIMEOUT = 120         # seconds
HUMAN_IS_WHITE = True         # set False to let LLM start
#MODEL_NAME = "gemma3:12b" 
MODEL_NAME = "qwen2.5-coder:14b" 



# ==================================================

# ===================== PROMPTING & PARSING =====================
# LAZY
# def build_prompt(fen: str, legal_uci: list[str], side_to_move: str) -> str:
#     """Create a strict prompt encouraging a single UCI move."""
#     moves_str = " ".join(legal_uci)
#     return (
#         "You are a chess engine. Pick the best move.\n\n"
#         f"Position (FEN): {fen}\n"
#         f"Side to move: {side_to_move}\n"
#         f"Legal moves (UCI): {moves_str}\n\n"
#         "Rules:\n"
#         "1) Respond with exactly ONE legal UCI move from the list.\n"
#         "2) No explanations, no punctuation, no code blocks—just the move (e.g., e2e4 or e7e8q).\n"
#     )


# ADVANCED
def build_prompt(fen: str, legal_uci: list[str], side_to_move: str) -> str:
    """
    Creates an advanced prompt to guide the LLM through a chess thinking process.
    """
    moves_str = " ".join(legal_uci)
    return (
        "You are a world-class chess grandmaster and a powerful strategic engine. Your task is to find the absolute best move in the given position. Follow this thinking process rigorously:\n\n"
        "1.  **Positional Evaluation:** Briefly analyze the current position. Consider king safety, material balance, central control, piece activity, and pawn structure for both sides.\n"
        "2.  **Candidate Moves:** Identify the top 3-5 most promising candidate moves from the legal moves list.\n"
        "3.  **Simulated Search:** For each candidate move, perform a short 'what-if' analysis. Project the likely continuation for at least 3 plies (your move, opponent's best reply, your next move). Evaluate the final position of this short line.\n"
        "4.  **Final Decision:** Based on your analysis, select the single best move that leads to the most advantageous position.\n\n"
        "--- CHESS POSITION ---\n"
        f"Position (FEN): {fen}\n"
        f"Side to move: {side_to_move}\n"
        f"Legal moves (UCI): {moves_str}\n\n"
        "--- RESPONSE RULES ---\n"
        "Your final output MUST contain exactly ONE legal UCI move from the list on the last line. You can optionally 'think out loud' before the move, but the move itself must be the final part of your response, with no other text after it. For example: `e2e4` or `e7e8q`."
    )
    
def parse_uci_from_text(text: str, legal_uci: set[str]) -> str | None:
    """Extract the first valid UCI token from text, ensuring it is legal."""
    text = text.strip().lower()
    # Look for a UCI-shaped token anywhere
    m = re.search(r"\b[a-h][1-8][a-h][1-8][qrbn]?\b", text)
    if m:
        uci = m.group(0)
        if uci in legal_uci:
            return uci
    # Or if the whole text is just the move
    if text in legal_uci:
        return text
    return None

def call_ollama(prompt: str) -> str:
    """
    Calls `ollama run <MODEL_NAME>` via subprocess and returns the raw text.
    Nothing leaves your machine. Requires the 'ollama' binary on PATH.
    """
    # You can also pass the prompt as a trailing arg: ["ollama","run",MODEL_NAME,prompt]
    # but piping via stdin is more robust for longer prompts.
    proc = subprocess.run(
        ["ollama", "run", MODEL_NAME],
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Ollama CLI error: {proc.stderr.strip()}")
    print (proc.stdout)
    return proc.stdout

# ===================== GUI APP =====================
SQUARE = 80
MARGIN = 20
BOARD_SIZE = SQUARE * 8
LIGHT = "#f0d9b5"
DARK = "#b58863"
HILITE = "#f6f669"
TARGET = "#a9d18e"
CHECK = "#ff9e9e"

UNICODE_PIECE = {
    chess.Piece(chess.PAWN,   chess.WHITE): "♙",
    chess.Piece(chess.KNIGHT, chess.WHITE): "♘",
    chess.Piece(chess.BISHOP, chess.WHITE): "♗",
    chess.Piece(chess.ROOK,   chess.WHITE): "♖",
    chess.Piece(chess.QUEEN,  chess.WHITE): "♕",
    chess.Piece(chess.KING,   chess.WHITE): "♔",
    chess.Piece(chess.PAWN,   chess.BLACK): "♟",
    chess.Piece(chess.KNIGHT, chess.BLACK): "♞",
    chess.Piece(chess.BISHOP, chess.BLACK): "♝",
    chess.Piece(chess.ROOK,   chess.BLACK): "♜",
    chess.Piece(chess.QUEEN,  chess.BLACK): "♛",
    chess.Piece(chess.KING,   chess.BLACK): "♚",
}

class ChessGUI:
    def __init__(self, root, human_is_white=True):
        self.root = root
        self.human_is_white = human_is_white
        self.board = chess.Board()
        self.selected_square = None
        self.legal_targets = set()
        self.engine_thinking = False

        root.title("Chess — LLM Opponent (Ollama + python-chess + Tkinter)")
        self.canvas = tk.Canvas(root, width=BOARD_SIZE, height=BOARD_SIZE)
        self.canvas.grid(row=0, column=0, columnspan=5, padx=MARGIN, pady=MARGIN)
        self.canvas.bind("<Button-1>", self.on_click)

        self.status = tk.StringVar()
        self.status.set("Your move (White)" if self.human_is_white else "LLM thinking...")
        tk.Label(root, textvariable=self.status).grid(row=1, column=0, sticky="w", padx=MARGIN)

        tk.Button(root, text="Undo", command=self.on_undo).grid(row=1, column=1, sticky="e")
        tk.Button(root, text="Export PGN", command=self.on_export_pgn).grid(row=1, column=2, sticky="e")
        tk.Button(root, text="New Game", command=self.on_new_game).grid(row=1, column=3, sticky="e")

        self.flip_var = tk.IntVar(value=0)
        tk.Checkbutton(root, text="Flip board", variable=self.flip_var, command=self.redraw).grid(row=1, column=4, sticky="e", padx=MARGIN)

        self.redraw()

        if not self.human_is_white:
            self.root.after(200, self.engine_move_async)

    # --- Board <-> Canvas mapping ---
    def square_to_xy(self, sq):
        file = chess.square_file(sq)
        rank = chess.square_rank(sq)
        if self.flip_var.get():
            file = 7 - file
            rank = 7 - rank
        x0 = file * SQUARE
        y0 = (7 - rank) * SQUARE
        return x0, y0

    def xy_to_square(self, x, y):
        file = x // SQUARE
        rank = 7 - (y // SQUARE)
        if self.flip_var.get():
            file = 7 - file
            rank = 7 - rank
        if 0 <= file < 8 and 0 <= rank < 8:
            return chess.square(file, rank)
        return None

    def redraw(self, last_move=None):
        self.canvas.delete("all")
        # squares
        for r in range(8):
            for f in range(8):
                ff, rr = (7 - f, 7 - r) if self.flip_var.get() else (f, r)
                x0 = f * SQUARE
                y0 = r * SQUARE
                color = LIGHT if (ff + rr) % 2 == 0 else DARK
                self.canvas.create_rectangle(x0, y0, x0 + SQUARE, y0 + SQUARE, fill=color, outline="")

        # in-check highlight
        if self.board.is_check():
            ksq = self.board.king(self.board.turn)
            if ksq is not None:
                x0, y0 = self.square_to_xy(ksq)
                self.canvas.create_rectangle(x0, y0, x0 + SQUARE, y0 + SQUARE, outline=CHECK, width=4)

        # selection + targets
        if self.selected_square is not None:
            x0, y0 = self.square_to_xy(self.selected_square)
            self.canvas.create_rectangle(x0+2, y0+2, x0 + SQUARE-2, y0 + SQUARE-2, outline=HILITE, width=3)
            for t in self.legal_targets:
                tx, ty = self.square_to_xy(t)
                self.canvas.create_oval(tx + SQUARE/2 - 10, ty + SQUARE/2 - 10,
                                        tx + SQUARE/2 + 10, ty + SQUARE/2 + 10,
                                        fill=TARGET, outline="")

        # pieces
        for sq in chess.SQUARES:
            p = self.board.piece_at(sq)
            if not p:
                continue
            x0, y0 = self.square_to_xy(sq)
            self.canvas.create_text(x0 + SQUARE/2, y0 + SQUARE/2,
                                    text=UNICODE_PIECE[p],
                                    font=("Segoe UI Symbol", int(SQUARE*0.7)))

        # last move arrow
        if last_move:
            x1, y1 = self.square_to_xy(last_move.from_square)
            x2, y2 = self.square_to_xy(last_move.to_square)
            self.canvas.create_line(x1 + SQUARE/2, y1 + SQUARE/2,
                                    x2 + SQUARE/2, y2 + SQUARE/2,
                                    width=6, arrow=tk.LAST)

        # status
        if self.board.is_game_over():
            outcome = self.board.outcome()
            if self.board.is_checkmate():
                who = "White" if outcome.winner else "Black"
                self.status.set(f"Checkmate — {who} wins.")
            else:
                self.status.set(f"Draw ({outcome.termination}).")
        else:
            side = "White" if self.board.turn else "Black"
            self.status.set(f"{side} to move" + (" — LLM thinking..." if self.engine_thinking else ""))

    # --- Interaction ---
    def on_click(self, event):
        if self.engine_thinking or self.board.is_game_over():
            return
        sq = self.xy_to_square(event.x, event.y)
        if sq is None:
            return

        turn_is_human = (self.board.turn and self.human_is_white) or ((not self.board.turn) and (not self.human_is_white))
        if not turn_is_human:
            return

        piece = self.board.piece_at(sq)

        if self.selected_square is None:
            if piece and piece.color == self.board.turn:
                self.selected_square = sq
                self.legal_targets = {m.to_square for m in self.board.legal_moves if m.from_square == sq}
                self.redraw()
            return

        from_sq = self.selected_square
        mv = None
        for m in self.board.legal_moves:
            if m.from_square == from_sq and m.to_square == sq:
                mv = m
                break

        if mv is None:
            if piece and piece.color == self.board.turn:
                self.selected_square = sq
                self.legal_targets = {m.to_square for m in self.board.legal_moves if m.from_square == sq}
                self.redraw()
            else:
                self.selected_square = None
                self.legal_targets = set()
                self.redraw()
            return

        # promotion
        if self.board.piece_at(from_sq).piece_type == chess.PAWN and chess.square_rank(sq) in (0, 7):
            promo = self.ask_promotion()
            mv = chess.Move(from_sq, sq, promotion=promo)

        self.push_and_redraw(mv)
        self.selected_square = None
        self.legal_targets = set()

        if not self.board.is_game_over():
            self.engine_move_async()

    def on_undo(self):
        if self.engine_thinking:
            return
        popped = False
        if len(self.board.move_stack) >= 1:
            self.board.pop(); popped = True
        if len(self.board.move_stack) >= 1:
            self.board.pop()
        if popped:
            self.redraw()
        else:
            messagebox.showinfo("Undo", "Nothing to undo.")

    def on_export_pgn(self):
        game = chess.pgn.Game.from_board(self.board)
        with open("game.pgn", "w", encoding="utf-8") as f:
            print(game, file=f)
        messagebox.showinfo("PGN", "Saved game.pgn")

    def on_new_game(self):
        if self.engine_thinking:
            return
        self.board = chess.Board()
        self.selected_square = None
        self.legal_targets = set()
        self.redraw()
        if not self.human_is_white:
            self.root.after(200, self.engine_move_async)

    def ask_promotion(self):
        choice = simpledialog.askstring("Promotion", "Promote to (Q/R/B/N)?", initialvalue="Q")
        if not choice:
            return chess.QUEEN
        c = choice.strip().upper()[:1]
        return {"Q": chess.QUEEN, "R": chess.ROOK, "B": chess.BISHOP, "N": chess.KNIGHT}.get(c, chess.QUEEN)

    def push_and_redraw(self, mv):
        self.board.push(mv)
        self.redraw(last_move=mv)

    # --- LLM turn (threaded) ---
    def engine_move_async(self):
        self.engine_thinking = True
        self.status.set("LLM thinking...")
        t = threading.Thread(target=self._engine_move_thread, daemon=True)
        t.start()

    def _engine_move_thread(self):
        t0 = time.time()
        mv = self.choose_move_via_llm()
        t1 = time.time()
        def apply():
            if mv:
                self.board.push(mv)
                self.redraw(last_move=mv)
            else:
                messagebox.showwarning("LLM", "No valid move returned; making a random move.")
                # Fallback: pick any legal move
                try:
                    self.board.push(next(iter(self.board.legal_moves)))
                    self.redraw()
                except StopIteration:
                    pass
            self.engine_thinking = False
            if not self.board.is_game_over():
                self.status.set(f"Your move (LLM {t1-t0:.2f}s)")
        self.root.after(0, apply)

    def choose_move_via_llm(self) -> chess.Move | None:
        if self.board.is_game_over():
            return None
        legal = [m.uci() for m in self.board.legal_moves]
        legal_set = set(legal)
        fen = self.board.fen()
        side = "White" if self.board.turn else "Black"

        prompt = build_prompt(fen, legal, side)
        try:
            raw = call_ollama(prompt)
        except Exception as e:
            print("Ollama error:", e)
            return None

        uci = parse_uci_from_text(raw or "", legal_set)
        if not uci:
            return None
        mv = chess.Move.from_uci(uci)
        if mv not in self.board.legal_moves:
            return None
        return mv

# ===================== RUN =====================
if __name__ == "__main__":
    root = tk.Tk()
    app = ChessGUI(root, human_is_white=HUMAN_IS_WHITE)
    root.mainloop()

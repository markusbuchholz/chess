# chess_gui_alpha_beta.py
# GUI chess vs a simple alpha-beta engine using Tkinter + python-chess.
# No extra GUI libs needed; just Python's standard library and python-chess.
import math
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog

import chess

# -------------------------
# Engine (alpha-beta)
# -------------------------
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

PST = {
    chess.PAWN: [
         0,  0,  0,  0,  0,  0,  0,  0,
         5, 10, 10,-20,-20, 10, 10,  5,
         5, -5,-10,  0,  0,-10, -5,  5,
         0,  0,  0, 20, 20,  0,  0,  0,
         5,  5, 10, 25, 25, 10,  5,  5,
        10, 10, 20, 30, 30, 20, 10, 10,
        50, 50, 50, 50, 50, 50, 50, 50,
         0,  0,  0,  0,  0,  0,  0,  0],
    chess.KNIGHT: [
        -50,-40,-30,-30,-30,-30,-40,-50,
        -40,-20,  0,  0,  0,  0,-20,-40,
        -30,  0, 10, 15, 15, 10,  0,-30,
        -30,  5, 15, 20, 20, 15,  5,-30,
        -30,  0, 15, 20, 20, 15,  0,-30,
        -30,  5, 10, 15, 15, 10,  5,-30,
        -40,-20,  0,  5,  5,  0,-20,-40,
        -50,-40,-30,-30,-30,-30,-40,-50],
    chess.BISHOP: [
        -20,-10,-10,-10,-10,-10,-10,-20,
        -10,  0,  0,  0,  0,  0,  0,-10,
        -10,  0,  5, 10, 10,  5,  0,-10,
        -10,  5,  5, 10, 10,  5,  5,-10,
        -10,  0, 10, 10, 10, 10,  0,-10,
        -10, 10, 10, 10, 10, 10, 10,-10,
        -10,  5,  0,  0,  0,  0,  5,-10,
        -20,-10,-10,-10,-10,-10,-10,-20],
    chess.ROOK: [
          0,  0,  0,  5,  5,  0,  0,  0,
         -5,  0,  0,  0,  0,  0,  0, -5,
         -5,  0,  0,  0,  0,  0,  0, -5,
         -5,  0,  0,  0,  0,  0,  0, -5,
         -5,  0,  0,  0,  0,  0,  0, -5,
         -5,  0,  0,  0,  0,  0,  0, -5,
          5, 10, 10, 10, 10, 10, 10,  5,
          0,  0,  0,  0,  0,  0,  0,  0],
    chess.QUEEN: [
        -20,-10,-10, -5, -5,-10,-10,-20,
        -10,  0,  0,  0,  0,  0,  0,-10,
        -10,  0,  5,  5,  5,  5,  0,-10,
         -5,  0,  5,  5,  5,  5,  0, -5,
          0,  0,  5,  5,  5,  5,  0, -5,
        -10,  5,  5,  5,  5,  5,  0,-10,
        -10,  0,  5,  0,  0,  0,  0,-10,
        -20,-10,-10, -5, -5,-10,-10,-20],
    chess.KING: [
        20, 30, 10,  0,  0, 10, 30, 20,
        20, 20,  0,  0,  0,  0, 20, 20,
       -10,-20,-20,-20,-20,-20,-20,-10,
       -20,-30,-30,-40,-40,-30,-30,-20,
       -30,-40,-40,-50,-50,-40,-40,-30,
       -30,-40,-40,-50,-50,-40,-40,-30,
       -30,-40,-40,-50,-50,-40,-40,-30,
       -30,-40,-40,-50,-50,-40,-40,-30],
}

def evaluate(board: chess.Board) -> int:
    if board.is_checkmate():
        return -999999 if board.turn else 999999
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_threefold_repetition():
        return 0
    score = 0
    for pt in PIECE_VALUES:
        for sq in board.pieces(pt, chess.WHITE):
            score += PIECE_VALUES[pt] + PST[pt][sq]
        for sq in board.pieces(pt, chess.BLACK):
            score -= PIECE_VALUES[pt] + PST[pt][chess.square_mirror(sq)]
    # light mobility
    mob = board.legal_moves.count()
    score += 5 * mob if board.turn else -5 * mob
    return score

def order_moves(board, moves):
    def key(m):
        s = 0
        if board.is_capture(m): s += 1000
        if m.promotion: s += 900
        board.push(m)
        if board.is_check(): s += 100
        board.pop()
        return -s
    return sorted(moves, key=key)

def search(board: chess.Board, depth: int, alpha: int, beta: int) -> int:
    if depth == 0 or board.is_game_over():
        return evaluate(board)
    best = -math.inf
    for move in order_moves(board, list(board.legal_moves)):
        board.push(move)
        score = -search(board, depth - 1, -beta, -alpha)
        board.pop()
        if score > best:
            best = score
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break
    return best

def best_move(board: chess.Board, depth: int):
    best_score = -math.inf
    best_mv = None
    for move in order_moves(board, list(board.legal_moves)):
        board.push(move)
        score = -search(board, depth - 1, -math.inf, math.inf)
        board.pop()
        if score > best_score:
            best_score = score
            best_mv = move
    return best_mv, best_score

# -------------------------
# GUI
# -------------------------
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
    def __init__(self, root, engine_depth=3, human_is_white=True):
        self.root = root
        self.engine_depth = engine_depth
        self.human_is_white = human_is_white
        self.board = chess.Board()
        self.history = []
        self.selected_square = None
        self.legal_targets = set()
        self.engine_thinking = False

        root.title("Chess — Alpha-Beta Engine (python-chess + Tkinter)")
        self.canvas = tk.Canvas(root, width=BOARD_SIZE, height=BOARD_SIZE)
        self.canvas.grid(row=0, column=0, columnspan=4, padx=MARGIN, pady=MARGIN)
        self.canvas.bind("<Button-1>", self.on_click)

        self.status = tk.StringVar()
        self.status.set("Your move (White)" if self.human_is_white else "Engine thinking...")
        tk.Label(root, textvariable=self.status).grid(row=1, column=0, sticky="w", padx=MARGIN)

        tk.Button(root, text="Undo", command=self.on_undo).grid(row=1, column=1, sticky="e")
        tk.Button(root, text="Hint", command=self.on_hint).grid(row=1, column=2, sticky="e")
        self.flip_var = tk.IntVar(value=0)
        tk.Checkbutton(root, text="Flip board", variable=self.flip_var, command=self.redraw).grid(row=1, column=3, sticky="e", padx=MARGIN)

        self.redraw()

        if not self.human_is_white:
            self.root.after(200, self.engine_move_async)

    # --- Board helpers ---
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
        # draw squares
        for rank in range(8):
            for file in range(8):
                f = file
                r = rank
                if self.flip_var.get():
                    f = 7 - file
                    r = 7 - rank
                x0 = file * SQUARE
                y0 = rank * SQUARE
                is_light = (f + r) % 2 == 0
                color = LIGHT if is_light else DARK
                self.canvas.create_rectangle(x0, y0, x0 + SQUARE, y0 + SQUARE, fill=color, outline="")

        # highlight king in check
        if self.board.is_check():
            ksq = self.board.king(self.board.turn)
            if ksq is not None:
                x0, y0 = self.square_to_xy(ksq)
                self.canvas.create_rectangle(x0, y0, x0 + SQUARE, y0 + SQUARE, outline=CHECK, width=4)

        # highlight selection and targets
        if self.selected_square is not None:
            x0, y0 = self.square_to_xy(self.selected_square)
            self.canvas.create_rectangle(x0+2, y0+2, x0 + SQUARE-2, y0 + SQUARE-2, outline=HILITE, width=3)
            for t in self.legal_targets:
                tx, ty = self.square_to_xy(t)
                self.canvas.create_oval(tx + SQUARE/2 - 10, ty + SQUARE/2 - 10,
                                        tx + SQUARE/2 + 10, ty + SQUARE/2 + 10,
                                        fill=TARGET, outline="")

        # draw pieces
        for sq in chess.SQUARES:
            piece = self.board.piece_at(sq)
            if not piece:
                continue
            x0, y0 = self.square_to_xy(sq)
            self.canvas.create_text(x0 + SQUARE/2, y0 + SQUARE/2,
                                    text=UNICODE_PIECE[piece],
                                    font=("Segoe UI Symbol", int(SQUARE*0.7)))

        # last move arrow
        if last_move:
            x1, y1 = self.square_to_xy(last_move.from_square)
            x2, y2 = self.square_to_xy(last_move.to_square)
            self.canvas.create_line(x1 + SQUARE/2, y1 + SQUARE/2,
                                    x2 + SQUARE/2, y2 + SQUARE/2,
                                    width=6, arrow=tk.LAST)

        # status text
        if self.board.is_game_over():
            outcome = self.board.outcome()
            if self.board.is_checkmate():
                who = "White" if outcome.winner else "Black"
                self.status.set(f"Checkmate — {who} wins.")
            else:
                self.status.set(f"Draw ({outcome.termination}).")
        else:
            side = "White" if self.board.turn else "Black"
            self.status.set(f"{side} to move")

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

        # if selecting own piece
        if self.selected_square is None:
            if piece and piece.color == self.board.turn:
                self.selected_square = sq
                self.legal_targets = {m.to_square for m in self.board.legal_moves if m.from_square == sq}
                self.redraw()
            return

        # second click: attempt move
        from_sq = self.selected_square
        mv = None
        for m in self.board.legal_moves:
            if m.from_square == from_sq and m.to_square == sq:
                mv = m
                break

        if mv is None:
            # reselect piece if clicked your own piece again
            if piece and piece.color == self.board.turn:
                self.selected_square = sq
                self.legal_targets = {m.to_square for m in self.board.legal_moves if m.from_square == sq}
                self.redraw()
            else:
                # clear selection
                self.selected_square = None
                self.legal_targets = set()
                self.redraw()
            return

        # promotion handling
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
        undone = False
        if len(self.board.move_stack) >= 1:
            self.board.pop()
            undone = True
        if len(self.board.move_stack) >= 1:
            # pop engine's move too (if present)
            self.board.pop()
        if undone:
            self.redraw()
        else:
            messagebox.showinfo("Undo", "Nothing to undo.")

    def on_hint(self):
        if self.engine_thinking or self.board.is_game_over():
            return
        mv, sc = best_move(self.board, max(2, self.engine_depth - 1))
        san = self.board.san(mv) if mv else "N/A"
        messagebox.showinfo("Hint", f"Try: {san}\nEval ≈ {sc/100:.2f}")

    def ask_promotion(self):
        choices = {"Queen": chess.QUEEN, "Rook": chess.ROOK, "Bishop": chess.BISHOP, "Knight": chess.KNIGHT}
        choice = simpledialog.askstring("Promotion", "Promote to (Q/R/B/N)?", initialvalue="Q")
        if not choice:
            return chess.QUEEN
        c = choice.strip().upper()[0]
        return {"Q": chess.QUEEN, "R": chess.ROOK, "B": chess.BISHOP, "N": chess.KNIGHT}.get(c, chess.QUEEN)

    def push_and_redraw(self, mv):
        self.board.push(mv)
        self.redraw(last_move=mv)

    # --- Engine turn in a thread so UI stays responsive ---
    def engine_move_async(self):
        self.engine_thinking = True
        self.status.set("Engine thinking...")
        t = threading.Thread(target=self._engine_move_thread, daemon=True)
        t.start()

    def _engine_move_thread(self):
        t0 = time.time()
        mv, sc = best_move(self.board, self.engine_depth)
        t1 = time.time()
        def apply():
            if mv:
                self.board.push(mv)
                self.redraw(last_move=mv)
            self.engine_thinking = False
            if not self.board.is_game_over():
                self.status.set(f"Your move (depth {self.engine_depth}, eval {sc/100:.2f}, {t1-t0:.2f}s)")
        self.root.after(0, apply)

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    # Configure sides and strength here:
    ENGINE_DEPTH = 3       # increase for stronger play (4–5 slower/stronger)
    HUMAN_IS_WHITE = True  # set False to let engine start

    root = tk.Tk()
    app = ChessGUI(root, engine_depth=ENGINE_DEPTH, human_is_white=HUMAN_IS_WHITE)
    root.mainloop()

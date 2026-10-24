"""Tile-map levels: 15 x 10 tiles of 32 px.

Legend: # solid, . empty, P player start, D real exit, ^ spike,
F fake spike (harmless), s hidden spike, v collapsing floor, d decoy exit (deadly).
"""
COLS, ROWS = 15, 10

LEVELS = [
    {"name": "Not everything bites", "map": [
        "###############",
        "#.............#",
        "#.............#",
        "#.............#",
        "#.............#",
        "#.............#",
        "#.............#",
        "#P..F...s...D.#",
        "###############",
        "###############",
    ]},
    {"name": "The floor is a liar", "map": [
        "###############",
        "#.............#",
        "#.............#",
        "#.............#",
        "#.............#",
        "#.............#",
        "#..........D..#",
        "#P.......^###.#",
        "#####vvv#######",
        "#####...#######",
    ]},
    {"name": "Nothing is what it seems", "map": [
        "###############",
        "#.............#",
        "#.............#",
        "#.............#",
        "#.............#",
        "#...........D.#",
        "#......vv.#####",
        "#P..##..s....d#",
        "###############",
        "###############",
    ]},
]


def parse(rows):
    """Return (grid, start): grid is a list of rows of characters, start is (col, row) of P."""
    grid = [list(row) for row in rows]
    start = next((c, r) for r, row in enumerate(grid) for c, ch in enumerate(row) if ch == "P")
    return grid, start


def validate(levels=LEVELS):
    """Raise ValueError unless every map is 15 x 10 with exactly one P and at least one D."""
    for level in levels:
        name, rows = level["name"], level["map"]
        if len(rows) != ROWS or any(len(row) != COLS for row in rows):
            raise ValueError(f"{name}: map must be {COLS} x {ROWS}")
        text = "".join(rows)
        if text.count("P") != 1:
            raise ValueError(f"{name}: needs exactly one P")
        if "D" not in text:
            raise ValueError(f"{name}: needs at least one D")
        unknown = set(text) - set("#.PD^Fsvd")
        if unknown:
            raise ValueError(f"{name}: unknown tiles {sorted(unknown)}")

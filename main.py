import math
from collections import deque
from datetime import datetime
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from asteval import Interpreter

from models import CalculatorLog, Expression, HistoryResponse

HISTORY_MAX = 1000
# HISTORY (in-memory for now)
history: deque[CalculatorLog] = deque(maxlen=HISTORY_MAX)

app = FastAPI(title="Mini Calculator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Safe evaluator ----------
aeval = Interpreter(minimal=True, usersyms={"pi": math.pi, "e": math.e})


@app.post("/calculate")
def calculate(expression: Expression):
    expr = expression.expr
    try:
        code = expression.expand_percent()
        result = aeval(code)
        if aeval.error:
            msg = "; ".join(str(e.get_error()) for e in aeval.error)
            aeval.error.clear()
            return {"ok": False, "expr": expr, "result": "", "error": msg}
        # Add history (only successful calculations are recorded)
        history.append(CalculatorLog(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            expr=expr,
            result=result,
        ))
        return {"ok": True, "expr": expr, "result": result, "error": ""}
    except Exception as e:
        return {"ok": False, "expr": expr, "error": str(e)}


@app.get("/history")
def get_history(
    limit: int | None = Query(default=None, ge=1, le=HISTORY_MAX),
) -> HistoryResponse:
    """Return the calculation history, newest first.

    `limit` is optional; when given it caps how many entries come back.
    """
    items: list[CalculatorLog] = list(history)[::-1]  # newest first
    if limit is not None:
        items = items[:limit]
    return HistoryResponse(count=len(items), total=len(history), items=items)


@app.delete("/history")
def clear_history():
    """Clear the whole history."""
    cleared = len(history)
    history.clear()
    return {"ok": True, "cleared": cleared, "total": 0}

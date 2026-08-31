"""Pydantic models for the Mini Calculator API request and response bodies."""

from pydantic import BaseModel, Field

from calculator import expand_percent


class Expression(BaseModel):
    """Body of the POST /calculate API."""

    expr: str = Field(..., description="The arithmetic expression to evaluate.")

    def expand_percent(self) -> str:
        """Return the expression with every % symbol expanded."""
        return expand_percent(self.expr)


class CalculatorLog(BaseModel):
    """One history entry, returned by the GET /history API."""

    timestamp: str = Field(..., description="When the calculation was made.")
    expr: str = Field(..., description="The expression the user submitted.")
    result: float = Field(..., description="The value the expression evaluated to.")

import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from app.tools.base import BaseTool, ToolResult

def parse_date(date_str: str) -> datetime.date:
    """Helper to parse common date formats into datetime.date."""
    # Strip any potential time part
    cleaned = date_str.strip().split(" ")[0].split("T")[0]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(cleaned, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Invalid date format: '{date_str}'. Supported format: YYYY-MM-DD.")

def add_months(source_date: datetime.date, months: int) -> datetime.date:
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    
    # Calculate days in target month
    is_leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    month_days = [31, 29 if is_leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    day = min(source_date.day, month_days[month - 1])
    
    return datetime.date(year, month, day)

def add_years(source_date: datetime.date, years: int) -> datetime.date:
    try:
        return source_date.replace(year=source_date.year + years)
    except ValueError:
        # Handle leap year Feb 29 edge case when moving to non-leap year
        return source_date.replace(year=source_date.year + years, day=28)

class DateCalculatorInput(BaseModel):
    operation: str = Field(
        ...,
        description="The date operation to perform: 'difference' (days/weeks between dates) or 'add_subtract' (add/subtract duration)."
    )
    start_date: str = Field(
        ...,
        description="The starting reference date in YYYY-MM-DD format."
    )
    end_date: Optional[str] = Field(
        default=None,
        description="The ending date in YYYY-MM-DD format (required for 'difference' operation)."
    )
    amount: Optional[int] = Field(
        default=None,
        description="The numeric offset amount (required for 'add_subtract', can be negative)."
    )
    unit: Optional[str] = Field(
        default=None,
        description="The unit for addition/subtraction: 'days', 'weeks', 'months', 'years' (required for 'add_subtract')."
    )

class DateCalculatorTool(BaseTool):
    name: str = "date_calculator"
    description: str = (
        "Perform offline date calculations to find the difference between two dates "
        "or add/subtract days, weeks, months, or years to a start date."
    )
    input_schema: Any = DateCalculatorInput
    permission_level: str = "safe"
    timeout_seconds: int = 5

    async def execute(
        self,
        operation: str,
        start_date: str,
        end_date: Optional[str] = None,
        amount: Optional[int] = None,
        unit: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        op = operation.strip().lower()
        
        try:
            d_start = parse_date(start_date)
        except ValueError as e:
            return ToolResult(success=False, error="INVALID_ARGUMENTS", metadata={"error_detail": str(e)})

        if op == "difference":
            if not end_date:
                return ToolResult(
                    success=False,
                    error="INVALID_ARGUMENTS",
                    metadata={"error_detail": "Field 'end_date' is required for date 'difference' operation."}
                )
            try:
                d_end = parse_date(end_date)
            except ValueError as e:
                return ToolResult(success=False, error="INVALID_ARGUMENTS", metadata={"error_detail": str(e)})

            diff = d_end - d_start
            days = diff.days
            weeks = round(days / 7, 2)
            
            return ToolResult(
                success=True,
                data={
                    "start_date": d_start.isoformat(),
                    "end_date": d_end.isoformat(),
                    "difference_days": days,
                    "difference_weeks": weeks
                }
            )

        elif op == "add_subtract":
            if amount is None:
                return ToolResult(
                    success=False,
                    error="INVALID_ARGUMENTS",
                    metadata={"error_detail": "Field 'amount' is required for 'add_subtract' operation."}
                )
            if not unit:
                return ToolResult(
                    success=False,
                    error="INVALID_ARGUMENTS",
                    metadata={"error_detail": "Field 'unit' is required for 'add_subtract' operation."}
                )

            u = unit.strip().lower()
            if u not in ("days", "weeks", "months", "years", "day", "week", "month", "year"):
                return ToolResult(
                    success=False,
                    error="INVALID_ARGUMENTS",
                    metadata={"error_detail": f"Unsupported unit: '{unit}'. Support values: 'days', 'weeks', 'months', 'years'."}
                )

            # Map singular to plural
            if u == "day": u = "days"
            elif u == "week": u = "weeks"
            elif u == "month": u = "months"
            elif u == "year": u = "years"

            if u == "days":
                res_date = d_start + datetime.timedelta(days=amount)
            elif u == "weeks":
                res_date = d_start + datetime.timedelta(weeks=amount)
            elif u == "months":
                res_date = add_months(d_start, amount)
            else: # years
                res_date = add_years(d_start, amount)

            return ToolResult(
                success=True,
                data={
                    "start_date": d_start.isoformat(),
                    "operation": "add" if amount >= 0 else "subtract",
                    "amount": abs(amount),
                    "unit": u,
                    "result_date": res_date.isoformat()
                }
            )

        else:
            return ToolResult(
                success=False,
                error="INVALID_ARGUMENTS",
                metadata={"error_detail": f"Unsupported operation: '{operation}'. Expected 'difference' or 'add_subtract'."}
            )

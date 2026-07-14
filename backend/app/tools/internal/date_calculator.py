import datetime
from typing import Optional, Any
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field
from app.tools.base import BaseTool, ToolResult

def parse_datetime_or_date(val: str, default_tz: Optional[str] = None) -> datetime.datetime:
    """Helper to parse common date/datetime formats or relative keywords into datetime.datetime."""
    val_clean = val.strip().lower()
    
    # 1. Determine active timezone
    try:
        tz = ZoneInfo(default_tz) if default_tz else datetime.timezone.utc
    except Exception:
        tz = datetime.timezone.utc
    
    # Get current time in that timezone
    now_tz = datetime.datetime.now(tz)
    
    if val_clean == "now":
        return now_tz
    elif val_clean == "today":
        return now_tz.replace(hour=0, minute=0, second=0, microsecond=0)
    elif val_clean == "tomorrow":
        return (now_tz + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif val_clean == "yesterday":
        return (now_tz - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        
    # 2. Try parsing datetime
    for fmt in (None, "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            if fmt is None:
                # fromisoformat handles standard ISO 8601
                # Replace 'z' or 'Z' at the end with '+00:00' to be safe, also replace space with T
                val_iso = val.strip().replace("z", "+00:00").replace("Z", "+00:00").replace(" ", "T")
                dt = datetime.datetime.fromisoformat(val_iso)
            else:
                dt = datetime.datetime.strptime(val.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            return dt
        except ValueError:
            pass
            
    # 3. Try parsing as plain date
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            d = datetime.datetime.strptime(val.strip(), fmt).date()
            return datetime.datetime.combine(d, datetime.time.min, tzinfo=tz)
        except ValueError:
            pass
            
    raise ValueError(f"Invalid date/datetime format or keyword: '{val}'. Supported formats include YYYY-MM-DD and ISO 8601.")

def format_output(dt: datetime.datetime, original_input: str) -> str:
    """Formats output as YYYY-MM-DD or full ISO datetime depending on original input format."""
    original_clean = original_input.strip().lower()
    if ":" in original_clean or "t" in original_clean or original_clean == "now":
        return dt.isoformat()
    else:
        return dt.date().isoformat()

def add_months_dt(source_dt: datetime.datetime, months: int) -> datetime.datetime:
    month = source_dt.month - 1 + months
    year = source_dt.year + month // 12
    month = month % 12 + 1
    
    # Calculate days in target month
    is_leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    month_days = [31, 29 if is_leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    day = min(source_dt.day, month_days[month - 1])
    
    return source_dt.replace(year=year, month=month, day=day)

def add_years_dt(source_dt: datetime.datetime, years: int) -> datetime.datetime:
    try:
        return source_dt.replace(year=source_dt.year + years)
    except ValueError:
        # Handle leap year Feb 29 edge case when moving to non-leap year
        return source_dt.replace(year=source_dt.year + years, day=28)

class DateCalculatorInput(BaseModel):
    operation: str = Field(
        ...,
        description="The date operation to perform: 'difference' (days/weeks/hours/minutes between dates) or 'add_subtract' (add/subtract duration)."
    )
    start_date: str = Field(
        ...,
        description="The starting reference date/datetime or relative keyword ('today', 'tomorrow', 'yesterday', 'now')."
    )
    end_date: Optional[str] = Field(
        default=None,
        description="The ending date/datetime or relative keyword (required for 'difference' operation)."
    )
    amount: Optional[int] = Field(
        default=None,
        description="The numeric offset amount (required for 'add_subtract', can be negative)."
    )
    unit: Optional[str] = Field(
        default=None,
        description="The unit for addition/subtraction: 'days', 'weeks', 'months', 'years', 'hours', 'minutes', 'seconds' (required for 'add_subtract')."
    )
    timezone: Optional[str] = Field(
        default=None,
        description="IANA timezone name (e.g. 'America/New_York') to resolve relative keywords or interpret naive datetimes. Defaults to UTC."
    )

class DateCalculatorTool(BaseTool):
    name: str = "date_calculator"
    description: str = (
        "Perform offline date calculations to find the difference between two dates/datetimes "
        "or add/subtract days, weeks, months, years, hours, minutes, or seconds to a start date/datetime."
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
        timezone: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        op = operation.strip().lower()
        
        # Parse timezone parameter to validate
        if timezone:
            try:
                ZoneInfo(timezone)
            except Exception:
                return ToolResult(success=False, error="INVALID_ARGUMENTS", metadata={"error_detail": f"Unknown or invalid timezone: '{timezone}'."})

        try:
            d_start = parse_datetime_or_date(start_date, timezone)
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
                d_end = parse_datetime_or_date(end_date, timezone)
            except ValueError as e:
                return ToolResult(success=False, error="INVALID_ARGUMENTS", metadata={"error_detail": str(e)})

            diff = d_end - d_start
            total_seconds = diff.total_seconds()
            days = diff.days
            weeks = round(total_seconds / (7 * 24 * 3600), 2)
            hours = round(total_seconds / 3600, 2)
            minutes = round(total_seconds / 60, 2)
            
            return ToolResult(
                success=True,
                data={
                    "start_date": format_output(d_start, start_date),
                    "end_date": format_output(d_end, end_date),
                    "difference_days": days,
                    "difference_weeks": weeks,
                    "difference_hours": hours,
                    "difference_minutes": minutes,
                    "difference_seconds": total_seconds
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
            supported_units = ("days", "weeks", "months", "years", "day", "week", "month", "year",
                               "hours", "minutes", "seconds", "hour", "minute", "second")
            if u not in supported_units:
                return ToolResult(
                    success=False,
                    error="INVALID_ARGUMENTS",
                    metadata={"error_detail": f"Unsupported unit: '{unit}'. Support values: 'days', 'weeks', 'months', 'years', 'hours', 'minutes', 'seconds'."}
                )

            # Map singular to plural
            if u == "day": u = "days"
            elif u == "week": u = "weeks"
            elif u == "month": u = "months"
            elif u == "year": u = "years"
            elif u == "hour": u = "hours"
            elif u == "minute": u = "minutes"
            elif u == "second": u = "seconds"

            if u == "days":
                res_date = d_start + datetime.timedelta(days=amount)
            elif u == "weeks":
                res_date = d_start + datetime.timedelta(weeks=amount)
            elif u == "months":
                res_date = add_months_dt(d_start, amount)
            elif u == "years":
                res_date = add_years_dt(d_start, amount)
            elif u == "hours":
                res_date = d_start + datetime.timedelta(hours=amount)
            elif u == "minutes":
                res_date = d_start + datetime.timedelta(minutes=amount)
            else: # seconds
                res_date = d_start + datetime.timedelta(seconds=amount)

            return ToolResult(
                success=True,
                data={
                    "start_date": format_output(d_start, start_date),
                    "operation": "add" if amount >= 0 else "subtract",
                    "amount": abs(amount),
                    "unit": u,
                    "result_date": format_output(res_date, start_date)
                }
            )

        else:
            return ToolResult(
                success=False,
                error="INVALID_ARGUMENTS",
                metadata={"error_detail": f"Unsupported operation: '{operation}'. Expected 'difference' or 'add_subtract'."}
            )

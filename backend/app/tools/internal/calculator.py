import ast
import operator
from pydantic import BaseModel, Field
from app.tools.base import BaseTool, ToolResult

SAFE_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}

SAFE_UNARY_OPERATORS = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

def safe_eval(expr_str: str):
    """Safely evaluates mathematical expressions using AST. Rejects non-arithmetic syntax."""
    # ast.parse with mode='eval' expects a single expression
    node = ast.parse(expr_str.strip(), mode='eval')
    
    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Only numeric constants are allowed.")
        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in SAFE_BINARY_OPERATORS:
                raise ValueError(f"Operator {op_type.__name__} is not allowed.")
            left = _eval(node.left)
            right = _eval(node.right)
            if op_type == ast.Div and right == 0:
                raise ZeroDivisionError("Division by zero is not allowed.")
            # Limit power operation parameters to avoid CPU DOS
            if op_type == ast.Pow:
                if abs(left) > 10000 or abs(right) > 100:
                    raise ValueError("Power operation parameters too large.")
            return SAFE_BINARY_OPERATORS[op_type](left, right)
        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in SAFE_UNARY_OPERATORS:
                raise ValueError(f"Operator {op_type.__name__} is not allowed.")
            operand = _eval(node.operand)
            return SAFE_UNARY_OPERATORS[op_type](operand)
        else:
            raise ValueError(f"Unsupported expression node: {type(node).__name__}")
            
    return _eval(node)

class CalculatorInput(BaseModel):
    expression: str = Field(..., description="The mathematical expression to evaluate (e.g. '125 * 48' or '(3 + 4) * 2').")

class CalculatorTool(BaseTool):
    name = "calculator"
    description = "A safe calculator tool for mathematical arithmetic. Supported operators: +, -, *, /, **, and parentheses."
    input_schema = CalculatorInput
    permission_level = "safe"
    timeout_seconds = 10

    async def execute(self, expression: str, **kwargs) -> ToolResult:
        try:
            res = safe_eval(expression)
            return ToolResult(
                success=True,
                data={"result": res},
                error=None
            )
        except ZeroDivisionError:
            return ToolResult(
                success=False,
                data=None,
                error="Division by zero is not allowed."
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to evaluate expression: {str(e)}"
            )
